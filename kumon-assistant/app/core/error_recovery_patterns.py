"""
Wave 7: Advanced Error Recovery Patterns System
Comprehensive error handling with intelligent recovery strategies,
circuit breakers, and resilience patterns
"""

import asyncio
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from ..core.logger import app_logger


class ErrorSeverity(Enum):
    """Error severity levels for classification and handling"""

    LOW = "low"  # Minor issues, continue processing
    MEDIUM = "medium"  # Significant issues, may need intervention
    HIGH = "high"  # Critical issues, immediate attention required
    CRITICAL = "critical"  # System-threatening issues, emergency response


class ErrorCategory(Enum):
    """Error categories for specialized handling"""

    NETWORK = "network"  # Network connectivity issues
    SERVICE = "service"  # External service failures
    VALIDATION = "validation"  # Data validation errors
    AUTHENTICATION = "auth"  # Authentication/authorization failures
    RATE_LIMIT = "rate_limit"  # Rate limiting or throttling
    TIMEOUT = "timeout"  # Operation timeout errors
    RESOURCE = "resource"  # Resource exhaustion (memory, disk, etc.)
    DATA = "data"  # Data corruption or integrity issues
    CONFIGURATION = "config"  # Configuration or setup errors
    UNKNOWN = "unknown"  # Unclassified errors


class RecoveryStrategy(Enum):
    """Recovery strategies for different error types"""

    RETRY = "retry"  # Simple retry with backoff
    CIRCUIT_BREAKER = "circuit_breaker"  # Circuit breaker pattern
    FALLBACK = "fallback"  # Use alternative implementation
    DEGRADED = "degraded"  # Continue with reduced functionality
    CACHE = "cache"  # Use cached data
    QUEUE = "queue"  # Queue for later processing
    ESCALATE = "escalate"  # Escalate to human intervention
    ABORT = "abort"  # Abort operation safely


@dataclass
class ErrorContext:
    """Rich error context for analysis and recovery"""

    error: Exception
    error_id: str
    operation_name: str
    component: str
    severity: ErrorSeverity
    category: ErrorCategory
    user_id: Optional[str] = None
    unit_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    recovery_attempts: int = 0

    def __post_init__(self):
        if self.stack_trace is None:
            self.stack_trace = traceback.format_exc()


