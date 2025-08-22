"""
Wave 5: Comprehensive Health Monitoring System
Railway-optimized health monitoring with circuit breaker integration
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import os

from .logger import app_logger
from .circuit_breaker import CircuitState
from .railway_config import detect_environment, DeploymentEnvironment


class HealthStatus(str, Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class ComponentHealth:
    """Individual component health tracking"""
    
    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout
        self.last_check = None
        self.status = HealthStatus.HEALTHY
        self.message = ""
        self.response_time = 0.0
        self.error_count = 0
        self.consecutive_failures = 0
        self.last_error = None
        
    def update_health(self, status: HealthStatus, message: str, response_time: float = 0.0, error: Exception = None):
        """Update component health status"""
        self.last_check = datetime.now(timezone.utc)
        self.status = status
        self.message = message
        self.response_time = response_time
        
        if status != HealthStatus.HEALTHY:
            self.error_count += 1
            self.consecutive_failures += 1
            if error:
                self.last_error = str(error)
        else:
            self.consecutive_failures = 0


class HealthMonitor:
    """Comprehensive system health monitoring"""
    
    def __init__(self):
        self.components: Dict[str, ComponentHealth] = {}
        self.environment = detect_environment()
        self.monitoring_enabled = True
        self.check_interval = 30.0  # 30 seconds
        self.timeout = 10.0 if self.environment == DeploymentEnvironment.RAILWAY else 30.0
        
        # Railway optimization: faster health checks
        if self.environment == DeploymentEnvironment.RAILWAY:
            self.check_interval = 15.0  # 15 seconds on Railway
            self.timeout = 5.0
    
    def register_component(self, name: str, timeout: Optional[float] = None) -> ComponentHealth:
        """Register a component for health monitoring"""
        if timeout is None:
            timeout = self.timeout
            
        component = ComponentHealth(name, timeout)
        self.components[name] = component
        
        app_logger.info(f"Health monitor registered component: {name}")
        return component
    
    async def check_database_health(self) -> Tuple[HealthStatus, str, float]:
        """Check database connectivity and performance"""
        start_time = time.time()
        
        try:
            from ..services.conversation_memory_service import ConversationMemoryService
            
            # Create service instance for health check
            service = ConversationMemoryService()
            
            # Perform basic health check with timeout
            health_result = await asyncio.wait_for(
                service.health_check(), 
                timeout=self.timeout
            )
            
            response_time = time.time() - start_time
            
            if health_result.get("status") == "healthy":
                return HealthStatus.HEALTHY, "Database connection healthy", response_time
            else:
                return HealthStatus.DEGRADED, f"Database issues: {health_result.get('message', 'Unknown')}", response_time
                
        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            return HealthStatus.UNHEALTHY, f"Database health check timeout ({self.timeout}s)", response_time
        except Exception as e:
            response_time = time.time() - start_time
            return HealthStatus.UNHEALTHY, f"Database health check failed: {str(e)}", response_time
    
    async def check_cache_health(self) -> Tuple[HealthStatus, str, float]:
        """Check cache system health"""
        start_time = time.time()
        
        try:
            from ..services.enhanced_cache_service import EnhancedCacheService
            
            service = EnhancedCacheService()
            
            # Test cache set/get
            test_key = f"health_check_{int(time.time())}"
            test_value = "health_test"
            
            await asyncio.wait_for(
                service.set(test_key, test_value, ttl=60),
                timeout=self.timeout
            )
            
            retrieved = await asyncio.wait_for(
                service.get(test_key),
                timeout=self.timeout
            )
            
            response_time = time.time() - start_time
            
            if retrieved == test_value:
                return HealthStatus.HEALTHY, "Cache system operational", response_time
            else:
                return HealthStatus.DEGRADED, "Cache data integrity issue", response_time
                
        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            return HealthStatus.UNHEALTHY, f"Cache health check timeout ({self.timeout}s)", response_time
        except Exception as e:
            response_time = time.time() - start_time
            return HealthStatus.DEGRADED, f"Cache health check failed: {str(e)}", response_time
    
    async def check_circuit_breaker_health(self) -> Tuple[HealthStatus, str, float]:
        """Check circuit breaker status across all services"""
        start_time = time.time()
        
        try:
            # Import circuit breaker registry
            from ..core.circuit_breaker import get_circuit_breaker_registry, CircuitState
            
            circuit_registry = get_circuit_breaker_registry()
            
            if not circuit_registry:
                return HealthStatus.HEALTHY, "No circuit breakers registered", 0.0
            
            open_breakers = []
            half_open_breakers = []
            total_failures = 0
            
            for name, breaker in circuit_registry.items():
                if breaker.state == CircuitState.OPEN:
                    open_breakers.append(name)
                elif breaker.state == CircuitState.HALF_OPEN:
                    half_open_breakers.append(name)
                
                total_failures += breaker.failure_count
            
            response_time = time.time() - start_time
            
            if open_breakers:
                return (
                    HealthStatus.DEGRADED, 
                    f"Circuit breakers open: {len(open_breakers)} ({', '.join(open_breakers[:3])}{'...' if len(open_breakers) > 3 else ''})",
                    response_time
                )
            elif half_open_breakers:
                return (
                    HealthStatus.DEGRADED,
                    f"Circuit breakers half-open: {len(half_open_breakers)}",
                    response_time
                )
            else:
                return HealthStatus.HEALTHY, f"All {len(circuit_registry)} circuit breakers closed", response_time
                
        except Exception as e:
            response_time = time.time() - start_time
            return HealthStatus.UNHEALTHY, f"Circuit breaker health check failed: {str(e)}", response_time
    
    async def check_memory_usage(self) -> Tuple[HealthStatus, str, float]:
        """Check system memory usage"""
        start_time = time.time()
        
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            response_time = time.time() - start_time
            
            # Railway-specific memory thresholds
            if self.environment == DeploymentEnvironment.RAILWAY:
                # Railway free tier has 512MB RAM
                if memory_percent > 90:
                    return HealthStatus.CRITICAL, f"Memory usage critical: {memory_percent:.1f}%", response_time
                elif memory_percent > 75:
                    return HealthStatus.UNHEALTHY, f"Memory usage high: {memory_percent:.1f}%", response_time
                elif memory_percent > 60:
                    return HealthStatus.DEGRADED, f"Memory usage elevated: {memory_percent:.1f}%", response_time
            else:
                # Local/development thresholds
                if memory_percent > 95:
                    return HealthStatus.CRITICAL, f"Memory usage critical: {memory_percent:.1f}%", response_time
                elif memory_percent > 85:
                    return HealthStatus.UNHEALTHY, f"Memory usage high: {memory_percent:.1f}%", response_time
                elif memory_percent > 70:
                    return HealthStatus.DEGRADED, f"Memory usage elevated: {memory_percent:.1f}%", response_time
            
            return HealthStatus.HEALTHY, f"Memory usage normal: {memory_percent:.1f}%", response_time
            
        except ImportError:
            # psutil not available, skip memory check
            response_time = time.time() - start_time
            return HealthStatus.HEALTHY, "Memory monitoring not available (psutil not installed)", response_time
        except Exception as e:
            response_time = time.time() - start_time
            return HealthStatus.DEGRADED, f"Memory check failed: {str(e)}", response_time
    
    async def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive system health check"""
        start_time = time.time()
        
        app_logger.info("Starting comprehensive health check...")
        
        # Run all health checks in parallel
        health_checks = await asyncio.gather(
            self.check_database_health(),
            self.check_cache_health(), 
            self.check_circuit_breaker_health(),
            self.check_memory_usage(),
            return_exceptions=True
        )
        
        # Process results
        components = {
            "database": health_checks[0],
            "cache": health_checks[1], 
            "circuit_breakers": health_checks[2],
            "memory": health_checks[3]
        }
        
        # Update component health
        for name, result in components.items():
            if isinstance(result, Exception):
                if name not in self.components:
                    self.register_component(name)
                self.components[name].update_health(
                    HealthStatus.CRITICAL, 
                    f"Health check exception: {str(result)}", 
                    0.0,
                    result
                )
            else:
                status, message, response_time = result
                if name not in self.components:
                    self.register_component(name)
                self.components[name].update_health(status, message, response_time)
        
        # Calculate overall health
        overall_status = self._calculate_overall_health()
        total_time = time.time() - start_time
        
        result = {
            "overall_status": overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": self.environment.value,
            "check_duration": round(total_time, 3),
            "components": {
                name: {
                    "status": component.status.value,
                    "message": component.message,
                    "response_time": round(component.response_time, 3),
                    "last_check": component.last_check.isoformat() if component.last_check else None,
                    "error_count": component.error_count,
                    "consecutive_failures": component.consecutive_failures
                }
                for name, component in self.components.items()
            }
        }
        
        app_logger.info(
            f"Health check completed: {overall_status.value} in {total_time:.3f}s",
            extra={"health_status": overall_status.value, "check_duration": total_time}
        )
        
        return result
    
    def _calculate_overall_health(self) -> HealthStatus:
        """Calculate overall system health based on component health"""
        if not self.components:
            return HealthStatus.HEALTHY
        
        critical_count = sum(1 for c in self.components.values() if c.status == HealthStatus.CRITICAL)
        unhealthy_count = sum(1 for c in self.components.values() if c.status == HealthStatus.UNHEALTHY)
        degraded_count = sum(1 for c in self.components.values() if c.status == HealthStatus.DEGRADED)
        
        # Any critical = overall critical
        if critical_count > 0:
            return HealthStatus.CRITICAL
        
        # More than half unhealthy = overall unhealthy
        if unhealthy_count > len(self.components) / 2:
            return HealthStatus.UNHEALTHY
        
        # Any unhealthy or more than half degraded = overall degraded
        if unhealthy_count > 0 or degraded_count > len(self.components) / 2:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY
    
    async def start_monitoring(self):
        """Start continuous health monitoring"""
        if not self.monitoring_enabled:
            app_logger.warning("Health monitoring is disabled")
            return
        
        app_logger.info(f"Starting health monitoring (interval: {self.check_interval}s)")
        
        while self.monitoring_enabled:
            try:
                await self.perform_health_check()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                app_logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """Stop health monitoring"""
        self.monitoring_enabled = False
        app_logger.info("Health monitoring stopped")
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get current health summary without performing new checks"""
        overall_status = self._calculate_overall_health()
        
        return {
            "overall_status": overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": self.environment.value,
            "components_count": len(self.components),
            "healthy_components": sum(1 for c in self.components.values() if c.status == HealthStatus.HEALTHY),
            "degraded_components": sum(1 for c in self.components.values() if c.status == HealthStatus.DEGRADED),
            "unhealthy_components": sum(1 for c in self.components.values() if c.status == HealthStatus.UNHEALTHY),
            "critical_components": sum(1 for c in self.components.values() if c.status == HealthStatus.CRITICAL)
        }


# Global health monitor instance
health_monitor = HealthMonitor()