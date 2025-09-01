"""
Circuit Breaker Pattern Implementation for Railway-Optimized Services

Provides fault tolerance and prevents cascade failures with:
- Fast failure detection (2 failures = open circuit)
- Quick recovery (15s timeout)
- Graceful degradation support
"""

import asyncio
import time
from typing import Callable, Any, Optional, TypeVar, Union
from functools import wraps
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..core.logger import app_logger


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject calls
    HALF_OPEN = "half_open" # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 2          # Railway-optimized: fail fast
    recovery_timeout: float = 15.0      # Railway-optimized: quick recovery
    expected_exception: type = Exception
    success_threshold: int = 1          # Successes to close circuit
    name: Optional[str] = None


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics"""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    circuit_opened_count: int = 0


class CircuitBreaker:
    """
    Railway-optimized circuit breaker implementation
    
    Features:
    - Fast failure detection (2 strikes = open)
    - Quick recovery attempts (15s)
    - Comprehensive logging for debugging
    - Statistics tracking
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._state_changed_time = time.time()
        self._lock = asyncio.Lock()
        
        app_logger.info(f"Circuit breaker '{self.config.name}' initialized", extra={
            "failure_threshold": config.failure_threshold,
            "recovery_timeout": config.recovery_timeout
        })
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        async with self._lock:
            self.stats.total_calls += 1
            
            # Check circuit state
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    app_logger.info(f"Circuit breaker '{self.config.name}' attempting recovery")
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.config.name}' is OPEN. "
                        f"Retry after {self._time_until_reset():.1f}s"
                    )
        
        # Execute the function
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await self._on_success()
            return result
            
        except self.config.expected_exception as e:
            await self._on_failure(e)
            raise
    
    async def _on_success(self):
        """Handle successful call"""
        async with self._lock:
            self.stats.success_count += 1
            self.stats.total_successes += 1
            self.stats.last_success_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                if self.stats.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.stats.failure_count = 0
                    self.stats.success_count = 0
                    app_logger.info(f"Circuit breaker '{self.config.name}' recovered to CLOSED state")
            
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                self.stats.failure_count = 0
    
    async def _on_failure(self, error: Exception):
        """Handle failed call"""
        async with self._lock:
            self.stats.failure_count += 1
            self.stats.total_failures += 1
            self.stats.last_failure_time = time.time()
            
            app_logger.warning(f"Circuit breaker '{self.config.name}' recorded failure", extra={
                "failure_count": self.stats.failure_count,
                "error": str(error)
            })
            
            if self.state == CircuitState.HALF_OPEN:
                # Failed during recovery, reopen immediately
                self.state = CircuitState.OPEN
                self._state_changed_time = time.time()
                self.stats.circuit_opened_count += 1
                app_logger.error(f"Circuit breaker '{self.config.name}' reopened after recovery failure")
                
            elif self.state == CircuitState.CLOSED:
                if self.stats.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    self._state_changed_time = time.time()
                    self.stats.circuit_opened_count += 1
                    app_logger.error(f"Circuit breaker '{self.config.name}' opened after {self.stats.failure_count} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time passed to attempt reset"""
        return time.time() - self._state_changed_time >= self.config.recovery_timeout
    
    def _time_until_reset(self) -> float:
        """Time remaining until reset attempt"""
        elapsed = time.time() - self._state_changed_time
        return max(0, self.config.recovery_timeout - elapsed)
    
    def get_state(self) -> dict:
        """Get circuit breaker state and stats"""
        return {
            "state": self.state.value,
            "stats": {
                "failure_count": self.stats.failure_count,
                "success_count": self.stats.success_count,
                "total_calls": self.stats.total_calls,
                "total_failures": self.stats.total_failures,
                "total_successes": self.stats.total_successes,
                "circuit_opened_count": self.stats.circuit_opened_count,
                "last_failure_time": self.stats.last_failure_time,
                "last_success_time": self.stats.last_success_time
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "name": self.config.name
            }
        }
    
    def reset(self):
        """Manually reset circuit breaker"""
        self.state = CircuitState.CLOSED
        self.stats.failure_count = 0
        self.stats.success_count = 0
        self._state_changed_time = time.time()
        app_logger.info(f"Circuit breaker '{self.config.name}' manually reset")


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# Decorator for easy use
def circuit_breaker(
    failure_threshold: int = 2,
    recovery_timeout: float = 15.0,
    expected_exception: type = Exception,
    name: Optional[str] = None
):
    """
    Circuit breaker decorator for Railway-optimized fault tolerance
    
    Usage:
        @circuit_breaker(failure_threshold=2, recovery_timeout=15, name="database")
        async def connect_to_database():
            # Your code here
            pass
    """
    def decorator(func: Callable) -> Callable:
        # Use function name if no name provided
        breaker_name = name or f"{func.__module__}.{func.__name__}"
        
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=breaker_name
        )
        
        breaker = CircuitBreaker(config)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run in event loop
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(breaker.call(func, *args, **kwargs))
        
        # Add method to get breaker state
        wrapper = async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        wrapper.get_circuit_state = breaker.get_state
        wrapper.reset_circuit = breaker.reset
        
        return wrapper
    
    return decorator


# Global circuit breaker registry for monitoring
_circuit_breakers = {}


def get_circuit_breaker_status() -> dict:
    """Get status of all circuit breakers"""
    return {
        name: breaker.get_state()
        for name, breaker in _circuit_breakers.items()
    }

def get_circuit_breaker_registry():
    """Get the global circuit breaker registry for health monitoring"""
    return _circuit_breakers