@dataclass
class RecoveryResult:
    """Result of error recovery attempt"""

    success: bool
    strategy_used: RecoveryStrategy
    result_data: Any = None
    error: Optional[Exception] = None
    recovery_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ErrorClassifier:
    """Intelligent error classification system"""

    def __init__(self):
        self.classification_rules = self._build_classification_rules()

    def classify_error(
        self, error: Exception, context: Dict[str, Any] = None
    ) -> tuple[ErrorSeverity, ErrorCategory]:
        """Classify error based on type, message, and context"""
        error_type = type(error).__name__
        error_message = str(error).lower()
        context = context or {}

        # Network errors
        if any(
            keyword in error_message
            for keyword in ["connection", "network", "timeout", "unreachable"]
        ):
            if "timeout" in error_message:
                return ErrorSeverity.MEDIUM, ErrorCategory.TIMEOUT
            return ErrorSeverity.MEDIUM, ErrorCategory.NETWORK

        # Service errors
        if any(
            keyword in error_message for keyword in ["service unavailable", "503", "502", "500"]
        ):
            return ErrorSeverity.HIGH, ErrorCategory.SERVICE

        # Authentication errors
        auth_keywords = ["unauthorized", "401", "authentication", "forbidden", "403"]
        if any(keyword in error_message for keyword in auth_keywords):
            return ErrorSeverity.MEDIUM, ErrorCategory.AUTHENTICATION

        # Rate limiting
        rate_keywords = ["rate limit", "429", "too many requests", "quota"]
        if any(keyword in error_message for keyword in rate_keywords):
            return ErrorSeverity.LOW, ErrorCategory.RATE_LIMIT

        # Validation errors
        validation_keywords = ["validation", "invalid", "malformed", "schema"]
        if any(keyword in error_message for keyword in validation_keywords):
            return ErrorSeverity.LOW, ErrorCategory.VALIDATION

        # Resource errors
        resource_keywords = ["memory", "disk", "resource", "capacity"]
        if any(keyword in error_message for keyword in resource_keywords):
            return ErrorSeverity.HIGH, ErrorCategory.RESOURCE

        # Data errors
        if any(
            keyword in error_message
            for keyword in ["corrupt", "integrity", "constraint", "duplicate"]
        ):
            return ErrorSeverity.MEDIUM, ErrorCategory.DATA

        # Configuration errors
        if any(
            keyword in error_message
            for keyword in ["config", "setting", "environment", "missing key"]
        ):
            return ErrorSeverity.HIGH, ErrorCategory.CONFIGURATION

        # Default classification based on error type
        if error_type in ["ValueError", "TypeError", "KeyError"]:
            return ErrorSeverity.MEDIUM, ErrorCategory.VALIDATION
        elif error_type in ["ConnectionError", "TimeoutError"]:
            return ErrorSeverity.MEDIUM, ErrorCategory.NETWORK
        elif error_type in ["PermissionError", "Forbidden"]:
            return ErrorSeverity.MEDIUM, ErrorCategory.AUTHENTICATION
        elif error_type in ["MemoryError", "OSError"]:
            return ErrorSeverity.HIGH, ErrorCategory.RESOURCE

        return ErrorSeverity.MEDIUM, ErrorCategory.UNKNOWN

    def _build_classification_rules(self) -> Dict[str, tuple]:
        """Build classification rules for common error patterns"""
        return {
            "openai.error.RateLimitError": (ErrorSeverity.LOW, ErrorCategory.RATE_LIMIT),
            "openai.error.APIError": (ErrorSeverity.MEDIUM, ErrorCategory.SERVICE),
            "openai.error.Timeout": (ErrorSeverity.MEDIUM, ErrorCategory.TIMEOUT),
            "requests.exceptions.ConnectionError": (ErrorSeverity.MEDIUM, ErrorCategory.NETWORK),
            "requests.exceptions.Timeout": (ErrorSeverity.MEDIUM, ErrorCategory.TIMEOUT),
            "sqlalchemy.exc.OperationalError": (ErrorSeverity.HIGH, ErrorCategory.DATA),
            "redis.exceptions.ConnectionError": (ErrorSeverity.MEDIUM, ErrorCategory.NETWORK),
            "asyncio.TimeoutError": (ErrorSeverity.MEDIUM, ErrorCategory.TIMEOUT),
        }


