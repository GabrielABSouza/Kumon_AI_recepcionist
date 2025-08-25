"""
Performance Optimization Middleware
Phase 4 Wave 4.2: Transparent performance optimization integration

Provides transparent performance optimization for:
- LLM request optimization (cost, reliability, error reduction)
- Message processing optimization
- Automatic optimization pipeline application
- No breaking changes to existing flows
"""

import time
import asyncio
from typing import Callable, Dict, Any, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.config import settings
from ..core.logger import app_logger as logger
from ..services.performance_integration_service import performance_integration


class PerformanceOptimizationMiddleware(BaseHTTPMiddleware):
    """Transparent performance optimization middleware"""
    
    def __init__(self, app: ASGIApp, enable_optimization: bool = True):
        super().__init__(app)
        self.enable_optimization = enable_optimization
        self.optimization_paths = {
            # LLM Service endpoints
            "/api/v1/llm-service",
            # Conversation processing endpoints
            "/api/v1/conversation", 
            "/api/v1/whatsapp/webhook",
            "/api/v1/units",
            "/api/v1/evolution/webhook"
        }
        
        # Track performance metrics
        self.request_count = 0
        self.optimization_count = 0
        self.total_optimization_time = 0.0
    
    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        """Process request with optional performance optimization"""
        
        start_time = time.time()
        
        # Check if optimization should be applied
        should_optimize = (
            self.enable_optimization and 
            self._should_optimize_request(request)
        )
        
        if should_optimize:
            return await self._dispatch_with_optimization(request, call_next, start_time)
        else:
            return await self._dispatch_normal(request, call_next, start_time)
    
    def _should_optimize_request(self, request: Request) -> bool:
        """Determine if request should be optimized"""
        
        # Skip if performance integration not initialized
        if not performance_integration.services_initialized:
            return False
        
        # Check if path matches optimization targets
        path = request.url.path
        for optimization_path in self.optimization_paths:
            if path.startswith(optimization_path):
                return True
        
        # Check for LLM-related requests in body (POST requests)
        if request.method == "POST":
            # Check Content-Type for JSON
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                return True
        
        return False
    
    async def _dispatch_with_optimization(
        self, 
        request: Request, 
        call_next: Callable[[Request], Response],
        start_time: float
    ) -> Response:
        """Process request with performance optimization"""
        
        try:
            self.request_count += 1
            optimization_start = time.time()
            
            # Extract request context for optimization
            request_context = await self._extract_request_context(request)
            
            # Apply optimizations if this is an LLM request
            if self._is_llm_request(request, request_context):
                response = await self._handle_llm_request_optimization(
                    request, call_next, request_context
                )
            else:
                # Apply general message processing optimization
                response = await self._handle_message_processing_optimization(
                    request, call_next, request_context
                )
            
            # Track optimization metrics
            optimization_time = time.time() - optimization_start
            self.optimization_count += 1
            self.total_optimization_time += optimization_time
            
            # Add performance headers
            if hasattr(response, 'headers'):
                response.headers["X-Performance-Optimized"] = "true"
                response.headers["X-Optimization-Time-Ms"] = f"{optimization_time * 1000:.2f}"
            
            return response
            
        except Exception as e:
            logger.error(f"Performance optimization middleware error: {e}")
            # Fallback to normal processing if optimization fails
            return await self._dispatch_normal(request, call_next, start_time)
    
    async def _dispatch_normal(
        self, 
        request: Request, 
        call_next: Callable[[Request], Response],
        start_time: float
    ) -> Response:
        """Process request normally without optimization"""
        
        response = await call_next(request)
        
        # Add standard performance headers
        if hasattr(response, 'headers'):
            response.headers["X-Performance-Optimized"] = "false"
            response.headers["X-Response-Time-Ms"] = f"{(time.time() - start_time) * 1000:.2f}"
        
        return response
    
    async def _extract_request_context(self, request: Request) -> Dict[str, Any]:
        """Extract request context for optimization decisions"""
        
        context = {
            "path": request.url.path,
            "method": request.method,
            "headers": dict(request.headers),
            "query_params": dict(request.query_params)
        }
        
        # Extract body for POST requests (careful not to consume the stream)
        if request.method == "POST":
            try:
                # Store original body for later use
                body = await request.body()
                if body:
                    # Create new request with body available for downstream processing
                    async def receive():
                        return {"type": "http.request", "body": body}
                    request._receive = receive
                    
                    # Try to parse JSON if possible
                    try:
                        import json
                        context["body"] = json.loads(body.decode())
                    except:
                        context["body"] = {"raw": body.decode()[:1000]}  # First 1000 chars
                
            except Exception as e:
                logger.debug(f"Could not extract request body: {e}")
                context["body"] = {}
        
        return context
    
    def _is_llm_request(self, request: Request, context: Dict[str, Any]) -> bool:
        """Determine if this is an LLM-related request"""
        
        path = request.url.path
        
        # Direct LLM service endpoints
        if "/api/v1/llm-service" in path:
            return True
        
        # Check request body for LLM-related content
        body = context.get("body", {})
        if isinstance(body, dict):
            # Look for common LLM request indicators
            llm_indicators = ["prompt", "message", "model", "temperature", "max_tokens"]
            if any(indicator in str(body).lower() for indicator in llm_indicators):
                return True
        
        return False
    
    async def _handle_llm_request_optimization(
        self,
        request: Request,
        call_next: Callable[[Request], Response], 
        context: Dict[str, Any]
    ) -> Response:
        """Handle LLM request with full optimization pipeline"""
        
        try:
            # Extract LLM parameters from request if possible
            body = context.get("body", {})
            
            if isinstance(body, dict) and "prompt" in body:
                # This is a direct LLM request - apply optimization
                optimized_operation = performance_integration.execute_optimized_operation
                
                # Create wrapper for the request processing
                async def llm_request_wrapper():
                    return await call_next(request)
                
                # Execute with performance optimization
                response = await optimized_operation(
                    "llm_request",
                    llm_request_wrapper,
                    prompt=body.get("prompt", ""),
                    system_message=body.get("system_message", ""),
                    model=body.get("model", "gpt-3.5-turbo"),
                    temperature=body.get("temperature", 0.7),
                    max_tokens=body.get("max_tokens")
                )
                
                return response
            else:
                # This might contain LLM processing but not direct - apply general optimization
                return await self._handle_message_processing_optimization(request, call_next, context)
            
        except Exception as e:
            logger.error(f"LLM request optimization failed: {e}")
            return await call_next(request)
    
    async def _handle_message_processing_optimization(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
        context: Dict[str, Any]
    ) -> Response:
        """Handle message processing with optimization"""
        
        try:
            # Apply reliability and error optimization for message processing
            async def message_processing_wrapper():
                return await call_next(request)
            
            response = await performance_integration.execute_optimized_operation(
                "message_processing",
                message_processing_wrapper
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Message processing optimization failed: {e}")
            return await call_next(request)
    
    async def get_middleware_stats(self) -> Dict[str, Any]:
        """Get middleware performance statistics"""
        
        avg_optimization_time = (
            self.total_optimization_time / self.optimization_count 
            if self.optimization_count > 0 else 0
        )
        
        optimization_rate = (
            (self.optimization_count / self.request_count * 100) 
            if self.request_count > 0 else 0
        )
        
        return {
            "total_requests": self.request_count,
            "optimized_requests": self.optimization_count,
            "optimization_rate_percentage": round(optimization_rate, 2),
            "average_optimization_time_ms": round(avg_optimization_time * 1000, 2),
            "total_optimization_time_seconds": round(self.total_optimization_time, 2),
            "optimization_enabled": self.enable_optimization,
            "optimization_paths": list(self.optimization_paths)
        }