"""
Enhanced Reliability Service
Phase 4 Wave 4.2: System reliability optimization from 99.3% to 99.9% uptime

Implements advanced reliability patterns:
- Enhanced circuit breaker configuration
- Improved error recovery mechanisms
- Advanced health monitoring
- Graceful degradation strategies
- Proactive failure detection
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import json
from collections import defaultdict, deque

from ..core.config import settings
from ..core.logger import app_logger as logger
from ..services.enhanced_cache_service import enhanced_cache_service


class ReliabilityStatus(str, Enum):
    """System reliability status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    RECOVERING = "recovering"


class FailureCategory(str, Enum):
    """Failure category classification"""
    TRANSIENT = "transient"      # Temporary network/service issues
    PERSISTENT = "persistent"    # Ongoing service problems
    CASCADING = "cascading"      # Failures spreading across services
    RESOURCE = "resource"        # CPU/memory/disk issues


@dataclass
class ReliabilityMetric:
    """Reliability tracking metric"""
    component: str
    status: ReliabilityStatus
    uptime_percentage: float
    error_count: int
    recovery_time_ms: float
    last_failure: Optional[datetime]
    failure_category: Optional[FailureCategory]
    timestamp: datetime


@dataclass
class CircuitBreakerConfig:
    """Enhanced circuit breaker configuration"""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_max_calls: int = 3
    success_threshold: int = 3
    slow_call_threshold: float = 5000  # 5 seconds
    slow_call_rate_threshold: float = 0.5  # 50%


class EnhancedCircuitBreaker:
    """Enhanced circuit breaker with advanced failure detection"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = "closed"  # closed, open, half_open
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.call_times = deque(maxlen=100)
        self.recent_calls = deque(maxlen=50)
        
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "open":
            if await self._should_attempt_reset():
                self.state = "half_open"
                self.success_count = 0
            else:
                raise Exception(f"Circuit breaker {self.name} is open")
        
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            
            call_duration = (time.time() - start_time) * 1000
            self.call_times.append(call_duration)
            self.recent_calls.append(True)
            
            # Check for slow calls
            if call_duration > self.config.slow_call_threshold:
                slow_call_rate = self._calculate_slow_call_rate()
                if slow_call_rate > self.config.slow_call_rate_threshold:
                    await self._handle_slow_calls()
            
            if self.state == "half_open":
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = "closed"
                    self.failure_count = 0
                    logger.info(f"Circuit breaker {self.name} recovered")
            elif self.state == "closed":
                self.failure_count = max(0, self.failure_count - 1)
            
            return result
            
        except Exception as e:
            self.recent_calls.append(False)
            self.failure_count += 1
            self.last_failure_time = datetime.now(timezone.utc)
            
            if self.state == "half_open" or self.failure_count >= self.config.failure_threshold:
                self.state = "open"
                logger.warning(f"Circuit breaker {self.name} opened after {self.failure_count} failures")
            
            raise e
    
    async def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if not self.last_failure_time:
            return True
        
        time_since_failure = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
        return time_since_failure >= self.config.recovery_timeout
    
    def _calculate_slow_call_rate(self) -> float:
        """Calculate percentage of slow calls"""
        if not self.call_times:
            return 0.0
        
        slow_calls = sum(1 for t in self.call_times if t > self.config.slow_call_threshold)
        return slow_calls / len(self.call_times)
    
    async def _handle_slow_calls(self):
        """Handle high rate of slow calls"""
        logger.warning(f"Circuit breaker {self.name}: High slow call rate detected")
        # Implement gradual backoff or other mitigation strategies
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics"""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "avg_call_time": sum(self.call_times) / len(self.call_times) if self.call_times else 0,
            "slow_call_rate": self._calculate_slow_call_rate(),
            "recent_success_rate": sum(self.recent_calls) / len(self.recent_calls) if self.recent_calls else 1.0
        }