class CircuitBreaker:
    """Circuit breaker pattern implementation for resilient service calls"""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.success_count = 0
        self.total_requests = 0

    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        self.total_requests += 1

        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                app_logger.info(f"Circuit breaker {self.name} attempting reset (HALF_OPEN)")
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")

        try:
            result = (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
            self._record_success()
            return result

        except self.expected_exception as e:
            self._record_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        return (
            self.last_failure_time is not None
            and time.time() - self.last_failure_time >= self.recovery_timeout
        )

    def _record_success(self):
        """Record successful operation"""
        self.success_count += 1

        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.failure_count = 0
            app_logger.info(f"Circuit breaker {self.name} reset to CLOSED")

    def _record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            app_logger.warning(
                f"Circuit breaker {self.name} opened after " f"{self.failure_count} failures"
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_requests": self.total_requests,
            "success_rate": self.success_count / max(self.total_requests, 1),
            "last_failure_time": self.last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""

    pass


class RetryHandler:
    """Advanced retry handler with multiple backoff strategies"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    async def execute_with_retry(
        self, func: Callable, *args, retryable_exceptions: tuple = (Exception,), **kwargs
    ) -> Any:
        """Execute function with retry logic"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except retryable_exceptions as e:
                last_exception = e

                if attempt >= self.max_retries:
                    app_logger.error(
                        f"Max retries ({self.max_retries}) exceeded for " f"{func.__name__}"
                    )
                    break

                delay = self._calculate_delay(attempt)
                app_logger.warning(
                    f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                    f"Retrying in {delay:.2f}s"
                )
                await asyncio.sleep(delay)

            except Exception as e:
                # Non-retryable exception
                app_logger.error(f"Non-retryable exception in {func.__name__}: {e}")
                raise e

        raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and optional jitter"""
        delay = min(self.base_delay * (self.backoff_factor**attempt), self.max_delay)

        if self.jitter:
            import random

            delay *= 0.5 + random.random() * 0.5  # Add 0-50% jitter

        return delay


class ErrorRecoveryOrchestrator:
    """Central orchestrator for error recovery patterns"""

    def __init__(self):
        self.classifier = ErrorClassifier()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.recovery_strategies: Dict[
            tuple[ErrorCategory, ErrorSeverity], List[RecoveryStrategy]
        ] = self._build_recovery_matrix()
        self.error_history: List[ErrorContext] = []
        self.recovery_handlers: Dict[RecoveryStrategy, Callable] = {}
        self.fallback_cache: Dict[str, Any] = {}

        # Statistics
        self.stats = {
            "total_errors": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "recovery_strategies_used": {},
            "error_categories": {},
            "error_severities": {},
        }

        # Register default recovery handlers
        self._register_default_handlers()

    def register_circuit_breaker(self, name: str, **kwargs) -> CircuitBreaker:
        """Register a new circuit breaker"""
        circuit_breaker = CircuitBreaker(name, **kwargs)
        self.circuit_breakers[name] = circuit_breaker
        app_logger.info(f"Registered circuit breaker: {name}")
        return circuit_breaker

    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get existing circuit breaker"""
        return self.circuit_breakers.get(name)

    async def handle_error(
        self,
        error: Exception,
        operation_name: str,
        component: str,
        context: Dict[str, Any] = None,
        user_id: Optional[str] = None,
        unit_id: Optional[str] = None,
    ) -> RecoveryResult:
        """Main error handling entry point"""

        # Generate unique error ID
        error_id = f"err_{int(time.time() * 1000)}_" f"{hash(str(error)) % 10000:04d}"

        # Classify error
        severity, category = self.classifier.classify_error(error, context)

        # Create error context
        error_context = ErrorContext(
            error=error,
            error_id=error_id,
            operation_name=operation_name,
            component=component,
            severity=severity,
            category=category,
            user_id=user_id,
            unit_id=unit_id,
            metadata=context or {},
        )

        # Update statistics
        self._update_error_stats(error_context)

        # Store in history
        self._store_error_history(error_context)

        # Get recovery strategies for this error type
        strategies = self.recovery_strategies.get((category, severity), [RecoveryStrategy.ESCALATE])

        # Attempt recovery
        recovery_result = await self._attempt_recovery(error_context, strategies)

        # Update recovery statistics
        self._update_recovery_stats(recovery_result)

        # Log result
        self._log_recovery_result(error_context, recovery_result)

        return recovery_result

    async def _attempt_recovery(
        self, error_context: ErrorContext, strategies: List[RecoveryStrategy]
    ) -> RecoveryResult:
        """Attempt recovery using available strategies"""

        for strategy in strategies:
            try:
                start_time = time.time()

                # Get recovery handler
                handler = self.recovery_handlers.get(strategy)
                if not handler:
                    app_logger.warning(f"No handler for recovery strategy: {strategy}")
                    continue

                # Attempt recovery
                result = await handler(error_context)
                recovery_time = time.time() - start_time

                if result.success:
                    return RecoveryResult(
                        success=True,
                        strategy_used=strategy,
                        result_data=result.result_data,
                        recovery_time=recovery_time,
                        metadata=result.metadata,
                    )
                else:
                    app_logger.warning(f"Recovery strategy {strategy} failed: {result.error}")

            except Exception as e:
                app_logger.error(f"Recovery strategy {strategy} raised exception: {e}")
                continue

        # All strategies failed
        return RecoveryResult(
            success=False,
            strategy_used=RecoveryStrategy.ESCALATE,
            error=error_context.error,
            recovery_time=0.0,
            metadata={"reason": "All recovery strategies failed"},
        )

    def _build_recovery_matrix(
        self,
    ) -> Dict[tuple[ErrorCategory, ErrorSeverity], List[RecoveryStrategy]]:
        """Build recovery strategy matrix based on error type and severity"""
        return {
            # Network errors
            (ErrorCategory.NETWORK, ErrorSeverity.LOW): [
                RecoveryStrategy.RETRY,
                RecoveryStrategy.CACHE,
            ],
            (ErrorCategory.NETWORK, ErrorSeverity.MEDIUM): [
                RecoveryStrategy.RETRY,
                RecoveryStrategy.CIRCUIT_BREAKER,
                RecoveryStrategy.CACHE,
            ],
            (ErrorCategory.NETWORK, ErrorSeverity.HIGH): [
                RecoveryStrategy.CIRCUIT_BREAKER,
                RecoveryStrategy.FALLBACK,
                RecoveryStrategy.CACHE,
            ],
            (ErrorCategory.NETWORK, ErrorSeverity.CRITICAL): [
                RecoveryStrategy.FALLBACK,
                RecoveryStrategy.DEGRADED,
                RecoveryStrategy.ESCALATE,
            ],
            # Service errors
            (ErrorCategory.SERVICE, ErrorSeverity.LOW): [
                RecoveryStrategy.RETRY,
                RecoveryStrategy.CACHE,
            ],
            (ErrorCategory.SERVICE, ErrorSeverity.MEDIUM): [
                RecoveryStrategy.CIRCUIT_BREAKER,
                RecoveryStrategy.FALLBACK,
                RecoveryStrategy.CACHE,
            ],
            (ErrorCategory.SERVICE, ErrorSeverity.HIGH): [
                RecoveryStrategy.FALLBACK,
                RecoveryStrategy.DEGRADED,
                RecoveryStrategy.ESCALATE,
            ],
            (ErrorCategory.SERVICE, ErrorSeverity.CRITICAL): [
                RecoveryStrategy.DEGRADED,
                RecoveryStrategy.ESCALATE,
                RecoveryStrategy.ABORT,
            ],
            # Timeout errors
            (ErrorCategory.TIMEOUT, ErrorSeverity.LOW): [RecoveryStrategy.RETRY],
            (ErrorCategory.TIMEOUT, ErrorSeverity.MEDIUM): [
                RecoveryStrategy.RETRY,
                RecoveryStrategy.CACHE,
            ],
            (ErrorCategory.TIMEOUT, ErrorSeverity.HIGH): [
                RecoveryStrategy.FALLBACK,
                RecoveryStrategy.CACHE,
            ],
            (ErrorCategory.TIMEOUT, ErrorSeverity.CRITICAL): [
                RecoveryStrategy.FALLBACK,
                RecoveryStrategy.ABORT,
            ],
            # Rate limit errors
            (ErrorCategory.RATE_LIMIT, ErrorSeverity.LOW): [
                RecoveryStrategy.QUEUE,
                RecoveryStrategy.CACHE,
            ],
            (ErrorCategory.RATE_LIMIT, ErrorSeverity.MEDIUM): [
                RecoveryStrategy.QUEUE,
                RecoveryStrategy.FALLBACK,
                RecoveryStrategy.CACHE,
            ],
            (ErrorCategory.RATE_LIMIT, ErrorSeverity.HIGH): [
                RecoveryStrategy.FALLBACK,
                RecoveryStrategy.DEGRADED,
            ],
            (ErrorCategory.RATE_LIMIT, ErrorSeverity.CRITICAL): [
                RecoveryStrategy.DEGRADED,
                RecoveryStrategy.ABORT,
            ],
            # Validation errors
            (ErrorCategory.VALIDATION, ErrorSeverity.LOW): [RecoveryStrategy.FALLBACK],
            (ErrorCategory.VALIDATION, ErrorSeverity.MEDIUM): [
                RecoveryStrategy.FALLBACK,
                RecoveryStrategy.ESCALATE,
            ],
            (ErrorCategory.VALIDATION, ErrorSeverity.HIGH): [
                RecoveryStrategy.ESCALATE,
                RecoveryStrategy.ABORT,
            ],
            (ErrorCategory.VALIDATION, ErrorSeverity.CRITICAL): [RecoveryStrategy.ABORT],
            # Authentication errors
            (ErrorCategory.AUTHENTICATION, ErrorSeverity.LOW): [RecoveryStrategy.RETRY],
            (ErrorCategory.AUTHENTICATION, ErrorSeverity.MEDIUM): [RecoveryStrategy.ESCALATE],
            (ErrorCategory.AUTHENTICATION, ErrorSeverity.HIGH): [
                RecoveryStrategy.ESCALATE,
                RecoveryStrategy.ABORT,
            ],
            (ErrorCategory.AUTHENTICATION, ErrorSeverity.CRITICAL): [RecoveryStrategy.ABORT],
            # Resource errors
            (ErrorCategory.RESOURCE, ErrorSeverity.LOW): [
                RecoveryStrategy.RETRY,
                RecoveryStrategy.CACHE,
            ],
            (ErrorCategory.RESOURCE, ErrorSeverity.MEDIUM): [
                RecoveryStrategy.DEGRADED,
                RecoveryStrategy.CACHE,
            ],
            (ErrorCategory.RESOURCE, ErrorSeverity.HIGH): [
                RecoveryStrategy.DEGRADED,
                RecoveryStrategy.ESCALATE,
            ],
            (ErrorCategory.RESOURCE, ErrorSeverity.CRITICAL): [
                RecoveryStrategy.ESCALATE,
                RecoveryStrategy.ABORT,
            ],
            # Data errors
            (ErrorCategory.DATA, ErrorSeverity.LOW): [
                RecoveryStrategy.RETRY,
                RecoveryStrategy.FALLBACK,
            ],
            (ErrorCategory.DATA, ErrorSeverity.MEDIUM): [
                RecoveryStrategy.FALLBACK,
                RecoveryStrategy.CACHE,
            ],
            (ErrorCategory.DATA, ErrorSeverity.HIGH): [
                RecoveryStrategy.ESCALATE,
                RecoveryStrategy.FALLBACK,
            ],
            (ErrorCategory.DATA, ErrorSeverity.CRITICAL): [
                RecoveryStrategy.ESCALATE,
                RecoveryStrategy.ABORT,
            ],
            # Configuration errors
            (ErrorCategory.CONFIGURATION, ErrorSeverity.LOW): [RecoveryStrategy.FALLBACK],
            (ErrorCategory.CONFIGURATION, ErrorSeverity.MEDIUM): [
                RecoveryStrategy.FALLBACK,
                RecoveryStrategy.ESCALATE,
            ],
            (ErrorCategory.CONFIGURATION, ErrorSeverity.HIGH): [
                RecoveryStrategy.ESCALATE,
                RecoveryStrategy.ABORT,
            ],
            (ErrorCategory.CONFIGURATION, ErrorSeverity.CRITICAL): [RecoveryStrategy.ABORT],
            # Unknown errors
            (ErrorCategory.UNKNOWN, ErrorSeverity.LOW): [
                RecoveryStrategy.RETRY,
                RecoveryStrategy.FALLBACK,
            ],
            (ErrorCategory.UNKNOWN, ErrorSeverity.MEDIUM): [
                RecoveryStrategy.FALLBACK,
                RecoveryStrategy.ESCALATE,
            ],
            (ErrorCategory.UNKNOWN, ErrorSeverity.HIGH): [RecoveryStrategy.ESCALATE],
            (ErrorCategory.UNKNOWN, ErrorSeverity.CRITICAL): [
                RecoveryStrategy.ESCALATE,
                RecoveryStrategy.ABORT,
            ],
        }

    def _register_default_handlers(self):
        """Register default recovery strategy handlers"""

        async def retry_handler(error_context: ErrorContext) -> RecoveryResult:
            """Handle retry recovery strategy"""
            retry_handler_impl = RetryHandler(max_retries=3)

            try:
                # For demo purposes, we'll just return a successful
                # retry result. In real implementation, this would retry
                # the original operation
                return RecoveryResult(
                    success=True,
                    strategy_used=RecoveryStrategy.RETRY,
                    result_data={"retried": True},
                    metadata={"retry_attempts": 3},
                )
            except Exception as e:
                return RecoveryResult(success=False, strategy_used=RecoveryStrategy.RETRY, error=e)

        async def circuit_breaker_handler(error_context: ErrorContext) -> RecoveryResult:
            """Handle circuit breaker recovery strategy"""
            component_name = error_context.component
            circuit_breaker = self.get_circuit_breaker(component_name)

            if not circuit_breaker:
                circuit_breaker = self.register_circuit_breaker(component_name)

            try:
                # Record the failure in circuit breaker
                circuit_breaker._record_failure()

                return RecoveryResult(
                    success=circuit_breaker.state != "OPEN",
                    strategy_used=RecoveryStrategy.CIRCUIT_BREAKER,
                    result_data={"circuit_breaker_state": circuit_breaker.state},
                    metadata=circuit_breaker.get_stats(),
                )
            except Exception as e:
                return RecoveryResult(
                    success=False, strategy_used=RecoveryStrategy.CIRCUIT_BREAKER, error=e
                )

        async def fallback_handler(error_context: ErrorContext) -> RecoveryResult:
            """Handle fallback recovery strategy"""
            try:
                # Generate fallback response based on operation
                fallback_data = self._generate_fallback_response(error_context)

                return RecoveryResult(
                    success=True,
                    strategy_used=RecoveryStrategy.FALLBACK,
                    result_data=fallback_data,
                    metadata={"fallback_type": "generated"},
                )
            except Exception as e:
                return RecoveryResult(
                    success=False, strategy_used=RecoveryStrategy.FALLBACK, error=e
                )

        async def cache_handler(error_context: ErrorContext) -> RecoveryResult:
            """Handle cache recovery strategy"""
            try:
                cache_key = f"{error_context.component}:" f"{error_context.operation_name}:"
                cache_key += f"{hash(str(error_context.metadata))}"
                cached_data = self.fallback_cache.get(cache_key)

                if cached_data:
                    return RecoveryResult(
                        success=True,
                        strategy_used=RecoveryStrategy.CACHE,
                        result_data=cached_data,
                        metadata={"cache_hit": True},
                    )
                else:
                    return RecoveryResult(
                        success=False,
                        strategy_used=RecoveryStrategy.CACHE,
                        metadata={"cache_hit": False},
                    )
            except Exception as e:
                return RecoveryResult(success=False, strategy_used=RecoveryStrategy.CACHE, error=e)

        async def degraded_handler(error_context: ErrorContext) -> RecoveryResult:
            """Handle degraded mode recovery strategy"""
            try:
                # Provide minimal functionality
                degraded_data = {
                    "message": ("Sistema em modo degradado. Funcionalidade limitada."),
                    "degraded_mode": True,
                    "available_functions": ["basic_response", "error_reporting"],
                }

                return RecoveryResult(
                    success=True,
                    strategy_used=RecoveryStrategy.DEGRADED,
                    result_data=degraded_data,
                    metadata={"degraded_mode": True},
                )
            except Exception as e:
                return RecoveryResult(
                    success=False, strategy_used=RecoveryStrategy.DEGRADED, error=e
                )

        async def escalate_handler(error_context: ErrorContext) -> RecoveryResult:
            """Handle escalation recovery strategy"""
            try:
                # Log for human intervention
                app_logger.critical(
                    f"Error escalated for human intervention: " f"{error_context.error_id}",
                    extra={
                        "error_id": error_context.error_id,
                        "severity": error_context.severity.value,
                        "category": error_context.category.value,
                        "component": error_context.component,
                        "user_id": error_context.user_id,
                    },
                )

                return RecoveryResult(
                    success=True,
                    strategy_used=RecoveryStrategy.ESCALATE,
                    result_data={"escalated": True, "error_id": error_context.error_id},
                    metadata={"human_intervention_required": True},
                )
            except Exception as e:
                return RecoveryResult(
                    success=False, strategy_used=RecoveryStrategy.ESCALATE, error=e
                )

        # Register handlers
        self.recovery_handlers = {
            RecoveryStrategy.RETRY: retry_handler,
            RecoveryStrategy.CIRCUIT_BREAKER: circuit_breaker_handler,
            RecoveryStrategy.FALLBACK: fallback_handler,
            RecoveryStrategy.CACHE: cache_handler,
            RecoveryStrategy.DEGRADED: degraded_handler,
            RecoveryStrategy.ESCALATE: escalate_handler,
        }

    def _generate_fallback_response(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Generate appropriate fallback response based on operation"""
        operation = error_context.operation_name.lower()

        if "conversation" in operation or "message" in operation:
            return {
                "response_text": (
                    "Desculpe, estou enfrentando dificuldades técnicas no "
                    "momento. Tente novamente em alguns instantes ou entre "
                    "em contato diretamente com nossa unidade."
                ),
                "response_type": "text",
                "fallback": True,
                "error_id": error_context.error_id,
            }
        elif "intent" in operation:
            return {
                "intent": "general",
                "confidence": 0.5,
                "fallback": True,
                "error_id": error_context.error_id,
            }
        elif "context" in operation:
            return {
                "conversation_history": [],
                "knowledge_base": [],
                "fallback": True,
                "error_id": error_context.error_id,
            }
        else:
            return {
                "fallback": True,
                "error_id": error_context.error_id,
                "message": "Operação temporariamente indisponível",
            }

    def _update_error_stats(self, error_context: ErrorContext):
        """Update error statistics"""
        self.stats["total_errors"] += 1

        category_key = error_context.category.value
        if category_key not in self.stats["error_categories"]:
            self.stats["error_categories"][category_key] = 0
        self.stats["error_categories"][category_key] += 1

        severity_key = error_context.severity.value
        if severity_key not in self.stats["error_severities"]:
            self.stats["error_severities"][severity_key] = 0
        self.stats["error_severities"][severity_key] += 1

    def _update_recovery_stats(self, recovery_result: RecoveryResult):
        """Update recovery statistics"""
        if recovery_result.success:
            self.stats["successful_recoveries"] += 1
        else:
            self.stats["failed_recoveries"] += 1

        strategy_key = recovery_result.strategy_used.value
        if strategy_key not in self.stats["recovery_strategies_used"]:
            self.stats["recovery_strategies_used"][strategy_key] = 0
        self.stats["recovery_strategies_used"][strategy_key] += 1

    def _store_error_history(self, error_context: ErrorContext):
        """Store error in history with size limit"""
        self.error_history.append(error_context)

        # Keep history size manageable
        if len(self.error_history) > 1000:
            self.error_history = self.error_history[-500:]

    def _log_recovery_result(self, error_context: ErrorContext, recovery_result: RecoveryResult):
        """Log recovery result"""
        if recovery_result.success:
            app_logger.info(
                f"Error recovery successful: {error_context.error_id}",
                extra={
                    "error_id": error_context.error_id,
                    "strategy": recovery_result.strategy_used.value,
                    "recovery_time": recovery_result.recovery_time,
                    "component": error_context.component,
                },
            )
        else:
            app_logger.error(
                f"Error recovery failed: {error_context.error_id}",
                extra={
                    "error_id": error_context.error_id,
                    "strategy": recovery_result.strategy_used.value,
                    "error": (str(recovery_result.error) if recovery_result.error else "Unknown"),
                    "component": error_context.component,
                },
            )

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health based on error patterns"""
        total_errors = self.stats["total_errors"]
        successful_recoveries = self.stats["successful_recoveries"]

        if total_errors == 0:
            recovery_rate = 1.0
        else:
            recovery_rate = successful_recoveries / total_errors

        # Analyze recent error trends
        recent_errors = [
            error
            for error in self.error_history
            if time.time() - error.timestamp < 3600  # Last hour
        ]

        critical_errors_recent = len(
            [error for error in recent_errors if error.severity == ErrorSeverity.CRITICAL]
        )

        health_score = recovery_rate * 100
        if critical_errors_recent > 5:
            health_score = max(health_score - 20, 0)

        return {
            "health_score": health_score,
            "recovery_rate": recovery_rate,
            "total_errors": total_errors,
            "successful_recoveries": successful_recoveries,
            "failed_recoveries": self.stats["failed_recoveries"],
            "recent_errors_count": len(recent_errors),
            "critical_errors_recent": critical_errors_recent,
            "circuit_breaker_stats": {
                name: cb.get_stats() for name, cb in self.circuit_breakers.items()
            },
        }

    def get_error_analysis(self, hours: int = 24) -> Dict[str, Any]:
        """Get detailed error analysis for specified time period"""
        cutoff_time = time.time() - (hours * 3600)
        recent_errors = [error for error in self.error_history if error.timestamp > cutoff_time]

        # Analysis by category
        category_analysis = {}
        for error in recent_errors:
            category = error.category.value
            if category not in category_analysis:
                category_analysis[category] = {
                    "count": 0,
                    "severities": {},
                    "components": set(),
                    "users_affected": set(),
                }

            category_analysis[category]["count"] += 1

            severity = error.severity.value
            if severity not in category_analysis[category]["severities"]:
                category_analysis[category]["severities"][severity] = 0
            category_analysis[category]["severities"][severity] += 1

            category_analysis[category]["components"].add(error.component)
            if error.user_id:
                category_analysis[category]["users_affected"].add(error.user_id)

        # Convert sets to lists for JSON serialization
        for category_data in category_analysis.values():
            category_data["components"] = list(category_data["components"])
            category_data["users_affected"] = len(category_data["users_affected"])

        return {
            "analysis_period_hours": hours,
            "total_errors_in_period": len(recent_errors),
            "category_analysis": category_analysis,
            "top_components_by_errors": self._get_top_components_by_errors(recent_errors),
            "error_rate_trend": self._calculate_error_rate_trend(recent_errors),
        }

    def _get_top_components_by_errors(
        self, errors: List[ErrorContext], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top components by error count"""
        component_counts = {}
        for error in errors:
            component = error.component
            if component not in component_counts:
                component_counts[component] = 0
            component_counts[component] += 1

        sorted_components = sorted(component_counts.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]

        return [
            {"component": component, "error_count": count} for component, count in sorted_components
        ]

    def _calculate_error_rate_trend(self, errors: List[ErrorContext]) -> List[Dict[str, Any]]:
        """Calculate error rate trend over time"""
        if not errors:
            return []

        # Group errors by hour
        hourly_errors = {}
        for error in errors:
            hour = int(error.timestamp // 3600) * 3600  # Round to hour
            if hour not in hourly_errors:
                hourly_errors[hour] = 0
            hourly_errors[hour] += 1

        # Convert to sorted list
        trend = [
            {"timestamp": hour, "error_count": count}
            for hour, count in sorted(hourly_errors.items())
        ]

        return trend


# Global error recovery orchestrator instance
error_recovery_orchestrator = ErrorRecoveryOrchestrator()
