"""
Production LLM Service with Failover & Cost Management
Unified service for LangGraph integration with backward compatibility
Implements StandardLLMInterface for complete interface standardization
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from ..core.config import settings
from ..core.logger import app_logger
from .cost_monitor import cost_monitor
from .enhanced_cache_service import enhanced_cache_service
from .interfaces.llm_interface import (
    InterfaceValidator,
    LLMInterfaceAdapter,
    LLMInterfaceType,
    StandardLLMInterface,
    StandardLLMRequest,
    StandardLLMResponse,
)
from .llm_base import (
    CompatibilityLayer,
    LLMMetrics,
    LLMProviderFactory,
    LLMRequest,
    LLMResponse,
    LLMRouter,
)
from .providers.anthropic_provider import AnthropicProvider
from .providers.openai_provider import OpenAIProvider
from .providers.twilio_provider import TwilioProvider


@dataclass
class FailoverConfig:
    """Configuration for failover behavior"""

    max_retries: int = 2
    retry_delay_seconds: float = 1.0
    failover_on_rate_limit: bool = True
    failover_on_model_error: bool = True
    failover_on_timeout: bool = True
    circuit_breaker_threshold: int = 5  # failures before circuit opens
    circuit_breaker_timeout: int = 60  # seconds


class ProductionLLMService(StandardLLMInterface):
    """
    Production-ready LLM service with comprehensive failover and monitoring
    Implements StandardLLMInterface for complete interface standardization

    Features:
    - OpenAI primary, Anthropic fallback
    - Real-time cost monitoring with budget enforcement
    - Circuit breaker pattern for reliability
    - Performance metrics and health monitoring
    - Standard interface compliance for all integrations
    - LangGraph and LangChain compatibility
    """

    def __init__(self, failover_config: Optional[FailoverConfig] = None):
        self.failover_config = failover_config or FailoverConfig()
        self.router = LLMRouter()
        self.compatibility_layer = CompatibilityLayer(self.router)
        self.circuit_breaker_counts: Dict[str, int] = {}
        self.circuit_breaker_opens: Dict[str, float] = {}
        self.is_initialized = False

        app_logger.info(
            "Production LLM service created",
            extra={
                "max_retries": self.failover_config.max_retries,
                "circuit_breaker_threshold": self.failover_config.circuit_breaker_threshold,
            },
        )

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
            model=getattr(settings, "OPENAI_MODEL", "gpt-4-turbo"),
            api_key=getattr(settings, "OPENAI_API_KEY", None),
        )

        anthropic_provider = LLMProviderFactory.create_provider(
            "anthropic",
            model=getattr(settings, "ANTHROPIC_MODEL", "claude-3-sonnet-20240229"),
            api_key=getattr(settings, "ANTHROPIC_API_KEY", None),
        )

        # Create Twilio provider for WhatsApp/SMS fallback
        twilio_provider = LLMProviderFactory.create_provider(
            "twilio",
            account_sid=getattr(settings, "TWILIO_ACCOUNT_SID", None),
            auth_token=getattr(settings, "TWILIO_AUTH_TOKEN", None),
        )

        # Add providers to router with priority order
        self.router.add_provider("openai", openai_provider, is_default=True)
        self.router.add_provider("anthropic", anthropic_provider, is_default=False)
        self.router.add_provider(
            "twilio", twilio_provider, is_default=False
        )  # Emergency fallback only

        # Configure routing rules
        self.router.add_routing_rule(
            {"max_tokens": 300, "context_type": "long_form"},
            "anthropic",  # Use Claude for longer responses
        )

        # Emergency communication routing - use Twilio only for critical notifications
        self.router.add_routing_rule(
            {"context_type": "emergency_notification", "delivery_method": "whatsapp"},
            "twilio",  # Use Twilio for emergency WhatsApp/SMS delivery
        )

        # Initialize cost monitor
        await cost_monitor.initialize()

        # Test connections
        await self._test_providers()

        self.is_initialized = True

        app_logger.info(
            "Production LLM service initialized",
            extra={
                "providers": list(self.router.providers.keys()),
                "default_provider": self.router.default_provider,
                "routing_rules": len(self.router.routing_rules),
                "interface_standard": "StandardLLMInterface",
                "interface_type": self.interface_type.value,
            },
        )

    async def _generate_streamed_response_internal(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
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
            context=context or {},
        )

        # Attempt with primary provider first
        primary_provider = self.router.default_provider

        async for chunk in self._stream_with_failover(request, primary_provider):
            yield chunk

    async def _stream_with_failover(
        self, request: LLMRequest, preferred_provider: Optional[str] = None
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
            budget_allowed, budget_status = await cost_monitor.check_budget_allowance(
                estimated_cost
            )

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
                    provider_name, request, accumulated_response, time.time() - start_time
                )

                # Reset circuit breaker on success
                self._reset_circuit_breaker(provider_name)

                return  # Successful completion

            except Exception as e:
                last_error = e

                app_logger.warning(
                    f"Provider {provider_name} failed: {e}",
                    extra={"error_type": type(e).__name__, "provider": provider_name},
                )

                # Update circuit breaker
                self._increment_circuit_breaker(provider_name)

                # Check if we should continue to next provider
                if self._should_continue_failover(e):
                    continue
                else:
                    break

        # All providers failed
        app_logger.error(
            "All LLM providers failed",
            extra={
                "last_error": str(last_error) if last_error else "Unknown",
                "providers_attempted": providers_to_try,
            },
        )

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
        self, provider_name: str, request: LLMRequest, response: str, duration: float
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
                        "message_count": len(request.messages),
                    },
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

            app_logger.warning(
                f"Circuit breaker opened for {provider_name}",
                extra={
                    "failure_count": current_count,
                    "threshold": self.failover_config.circuit_breaker_threshold,
                },
            )

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
            "InternalServerError",
        ]

        return any(err_type in error_type for err_type in continue_on)

    async def _test_providers(self):
        """Test all provider connections"""
        for provider_name, provider in self.router.providers.items():
            try:
                if hasattr(provider, "test_connection"):
                    result = await provider.test_connection()

                    if result.get("success"):
                        app_logger.info(
                            f"Provider {provider_name} connection successful", extra=result
                        )
                    else:
                        app_logger.warning(
                            f"Provider {provider_name} connection failed", extra=result
                        )

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
                "performance_metrics": provider.get_performance_metrics(),
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
                "timeout_seconds": self.failover_config.circuit_breaker_timeout,
            },
        }

    def _parse_messages(
        self, messages: List[Dict[str, str]]
    ) -> tuple[str, str, List[Dict[str, str]]]:
        """
        Parse messages into system prompt, user message, and conversation history

        Args:
            messages: List of message dictionaries with 'role' and 'content'

        Returns:
            Tuple of (system_prompt, user_message, conversation_history)
        """
        system_prompt = ""
        user_message = ""
        conversation_history = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = content
            elif role == "user":
                user_message = content  # Will be overwritten by last user message
            elif role == "assistant":
                conversation_history.append(msg)

        # Ensure we have the last user message if multiple exist
        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        if user_messages:
            user_message = user_messages[-1].get("content", "")

        return system_prompt, user_message, conversation_history

    async def generate_response_legacy(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate complete response by streaming and collecting output

        Compatibility method for LangChain adapters that expect non-streaming response.
        This method wraps the streaming interface to provide a complete response.

        Args:
            messages: List of conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Response randomness (0.0-1.0)
            **kwargs: Additional generation parameters

        Returns:
            LLMResponse object with complete response content

        Raises:
            RuntimeError: If response generation fails
        """
        if not self.is_initialized:
            await self.initialize()

        start_time = time.time()

        try:
            # Use shared message parsing method
            system_prompt, user_message, conversation_history = self._parse_messages(messages)

            # Track metrics
            chunks_received = 0
            first_chunk_time = None

            # Stream and collect complete response
            full_response = ""
            async for chunk in self.generate_streamed_response(
                user_message=user_message,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                max_tokens=max_tokens,
                temperature=temperature,
                context=kwargs.get("context", {}),
            ):
                full_response += chunk
                chunks_received += 1
                if chunks_received == 1:
                    first_chunk_time = time.time()

            completion_time = time.time()

            # Get provider information
            provider = self.router.providers.get(self.router.default_provider)
            provider_name = self.router.default_provider
            model_name = getattr(provider, "model", "unknown")

            # Create proper metrics object
            metrics = LLMMetrics(
                provider=provider_name,
                model=model_name,
                start_time=start_time,
                first_chunk_time=first_chunk_time,
                completion_time=completion_time,
                total_chunks=chunks_received,
                total_characters=len(full_response),
                # Token counting will be estimated for now - proper tokenizer can be added later
                input_tokens=self._estimate_tokens(
                    " ".join(msg.get("content", "") for msg in messages)
                ),
                output_tokens=self._estimate_tokens(full_response),
                cost_estimate=None,  # Will be calculated by cost monitor
            )

            # Create proper LLMResponse
            response = LLMResponse(
                content=full_response,
                metrics=metrics,
                provider=provider_name,
                model=model_name,
                finish_reason="stop",
                usage={
                    "prompt_tokens": metrics.input_tokens,
                    "completion_tokens": metrics.output_tokens,
                    "total_tokens": (metrics.input_tokens or 0) + (metrics.output_tokens or 0),
                },
            )

            app_logger.info(
                "Response generation completed",
                extra={
                    "provider": provider_name,
                    "model": model_name,
                    "response_length": len(full_response),
                    "duration_ms": metrics.total_duration_ms,
                    "first_chunk_ms": metrics.first_chunk_latency_ms,
                    "total_chunks": chunks_received,
                },
            )

            return response

        except asyncio.TimeoutError:
            app_logger.error("Response generation timed out")
            raise RuntimeError("Response generation timed out") from None
        except Exception as e:
            app_logger.error(
                "Response generation failed",
                extra={"error_type": type(e).__name__, "provider": self.router.default_provider},
            )
            raise RuntimeError("Response generation temporarily unavailable") from e

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text

        This is a simple estimation. For production, consider using tiktoken
        or the provider's tokenizer for accurate counts.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        # More accurate estimation based on common patterns
        # Average English word is ~4.7 characters, average token is ~0.75 words
        words = len(text.split())
        chars = len(text)

        # Use combination of word count and character count for better estimate
        # This accounts for punctuation, special characters, etc.
        word_estimate = words * 1.3  # Tokens tend to be slightly more than words
        char_estimate = chars / 4.0  # Fallback character-based estimate

        # Weight word estimate more heavily for normal text
        if words > 0:
            return int(word_estimate * 0.7 + char_estimate * 0.3)
        else:
            return int(char_estimate)

    # StandardLLMInterface implementation
    @property
    def interface_type(self) -> LLMInterfaceType:
        """Return interface type"""
        return LLMInterfaceType.COMPLETE

    @property
    def model_name(self) -> str:
        """Return current model name"""
        if self.router and self.router.default_provider:
            provider = self.router.providers.get(self.router.default_provider)
            return getattr(provider, "model", "unknown")
        return "unknown"

    @property
    def provider_name(self) -> str:
        """Return current provider name"""
        return self.router.default_provider if self.router else "unknown"

    async def generate_response(self, request: StandardLLMRequest) -> StandardLLMResponse:
        """
        StandardLLMInterface compliant generate_response method

        Args:
            request: StandardLLMRequest with all parameters

        Returns:
            StandardLLMResponse with complete response data
        """
        if not self.is_initialized:
            await self.initialize()

        # Validate request
        InterfaceValidator.validate_request(request)

        start_time = time.time()

        try:
            # Extract message components using shared parsing method
            system_prompt, user_message, conversation_history = self._parse_messages(
                request.messages
            )

            # Generate response using existing streaming infrastructure
            full_response = ""
            chunks_received = 0
            first_chunk_time = None

            async for chunk in self._generate_streamed_response_internal(
                user_message=user_message,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                context=request.context or {},
            ):
                full_response += chunk
                chunks_received += 1
                if chunks_received == 1:
                    first_chunk_time = time.time()

            completion_time = time.time()

            # Create standardized response
            response = StandardLLMResponse(
                content=full_response,
                interface_type=LLMInterfaceType.COMPLETE,
                model_used=self.model_name,
                provider=self.provider_name,
                token_usage={
                    "prompt_tokens": self._estimate_tokens(
                        " ".join(msg.get("content", "") for msg in request.messages)
                    ),
                    "completion_tokens": self._estimate_tokens(full_response),
                    "total_tokens": self._estimate_tokens(
                        " ".join(msg.get("content", "") for msg in request.messages)
                    )
                    + self._estimate_tokens(full_response),
                },
                finish_reason="stop",
                metadata={
                    "chunks_received": chunks_received,
                    "first_chunk_latency_ms": (
                        (first_chunk_time - start_time) * 1000 if first_chunk_time else None
                    ),
                    "total_duration_ms": (completion_time - start_time) * 1000,
                    "workflow_stage": request.workflow_stage,
                    "request_metadata": request.metadata,
                },
            )

            # Validate response
            InterfaceValidator.validate_response(response)

            app_logger.info(
                "Standard interface response generated",
                extra={
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "response_length": len(full_response),
                    "interface_type": response.interface_type.value,
                    "duration_ms": response.metadata["total_duration_ms"],
                },
            )

            return response

        except Exception as e:
            app_logger.error(
                "Standard interface response generation failed",
                extra={"error": str(e), "provider": self.provider_name},
            )
            raise

    async def generate_streamed_response(self, request: StandardLLMRequest) -> AsyncIterator[str]:
        """
        StandardLLMInterface compliant streaming method

        Args:
            request: StandardLLMRequest with streaming enabled

        Yields:
            Response chunks as strings
        """
        # Validate request
        InterfaceValidator.validate_request(request)

        # Extract message components
        system_prompt, user_message, conversation_history = self._parse_messages(request.messages)

        # Stream using existing infrastructure
        async for chunk in self._generate_streamed_response_internal(
            user_message=user_message,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            context=request.context or {},
        ):
            yield chunk

    async def ainvoke(self, messages: List[Any], **kwargs) -> Any:
        """LangChain/LangGraph async invoke compatibility"""
        try:
            # Convert to standard request
            request = LLMInterfaceAdapter.to_standard_request(
                messages, LLMInterfaceType.LANGCHAIN, **kwargs
            )

            # Generate response
            response = await self.generate_response(request)

            # Return in LangChain format
            return response.to_langchain_format()

        except Exception as e:
            app_logger.error(f"ainvoke error: {e}")
            raise

    def invoke(self, messages: List[Any], **kwargs) -> Any:
        """LangChain synchronous invoke compatibility"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                raise RuntimeError("Cannot run sync invoke in async context. Use ainvoke instead.")
            else:
                return loop.run_until_complete(self.ainvoke(messages, **kwargs))
        except Exception as e:
            app_logger.error(f"invoke error: {e}")
            raise

    async def astream(self, messages: List[Any], **kwargs) -> AsyncIterator[str]:
        """LangChain/LangGraph async streaming compatibility"""
        try:
            # Convert to standard request
            request = LLMInterfaceAdapter.to_standard_request(
                messages, LLMInterfaceType.LANGCHAIN, stream=True, **kwargs
            )

            # Stream response
            async for chunk in self.generate_streamed_response(request):
                yield chunk

        except Exception as e:
            app_logger.error(f"astream error: {e}")
            raise

    # Backward compatibility methods
    async def generate_streamed_response_legacy(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """Legacy generate_streamed_response method for backward compatibility"""

        async for chunk in self._generate_streamed_response_internal(
            user_message=user_message,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            max_tokens=max_tokens,
            temperature=temperature,
            context=context,
        ):
            yield chunk

    async def stream_response(
        self, messages: List[Dict[str, str]], context: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[str]:
        """Backward compatible stream_response method"""
        return self.compatibility_layer.stream_response(messages, context)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Backward compatible performance metrics"""
        return self.compatibility_layer.get_performance_metrics()

    async def generate_business_response(self, **kwargs) -> StandardLLMResponse:
        """Provides backward compatibility for services expecting this method name."""
        # This is a wrapper for the main generate_response method.
        # It adapts the call to the standardized interface.
        app_logger.info("generate_business_response called (compatibility layer)")

        # Create a standard request from the provided kwargs
        request = StandardLLMRequest(
            messages=kwargs.get("messages", []),
            max_tokens=kwargs.get("max_tokens"),
            temperature=kwargs.get("temperature"),
            context=kwargs.get("context", {}),
            workflow_stage=kwargs.get("workflow_stage", "business_response"),
            user_input=kwargs.get("user_input", ""),
            metadata=kwargs.get("metadata", {}),
        )

        return await self.generate_response(request)


# This file will be modified to remove global instance creation.
# The new content will be added in a subsequent step.
