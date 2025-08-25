"""
LLM Service Abstraction Layer
Provides unified interface for multiple LLM providers
ZERO BREAKING CHANGES: Existing LLMStreamingService remains unchanged
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any, List, Union
from dataclasses import dataclass
from enum import Enum
import logging

from ..core.config import settings
from ..core.logger import app_logger


class LLMProvider(Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class LLMMetrics:
    """Enhanced metrics for multi-provider tracking"""
    provider: str
    model: str
    start_time: float
    first_chunk_time: Optional[float] = None
    completion_time: Optional[float] = None
    total_chunks: int = 0
    total_characters: int = 0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_estimate: Optional[float] = None
    
    @property
    def first_chunk_latency_ms(self) -> float:
        """First chunk latency in milliseconds"""
        if self.first_chunk_time:
            return (self.first_chunk_time - self.start_time) * 1000
        return 0.0
    
    @property
    def total_duration_ms(self) -> float:
        """Total completion time in milliseconds"""
        if self.completion_time:
            return (self.completion_time - self.start_time) * 1000
        return 0.0
    
    @property
    def throughput_chars_per_sec(self) -> float:
        """Characters per second throughput"""
        if self.completion_time and self.total_characters > 0:
            duration_sec = self.completion_time - self.start_time
            return self.total_characters / duration_sec if duration_sec > 0 else 0
        return 0.0


@dataclass 
class LLMRequest:
    """Standard request format for all providers"""
    messages: List[Dict[str, str]]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: bool = True
    context: Optional[Dict[str, Any]] = None
    provider_specific: Optional[Dict[str, Any]] = None


@dataclass
class LLMResponse:
    """Standard response format for all providers"""
    content: str
    metrics: LLMMetrics
    provider: str
    model: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, provider_name: str, model: str):
        self.provider_name = provider_name
        self.model = model
        self.metrics_history: List[LLMMetrics] = []
        
    @abstractmethod
    async def stream_response(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream response chunks from the provider"""
        pass
    
    @abstractmethod
    async def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Generate complete response (non-streaming)"""
        pass
    
    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for token usage"""
        pass
    
    @abstractmethod
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get current rate limit information"""
        pass
    
    def add_metrics(self, metrics: LLMMetrics):
        """Add metrics to history"""
        self.metrics_history.append(metrics)
        
        # Keep only last 100 metrics
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for this provider"""
        if not self.metrics_history:
            return {"provider": self.provider_name, "status": "no_data"}
        
        recent_metrics = self.metrics_history[-10:]
        
        first_chunk_latencies = [m.first_chunk_latency_ms for m in recent_metrics if m.first_chunk_time]
        total_durations = [m.total_duration_ms for m in recent_metrics if m.completion_time]
        costs = [m.cost_estimate for m in recent_metrics if m.cost_estimate is not None]
        
        return {
            "provider": self.provider_name,
            "model": self.model,
            "requests_tracked": len(self.metrics_history),
            "recent_requests": len(recent_metrics),
            "avg_first_chunk_ms": sum(first_chunk_latencies) / len(first_chunk_latencies) if first_chunk_latencies else 0,
            "avg_total_duration_ms": sum(total_durations) / len(total_durations) if total_durations else 0,
            "avg_cost": sum(costs) / len(costs) if costs else 0,
            "total_cost": sum(costs) if costs else 0,
            "target_met_percentage": (
                len([l for l in first_chunk_latencies if l < 200]) / len(first_chunk_latencies) * 100
                if first_chunk_latencies else 0
            )
        }


class LLMProviderFactory:
    """Factory for creating LLM provider instances"""
    
    _providers: Dict[str, type] = {}
    
    @classmethod
    def register_provider(cls, provider_name: str, provider_class: type):
        """Register a new provider class"""
        cls._providers[provider_name] = provider_class
        app_logger.info(f"Registered LLM provider: {provider_name}")
    
    @classmethod
    def create_provider(cls, provider_name: str, **kwargs) -> BaseLLMProvider:
        """Create provider instance"""
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown provider: {provider_name}. Available: {list(cls._providers.keys())}")
        
        provider_class = cls._providers[provider_name]
        return provider_class(**kwargs)
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """List available providers"""
        return list(cls._providers.keys())


