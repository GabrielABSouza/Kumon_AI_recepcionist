"""
Performance Monitoring Middleware for FastAPI

Real-time performance tracking middleware that captures:
- Request/response times
- Error rates and status codes  
- Concurrent request tracking
- Queue size monitoring
- Endpoint-specific performance metrics
- Performance anomaly detection
"""

import time
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict, deque
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import threading

from ..core.logger import app_logger


class PerformanceTracker:
    """Thread-safe performance metrics tracker"""
    
    def __init__(self):
        self._lock = threading.Lock()
        
        # Request tracking
        self.active_requests: Dict[str, float] = {}  # request_id -> start_time
        self.completed_requests = deque(maxlen=1000)  # Recent requests for analysis
        
        # Metrics aggregation  
        self.metrics = {
            "total_requests": 0,
            "total_errors": 0,
            "total_response_time": 0.0,
            "response_times": deque(maxlen=100),  # Last 100 response times
            "error_rates_by_minute": defaultdict(int),
            "requests_by_endpoint": defaultdict(int),
            "response_times_by_endpoint": defaultdict(lambda: deque(maxlen=50)),
            "status_codes": defaultdict(int),
            "concurrent_request_count": 0,
            "max_concurrent_requests": 0,
            "queue_sizes": deque(maxlen=50)
        }
        
        # Performance calculation cache
        self._last_calculation_time = datetime.now()
        self._cached_metrics: Optional[Dict[str, Any]] = None
        self._cache_duration = timedelta(seconds=5)  # 5-second cache
        
        app_logger.info("Performance Tracker initialized")
    
    def start_request(self, request_id: str, endpoint: str) -> float:
        """Start tracking a request"""
        
        start_time = time.time()
        
        with self._lock:
            self.active_requests[request_id] = start_time
            self.metrics["concurrent_request_count"] = len(self.active_requests)
            self.metrics["max_concurrent_requests"] = max(
                self.metrics["max_concurrent_requests"],
                self.metrics["concurrent_request_count"]
            )
            self.metrics["requests_by_endpoint"][endpoint] += 1
        
        return start_time
    
    def finish_request(
        self, 
        request_id: str, 
        endpoint: str, 
        status_code: int, 
        response_time: float
    ):
        """Finish tracking a request"""
        
        with self._lock:
            # Remove from active requests
            if request_id in self.active_requests:
                del self.active_requests[request_id]
            
            # Update metrics
            self.metrics["total_requests"] += 1
            self.metrics["total_response_time"] += response_time
            self.metrics["response_times"].append(response_time)
            self.metrics["response_times_by_endpoint"][endpoint].append(response_time)
            self.metrics["status_codes"][status_code] += 1
            self.metrics["concurrent_request_count"] = len(self.active_requests)
            
            # Track errors
            if status_code >= 400:
                self.metrics["total_errors"] += 1
                
                # Error rate by minute
                current_minute = datetime.now().replace(second=0, microsecond=0)
                self.metrics["error_rates_by_minute"][current_minute] += 1
            
            # Store completed request for analysis
            self.completed_requests.append({
                "timestamp": datetime.now(),
                "endpoint": endpoint,
                "status_code": status_code,
                "response_time": response_time,
                "request_id": request_id
            })
            
            # Clear cache on updates
            self._cached_metrics = None
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics with caching"""
        
        now = datetime.now()
        
        # Return cached metrics if still valid
        if (self._cached_metrics and 
            now - self._last_calculation_time < self._cache_duration):
            return self._cached_metrics
        
        with self._lock:
            metrics = self._calculate_metrics()
            
            # Cache the results
            self._cached_metrics = metrics
            self._last_calculation_time = now
            
            return metrics
    
    def _calculate_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics"""
        
        total_requests = self.metrics["total_requests"]
        total_errors = self.metrics["total_errors"]
        response_times = list(self.metrics["response_times"])
        
        # Basic metrics
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0.0
        avg_response_time = (
            self.metrics["total_response_time"] / total_requests 
            if total_requests > 0 else 0.0
        ) * 1000  # Convert to milliseconds
        
        # Percentile calculations
        if response_times:
            sorted_times = sorted(response_times)
            count = len(sorted_times)
            
            p95_index = int(0.95 * count)
            p99_index = int(0.99 * count)
            
            p95_response_time = sorted_times[min(p95_index, count - 1)] * 1000
            p99_response_time = sorted_times[min(p99_index, count - 1)] * 1000
        else:
            p95_response_time = p99_response_time = 0.0
        
        # Requests per second (last minute)
        recent_requests = [
            req for req in self.completed_requests
            if (datetime.now() - req["timestamp"]).total_seconds() <= 60
        ]
        requests_per_second = len(recent_requests) / 60.0
        
        # Endpoint-specific metrics
        endpoint_metrics = {}
        for endpoint, times in self.metrics["response_times_by_endpoint"].items():
            if times:
                endpoint_times = list(times)
                endpoint_metrics[endpoint] = {
                    "avg_response_time_ms": sum(endpoint_times) / len(endpoint_times) * 1000,
                    "request_count": self.metrics["requests_by_endpoint"][endpoint],
                    "p95_response_time_ms": sorted(endpoint_times)[int(0.95 * len(endpoint_times))] * 1000 if endpoint_times else 0.0
                }
        
        # Error rate trends
        current_time = datetime.now()
        recent_error_rates = []
        for i in range(5):  # Last 5 minutes
            minute = current_time - timedelta(minutes=i)
            minute_key = minute.replace(second=0, microsecond=0)
            errors_in_minute = self.metrics["error_rates_by_minute"].get(minute_key, 0)
            recent_error_rates.append(errors_in_minute)
        
        # Concurrent request statistics
        current_concurrent = self.metrics["concurrent_request_count"]
        max_concurrent = self.metrics["max_concurrent_requests"]
        
        # Queue size (for webhook processing)
        current_queue_size = len([
            req for req in self.completed_requests
            if req["endpoint"].endswith("/webhook") and
            (datetime.now() - req["timestamp"]).total_seconds() <= 30
        ])
        
        self.metrics["queue_sizes"].append(current_queue_size)
        
        return {
            "timestamp": datetime.now(),
            "requests_per_second": requests_per_second,
            "avg_response_time_ms": avg_response_time,
            "p95_response_time_ms": p95_response_time,
            "p99_response_time_ms": p99_response_time,
            "error_rate_percent": error_rate,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "concurrent_requests": current_concurrent,
            "max_concurrent_requests": max_concurrent,
            "queue_size": current_queue_size,
            "avg_queue_size": sum(self.metrics["queue_sizes"]) / len(self.metrics["queue_sizes"]) if self.metrics["queue_sizes"] else 0,
            "endpoint_metrics": endpoint_metrics,
            "status_code_distribution": dict(self.metrics["status_codes"]),
            "error_rate_trend": recent_error_rates,
            "webhook_processing_time_ms": endpoint_metrics.get("/api/v1/whatsapp/webhook", {}).get("avg_response_time_ms", 0.0)
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status based on current performance"""
        
        metrics = self.get_current_metrics()
        
        # Performance health scoring
        health_factors = {
            "response_time": self._score_response_time(metrics["avg_response_time_ms"]),
            "error_rate": self._score_error_rate(metrics["error_rate_percent"]),
            "concurrent_load": self._score_concurrent_load(metrics["concurrent_requests"]),
            "queue_health": self._score_queue_health(metrics["queue_size"])
        }
        
        # Overall health score (0-100)
        overall_health = sum(health_factors.values()) / len(health_factors)
        
        # Health status
        if overall_health >= 90:
            status = "excellent"
        elif overall_health >= 80:
            status = "good" 
        elif overall_health >= 60:
            status = "degraded"
        elif overall_health >= 40:
            status = "poor"
        else:
            status = "critical"
        
        return {
            "overall_health_score": overall_health,
            "health_status": status,
            "health_factors": health_factors,
            "recommendations": self._get_health_recommendations(health_factors)
        }
    
    def _score_response_time(self, avg_response_time_ms: float) -> float:
        """Score response time health (0-100)"""
        
        if avg_response_time_ms <= 100:
            return 100.0
        elif avg_response_time_ms <= 500:
            return 90.0
        elif avg_response_time_ms <= 1000:
            return 70.0
        elif avg_response_time_ms <= 2000:
            return 50.0
        elif avg_response_time_ms <= 5000:
            return 30.0
        else:
            return 10.0
    
    def _score_error_rate(self, error_rate_percent: float) -> float:
        """Score error rate health (0-100)"""
        
        if error_rate_percent <= 0.1:
            return 100.0
        elif error_rate_percent <= 0.5:
            return 90.0
        elif error_rate_percent <= 1.0:
            return 80.0
        elif error_rate_percent <= 2.0:
            return 60.0
        elif error_rate_percent <= 5.0:
            return 40.0
        else:
            return 20.0
    
    def _score_concurrent_load(self, concurrent_requests: int) -> float:
        """Score concurrent load health (0-100)"""
        
        if concurrent_requests <= 10:
            return 100.0
        elif concurrent_requests <= 25:
            return 90.0
        elif concurrent_requests <= 50:
            return 80.0
        elif concurrent_requests <= 100:
            return 60.0
        elif concurrent_requests <= 200:
            return 40.0
        else:
            return 20.0
    
    def _score_queue_health(self, queue_size: int) -> float:
        """Score queue health (0-100)"""
        
        if queue_size <= 5:
            return 100.0
        elif queue_size <= 15:
            return 80.0
        elif queue_size <= 30:
            return 60.0
        elif queue_size <= 50:
            return 40.0
        else:
            return 20.0
    
    def _get_health_recommendations(self, health_factors: Dict[str, float]) -> List[str]:
        """Get performance improvement recommendations"""
        
        recommendations = []
        
        if health_factors["response_time"] < 70:
            recommendations.append("Consider optimizing API response times - current performance is below optimal")
        
        if health_factors["error_rate"] < 80:
            recommendations.append("High error rate detected - investigate and fix error sources")
        
        if health_factors["concurrent_load"] < 60:
            recommendations.append("High concurrent load - consider scaling or load balancing")
        
        if health_factors["queue_health"] < 60:
            recommendations.append("Webhook processing queue is backing up - optimize processing speed")
        
        if not recommendations:
            recommendations.append("System performance is optimal - continue monitoring")
        
        return recommendations


# Global performance tracker instance
performance_tracker = PerformanceTracker()


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for real-time performance monitoring
    
    Features:
    - Request/response time tracking
    - Error rate monitoring
    - Concurrent request tracking
    - Endpoint-specific metrics
    - Performance anomaly detection
    - Real-time dashboard data collection
    """
    
    def __init__(self, app, enable_detailed_logging: bool = False):
        super().__init__(app)
        self.enable_detailed_logging = enable_detailed_logging
        self.tracker = performance_tracker
        
        app_logger.info("Performance Middleware initialized")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with performance tracking"""
        
        # Generate unique request ID
        request_id = f"{id(request)}_{time.time()}"
        
        # Extract endpoint for tracking
        endpoint = f"{request.method} {request.url.path}"
        
        # Start request tracking
        start_time = self.tracker.start_request(request_id, endpoint)
        
        try:
            # Process the request
            response: Response = await call_next(request)
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Finish request tracking
            self.tracker.finish_request(
                request_id=request_id,
                endpoint=endpoint,
                status_code=response.status_code,
                response_time=response_time
            )
            
            # Add performance headers to response
            response.headers["X-Response-Time"] = f"{response_time * 1000:.2f}ms"
            response.headers["X-Request-ID"] = request_id
            
            # Detailed logging for slow requests
            if self.enable_detailed_logging and response_time > 1.0:  # Log requests > 1 second
                app_logger.warning(
                    f"Slow request detected: {endpoint}",
                    extra={
                        "request_id": request_id,
                        "response_time_ms": response_time * 1000,
                        "status_code": response.status_code,
                        "endpoint": endpoint
                    }
                )
            
            return response
            
        except Exception as e:
            # Handle errors
            response_time = time.time() - start_time
            
            # Track as error (status 500)
            self.tracker.finish_request(
                request_id=request_id,
                endpoint=endpoint, 
                status_code=500,
                response_time=response_time
            )
            
            app_logger.error(
                f"Request error: {endpoint}",
                extra={
                    "request_id": request_id,
                    "response_time_ms": response_time * 1000,
                    "error": str(e),
                    "endpoint": endpoint
                },
                exc_info=True
            )
            
            # Re-raise the exception
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return self.tracker.get_current_metrics()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return self.tracker.get_health_status()


# Performance instrumentation decorator
def performance_monitor(operation_name: str, category: str = "general"):
    """
    Decorator for monitoring performance of specific operations
    
    Args:
        operation_name: Name of the operation being monitored
        category: Category (e.g., 'ai', 'database', 'api')
    """
    
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = f"{operation_name}_{id(start_time)}"
            
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Log successful operation
                app_logger.info(
                    f"Operation completed: {operation_name}",
                    extra={
                        "operation_id": operation_id,
                        "execution_time_ms": execution_time * 1000,
                        "category": category,
                        "status": "success"
                    }
                )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                # Log failed operation
                app_logger.error(
                    f"Operation failed: {operation_name}",
                    extra={
                        "operation_id": operation_id,
                        "execution_time_ms": execution_time * 1000,
                        "category": category,
                        "status": "error",
                        "error": str(e)
                    },
                    exc_info=True
                )
                
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = f"{operation_name}_{id(start_time)}"
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Log successful operation
                app_logger.info(
                    f"Operation completed: {operation_name}",
                    extra={
                        "operation_id": operation_id,
                        "execution_time_ms": execution_time * 1000,
                        "category": category,
                        "status": "success"
                    }
                )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                # Log failed operation  
                app_logger.error(
                    f"Operation failed: {operation_name}",
                    extra={
                        "operation_id": operation_id,
                        "execution_time_ms": execution_time * 1000,
                        "category": category,
                        "status": "error",
                        "error": str(e)
                    },
                    exc_info=True
                )
                
                raise
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator