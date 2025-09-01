"""
Anthropic Provider Implementation
Claude-3 integration with failover capability for production resilience
"""

import asyncio
import time
import json
from typing import AsyncIterator, Optional, Dict, Any, List

# Graceful import fallback for optional Anthropic dependency
try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    AsyncAnthropic = None

from ...core.config import settings
from ...core.logger import app_logger
from ..llm_base import BaseLLMProvider, LLMRequest, LLMResponse, LLMMetrics


class AnthropicProvider(BaseLLMProvider):
    """Anthropic provider implementation with Claude-3 models"""
    
    def __init__(self, model: str = None, api_key: str = None, **kwargs):
        super().__init__("anthropic", model or getattr(settings, 'ANTHROPIC_MODEL', 'claude-3-sonnet-20240229'))
        
        # Check if Anthropic is available
        if not ANTHROPIC_AVAILABLE:
            self.client = None
            app_logger.warning("Anthropic package not installed - provider will be unavailable")
            return
        
        # Check API key availability
        api_key = api_key or getattr(settings, 'ANTHROPIC_API_KEY', None)
        if not api_key:
            self.client = None
            app_logger.warning("Anthropic API key not configured - provider will be unavailable")
            return
            
        self.client = AsyncAnthropic(
            api_key=api_key,
            timeout=30.0,
            max_retries=2
        )
        
        # Default configuration for Kumon business context
        self.default_config = {
            "model": self.model,
            "max_tokens": 500,
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "stream": True
        }
        
        # Portuguese-optimized system prompt for business context
        self.system_prompt = """Você é Cecília, assistente virtual da unidade Kumon Vila A em Porto Alegre. 
Suas características:
- Comunicação profissional, acolhedora e em português brasileiro
- Especialista em metodologia Kumon (matemática e português)
- Focada em agendamento de visitas e qualificação de leads
- Preços: R$ 375,00 por matéria + R$ 100,00 taxa de matrícula
- Atendimento: Segunda a sexta, 9h às 12h e 14h às 17h
- Contato para casos complexos: (51) 99692-1999"""
        
        app_logger.info("Anthropic provider initialized", extra={
            "model": self.model,
            "provider": "anthropic",
            "api_key_configured": bool(api_key),
            "status": "ready" if self.client else "unavailable"
        })
    
    async def stream_response(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream response using Anthropic Claude API"""
        if not ANTHROPIC_AVAILABLE or self.client is None:
            app_logger.warning("Anthropic service unavailable - using fallback response")
            yield "Desculpe, o serviço alternativo está temporariamente indisponível. Entre em contato: (51) 99692-1999"
            return
        
        metrics = LLMMetrics(
            provider="anthropic",
            model=self.model,
            start_time=time.time()
        )
        
        try:
            # Build request config
            config = self.default_config.copy()
            if request.max_tokens:
                config["max_tokens"] = request.max_tokens
            if request.temperature is not None:
                config["temperature"] = request.temperature
            if request.provider_specific:
                config.update(request.provider_specific)
            
            # Format messages for Anthropic (system prompt separate)
            messages = request.messages.copy()
            system_content = self.system_prompt
            
            # Extract system message if present
            if messages and messages[0]["role"] == "system":
                system_content = messages[0]["content"]
                messages = messages[1:]
            
            app_logger.info("Starting Anthropic streaming request", extra={
                "message_count": len(messages),
                "model": config["model"],
                "max_tokens": config["max_tokens"]
            })
            
            # Create streaming request
            stream = await self.client.messages.create(
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                system=system_content,
                messages=messages,
                stream=True
            )
            
            # Process streaming chunks
            accumulated_text = ""
            chunk_buffer = ""
            target_chunk_size = 50
            
            async for chunk in stream:
                current_time = time.time()
                
                # Track first chunk
                if metrics.first_chunk_time is None:
                    metrics.first_chunk_time = current_time
                    first_chunk_latency = metrics.first_chunk_latency_ms
                    
                    app_logger.info("First chunk received", extra={
                        "latency_ms": first_chunk_latency,
                        "target_met": first_chunk_latency < 200,
                        "provider": "anthropic"
                    })
                    
                    if first_chunk_latency > 200:
                        app_logger.warning(f"Anthropic first chunk latency {first_chunk_latency:.2f}ms exceeds 200ms target")
                
                # Extract content from different chunk types
                if chunk.type == "content_block_delta":
                    if hasattr(chunk.delta, 'text'):
                        content = chunk.delta.text
                        metrics.total_characters += len(content)
                        accumulated_text += content
                        chunk_buffer += content
                        
                        # Yield chunks when buffer reaches target size
                        while len(chunk_buffer) >= target_chunk_size:
                            yield chunk_buffer[:target_chunk_size]
                            chunk_buffer = chunk_buffer[target_chunk_size:]
                            metrics.total_chunks += 1
                
                elif chunk.type == "message_delta":
                    # Final chunk with usage stats
                    if hasattr(chunk, 'usage'):
                        metrics.input_tokens = getattr(chunk.usage, 'input_tokens', None)
                        metrics.output_tokens = getattr(chunk.usage, 'output_tokens', None)
            
            # Yield any remaining content
            if chunk_buffer:
                yield chunk_buffer
                metrics.total_chunks += 1
            
            # Final metrics
            metrics.completion_time = time.time()
            
            # Estimate cost
            if metrics.input_tokens and metrics.output_tokens:
                metrics.cost_estimate = self.estimate_cost(metrics.input_tokens, metrics.output_tokens)
            elif metrics.total_characters > 0:
                # Rough estimate for Claude: ~3.5 chars per token
                estimated_output_tokens = max(1, metrics.total_characters // 4)
                estimated_input_tokens = max(1, sum(len(msg["content"]) for msg in messages) // 4)
                metrics.input_tokens = estimated_input_tokens
                metrics.output_tokens = estimated_output_tokens
                metrics.cost_estimate = self.estimate_cost(estimated_input_tokens, estimated_output_tokens)
            
            # Log performance metrics
            app_logger.info("Anthropic streaming completed", extra={
                "first_chunk_ms": metrics.first_chunk_latency_ms,
                "total_duration_ms": metrics.total_duration_ms,
                "total_chunks": metrics.total_chunks,
                "total_characters": metrics.total_characters,
                "cost_estimate": metrics.cost_estimate,
                "provider": "anthropic",
                "accumulated_text_length": len(accumulated_text)
            })
            
            # Store metrics
            self.add_metrics(metrics)
                
        except Exception as e:
            # Log detailed error internally without exposing details
            app_logger.error("LLM service error occurred", extra={
                "elapsed_ms": (time.time() - metrics.start_time) * 1000,
                "provider": "anthropic",
                "error_type": type(e).__name__,
                "error_id": f"llm_error_{int(time.time())}"
            })
            
            # Yield sanitized fallback response
            yield "Desculpe, houve um problema técnico temporário. Para atendimento imediato, entre em contato: (51) 99692-1999"
    
    async def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Generate complete response (non-streaming)"""
        if not ANTHROPIC_AVAILABLE or self.client is None:
            raise ValueError("Anthropic service not available - package not installed or API key not configured")
        
        metrics = LLMMetrics(
            provider="anthropic",
            model=self.model,
            start_time=time.time()
        )
        
        try:
            # Build request config (non-streaming)
            config = self.default_config.copy()
            config["stream"] = False
            
            if request.max_tokens:
                config["max_tokens"] = request.max_tokens
            if request.temperature is not None:
                config["temperature"] = request.temperature
            if request.provider_specific:
                config.update(request.provider_specific)
            
            # Format messages for Anthropic
            messages = request.messages.copy()
            system_content = self.system_prompt
            
            if messages and messages[0]["role"] == "system":
                system_content = messages[0]["content"]
                messages = messages[1:]
            
            # Make request
            response = await self.client.messages.create(
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                system=system_content,
                messages=messages
            )
            
            metrics.completion_time = time.time()
            content = response.content[0].text if response.content else ""
            metrics.total_characters = len(content)
            
            # Extract usage information
            if response.usage:
                metrics.input_tokens = response.usage.input_tokens
                metrics.output_tokens = response.usage.output_tokens
                metrics.cost_estimate = self.estimate_cost(
                    response.usage.input_tokens,
                    response.usage.output_tokens
                )
            
            self.add_metrics(metrics)
            
            return LLMResponse(
                content=content,
                metrics=metrics,
                provider="anthropic",
                model=self.model,
                finish_reason=getattr(response, 'stop_reason', None),
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                } if response.usage else None
            )
            
        except Exception as e:
            # Log detailed error internally
            app_logger.error("LLM generation failed", extra={
                "provider": "anthropic", 
                "error_type": type(e).__name__,
                "error_id": f"llm_gen_error_{int(time.time())}"
            })
            # Re-raise with sanitized message
            raise ValueError("LLM service temporarily unavailable") from e
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for Anthropic usage"""
        # Claude-3 pricing (as of 2024) - in USD
        if "claude-3-opus" in self.model.lower():
            # Claude-3 Opus rates
            input_cost = input_tokens * 0.015 / 1000  # $15 per 1M tokens
            output_cost = output_tokens * 0.075 / 1000  # $75 per 1M tokens
        elif "claude-3-sonnet" in self.model.lower():
            # Claude-3 Sonnet rates  
            input_cost = input_tokens * 0.003 / 1000  # $3 per 1M tokens
            output_cost = output_tokens * 0.015 / 1000  # $15 per 1M tokens
        elif "claude-3-haiku" in self.model.lower():
            # Claude-3 Haiku rates
            input_cost = input_tokens * 0.00025 / 1000  # $0.25 per 1M tokens
            output_cost = output_tokens * 0.00125 / 1000  # $1.25 per 1M tokens
        else:
            # Default to Sonnet rates
            input_cost = input_tokens * 0.003 / 1000
            output_cost = output_tokens * 0.015 / 1000
        
        # Convert to BRL (approximate rate: 1 USD = 5.20 BRL)
        usd_cost = input_cost + output_cost
        brl_cost = usd_cost * 5.20
        
        return brl_cost
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get Anthropic rate limit information"""
        # Return typical Anthropic rate limits
        return {
            "requests_per_minute": 50,  # Conservative estimate
            "tokens_per_minute": 40000,
            "requests_per_day": 1000,
            "concurrent_requests": 5
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Anthropic API connection"""
        try:
            if not ANTHROPIC_AVAILABLE:
                return {
                    "success": False,
                    "provider": "anthropic",
                    "error": "Anthropic package not installed"
                }
                
            if self.client is None:
                return {
                    "success": False,
                    "provider": "anthropic", 
                    "error": "API key not configured"
                }
            
            test_request = LLMRequest(
                messages=[{"role": "user", "content": "Olá! Teste de conexão."}],
                max_tokens=20
            )
            
            start_time = time.time()
            response = await self.generate_response(test_request)
            duration = time.time() - start_time
            
            return {
                "success": True,
                "provider": "anthropic",
                "model": self.model,
                "response_time_ms": duration * 1000,
                "test_response": response.content[:50] + "..." if len(response.content) > 50 else response.content,
                "cost_estimate": response.metrics.cost_estimate
            }
            
        except Exception as e:
            # Log detailed error internally
            app_logger.error("LLM connection test failed", extra={
                "provider": "anthropic",
                "error_type": type(e).__name__,
                "error_id": f"conn_test_error_{int(time.time())}"
            })
            return {
                "success": False,
                "provider": "anthropic",
                "error": "Connection test failed"
            }