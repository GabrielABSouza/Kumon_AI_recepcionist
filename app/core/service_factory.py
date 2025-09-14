"""
Service Factory - Centralized service management with lazy loading

This factory eliminates circular imports by providing a central registry
for all application services with lazy initialization and dependency injection.

Key features:
- Singleton pattern for service instances
- Lazy loading to prevent import circular dependencies
- Async initialization support
- Thread-safe access with locks
- Detailed logging for debugging
- Service health monitoring
"""

import logging
import threading
import time
from typing import Any, Dict, Optional, Type, TypeVar

T = TypeVar("T")


class ServiceFactory:
    """
    Centralized service factory implementing singleton pattern with lazy loading.

    Eliminates circular imports by deferring service instantiation until needed
    and managing dependencies through the factory pattern.
    """

    _instance: Optional["ServiceFactory"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ServiceFactory":
        """Ensure singleton instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the service factory"""
        if not hasattr(self, "_initialized"):
            self._services: Dict[str, Any] = {}
            self._service_configs: Dict[str, Dict[str, Any]] = {}
            self._initialization_status: Dict[str, bool] = {}
            self._service_locks: Dict[str, threading.Lock] = {}
            self._logger = logging.getLogger(__name__)
            self._initialized = True

            self._logger.info("🏭 Service Factory initialized")

    def register_service(
        self,
        name: str,
        service_class: Type[T],
        dependencies: Optional[list] = None,
        initialization_args: Optional[Dict[str, Any]] = None,
        async_init: bool = True,
    ) -> None:
        """
        Register a service with the factory.

        Args:
            name: Service identifier
            service_class: Class to instantiate
            dependencies: List of dependency service names
            initialization_args: Arguments for service initialization
            async_init: Whether service requires async initialization
        """
        with self._lock:
            self._service_configs[name] = {
                "class": service_class,
                "dependencies": dependencies or [],
                "init_args": initialization_args or {},
                "async_init": async_init,
            }
            self._service_locks[name] = threading.Lock()
            self._logger.info(f"📋 Registered service: {name}")

    async def get_service(self, name: str) -> Any:
        """
        Get service instance, creating it if necessary.

        Args:
            name: Service identifier

        Returns:
            Service instance

        Raises:
            ValueError: If service not registered
            RuntimeError: If service initialization fails
        """
        if name not in self._service_configs:
            raise ValueError(f"Service '{name}' not registered")

        # Return existing instance if available
        if name in self._services:
            return self._services[name]

        # Thread-safe service creation
        with self._service_locks[name]:
            # Double-check pattern
            if name in self._services:
                return self._services[name]

            return await self._create_service(name)

    async def _create_service(self, name: str) -> Any:
        """
        Create and initialize service instance.

        Args:
            name: Service identifier

        Returns:
            Initialized service instance
        """
        config = self._service_configs[name]
        start_time = time.time()

        self._logger.info(f"🔨 Creating service: {name}")

        try:
            # Resolve dependencies first
            dependencies = {}
            for dep_name in config["dependencies"]:
                dependencies[dep_name] = await self.get_service(dep_name)
                self._logger.debug(f"  ✅ Resolved dependency: {dep_name}")

            # Create service instance
            service_class = config["class"]
            init_args = {**config["init_args"], **dependencies}

            # Handle different initialization patterns
            if name == "intent_classifier":
                # Intent classifier can work without LLM (uses pattern matching as fallback)
                instance = service_class(
                    llm_service_instance=dependencies.get("llm_service", None)
                )
            elif name == "langchain_rag_service":
                # Special case: Create LangChain adapter for RAG service
                from ..adapters.langchain_adapter import create_langchain_adapter

                llm_service = dependencies.get("llm_service")
                langchain_adapter = create_langchain_adapter(
                    llm_service, adapter_type="runnable"
                )
                instance = service_class(langchain_adapter)
            elif config["dependencies"] and any(
                "llm_service" in dep for dep in config["dependencies"]
            ):
                # Fallback for other services that might expect llm_service as a positional argument
                instance = service_class(dependencies.get("llm_service"))
            else:
                # Standard initialization
                instance = service_class(**init_args)

            # Initialize if required
            if config["async_init"] and hasattr(instance, "initialize"):
                self._logger.debug(f"  🔄 Async initializing: {name}")
                await instance.initialize()
                self._logger.debug(f"  ✅ Async initialization complete: {name}")

            # Store instance
            self._services[name] = instance
            self._initialization_status[name] = True

            elapsed = time.time() - start_time
            self._logger.info(
                f"✅ Service created successfully: {name} ({elapsed:.2f}s)"
            )

            return instance

        except Exception as e:
            self._initialization_status[name] = False
            elapsed = time.time() - start_time
            self._logger.error(
                f"❌ Failed to create service '{name}' ({elapsed:.2f}s): {e}"
            )
            raise RuntimeError(f"Service initialization failed: {name}") from e

    def get_service_sync(self, name: str) -> Optional[Any]:
        """
        Get service instance synchronously (returns None if not yet created).

        Args:
            name: Service identifier

        Returns:
            Service instance or None if not created
        """
        return self._services.get(name)

    async def initialize_core_services(self) -> None:
        """Initialize all core services in correct dependency order"""
        self._logger.info("🚀 Initializing core services...")

        # Define initialization order based on dependencies
        service_order = [
            "llm_service",
            "intent_classifier",
            # "secure_workflow",  # REMOVED: Replaced by CeciliaWorkflow
            "langchain_rag_service",
        ]

        for service_name in service_order:
            if service_name in self._service_configs:
                try:
                    await self.get_service(service_name)
                except Exception as e:
                    self._logger.error(f"❌ Failed to initialize {service_name}: {e}")
                    # Continue with other services

        self._logger.info("✅ Core services initialization completed")

    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered services"""
        status = {}

        for name, config in self._service_configs.items():
            status[name] = {
                "registered": True,
                "initialized": self._initialization_status.get(name, False),
                "instance_exists": name in self._services,
                "dependencies": config["dependencies"],
                "async_init": config["async_init"],
            }

        return status

    def clear_service(self, name: str) -> bool:
        """
        Clear a specific service instance (for testing/debugging).

        Args:
            name: Service identifier

        Returns:
            True if service was cleared
        """
        with self._lock:
            if name in self._services:
                del self._services[name]
                self._initialization_status[name] = False
                self._logger.info(f"🗑️ Cleared service: {name}")
                return True
            return False

    def clear_all_services(self) -> None:
        """Clear all service instances (for testing/debugging)"""
        with self._lock:
            self._services.clear()
            self._initialization_status.clear()
            self._logger.info("🗑️ Cleared all services")


# Global singleton instance
service_factory = ServiceFactory()


# Convenience functions for common services
async def get_llm_service():
    """Get LLM service instance"""
    return await service_factory.get_service("llm_service")


async def get_langchain_rag_service():
    """Get LangChain RAG service instance"""
    return await service_factory.get_service("langchain_rag_service")


async def get_intent_classifier():
    """Get intent classifier service instance"""
    return await service_factory.get_service("intent_classifier")


# REMOVED: SecureConversationWorkflow replaced by CeciliaWorkflow
# async def get_secure_workflow():
#     """Get secure workflow service instance"""
#     return await service_factory.get_service("secure_workflow")


async def get_intent_first_router():
    """Get IntentFirstRouter service instance"""
    from ..core.optimized_startup import optimized_startup_manager

    return await optimized_startup_manager.get_service_lazy("intent_first_router")


def register_core_services():
    """Register all core application services"""
    logger = logging.getLogger(__name__)
    logger.info("📋 Registering core services...")

    # Import here to avoid circular imports
    # Temporarily disable LangChainRAGService due to qdrant dependency
    # from ..services.langchain_rag import LangChainRAGService
    from ..services.production_llm_service import ProductionLLMService
    from ..workflows.intent_classifier import AdvancedIntentClassifier

    # REMOVED: SecureConversationWorkflow replaced by CeciliaWorkflow
    # from ..workflows.secure_conversation_workflow import SecureConversationWorkflow
    # Register LLM service (no dependencies)
    service_factory.register_service(
        name="llm_service",
        service_class=ProductionLLMService,
        dependencies=[],
        async_init=True,
    )

    # Register intent classifier (LLM is optional - works with pattern matching)
    service_factory.register_service(
        name="intent_classifier",
        service_class=AdvancedIntentClassifier,
        dependencies=[],  # No hard dependencies - LLM is optional
        initialization_args={
            "llm_service_instance": None
        },  # Optional - will be added if available
        async_init=False,
    )

    # REMOVED: SecureConversationWorkflow replaced by CeciliaWorkflow
    # service_factory.register_service(
    #     name="secure_workflow",
    #     service_class=SecureConversationWorkflow,
    #     dependencies=[],
    #     async_init=False,
    # )

    # Register LangChain RAG service (depends on LLM service)
    # Temporarily disabled due to qdrant dependency
    # service_factory.register_service(
    #     name="langchain_rag_service",
    #     service_class=LangChainRAGService,
    #     dependencies=["llm_service"],
    #     async_init=True,
    # )

    logger.info("✅ Core services registered successfully")
