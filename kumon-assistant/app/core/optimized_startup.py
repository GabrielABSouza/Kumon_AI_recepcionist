"""
Wave 5: Optimized Startup System
Advanced service initialization optimization with lazy loading and parallel processing
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .logger import app_logger


class ServicePriority(Enum):
    """Service initialization priority levels"""

    CRITICAL = "critical"  # Must be available immediately (health, auth)
    HIGH = "high"  # Core business logic (LLM, workflows)
    MEDIUM = "medium"  # Enhanced features (caching, monitoring)
    LOW = "low"  # Optional features (analytics, optimization)
    DEFERRED = "deferred"  # Background services (cleanup, maintenance)


class InitializationStrategy(Enum):
    """Different initialization strategies"""

    EAGER = "eager"  # Initialize immediately at startup
    LAZY = "lazy"  # Initialize on first use
    BACKGROUND = "background"  # Initialize in background after startup
    CONDITIONAL = "conditional"  # Initialize based on conditions


@dataclass
class ServiceConfig:
    """Configuration for optimized service initialization"""

    name: str
    priority: ServicePriority
    strategy: InitializationStrategy
    timeout_seconds: float = 30.0
    dependencies: List[str] = field(default_factory=list)
    conditions: Optional[Dict[str, Any]] = None
    health_check: Optional[Callable] = None
    initialization_function: Optional[Callable] = None
    cleanup_function: Optional[Callable] = None
    critical_for_health: bool = False


class OptimizedStartupManager:
    """
    Advanced startup manager implementing lazy loading, parallel initialization,
    and intelligent service prioritization for sub-10-second startup times.
    """

    def __init__(self):
        self.services: Dict[str, ServiceConfig] = {}
        self.initialized_services: Set[str] = set()
        self.initializing_services: Set[str] = set()
        self.failed_services: Set[str] = set()
        self.service_instances: Dict[str, Any] = {}
        self.startup_metrics: Dict[str, float] = {}
        self.background_tasks: List[asyncio.Task] = []
        self.thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="service-init")

        # Performance tracking
        self.startup_start_time: Optional[float] = None
        self.critical_services_ready_time: Optional[float] = None
        self.total_startup_time: Optional[float] = None

    def register_service(self, config: ServiceConfig):
        """Register a service for optimized initialization"""
        self.services[config.name] = config
        app_logger.debug(
            f"Registered service '{config.name}' with {config.strategy.value} strategy"
        )

    async def optimized_startup(self) -> Dict[str, Any]:
        """
        Execute optimized startup sequence with parallel processing and lazy loading

        Returns:
            Startup metrics and status information
        """
        self.startup_start_time = time.time()
        app_logger.info("🚀 Starting optimized startup sequence...")

        # Phase 1: Critical services (must be ready for health checks)
        critical_start = time.time()
        await self._initialize_critical_services()
        self.critical_services_ready_time = time.time() - critical_start

        # Phase 2: High priority services (parallel initialization)
        high_priority_start = time.time()
        await self._initialize_high_priority_services()
        high_priority_time = time.time() - high_priority_start

        # Phase 3: Background initialization for medium/low priority
        background_start = time.time()
        self._start_background_initialization()
        background_setup_time = time.time() - background_start

        # Phase 4: Deferred services (scheduled for later)
        self._schedule_deferred_services()

        self.total_startup_time = time.time() - self.startup_start_time

        # Generate startup report
        startup_report = {
            "status": "completed",
            "total_startup_time": self.total_startup_time,
            "critical_services_time": self.critical_services_ready_time,
            "high_priority_time": high_priority_time,
            "background_setup_time": background_setup_time,
            "services_ready": len(self.initialized_services),
            "services_initializing": len(self.initializing_services),
            "services_failed": len(self.failed_services),
            "background_tasks": len(self.background_tasks),
            "critical_services": [
                name
                for name, config in self.services.items()
                if config.priority == ServicePriority.CRITICAL
            ],
            "lazy_services": [
                name
                for name, config in self.services.items()
                if config.strategy == InitializationStrategy.LAZY
            ],
        }

        app_logger.info(
            f"✅ Optimized startup completed in {self.total_startup_time:.2f}s "
            f"(Critical: {self.critical_services_ready_time:.2f}s)"
        )

        return startup_report

    async def _initialize_critical_services(self):
        """Initialize critical services that must be available immediately"""
        critical_services = [
            name
            for name, config in self.services.items()
            if config.priority == ServicePriority.CRITICAL
        ]

        if not critical_services:
            app_logger.info("No critical services to initialize")
            return

        app_logger.info(f"Initializing {len(critical_services)} critical services...")

        # Initialize critical services sequentially to ensure dependencies
        for service_name in critical_services:
            await self._initialize_single_service(service_name, timeout_override=5.0)

        app_logger.info(f"✅ Critical services initialized: {len(self.initialized_services)}")

    async def _initialize_high_priority_services(self):
        """Initialize high priority services in parallel"""
        high_priority_services = [
            name
            for name, config in self.services.items()
            if config.priority == ServicePriority.HIGH
            and config.strategy == InitializationStrategy.EAGER
        ]

        if not high_priority_services:
            app_logger.info("No high priority services to initialize")
            return

        app_logger.info(
            f"Initializing {len(high_priority_services)} high priority services in parallel..."
        )

        # Group services by dependencies for parallel execution
        independent_services = [
            name
            for name in high_priority_services
            if not self.services[name].dependencies
            or all(dep in self.initialized_services for dep in self.services[name].dependencies)
        ]

        # Initialize independent services in parallel
        if independent_services:
            tasks = [self._initialize_single_service(name) for name in independent_services]
            await asyncio.gather(*tasks, return_exceptions=True)

        # Initialize remaining services that had dependencies
        remaining_services = (
            set(high_priority_services) - set(independent_services) - self.initialized_services
        )
        for service_name in remaining_services:
            await self._initialize_single_service(service_name)

        app_logger.info(f"✅ High priority services initialized: {len(self.initialized_services)}")

    def _start_background_initialization(self):
        """Start background initialization for medium and low priority services"""
        background_services = [
            name
            for name, config in self.services.items()
            if config.priority in [ServicePriority.MEDIUM, ServicePriority.LOW]
            and config.strategy == InitializationStrategy.BACKGROUND
        ]

        if not background_services:
            app_logger.info("No background services to initialize")
            return

        app_logger.info(
            f"Starting background initialization for {len(background_services)} services..."
        )

        # Create background tasks for each service
        for service_name in background_services:
            task = asyncio.create_task(
                self._background_service_init(service_name), name=f"bg-init-{service_name}"
            )
            self.background_tasks.append(task)

        app_logger.info(f"✅ {len(self.background_tasks)} background initialization tasks started")

    def _schedule_deferred_services(self):
        """Schedule deferred services for later initialization"""
        deferred_services = [
            name
            for name, config in self.services.items()
            if config.priority == ServicePriority.DEFERRED
        ]

        if not deferred_services:
            app_logger.info("No deferred services to schedule")
            return

        app_logger.info(f"Scheduling {len(deferred_services)} deferred services...")

        # Schedule deferred services to run after a delay
        for service_name in deferred_services:
            task = asyncio.create_task(
                self._deferred_service_init(service_name), name=f"deferred-{service_name}"
            )
            self.background_tasks.append(task)

        app_logger.info(f"✅ Deferred services scheduled")

    async def _initialize_single_service(
        self, service_name: str, timeout_override: Optional[float] = None
    ):
        """Initialize a single service with error handling and timeout"""
        if service_name in self.initialized_services:
            return

        if service_name in self.initializing_services:
            app_logger.warning(f"Service '{service_name}' already initializing, skipping")
            return

        config = self.services[service_name]
        timeout = timeout_override or config.timeout_seconds

        self.initializing_services.add(service_name)
        start_time = time.time()

        try:
            app_logger.debug(f"Initializing service: {service_name}")

            # Check conditions
            if config.conditions and not self._check_conditions(config.conditions):
                app_logger.info(f"Service '{service_name}' conditions not met, skipping")
                return

            # Check dependencies
            for dep in config.dependencies:
                if dep not in self.initialized_services:
                    if dep in self.services:
                        await self._initialize_single_service(dep)
                    else:
                        raise RuntimeError(f"Dependency '{dep}' not available for '{service_name}'")

            # Initialize service
            if config.initialization_function:
                await asyncio.wait_for(config.initialization_function(), timeout=timeout)
            else:
                app_logger.warning(f"No initialization function for service '{service_name}'")

            # Health check
            if config.health_check:
                health_result = await config.health_check()
                if not health_result:
                    raise RuntimeError(f"Health check failed for '{service_name}'")

            self.initialized_services.add(service_name)
            elapsed = time.time() - start_time
            self.startup_metrics[service_name] = elapsed

            app_logger.info(f"✅ Service '{service_name}' initialized in {elapsed:.2f}s")

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            app_logger.error(
                f"❌ Service '{service_name}' initialization timeout after {elapsed:.2f}s"
            )
            self.failed_services.add(service_name)

        except Exception as e:
            elapsed = time.time() - start_time
            app_logger.error(
                f"❌ Service '{service_name}' initialization failed ({elapsed:.2f}s): {e}"
            )
            self.failed_services.add(service_name)

        finally:
            self.initializing_services.discard(service_name)

    async def _background_service_init(self, service_name: str):
        """Initialize service in background with delay to reduce startup impact"""
        # Add small delay to avoid startup resource contention
        await asyncio.sleep(2.0)
        await self._initialize_single_service(service_name)

    async def _deferred_service_init(self, service_name: str):
        """Initialize deferred service after significant delay"""
        # Wait for main startup to complete and system to stabilize
        await asyncio.sleep(30.0)
        await self._initialize_single_service(service_name)

    def _check_conditions(self, conditions: Dict[str, Any]) -> bool:
        """Check if service initialization conditions are met"""
        import os

        for condition_type, condition_value in conditions.items():
            if condition_type == "env_var":
                if not os.getenv(condition_value):
                    return False
            elif condition_type == "setting":
                from .config import settings

                if not getattr(settings, condition_value, False):
                    return False
            elif condition_type == "service_available":
                if condition_value not in self.initialized_services:
                    return False

        return True

    async def get_service_lazy(self, service_name: str) -> Any:
        """
        Get service instance, initializing it lazily if needed

        Args:
            service_name: Name of the service to get

        Returns:
            Service instance

        Raises:
            RuntimeError: If service initialization fails
        """
        # Return existing instance if available
        if service_name in self.service_instances:
            return self.service_instances[service_name]

        # Check if service is registered
        if service_name not in self.services:
            raise RuntimeError(f"Service '{service_name}' not registered")

        config = self.services[service_name]

        # If service is configured for lazy loading and not yet initialized
        if (
            config.strategy == InitializationStrategy.LAZY
            and service_name not in self.initialized_services
        ):
            app_logger.info(f"Lazy loading service: {service_name}")
            await self._initialize_single_service(service_name)

        # Wait for service if it's currently initializing
        timeout = 30.0  # Maximum wait time
        start_wait = time.time()
        while service_name in self.initializing_services and (time.time() - start_wait) < timeout:
            await asyncio.sleep(0.1)

        if service_name in self.failed_services:
            raise RuntimeError(f"Service '{service_name}' failed to initialize")

        if service_name not in self.initialized_services:
            raise RuntimeError(f"Service '{service_name}' not available")

        return self.service_instances.get(service_name)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all critical services"""
        health_results = {}
        overall_healthy = True

        critical_services = [
            name for name, config in self.services.items() if config.critical_for_health
        ]

        for service_name in critical_services:
            if service_name in self.initialized_services:
                config = self.services[service_name]
                if config.health_check:
                    try:
                        result = await config.health_check()
                        health_results[service_name] = {
                            "status": "healthy" if result else "unhealthy",
                            "initialized": True,
                        }
                        if not result:
                            overall_healthy = False
                    except Exception as e:
                        health_results[service_name] = {
                            "status": "error",
                            "error": str(e),
                            "initialized": True,
                        }
                        overall_healthy = False
                else:
                    health_results[service_name] = {
                        "status": "no_health_check",
                        "initialized": True,
                    }
            else:
                health_results[service_name] = {"status": "not_initialized", "initialized": False}
                if service_name not in self.failed_services:
                    overall_healthy = False

        return {
            "overall_status": "healthy" if overall_healthy else "degraded",
            "services": health_results,
            "initialized_count": len(self.initialized_services),
            "failed_count": len(self.failed_services),
            "background_tasks": len([t for t in self.background_tasks if not t.done()]),
        }

    async def shutdown(self):
        """Cleanup and shutdown all services"""
        app_logger.info("🔄 Starting optimized shutdown...")

        # Cancel background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        # Wait for cancellation
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

        # Cleanup services in reverse order
        cleanup_order = list(reversed(list(self.initialized_services)))

        for service_name in cleanup_order:
            config = self.services.get(service_name)
            if config and config.cleanup_function:
                try:
                    await config.cleanup_function()
                    app_logger.debug(f"✅ Cleaned up service: {service_name}")
                except Exception as e:
                    app_logger.error(f"❌ Error cleaning up service '{service_name}': {e}")

        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)

        app_logger.info("✅ Optimized shutdown completed")

    def get_startup_metrics(self) -> Dict[str, Any]:
        """Get detailed startup performance metrics"""
        return {
            "total_startup_time": self.total_startup_time,
            "critical_services_time": self.critical_services_ready_time,
            "services_initialized": len(self.initialized_services),
            "services_failed": len(self.failed_services),
            "background_tasks_active": len([t for t in self.background_tasks if not t.done()]),
            "service_metrics": self.startup_metrics.copy(),
            "performance_target_met": (
                self.total_startup_time < 10.0 if self.total_startup_time else False
            ),
        }


# Global optimized startup manager instance
optimized_startup_manager = OptimizedStartupManager()
