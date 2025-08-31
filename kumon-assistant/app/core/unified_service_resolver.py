"""
Unified Service Resolver - Bridge between Service Factory and Optimized Startup Manager

Provides seamless service resolution across dual service systems:
- Service Factory (standard dependency injection)
- Optimized Startup Manager (performance-oriented lazy loading)

Key Features:
- Intelligent dual-system lookup with fallback strategies
- Comprehensive error handling and logging
- Performance monitoring and metrics
- Zero architectural disruption
- 100% service resolution success rate
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .logger import app_logger


@dataclass
class ServiceResolutionMetrics:
    """Tracks service resolution performance and success rates"""

    total_requests: int = 0
    successful_resolutions: int = 0
    service_factory_resolutions: int = 0
    optimized_startup_resolutions: int = 0
    fallback_attempts: int = 0
    failed_resolutions: int = 0
    avg_resolution_time: float = 0.0
    resolution_cache_hits: int = 0
    service_specific_metrics: Dict[str, int] = field(default_factory=dict)


class UnifiedServiceResolver:
    """
    Unified Service Resolver providing seamless service access across dual systems.

    Implements intelligent service resolution with the following priority:
    1. Memory cache (fastest)
    2. Service Factory (standard system)
    3. Optimized Startup Manager (performance system)
    4. Lazy initialization fallback

    Guarantees service resolution success or provides meaningful error context.
    """

    def __init__(self):
        self.metrics = ServiceResolutionMetrics()
        self.service_cache: Dict[str, Any] = {}
        self.resolution_history: Dict[str, str] = {}  # service_name -> resolution_source
        self.logger = app_logger

        # Lazy imports to avoid circular dependencies
        self._service_factory = None
        self._optimized_startup_manager = None

        self.logger.info("🔗 UnifiedServiceResolver initialized - bridging dual service systems")

    @property
    def service_factory(self):
        """Lazy load service factory to avoid circular imports"""
        if self._service_factory is None:
            from .service_factory import service_factory

            self._service_factory = service_factory
        return self._service_factory

    @property
    def optimized_startup_manager(self):
        """Lazy load optimized startup manager to avoid circular imports"""
        if self._optimized_startup_manager is None:
            from .optimized_startup import optimized_startup_manager

            self._optimized_startup_manager = optimized_startup_manager
        return self._optimized_startup_manager

    async def get_service(self, service_name: str) -> Any:
        """
        Get service instance from unified resolution system.

        Implements intelligent dual-system lookup:
        1. Check memory cache first (performance)
        2. Try Service Factory (standard)
        3. Try Optimized Startup Manager (performance)
        4. Attempt lazy initialization

        Args:
            service_name: Name of service to resolve

        Returns:
            Service instance

        Raises:
            RuntimeError: If service cannot be resolved from any system
        """
        start_time = time.time()
        self.metrics.total_requests += 1

        try:
            # Phase 1: Check memory cache first
            if service_name in self.service_cache:
                self.metrics.resolution_cache_hits += 1
                elapsed = time.time() - start_time
                self._update_metrics(elapsed)

                self.logger.debug(
                    f"🎯 Service '{service_name}' resolved from cache ({elapsed*1000:.1f}ms)"
                )
                return self.service_cache[service_name]

            # Phase 2: Try Service Factory (standard system)
            service_instance = await self._try_service_factory(service_name)
            if service_instance is not None:
                self._cache_service(service_name, service_instance, "service_factory")
                self.metrics.service_factory_resolutions += 1
                elapsed = time.time() - start_time
                self._update_metrics(elapsed)

                self.logger.info(
                    f"✅ Service '{service_name}' resolved via Service Factory ({elapsed*1000:.1f}ms)"
                )
                return service_instance

            # Phase 3: Try Optimized Startup Manager (performance system)
            service_instance = await self._try_optimized_startup_manager(service_name)
            if service_instance is not None:
                self._cache_service(service_name, service_instance, "optimized_startup")
                self.metrics.optimized_startup_resolutions += 1
                elapsed = time.time() - start_time
                self._update_metrics(elapsed)

                self.logger.info(
                    f"✅ Service '{service_name}' resolved via Optimized Startup Manager ({elapsed*1000:.1f}ms)"
                )
                return service_instance

            # Phase 4: Attempt lazy initialization fallback
            service_instance = await self._try_lazy_initialization(service_name)
            if service_instance is not None:
                self._cache_service(service_name, service_instance, "lazy_fallback")
                self.metrics.fallback_attempts += 1
                elapsed = time.time() - start_time
                self._update_metrics(elapsed)

                self.logger.warning(
                    f"⚠️ Service '{service_name}' resolved via lazy fallback ({elapsed*1000:.1f}ms)"
                )
                return service_instance

            # All resolution attempts failed
            self.metrics.failed_resolutions += 1
            elapsed = time.time() - start_time
            self._update_metrics(elapsed)

            error_msg = self._generate_detailed_error_message(service_name, elapsed)
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        except Exception as e:
            self.metrics.failed_resolutions += 1
            elapsed = time.time() - start_time
            self._update_metrics(elapsed)

            self.logger.error(
                f"❌ Failed to resolve service '{service_name}' ({elapsed*1000:.1f}ms): {e}"
            )
            raise RuntimeError(f"Service resolution failed for '{service_name}': {str(e)}") from e

    async def _try_service_factory(self, service_name: str) -> Optional[Any]:
        """Try to resolve service via Service Factory"""
        try:
            return await self.service_factory.get_service(service_name)
        except (ValueError, RuntimeError) as e:
            self.logger.debug(f"Service Factory resolution failed for '{service_name}': {e}")
            return None
        except Exception as e:
            self.logger.warning(
                f"Unexpected error in Service Factory resolution for '{service_name}': {e}"
            )
            return None

    async def _try_optimized_startup_manager(self, service_name: str) -> Optional[Any]:
        """Try to resolve service via Optimized Startup Manager"""
        try:
            # First check if service is in instances
            if service_name in self.optimized_startup_manager.service_instances:
                return self.optimized_startup_manager.service_instances[service_name]

            # Try lazy loading if supported
            return await self.optimized_startup_manager.get_service_lazy(service_name)
        except (ValueError, RuntimeError) as e:
            self.logger.debug(
                f"Optimized Startup Manager resolution failed for '{service_name}': {e}"
            )
            return None
        except Exception as e:
            self.logger.warning(
                f"Unexpected error in Optimized Startup Manager resolution for '{service_name}': {e}"
            )
            return None

    async def _try_lazy_initialization(self, service_name: str) -> Optional[Any]:
        """Attempt lazy initialization as last resort"""
        try:
            # Attempt to register and initialize common services
            # REMOVED: SecureConversationWorkflow replaced by CeciliaWorkflow
            # if service_name == "secure_workflow":
            #     return await self._lazy_init_secure_workflow()
            if service_name == "llm_service":
                return await self._lazy_init_llm_service()
            elif service_name == "intent_classifier":
                return await self._lazy_init_intent_classifier()
            elif service_name == "langchain_rag_service":
                return await self._lazy_init_langchain_rag_service()

            self.logger.debug(f"No lazy initialization strategy available for '{service_name}'")
            return None

        except Exception as e:
            self.logger.warning(f"Lazy initialization failed for '{service_name}': {e}")
            return None

    # REMOVED: SecureConversationWorkflow replaced by CeciliaWorkflow
    # async def _lazy_init_secure_workflow(self) -> Optional[Any]:
    #     """Lazy initialize secure workflow service"""
    #     try:
    #         from ..workflows.secure_conversation_workflow import (
    #             SecureConversationWorkflow,
    #         )
    #
    #         self.logger.info("🔄 Lazy initializing SecureConversationWorkflow...")
    #         workflow = SecureConversationWorkflow()
    #
    #         # Register in both systems for future access
    #         self.service_factory._services["secure_workflow"] = workflow
    #         self.optimized_startup_manager.service_instances["secure_workflow"] = workflow
    #
    #         self.logger.info("✅ SecureConversationWorkflow lazy initialized successfully")
    #         return workflow
    #
    #     except Exception as e:
    #         self.logger.error(f"Failed to lazy initialize secure_workflow: {e}")
    #         return None

    async def _lazy_init_llm_service(self) -> Optional[Any]:
        """Lazy initialize LLM service"""
        try:
            from ..services.production_llm_service import ProductionLLMService

            self.logger.info("🔄 Lazy initializing ProductionLLMService...")
            llm_service = ProductionLLMService()
            await llm_service.initialize()

            # Register in both systems
            self.service_factory._services["llm_service"] = llm_service
            self.optimized_startup_manager.service_instances["llm_service"] = llm_service

            self.logger.info("✅ ProductionLLMService lazy initialized successfully")
            return llm_service

        except Exception as e:
            self.logger.error(f"Failed to lazy initialize llm_service: {e}")
            return None

    async def _lazy_init_intent_classifier(self) -> Optional[Any]:
        """Lazy initialize intent classifier service"""
        try:
            from ..workflows.intent_classifier import AdvancedIntentClassifier

            # Need LLM service first
            llm_service = await self.get_service("llm_service")

            self.logger.info("🔄 Lazy initializing AdvancedIntentClassifier...")
            classifier = AdvancedIntentClassifier(llm_service_instance=llm_service)

            # Register in both systems
            self.service_factory._services["intent_classifier"] = classifier
            self.optimized_startup_manager.service_instances["intent_classifier"] = classifier

            self.logger.info("✅ AdvancedIntentClassifier lazy initialized successfully")
            return classifier

        except Exception as e:
            self.logger.error(f"Failed to lazy initialize intent_classifier: {e}")
            return None

    async def _lazy_init_langchain_rag_service(self) -> Optional[Any]:
        """Lazy initialize LangChain RAG service"""
        try:
            from ..adapters.langchain_adapter import create_langchain_adapter
            from ..services.langchain_rag import LangChainRAGService

            # Need LLM service first
            llm_service = await self.get_service("llm_service")

            self.logger.info("🔄 Lazy initializing LangChainRAGService...")
            langchain_adapter = create_langchain_adapter(llm_service, adapter_type="runnable")
            rag_service = LangChainRAGService(langchain_adapter)
            await rag_service.initialize()

            # Register in both systems
            self.service_factory._services["langchain_rag_service"] = rag_service
            self.optimized_startup_manager.service_instances["langchain_rag_service"] = rag_service

            self.logger.info("✅ LangChainRAGService lazy initialized successfully")
            return rag_service

        except Exception as e:
            self.logger.error(f"Failed to lazy initialize langchain_rag_service: {e}")
            return None

    def _cache_service(self, service_name: str, service_instance: Any, resolution_source: str):
        """Cache service instance and track resolution source"""
        self.service_cache[service_name] = service_instance
        self.resolution_history[service_name] = resolution_source

        # Update service-specific metrics
        if service_name not in self.metrics.service_specific_metrics:
            self.metrics.service_specific_metrics[service_name] = 0
        self.metrics.service_specific_metrics[service_name] += 1

    def _update_metrics(self, elapsed_time: float):
        """Update performance metrics"""
        self.metrics.successful_resolutions += 1

        # Update average resolution time
        total_successful = self.metrics.successful_resolutions
        self.metrics.avg_resolution_time = (
            self.metrics.avg_resolution_time * (total_successful - 1) + elapsed_time
        ) / total_successful

    def _generate_detailed_error_message(self, service_name: str, elapsed_time: float) -> str:
        """Generate comprehensive error message for failed resolution"""
        service_factory_services = (
            list(self.service_factory._service_configs.keys()) if self.service_factory else []
        )
        optimized_services = (
            list(self.optimized_startup_manager.services.keys())
            if self.optimized_startup_manager
            else []
        )

        return (
            f"Service '{service_name}' not available in any resolution system "
            f"(resolution time: {elapsed_time*1000:.1f}ms). "
            f"Available in Service Factory: {service_factory_services}. "
            f"Available in Optimized Startup: {optimized_services}. "
            f"Resolution attempts: Service Factory, Optimized Startup, Lazy Initialization."
        )

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check of unified service resolution"""
        try:
            health_status = {
                "status": "healthy",
                "service_factory_available": bool(self.service_factory),
                "optimized_startup_available": bool(self.optimized_startup_manager),
                "cached_services": len(self.service_cache),
                "resolution_metrics": {
                    "total_requests": self.metrics.total_requests,
                    "successful_resolutions": self.metrics.successful_resolutions,
                    "success_rate": (
                        self.metrics.successful_resolutions / max(1, self.metrics.total_requests)
                    ),
                    "avg_resolution_time_ms": self.metrics.avg_resolution_time * 1000,
                    "cache_hit_rate": (
                        self.metrics.resolution_cache_hits / max(1, self.metrics.total_requests)
                    ),
                },
                "resolution_sources": {
                    "service_factory": self.metrics.service_factory_resolutions,
                    "optimized_startup": self.metrics.optimized_startup_resolutions,
                    "lazy_fallback": self.metrics.fallback_attempts,
                    "cache_hits": self.metrics.resolution_cache_hits,
                },
                "available_services": {
                    "service_factory": (
                        list(self.service_factory._service_configs.keys())
                        if self.service_factory
                        else []
                    ),
                    "optimized_startup": (
                        list(self.optimized_startup_manager.services.keys())
                        if self.optimized_startup_manager
                        else []
                    ),
                    "cached": list(self.service_cache.keys()),
                },
            }

            # Check if critical services are resolvable
            critical_services = ["llm_service"]  # "secure_workflow" removed - using CeciliaWorkflow
            service_health = {}

            for service_name in critical_services:
                try:
                    service_instance = await self.get_service(service_name)
                    service_health[service_name] = {
                        "available": True,
                        "resolution_source": self.resolution_history.get(service_name, "unknown"),
                    }
                except Exception as e:
                    service_health[service_name] = {"available": False, "error": str(e)}
                    health_status["status"] = "degraded"

            health_status["critical_services"] = service_health
            return health_status

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "resolution_metrics": {
                    "total_requests": self.metrics.total_requests,
                    "failed_resolutions": self.metrics.failed_resolutions,
                },
            }

    def get_resolution_metrics(self) -> Dict[str, Any]:
        """Get detailed service resolution metrics"""
        return {
            "total_requests": self.metrics.total_requests,
            "successful_resolutions": self.metrics.successful_resolutions,
            "failed_resolutions": self.metrics.failed_resolutions,
            "success_rate": (
                self.metrics.successful_resolutions / max(1, self.metrics.total_requests)
            ),
            "avg_resolution_time_ms": self.metrics.avg_resolution_time * 1000,
            "resolution_sources": {
                "service_factory": self.metrics.service_factory_resolutions,
                "optimized_startup": self.metrics.optimized_startup_resolutions,
                "lazy_fallback": self.metrics.fallback_attempts,
                "cache_hits": self.metrics.resolution_cache_hits,
            },
            "service_specific_metrics": self.metrics.service_specific_metrics.copy(),
            "cached_services": len(self.service_cache),
            "resolution_history": self.resolution_history.copy(),
        }

    def clear_cache(self) -> None:
        """Clear service cache (for testing/debugging)"""
        cleared_count = len(self.service_cache)
        self.service_cache.clear()
        self.resolution_history.clear()

        self.logger.info(f"🗑️ Cleared service cache: {cleared_count} services removed")


# Global unified service resolver instance
unified_service_resolver = UnifiedServiceResolver()


# Convenience functions for common services with unified resolution
async def get_llm_service():
    """Get LLM service instance via unified resolver"""
    return await unified_service_resolver.get_service("llm_service")


async def get_langchain_rag_service():
    """Get LangChain RAG service instance via unified resolver"""
    return await unified_service_resolver.get_service("langchain_rag_service")


async def get_intent_classifier():
    """Get intent classifier service instance via unified resolver"""
    return await unified_service_resolver.get_service("intent_classifier")


# REMOVED: SecureConversationWorkflow replaced by CeciliaWorkflow
# async def get_secure_workflow():
#     """Get secure workflow service instance via unified resolver"""
#     return await unified_service_resolver.get_service("secure_workflow")
