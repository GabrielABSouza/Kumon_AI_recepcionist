"""
OpenAI Provider Implementation
Wraps existing LLMStreamingService functionality with new abstraction
ZERO BREAKING CHANGES: Uses existing service internally
"""

import asyncio
import time
from typing import AsyncIterator, Optional, Dict, Any, List
from openai import AsyncOpenAI

from ...core.config import settings
from ...core.logger import app_logger
from ..llm_base import BaseLLMProvider, LLMRequest, LLMResponse, LLMMetrics
from ..llm_streaming_service import StreamingBuffer


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider implementation using existing streaming service logic"""
    
    def __init__(self, model: str = None, api_key: str = None, **kwargs):
        super().__init__("openai", model or getattr(settings, 'OPENAI_MODEL', 'gpt-4-turbo'))
        
        self.client = AsyncOpenAI(
            api_key=api_key or settings.OPENAI_API_KEY,
            timeout=30.0,
            max_retries=2
        )
        
        # Default configuration - matches existing service
        self.default_config = {
            "model": self.model,
            "stream": True,
            "max_tokens": 500,
            "temperature": 0.7,
            "presence_penalty": 0.1,
            "frequency_penalty": 0.1,
            "top_p": 0.95
        }
        
        app_logger.info("OpenAI provider initialized", extra={
            "model": self.model,
            "provider": "openai",
            "api_key_configured": bool(api_key or settings.OPENAI_API_KEY),
            "status": "ready"
        })
    
    async def stream_response(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream response using OpenAI API"""
        metrics = LLMMetrics(
            provider="openai",
            model=self.model,
            start_time=time.time()
        )
        
        buffer = StreamingBuffer(target_chunk_size=50)
        
        try:
            # Build request config
            config = self.default_config.copy()
            if request.max_tokens:
                config["max_tokens"] = request.max_tokens
            if request.temperature is not None:
                config["temperature"] = request.temperature
            if request.provider_specific:
                config.update(request.provider_specific)
            
            app_logger.info("Starting OpenAI streaming request", extra={
                "message_count": len(request.messages),
                "model": config["model"],
                "max_tokens": config["max_tokens"]
            })
            
            # Create streaming request
            stream = await self.client.chat.completions.create(
                messages=request.messages,
                **config
            )
            
            # Process streaming chunks
            async for chunk in stream:
                current_time = time.time()
                
                # Track first chunk
                if metrics.first_chunk_time is None:
                    metrics.first_chunk_time = current_time
                    first_chunk_latency = metrics.first_chunk_latency_ms
                    
                    app_logger.info("First chunk received", extra={
                        "latency_ms": first_chunk_latency,
                        "target_met": first_chunk_latency < 200,
                        "provider": "openai"
                    })
                    
                    if first_chunk_latency > 200:
                        app_logger.warning(f"OpenAI first chunk latency {first_chunk_latency:.2f}ms exceeds 200ms target")
                
                # Extract content
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    metrics.total_characters += len(content)
                    
                    # Buffer and yield ready chunks
                    ready_chunks = buffer.add_content(content)
                    for ready_chunk in ready_chunks:
                        metrics.total_chunks += 1
                        yield ready_chunk
            
            # Yield any remaining content
            remaining = buffer.flush()
            if remaining:
                metrics.total_chunks += 1
                yield remaining
            
            # Final metrics
            metrics.completion_time = time.time()
            
            # Estimate cost (approximate)
            if metrics.total_characters > 0:
                # Rough estimate: ~4 chars per token
                estimated_output_tokens = metrics.total_characters // 4
                estimated_input_tokens = sum(len(msg["content"]) for msg in request.messages) // 4
                metrics.input_tokens = estimated_input_tokens
                metrics.output_tokens = estimated_output_tokens
                metrics.cost_estimate = self.estimate_cost(estimated_input_tokens, estimated_output_tokens)
            
            # Log performance metrics
            app_logger.info("OpenAI streaming completed", extra={
                "first_chunk_ms": metrics.first_chunk_latency_ms,
                "total_duration_ms": metrics.total_duration_ms,
                "total_chunks": metrics.total_chunks,
                "total_characters": metrics.total_characters,
                "cost_estimate": metrics.cost_estimate,
                "provider": "openai"
            })
            
            # Store metrics
            self.add_metrics(metrics)
                
        except Exception as e:
            app_logger.error(f"OpenAI streaming error: {e}", extra={
                "elapsed_ms": (time.time() - metrics.start_time) * 1000,
                "provider": "openai"
            })
            
            # Yield fallback response
            yield "Desculpe, houve um problema técnico. Como posso ajudá-lo?"
    
    async def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Generate complete response (non-streaming)"""
        metrics = LLMMetrics(
            provider="openai",
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
            
            # Make request
            response = await self.client.chat.completions.create(
                messages=request.messages,
                **config
            )
            
            metrics.completion_time = time.time()
            content = response.choices[0].message.content
            metrics.total_characters = len(content)
            
            # Extract usage information
            if response.usage:
                metrics.input_tokens = response.usage.prompt_tokens
                metrics.output_tokens = response.usage.completion_tokens
                metrics.cost_estimate = self.estimate_cost(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )
            
            self.add_metrics(metrics)
            
            return LLMResponse(
                content=content,
                metrics=metrics,
                provider="openai",
                model=self.model,
                finish_reason=response.choices[0].finish_reason,
                usage=response.usage.model_dump() if response.usage else None
            )
            
        except Exception as e:
            app_logger.error(f"OpenAI generation error: {e}", extra={
                "provider": "openai"
            })
            raise
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for OpenAI usage"""
        # GPT-4 Turbo pricing (as of 2024)
        if "gpt-4" in self.model.lower():
            if "turbo" in self.model.lower() or "1106" in self.model or "0125" in self.model:
                # GPT-4 Turbo rates
                input_cost = input_tokens * 0.01 / 1000  # $0.01 per 1K tokens
                output_cost = output_tokens * 0.03 / 1000  # $0.03 per 1K tokens
            else:
                # GPT-4 standard rates
                input_cost = input_tokens * 0.03 / 1000  # $0.03 per 1K tokens
                output_cost = output_tokens * 0.06 / 1000  # $0.06 per 1K tokens
        elif "gpt-3.5" in self.model.lower():
            # GPT-3.5 Turbo rates
            input_cost = input_tokens * 0.0005 / 1000  # $0.0005 per 1K tokens
            output_cost = output_tokens * 0.0015 / 1000  # $0.0015 per 1K tokens
        else:
            # Default to GPT-4 rates
            input_cost = input_tokens * 0.01 / 1000
            output_cost = output_tokens * 0.03 / 1000
        
        return input_cost + output_cost
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get OpenAI rate limit information"""
        # Return typical OpenAI rate limits
        if "gpt-4" in self.model.lower():
            return {
                "requests_per_minute": 500,
                "tokens_per_minute": 30000,
                "requests_per_day": 10000
            }
        else:
            return {
                "requests_per_minute": 3500,
                "tokens_per_minute": 90000,
                "requests_per_day": 10000
            }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test OpenAI API connection"""
        try:
            test_request = LLMRequest(
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )
            
            start_time = time.time()
            response = await self.generate_response(test_request)
            duration = time.time() - start_time
            
            return {
                "success": True,
                "provider": "openai",
                "model": self.model,
                "response_time_ms": duration * 1000,
                "test_response": response.content[:50] + "..." if len(response.content) > 50 else response.content
            }
            
        except Exception as e:
            return {
                "success": False,
                "provider": "openai",
                "error": str(e)
            }