class LLMRouter:
    """Routes requests to appropriate LLM provider with load balancing"""
    
    def __init__(self):
        self.providers: Dict[str, BaseLLMProvider] = {}
        self.default_provider: Optional[str] = None
        self.routing_rules: List[Dict[str, Any]] = []
        
    def add_provider(self, name: str, provider: BaseLLMProvider, is_default: bool = False):
        """Add a provider to the router"""
        self.providers[name] = provider
        if is_default or not self.default_provider:
            self.default_provider = name
        
        app_logger.info(f"Added LLM provider to router: {name}", extra={
            "provider": provider.provider_name,
            "model": provider.model,
            "is_default": is_default
        })
    
    def add_routing_rule(self, condition: Dict[str, Any], provider_name: str):
        """Add routing rule for request selection"""
        self.routing_rules.append({
            "condition": condition,
            "provider": provider_name
        })
    
    def select_provider(self, request: LLMRequest) -> str:
        """Select best provider for request"""
        # Apply routing rules
        for rule in self.routing_rules:
            if self._matches_condition(request, rule["condition"]):
                if rule["provider"] in self.providers:
                    return rule["provider"]
        
        # Return default provider
        return self.default_provider or list(self.providers.keys())[0]
    
    def _matches_condition(self, request: LLMRequest, condition: Dict[str, Any]) -> bool:
        """Check if request matches routing condition"""
        # Simple rule matching - can be extended
        if "max_tokens" in condition:
            if request.max_tokens and request.max_tokens > condition["max_tokens"]:
                return True
        
        if "context_type" in condition and request.context:
            if request.context.get("type") == condition["context_type"]:
                return True
        
        return False
    
    async def stream_response(self, request: LLMRequest, provider_name: Optional[str] = None) -> AsyncIterator[str]:
        """Stream response using selected provider"""
        if provider_name and provider_name in self.providers:
            provider = self.providers[provider_name]
        else:
            provider_name = self.select_provider(request)
            provider = self.providers[provider_name]
        
        app_logger.info(f"Routing request to provider: {provider_name}")
        
        async for chunk in provider.stream_response(request):
            yield chunk
    
    async def generate_response(self, request: LLMRequest, provider_name: Optional[str] = None) -> LLMResponse:
        """Generate response using selected provider"""
        if provider_name and provider_name in self.providers:
            provider = self.providers[provider_name]
        else:
            provider_name = self.select_provider(request)
            provider = self.providers[provider_name]
        
        return await provider.generate_response(request)
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics from all providers"""
        return {
            name: provider.get_performance_metrics()
            for name, provider in self.providers.items()
        }


class CompatibilityLayer:
    """
    Maintains backward compatibility with existing LLMStreamingService
    Provides same interface while enabling new functionality
    """
    
    def __init__(self, llm_router: LLMRouter):
        self.router = llm_router
        
    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[str]:
        """Backward compatible stream_response method"""
        request = LLMRequest(
            messages=messages,
            context=context,
            max_tokens=500,
            temperature=0.7
        )
        
        async for chunk in self.router.stream_response(request):
            yield chunk
    
    async def generate_streamed_response(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncIterator[str]:
        """Backward compatible generate_streamed_response method"""
        messages = [{"role": "system", "content": system_prompt}]
        
        if conversation_history:
            messages.extend(conversation_history[-5:])
        
        messages.append({"role": "user", "content": user_message})
        
        async for chunk in self.stream_response(messages):
            yield chunk
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Backward compatible performance metrics"""
        all_metrics = self.router.get_all_metrics()
        
        # Return metrics in same format as original service
        if not all_metrics:
            return {"status": "no_data"}
        
        # Aggregate metrics from all providers
        default_provider = self.router.default_provider
        if default_provider and default_provider in all_metrics:
            return all_metrics[default_provider]
        
        # If no default, return first provider's metrics
        return list(all_metrics.values())[0] if all_metrics else {"status": "no_data"}