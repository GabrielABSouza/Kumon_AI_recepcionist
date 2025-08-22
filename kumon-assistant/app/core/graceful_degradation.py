"""
Graceful Degradation Handlers for Railway-Optimized Services

Provides fallback strategies when circuit breakers open:
- In-memory caching fallback
- Default responses
- Reduced functionality mode
"""

from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone

from .logger import app_logger
from .circuit_breaker import CircuitBreakerOpenError


class GracefulDegradationHandler:
    """Handles graceful degradation when services fail"""
    
    def __init__(self):
        self.in_memory_cache: Dict[str, Any] = {}
        self.degradation_active = False
        self.degradation_start_time: Optional[datetime] = None
        
    def activate_degradation(self, service_name: str):
        """Activate degradation mode for a service"""
        if not self.degradation_active:
            self.degradation_active = True
            self.degradation_start_time = datetime.now(timezone.utc)
            app_logger.warning(f"Graceful degradation activated for {service_name}")
    
    def deactivate_degradation(self, service_name: str):
        """Deactivate degradation mode"""
        if self.degradation_active:
            self.degradation_active = False
            duration = (datetime.now(timezone.utc) - self.degradation_start_time).total_seconds()
            app_logger.info(f"Graceful degradation deactivated for {service_name} after {duration:.1f}s")
            self.degradation_start_time = None


# Service-specific handlers
class MemoryServiceDegradation(GracefulDegradationHandler):
    """Fallback for conversation memory service"""
    
    def __init__(self):
        super().__init__()
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
    async def create_session_fallback(self, phone_number: str, **kwargs) -> Dict[str, Any]:
        """Create session in memory when database is down"""
        self.activate_degradation("memory_service")
        
        session_id = f"fallback_{phone_number}_{datetime.now(timezone.utc).timestamp()}"
        session = {
            "session_id": session_id,
            "phone_number": phone_number,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "messages": [],
            "is_fallback": True
        }
        
        self.sessions[session_id] = session
        app_logger.warning(f"Created fallback session {session_id} in memory")
        
        return session
    
    async def get_session_fallback(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session from memory fallback"""
        return self.sessions.get(session_id)
    
    async def add_message_fallback(self, session_id: str, message: Dict[str, Any]) -> bool:
        """Add message to in-memory session"""
        if session_id in self.sessions:
            self.sessions[session_id]["messages"].append(message)
            return True
        return False


class CacheServiceDegradation(GracefulDegradationHandler):
    """Fallback for cache service"""
    
    def __init__(self):
        super().__init__()
        self.local_cache: Dict[str, Tuple[Any, float]] = {}
        
    async def get_fallback(self, key: str) -> Optional[Any]:
        """Get from local cache when Redis is down"""
        self.activate_degradation("cache_service")
        
        if key in self.local_cache:
            value, expiry = self.local_cache[key]
            if datetime.now(timezone.utc).timestamp() < expiry:
                return value
            else:
                del self.local_cache[key]
        
        return None
    
    async def set_fallback(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set in local cache when Redis is down"""
        self.activate_degradation("cache_service")
        
        expiry = datetime.now(timezone.utc).timestamp() + ttl
        self.local_cache[key] = (value, expiry)
        
        # Limit cache size to prevent memory issues
        if len(self.local_cache) > 1000:
            # Remove oldest entries
            sorted_keys = sorted(self.local_cache.keys(), 
                               key=lambda k: self.local_cache[k][1])
            for k in sorted_keys[:200]:  # Remove 20% oldest
                del self.local_cache[k]
        
        return True


class BusinessRulesServiceDegradation(GracefulDegradationHandler):
    """Fallback for business rules engine"""
    
    def __init__(self):
        super().__init__()
        
    async def validate_fallback(self, rule_type: str, **kwargs) -> Dict[str, Any]:
        """Provide default validation when rules engine is down"""
        self.activate_degradation("business_rules")
        
        # Conservative defaults - prefer safety
        default_responses = {
            "pricing": {
                "result": "APPROVED",
                "message": "Matemática: R$ 375,00/mês + Matrícula: R$ 100,00",
                "is_fallback": True
            },
            "hours": {
                "result": "WARNING",
                "message": "Horário de atendimento: Segunda a Sexta, 8h às 18h",
                "is_fallback": True
            },
            "handoff": {
                "result": "WARNING",
                "message": "Vou verificar com nossa equipe. Por favor, aguarde.",
                "is_fallback": True
            }
        }
        
        return default_responses.get(rule_type, {
            "result": "WARNING",
            "message": "Sistema em manutenção. Por favor, tente novamente.",
            "is_fallback": True
        })


# Global degradation handlers
memory_degradation = MemoryServiceDegradation()
cache_degradation = CacheServiceDegradation()
rules_degradation = BusinessRulesServiceDegradation()


# Decorator for automatic fallback
def with_fallback(fallback_handler: Callable):
    """Decorator to automatically use fallback when circuit breaker is open"""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except CircuitBreakerOpenError:
                app_logger.warning(f"Circuit breaker open for {func.__name__}, using fallback")
                return await fallback_handler(*args, **kwargs)
        
        return wrapper
    return decorator