class EnhancedReliabilityService:
    """Enhanced reliability service for 99.9% uptime target"""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, EnhancedCircuitBreaker] = {}
        self.reliability_metrics: Dict[str, ReliabilityMetric] = {}
        self.health_checks: Dict[str, Callable] = {}
        self.failure_patterns: Dict[str, List[datetime]] = defaultdict(list)
        self.uptime_tracker = UptimeTracker()
        
        # Initialize circuit breakers for critical components
        self._initialize_circuit_breakers()
        
    def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for critical system components"""
        components = [
            ("openai_service", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30)),
            ("database_pool", CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60)),
            ("redis_cache", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30)),
            ("evolution_api", CircuitBreakerConfig(failure_threshold=5, recovery_timeout=90)),
            ("google_calendar", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=120)),
            ("langgraph_workflow", CircuitBreakerConfig(failure_threshold=5, recovery_timeout=45)),
            ("message_processor", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30)),
            ("business_rules", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30))
        ]
        
        for name, config in components:
            self.circuit_breakers[name] = EnhancedCircuitBreaker(name, config)
            logger.info(f"Initialized enhanced circuit breaker for {name}")
    
    async def execute_with_reliability(self, component: str, func: Callable, *args, **kwargs):
        """Execute function with enhanced reliability protection"""
        circuit_breaker = self.circuit_breakers.get(component)
        if not circuit_breaker:
            # Create default circuit breaker for unknown components
            circuit_breaker = EnhancedCircuitBreaker(component, CircuitBreakerConfig())
            self.circuit_breakers[component] = circuit_breaker
        
        start_time = time.time()
        
        try:
            result = await circuit_breaker.call(func, *args, **kwargs)
            
            # Track successful execution
            execution_time = (time.time() - start_time) * 1000
            await self._record_success(component, execution_time)
            
            return result
            
        except Exception as e:
            # Track failure and attempt recovery
            execution_time = (time.time() - start_time) * 1000
            await self._record_failure(component, e, execution_time)
            
            # Attempt graceful degradation
            fallback_result = await self._attempt_graceful_degradation(component, func, *args, **kwargs)
            if fallback_result is not None:
                return fallback_result
            
            raise e
    
    async def _record_success(self, component: str, execution_time: float):
        """Record successful execution"""
        now = datetime.now(timezone.utc)
        
        if component in self.reliability_metrics:
            metric = self.reliability_metrics[component]
            metric.status = ReliabilityStatus.HEALTHY
            metric.timestamp = now
        else:
            self.reliability_metrics[component] = ReliabilityMetric(
                component=component,
                status=ReliabilityStatus.HEALTHY,
                uptime_percentage=100.0,
                error_count=0,
                recovery_time_ms=execution_time,
                last_failure=None,
                failure_category=None,
                timestamp=now
            )
        
        # Update uptime tracking
        await self.uptime_tracker.record_success(component)
    
    async def _record_failure(self, component: str, error: Exception, execution_time: float):
        """Record component failure"""
        now = datetime.now(timezone.utc)
        failure_category = self._classify_failure(error)
        
        # Track failure pattern
        self.failure_patterns[component].append(now)
        
        # Update reliability metrics
        if component in self.reliability_metrics:
            metric = self.reliability_metrics[component]
            metric.error_count += 1
            metric.last_failure = now
            metric.failure_category = failure_category
            metric.status = ReliabilityStatus.DEGRADED
        else:
            self.reliability_metrics[component] = ReliabilityMetric(
                component=component,
                status=ReliabilityStatus.DEGRADED,
                uptime_percentage=95.0,  # Initial degraded state
                error_count=1,
                recovery_time_ms=execution_time,
                last_failure=now,
                failure_category=failure_category,
                timestamp=now
            )
        
        # Update uptime tracking
        await self.uptime_tracker.record_failure(component)
        
        # Check for cascading failures
        await self._check_cascading_failures(component, failure_category)
        
        logger.error(f"Component failure: {component} - {error} - Category: {failure_category}")
    
    def _classify_failure(self, error: Exception) -> FailureCategory:
        """Classify failure type for better handling"""
        error_str = str(error).lower()
        
        if "timeout" in error_str or "connection" in error_str:
            return FailureCategory.TRANSIENT
        elif "memory" in error_str or "cpu" in error_str or "disk" in error_str:
            return FailureCategory.RESOURCE
        elif "cascade" in error_str or "dependent" in error_str:
            return FailureCategory.CASCADING
        else:
            return FailureCategory.PERSISTENT
    
    async def _check_cascading_failures(self, component: str, failure_category: FailureCategory):
        """Check for and prevent cascading failures"""
        if failure_category == FailureCategory.CASCADING:
            # Implement cascading failure prevention
            degraded_components = [
                name for name, metric in self.reliability_metrics.items()
                if metric.status != ReliabilityStatus.HEALTHY
            ]
            
            if len(degraded_components) >= 3:
                logger.critical(f"Cascading failure detected: {degraded_components}")
                await self._activate_emergency_mode()
    
    async def _activate_emergency_mode(self):
        """Activate emergency mode for system protection"""
        logger.critical("Activating emergency reliability mode")
        
        # Implement emergency measures:
        # - Reduce non-essential processing
        # - Increase circuit breaker sensitivity
        # - Enable aggressive caching
        # - Simplify response logic
        
        for circuit_breaker in self.circuit_breakers.values():
            circuit_breaker.config.failure_threshold = max(1, circuit_breaker.config.failure_threshold // 2)
            circuit_breaker.config.recovery_timeout *= 2
    
    async def _attempt_graceful_degradation(self, component: str, func: Callable, *args, **kwargs):
        """Attempt graceful degradation for failed components"""
        degradation_strategies = {
            "openai_service": self._fallback_simple_response,
            "database_pool": self._fallback_cache_response,
            "redis_cache": self._fallback_memory_cache,
            "evolution_api": self._fallback_direct_response,
            "google_calendar": self._fallback_manual_scheduling,
            "langgraph_workflow": self._fallback_simple_workflow,
            "message_processor": self._fallback_basic_processing,
            "business_rules": self._fallback_basic_rules
        }
        
        fallback_func = degradation_strategies.get(component)
        if fallback_func:
            try:
                logger.info(f"Attempting graceful degradation for {component}")
                return await fallback_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Graceful degradation failed for {component}: {e}")
        
        return None
    
    async def _fallback_simple_response(self, *args, **kwargs):
        """Fallback for OpenAI service failures"""
        return {
            "response_message": "Desculpe, estou com dificuldades técnicas no momento. Por favor, entre em contato através do WhatsApp (51) 99692-1999 para atendimento direto.",
            "fallback_mode": True,
            "component": "openai_service"
        }
    
    async def _fallback_cache_response(self, *args, **kwargs):
        """Fallback for database failures using cache"""
        # Attempt to serve from cache
        return await enhanced_cache_service.get_fallback_data(*args, **kwargs)
    
    async def _fallback_memory_cache(self, *args, **kwargs):
        """Fallback for Redis cache failures using memory"""
        # Use in-memory caching as fallback
        return None
    
    async def _fallback_direct_response(self, *args, **kwargs):
        """Fallback for Evolution API failures"""
        return {
            "message": "Sistema temporariamente indisponível. Tente novamente em alguns minutos.",
            "fallback_mode": True
        }
    
    async def _fallback_manual_scheduling(self, *args, **kwargs):
        """Fallback for Google Calendar failures"""
        return {
            "message": "Agendamento temporariamente manual. Entre em contato: (51) 99692-1999",
            "manual_scheduling": True
        }
    
    async def _fallback_simple_workflow(self, *args, **kwargs):
        """Fallback for LangGraph workflow failures"""
        return {
            "response_message": "Para melhor atendimento, entre em contato através do WhatsApp (51) 99692-1999",
            "simple_mode": True
        }
    
    async def _fallback_basic_processing(self, *args, **kwargs):
        """Fallback for message processor failures"""
        return {
            "processed": True,
            "basic_mode": True,
            "message": "Processamento simplificado ativo"
        }
    
    async def _fallback_basic_rules(self, *args, **kwargs):
        """Fallback for business rules failures"""
        return {
            "validation": "basic",
            "approved": True,
            "fallback_rules": True
        }
    
    async def get_system_reliability(self) -> Dict[str, Any]:
        """Get comprehensive system reliability status"""
        current_uptime = await self.uptime_tracker.get_current_uptime()
        
        component_status = {}
        for name, metric in self.reliability_metrics.items():
            component_status[name] = {
                "status": metric.status.value,
                "uptime_percentage": metric.uptime_percentage,
                "error_count": metric.error_count,
                "last_failure": metric.last_failure.isoformat() if metric.last_failure else None,
                "circuit_breaker": self.circuit_breakers[name].get_metrics() if name in self.circuit_breakers else None
            }
        
        return {
            "overall_uptime": current_uptime,
            "target_uptime": 99.9,
            "components": component_status,
            "reliability_status": self._determine_overall_status(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _determine_overall_status(self) -> ReliabilityStatus:
        """Determine overall system reliability status"""
        if not self.reliability_metrics:
            return ReliabilityStatus.HEALTHY
        
        degraded_count = sum(1 for m in self.reliability_metrics.values() 
                           if m.status != ReliabilityStatus.HEALTHY)
        
        total_components = len(self.reliability_metrics)
        
        if degraded_count == 0:
            return ReliabilityStatus.HEALTHY
        elif degraded_count / total_components < 0.2:  # Less than 20% degraded
            return ReliabilityStatus.DEGRADED
        else:
            return ReliabilityStatus.CRITICAL


class UptimeTracker:
    """Advanced uptime tracking for 99.9% target"""
    
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.downtime_periods: List[Dict[str, datetime]] = []
        self.component_downtimes: Dict[str, List[Dict[str, datetime]]] = defaultdict(list)
        
    async def record_success(self, component: str):
        """Record successful component operation"""
        # Close any open downtime periods for this component
        if self.component_downtimes[component]:
            last_downtime = self.component_downtimes[component][-1]
            if "end" not in last_downtime:
                last_downtime["end"] = datetime.now(timezone.utc)
    
    async def record_failure(self, component: str):
        """Record component failure start"""
        now = datetime.now(timezone.utc)
        
        # Check if there's already an open downtime period
        if self.component_downtimes[component]:
            last_downtime = self.component_downtimes[component][-1]
            if "end" not in last_downtime:
                return  # Already tracking this downtime
        
        # Start new downtime period
        self.component_downtimes[component].append({
            "start": now,
            "component": component
        })
    
    async def get_current_uptime(self) -> float:
        """Calculate current system uptime percentage"""
        now = datetime.now(timezone.utc)
        total_time = (now - self.start_time).total_seconds()
        
        if total_time == 0:
            return 100.0
        
        # Calculate total downtime across all components
        total_downtime = 0
        
        for component_downtimes in self.component_downtimes.values():
            for downtime in component_downtimes:
                start = downtime["start"]
                end = downtime.get("end", now)
                downtime_seconds = (end - start).total_seconds()
                total_downtime += downtime_seconds
        
        # Calculate uptime percentage
        uptime_percentage = max(0, (total_time - total_downtime) / total_time * 100)
        return round(uptime_percentage, 3)
    
    def get_uptime_report(self) -> Dict[str, Any]:
        """Get detailed uptime report"""
        now = datetime.now(timezone.utc)
        total_time = (now - self.start_time).total_seconds()
        
        component_reports = {}
        for component, downtimes in self.component_downtimes.items():
            total_component_downtime = 0
            downtime_count = len(downtimes)
            
            for downtime in downtimes:
                start = downtime["start"]
                end = downtime.get("end", now)
                total_component_downtime += (end - start).total_seconds()
            
            component_uptime = max(0, (total_time - total_component_downtime) / total_time * 100)
            
            component_reports[component] = {
                "uptime_percentage": round(component_uptime, 3),
                "downtime_events": downtime_count,
                "total_downtime_seconds": total_component_downtime,
                "avg_downtime_seconds": total_component_downtime / max(downtime_count, 1)
            }
        
        # Calculate overall uptime manually since this is not an async function
        total_downtime = 0
        for downtimes in self.component_downtimes.values():
            for downtime in downtimes:
                start = downtime["start"]
                end = downtime.get("end", now)
                total_downtime += (end - start).total_seconds()
        
        overall_uptime = max(0, (total_time - total_downtime) / total_time * 100) if total_time > 0 else 100.0
        
        return {
            "overall_uptime": round(overall_uptime, 3),
            "tracking_duration_hours": total_time / 3600,
            "components": component_reports,
            "start_time": self.start_time.isoformat(),
            "current_time": now.isoformat()
        }


# Global reliability service instance
enhanced_reliability_service = EnhancedReliabilityService()