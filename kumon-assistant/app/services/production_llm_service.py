"""
Production LLM Service with Failover & Cost Management
Unified service for LangGraph integration with backward compatibility
"""

import asyncio
import time
from typing import AsyncIterator, Optional, Dict, Any, List, Union
from dataclasses import dataclass

from ..core.config import settings
from ..core.logger import app_logger
from .llm_base import (
    LLMRouter, 
    CompatibilityLayer, 
    LLMProviderFactory, 
    LLMRequest, 
    LLMResponse,
    LLMMetrics
)
from .providers.openai_provider import OpenAIProvider
from .providers.anthropic_provider import AnthropicProvider
from .providers.twilio_provider import TwilioProvider
from .cost_monitor import cost_monitor
from .enhanced_cache_service import enhanced_cache_service


@dataclass
class FailoverConfig:
    """Configuration for failover behavior"""
    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    failover_on_rate_limit: bool = True
    failover_on_model_error: bool = True
    failover_on_timeout: bool = True
    circuit_breaker_threshold: int = 5  # failures before circuit opens
    circuit_breaker_timeout: int = 60   # seconds


class ProductionLLMService:
    """
    Production-ready LLM service with comprehensive failover and monitoring
    
    Features:
    - OpenAI primary, Anthropic fallback
    - Real-time cost monitoring with budget enforcement
    - Circuit breaker pattern for reliability
    - Performance metrics and health monitoring
    - Backward compatibility with existing LLMStreamingService
    - LangGraph integration ready
    """
    
    def __init__(self, failover_config: Optional[FailoverConfig] = None):
        self.failover_config = failover_config or FailoverConfig()
        self.router = LLMRouter()
        self.compatibility_layer = CompatibilityLayer(self.router)
        self.circuit_breaker_counts: Dict[str, int] = {}
        self.circuit_breaker_opens: Dict[str, float] = {}
        self.is_initialized = False
        
        app_logger.info("Production LLM service created", extra={
            "max_retries": self.failover_config.max_retries,
            "circuit_breaker_threshold": self.failover_config.circuit_breaker_threshold
        })
    
    async def initialize(self):
        """Initialize service with providers and routing"""
        if self.is_initialized:
            return
        
        # Register provider classes
        LLMProviderFactory.register_provider("openai", OpenAIProvider)
        LLMProviderFactory.register_provider("anthropic", AnthropicProvider)
        LLMProviderFactory.register_provider("twilio", TwilioProvider)
        
        # Create providers
        openai_provider = LLMProviderFactory.create_provider(
            "openai",
            model=getattr(settings, 'OPENAI_MODEL', 'gpt-4-turbo'),
            api_key=getattr(settings, 'OPENAI_API_KEY', None)
        )
        
        anthropic_provider = LLMProviderFactory.create_provider(
            "anthropic", 
            model=getattr(settings, 'ANTHROPIC_MODEL', 'claude-3-sonnet-20240229'),
            api_key=getattr(settings, 'ANTHROPIC_API_KEY', None)
        )
        
        # Create Twilio provider for WhatsApp/SMS fallback
        twilio_provider = LLMProviderFactory.create_provider(
            "twilio",
            account_sid=getattr(settings, 'TWILIO_ACCOUNT_SID', None),
            auth_token=getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        )
        
        # Add providers to router with priority order
        self.router.add_provider("openai", openai_provider, is_default=True)
        self.router.add_provider("anthropic", anthropic_provider, is_default=False)
        self.router.add_provider("twilio", twilio_provider, is_default=False)  # Emergency fallback only
        
        # Configure routing rules
        self.router.add_routing_rule(
            {"max_tokens": 300, "context_type": "long_form"},
            "anthropic"  # Use Claude for longer responses
        )
        
        # Emergency communication routing - use Twilio only for critical notifications
        self.router.add_routing_rule(
            {"context_type": "emergency_notification", "delivery_method": "whatsapp"},
            "twilio"  # Use Twilio for emergency WhatsApp/SMS delivery
        )
        
        # Initialize cost monitor
        await cost_monitor.initialize()
        
        # Test connections
        await self._test_providers()
        
        self.is_initialized = True
        
        app_logger.info("Production LLM service initialized", extra={
            "providers": list(self.router.providers.keys()),
            "default_provider": self.router.default_provider,
            "routing_rules": len(self.router.routing_rules)
        })
    
    async def generate_streamed_response(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[str]:
        """
        Generate streamed response with cost monitoring and failover
        
        This is the main method for LangGraph integration
        """
        if not self.is_initialized:
            await self.initialize()
        
        # Build request
        messages = [{"role": "system", "content": system_prompt}]
        
        if conversation_history:
            messages.extend(conversation_history[-5:])  # Keep last 5 exchanges
        
        messages.append({"role": "user", "content": user_message})
        
        request = LLMRequest(
            messages=messages,
            max_tokens=max_tokens or 500,
            temperature=temperature or 0.7,
            context=context or {}
        )
        
        # Attempt with primary provider first
        primary_provider = self.router.default_provider
        
        async for chunk in self._stream_with_failover(request, primary_provider):
            yield chunk
    
    async def _stream_with_failover(
        self,
        request: LLMRequest,
        preferred_provider: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Stream response with comprehensive failover logic"""
        providers_to_try = []
        
        # Determine provider order
        if preferred_provider and preferred_provider in self.router.providers:
            providers_to_try.append(preferred_provider)
        
        # Add other providers as fallbacks
        for provider_name in self.router.providers.keys():
            if provider_name not in providers_to_try:
                providers_to_try.append(provider_name)
        
        last_error = None
        
        for provider_name in providers_to_try:
            # Check circuit breaker
            if self._is_circuit_breaker_open(provider_name):
                app_logger.info(f"Circuit breaker open for {provider_name}, skipping")
                continue
            
            # Check budget before making request
            estimated_cost = await self._estimate_request_cost(request, provider_name)
            budget_allowed, budget_status = await cost_monitor.check_budget_allowance(estimated_cost)
            
            if not budget_allowed:
                app_logger.error("Request blocked due to budget constraints", extra=budget_status)
                yield "Desculpe, o limite de orçamento diário foi atingido. Para atendimento imediato, entre em contato: (51) 99692-1999"
                return
            
            try:
                app_logger.info(f"Attempting request with provider: {provider_name}")
                
                provider = self.router.providers[provider_name]
                accumulated_response = ""
                start_time = time.time()
                
                # Stream response
                async for chunk in provider.stream_response(request):
                    accumulated_response += chunk
                    yield chunk
                
                # Track successful usage
                await self._track_successful_usage(
                    provider_name,
                    request,
                    accumulated_response,
                    time.time() - start_time
                )
                
                # Reset circuit breaker on success
                self._reset_circuit_breaker(provider_name)
                
                return  # Successful completion
                
            except Exception as e:
                last_error = e
                
                app_logger.warning(f"Provider {provider_name} failed: {e}", extra={
                    "error_type": type(e).__name__,
                    "provider": provider_name
                })
                
                # Update circuit breaker
                self._increment_circuit_breaker(provider_name)
                
                # Check if we should continue to next provider
                if self._should_continue_failover(e):
                    continue
                else:
                    break
        
        # All providers failed
        app_logger.error("All LLM providers failed", extra={
            "last_error": str(last_error) if last_error else "Unknown",
            "providers_attempted": providers_to_try
        })
        
        yield "Desculpe, estou enfrentando dificuldades técnicas no momento. Para atendimento imediato, entre em contato: (51) 99692-1999"
    
    async def _estimate_request_cost(self, request: LLMRequest, provider_name: str) -> float:
        """Estimate cost for request before execution"""
        provider = self.router.providers.get(provider_name)
        if not provider:
            return 0.0
        
        try:
            # Rough token estimation
            total_content = " ".join(msg["content"] for msg in request.messages)
            estimated_input_tokens = len(total_content) // 4  # ~4 chars per token
            estimated_output_tokens = request.max_tokens or 500
            
            return provider.estimate_cost(estimated_input_tokens, estimated_output_tokens)
        
        except Exception as e:
            app_logger.warning(f"Cost estimation error for {provider_name}: {e}")
            return 0.05  # Conservative fallback estimate
    
    async def _track_successful_usage(
        self,
        provider_name: str,
        request: LLMRequest,
        response: str,
        duration: float
    ):
        """Track successful usage for cost monitoring"""
        try:
            provider = self.router.providers[provider_name]
            
            # Get last metrics from provider
            if provider.metrics_history:
                latest_metrics = provider.metrics_history[-1]
                
                await cost_monitor.track_usage(
                    provider=provider_name,
                    model=provider.model,
                    input_tokens=latest_metrics.input_tokens or 0,
                    output_tokens=latest_metrics.output_tokens or 0,
                    cost_brl=latest_metrics.cost_estimate or 0.0,
                    context={
                        "duration_seconds": duration,
                        "response_length": len(response),
                        "message_count": len(request.messages)
                    }
                )
            
        except Exception as e:
            app_logger.error(f"Error tracking usage: {e}")
    
    def _is_circuit_breaker_open(self, provider_name: str) -> bool:
        """Check if circuit breaker is open for provider"""
        if provider_name not in self.circuit_breaker_opens:
            return False
        
        open_time = self.circuit_breaker_opens[provider_name]
        elapsed = time.time() - open_time
        
        if elapsed > self.failover_config.circuit_breaker_timeout:
            # Circuit breaker timeout expired, close it
            del self.circuit_breaker_opens[provider_name]
            self.circuit_breaker_counts[provider_name] = 0
            return False
        
        return True
    
    def _increment_circuit_breaker(self, provider_name: str):
        """Increment circuit breaker failure count"""
        current_count = self.circuit_breaker_counts.get(provider_name, 0) + 1
        self.circuit_breaker_counts[provider_name] = current_count
        
        if current_count >= self.failover_config.circuit_breaker_threshold:
            self.circuit_breaker_opens[provider_name] = time.time()
            
            app_logger.warning(f"Circuit breaker opened for {provider_name}", extra={
                "failure_count": current_count,
                "threshold": self.failover_config.circuit_breaker_threshold
            })
    
    def _reset_circuit_breaker(self, provider_name: str):
        """Reset circuit breaker on successful request"""
        if provider_name in self.circuit_breaker_counts:
            self.circuit_breaker_counts[provider_name] = 0
        
        if provider_name in self.circuit_breaker_opens:
            del self.circuit_breaker_opens[provider_name]
    
    def _should_continue_failover(self, error: Exception) -> bool:
        """Determine if should continue to next provider on error"""
        error_type = type(error).__name__
        
        # Continue failover for these error types
        continue_on = [
            "RateLimitError",
            "TimeoutError", 
            "APIConnectionError",
            "APITimeoutError",
            "InternalServerError"
        ]
        
        return any(err_type in error_type for err_type in continue_on)
    
    async def _test_providers(self):
        """Test all provider connections"""
        for provider_name, provider in self.router.providers.items():
            try:
                if hasattr(provider, 'test_connection'):
                    result = await provider.test_connection()
                    
                    if result.get("success"):
                        app_logger.info(f"Provider {provider_name} connection successful", extra=result)
                    else:
                        app_logger.warning(f"Provider {provider_name} connection failed", extra=result)
                        
            except Exception as e:
                app_logger.error(f"Error testing provider {provider_name}: {e}")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        if not self.is_initialized:
            return {"status": "not_initialized"}
        
        provider_health = {}
        
        for provider_name, provider in self.router.providers.items():
            provider_health[provider_name] = {
                "available": not self._is_circuit_breaker_open(provider_name),
                "failure_count": self.circuit_breaker_counts.get(provider_name, 0),
                "performance_metrics": provider.get_performance_metrics()
            }
        
        # Get cost status
        daily_summary = await cost_monitor.get_daily_summary()
        
        return {
            "status": "healthy",
            "initialized": self.is_initialized,
            "default_provider": self.router.default_provider,
            "providers": provider_health,
            "cost_status": daily_summary,
            "circuit_breaker_config": {
                "threshold": self.failover_config.circuit_breaker_threshold,
                "timeout_seconds": self.failover_config.circuit_breaker_timeout
            }
        }
    
    # Backward compatibility methods
    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[str]:
        """Backward compatible stream_response method"""
        return self.compatibility_layer.stream_response(messages, context)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Backward compatible performance metrics"""
        return self.compatibility_layer.get_performance_metrics()


# Global production LLM service instance
production_llm_service = ProductionLLMService()


async def initialize_production_llm_service():
    """Initialize global production LLM service"""
    await production_llm_service.initialize()


# Convenience function for LangGraph integration
async def generate_llm_response(
    user_message: str,
    system_prompt: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    **kwargs
) -> AsyncIterator[str]:
    """
    Convenient function for LangGraph node integration
    
    Usage in LangGraph nodes:
        async for chunk in generate_llm_response(user_input, system_prompt, history):
            # Process streaming response
    """
    if not production_llm_service.is_initialized:
        await production_llm_service.initialize()
    
    async for chunk in production_llm_service.generate_streamed_response(
        user_message, system_prompt, conversation_history, **kwargs
    ):
        yield chunk