"""
Enterprise Circuit Breaker for Google Calendar API
Implements resilient patterns for external service integration
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable
from functools import wraps
from enum import Enum
import logging

from googleapiclient.errors import HttpError
from ..core.config import settings
from ..core.logger import app_logger


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit breaker active - failing fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CalendarCircuitBreaker:
    """
    Enterprise-grade circuit breaker for Google Calendar API
    
    Features:
    - Exponential backoff with jitter
    - Configurable failure thresholds
    - Automatic recovery testing
    - Comprehensive metrics collection
    - Graceful degradation support
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        success_threshold: int = 2,
        timeout: int = 10
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.timeout = timeout
        
        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.next_attempt_time: Optional[datetime] = None
        
        # Metrics
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0
        self.total_circuit_opens = 0
        self.total_fallback_calls = 0
        
        # Circuit breaker lock for thread safety
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker protection
        
        Args:
            func: Function to execute (Google Calendar API call)
            *args, **kwargs: Function arguments
            
        Returns:
            Function result or raises CircuitBreakerOpenError
            
        Raises:
            CircuitBreakerOpenError: When circuit is open
            HttpError: When Google API returns error
        """
        async with self._lock:
            self.total_requests += 1
            
            # Check if circuit should be open
            if await self._should_attempt():
                try:
                    # Execute the function with timeout
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=self.timeout
                    )
                    
                    # Record success
                    await self._record_success()
                    return result
                    
                except (HttpError, asyncio.TimeoutError, Exception) as e:
                    # Record failure
                    await self._record_failure(e)
                    raise
            else:
                # Circuit is open - fail fast
                self.total_fallback_calls += 1
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is {self.state.value}. "
                    f"Next attempt at {self.next_attempt_time}"
                )
    
    async def _should_attempt(self) -> bool:
        """Determine if request should be attempted"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.next_attempt_time and datetime.now() >= self.next_attempt_time:
                app_logger.info("Circuit breaker entering HALF_OPEN state for recovery test")
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            # Allow limited requests to test recovery
            return True
        
        return False
    
    async def _record_success(self):
        """Record successful API call"""
        self.total_successes += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                # Service has recovered
                app_logger.info("Circuit breaker returning to CLOSED state - service recovered")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.last_failure_time = None
                self.next_attempt_time = None
        else:
            # Reset failure count on successful calls in CLOSED state
            self.failure_count = max(0, self.failure_count - 1)
    
    async def _record_failure(self, exception: Exception):
        """Record failed API call"""
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        app_logger.warning(
            f"Google Calendar API failure #{self.failure_count}: {str(exception)}"
        )
        
        if self.state == CircuitState.HALF_OPEN:
            # Recovery test failed - return to OPEN
            app_logger.error("Circuit breaker recovery test failed - returning to OPEN state")
            self.state = CircuitState.OPEN
            self.success_count = 0
            self._set_next_attempt_time()
        
        elif self.failure_count >= self.failure_threshold:
            # Open the circuit
            app_logger.error(
                f"Circuit breaker OPENING - failure threshold ({self.failure_threshold}) exceeded"
            )
            self.state = CircuitState.OPEN
            self.total_circuit_opens += 1
            self._set_next_attempt_time()
    
    def _set_next_attempt_time(self):
        """Set next attempt time with exponential backoff"""
        # Exponential backoff: 2^(open_count) * recovery_timeout with jitter
        backoff_multiplier = min(2 ** (self.total_circuit_opens - 1), 32)  # Cap at 32x
        backoff_seconds = self.recovery_timeout * backoff_multiplier
        
        # Add jitter (±25%)
        import random
        jitter = random.uniform(0.75, 1.25)
        backoff_seconds = int(backoff_seconds * jitter)
        
        self.next_attempt_time = datetime.now() + timedelta(seconds=backoff_seconds)
        app_logger.info(
            f"Circuit breaker will retry at {self.next_attempt_time} "
            f"(backoff: {backoff_seconds}s)"
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive circuit breaker metrics"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "total_circuit_opens": self.total_circuit_opens,
            "total_fallback_calls": self.total_fallback_calls,
            "failure_rate": (self.total_failures / max(1, self.total_requests)) * 100,
            "success_rate": (self.total_successes / max(1, self.total_requests)) * 100,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "next_attempt_time": self.next_attempt_time.isoformat() if self.next_attempt_time else None,
            "is_healthy": self.state == CircuitState.CLOSED,
            "configuration": {
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "success_threshold": self.success_threshold,
                "timeout": self.timeout
            }
        }
    
    def reset(self):
        """Reset circuit breaker to initial state (for testing/admin)"""
        app_logger.info("Circuit breaker manually reset to CLOSED state")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.next_attempt_time = None


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and calls are being rejected"""
    pass


# Global calendar circuit breaker instance
calendar_circuit_breaker = CalendarCircuitBreaker(
    failure_threshold=getattr(settings, 'CIRCUIT_BREAKER_FAILURE_THRESHOLD', 5),
    recovery_timeout=getattr(settings, 'CIRCUIT_BREAKER_RECOVERY_TIMEOUT', 30),
    success_threshold=getattr(settings, 'CIRCUIT_BREAKER_SUCCESS_THRESHOLD', 2),
    timeout=getattr(settings, 'CIRCUIT_BREAKER_TIMEOUT', 10)
)


def circuit_breaker(func: Callable) -> Callable:
    """
    Decorator to apply circuit breaker protection to Google Calendar API calls
    
    Usage:
        @circuit_breaker
        async def calendar_api_call():
            # Google Calendar API operation
            pass
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await calendar_circuit_breaker.call(func, *args, **kwargs)
    
    return wrapper