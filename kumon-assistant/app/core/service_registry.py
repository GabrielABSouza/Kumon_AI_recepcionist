"""
Wave 5: Service Registry Configuration
Defines initialization strategies and priorities for all services
"""

import os
from typing import Any, Dict

from .config import settings
from .logger import app_logger
from .optimized_startup import (
    InitializationStrategy,
    ServiceConfig,
    ServicePriority,
    optimized_startup_manager,
)


async def _initialize_llm_service():
    """Initialize production LLM service"""
    from ..services.production_llm_service import ProductionLLMService

    service = ProductionLLMService()
    await service.initialize()
    # CRITICAL FIX: Ensure service instance is stored for dependency injection
    optimized_startup_manager.service_instances["llm_service"] = service
    app_logger.info(f"✅ LLM service instance stored: {type(service).__name__}")
    return service


async def _initialize_intent_classifier():
    """Initialize intent classifier service"""
    from ..workflows.intent_classifier import AdvancedIntentClassifier

    # LLM service is optional - try to get it but don't fail if not available
    llm_service = optimized_startup_manager.service_instances.get("llm_service")
    if not llm_service:
        try:
            llm_service = await optimized_startup_manager.get_service_lazy("llm_service")
        except Exception as e:
            app_logger.info(
                f"LLM service not available for intent classifier, using pattern matching only: {e}"
            )
            llm_service = None

    classifier = AdvancedIntentClassifier(llm_service)
    # CRITICAL FIX: Ensure service instance is stored for dependency injection
    optimized_startup_manager.service_instances["intent_classifier"] = classifier
    app_logger.info(f"✅ Intent classifier instance stored: {type(classifier).__name__}")
    return classifier


# REMOVED: SecureConversationWorkflow replaced by CeciliaWorkflow
# async def _initialize_secure_workflow():
#     """Initialize secure conversation workflow"""
#     from ..workflows.secure_conversation_workflow import SecureConversationWorkflow
#
#     workflow = SecureConversationWorkflow()
#     # CRITICAL FIX: Ensure service instance is stored for dependency injection
#     optimized_startup_manager.service_instances["secure_workflow"] = workflow
#     app_logger.info(f"✅ Secure workflow instance stored: {type(workflow).__name__}")
#     return workflow


async def _initialize_langchain_rag():
    """Initialize LangChain RAG service"""
    from ..adapters.langchain_adapter import create_langchain_adapter
    from ..services.langchain_rag import LangChainRAGService

    llm_service = optimized_startup_manager.service_instances.get("llm_service")
    if not llm_service:
        llm_service = await optimized_startup_manager.get_service_lazy("llm_service")

    adapter = create_langchain_adapter(llm_service, adapter_type="runnable")
    rag_service = LangChainRAGService(adapter)
    await rag_service.initialize()
    # CRITICAL FIX: Ensure service instance is stored for dependency injection
    optimized_startup_manager.service_instances["langchain_rag_service"] = rag_service
    app_logger.info(f"✅ LangChain RAG service instance stored: {type(rag_service).__name__}")
    return rag_service


async def _initialize_cache_manager():
    """Initialize enhanced cache system"""
    from ..services.cache_manager import cache_manager

    await cache_manager.initialize()
    await cache_manager.warm_common_patterns()
    return cache_manager


async def _initialize_health_monitor():
    """Initialize health monitoring system"""
    from ..core.health_monitor import health_monitor

    # Register core components
    health_monitor.register_component("database", timeout=10.0)
    health_monitor.register_component("cache", timeout=5.0)
    health_monitor.register_component("circuit_breakers", timeout=2.0)
    health_monitor.register_component("memory", timeout=1.0)

    # Perform initial health check
    await health_monitor.perform_health_check()

    # Start monitoring only in production
    if settings.ENVIRONMENT == "production":
        import asyncio

        asyncio.create_task(health_monitor.start_monitoring())

    return health_monitor


async def _initialize_memory_service():
    """Initialize conversation memory service"""
    if not settings.MEMORY_ENABLE_SYSTEM:
        return None

    from ..services.conversation_memory_service import conversation_memory_service

    timeout = 30.0 if os.getenv("RAILWAY_ENVIRONMENT") else 60.0
    await conversation_memory_service.initialize()

    # Perform health check
    health_status = await conversation_memory_service.health_check()
    app_logger.info(f"Memory system health: {health_status}")

    return conversation_memory_service


async def _initialize_cost_monitor():
    """Initialize cost monitoring service"""
    from ..services.cost_monitor import cost_monitor

    await cost_monitor.initialize()
    return cost_monitor


async def _initialize_vector_store():
    """Initialize vector store for RAG"""
    from ..services.vector_store import vector_store

    await vector_store.initialize()
    return vector_store




async def _initialize_security_manager():
    """Initialize security management system"""
    from ..security.security_manager import security_manager

    return security_manager


async def _initialize_workflow_orchestrator():
    """Initialize workflow orchestration system"""
    from ..workflows.workflow_orchestrator import workflow_orchestrator

    return workflow_orchestrator


async def _initialize_intent_first_router():
    """Initialize IntentFirstRouter service for fast template responses"""
    from ..services.intent_first_router import IntentFirstRouter

    router = IntentFirstRouter()
    # Store service instance for dependency injection
    optimized_startup_manager.service_instances["intent_first_router"] = router
    app_logger.info(f"✅ IntentFirstRouter initialized successfully: {type(router).__name__}")
    return router


async def _health_check_llm_service() -> bool:
    """Health check for LLM service"""
    try:
        llm_service = optimized_startup_manager.service_instances.get("llm_service")
        if not llm_service:
            return False
        health = await llm_service.get_health_status()
        return health.get("status") in ["healthy", "good"]
    except:
        return False


async def _health_check_rag_service() -> bool:
    """Health check for RAG service"""
    try:
        rag_service = optimized_startup_manager.service_instances.get("langchain_rag_service")
        if not rag_service:
            return False
        # Simple test query
        result = await rag_service.query("test", max_results=1)
        return result is not None
    except:
        return False


async def _health_check_cache() -> bool:
    """Health check for cache system"""
    try:
        from ..services.cache_manager import cache_manager

        health = await cache_manager.health_check()
        return health.get("status") == "healthy"
    except:
        return False


async def _health_check_memory() -> bool:
    """Health check for memory service"""
    try:
        if not settings.MEMORY_ENABLE_SYSTEM:
            return True  # Not required, so healthy by default
        from ..services.conversation_memory_service import conversation_memory_service

        health = await conversation_memory_service.health_check()
        return "error" not in str(health).lower()
    except:
        return False


def register_all_services():
    """Register all services with their optimization configurations"""

    # CRITICAL SERVICES (must be available for health checks)
    optimized_startup_manager.register_service(
        ServiceConfig(
            name="health_monitor",
            priority=ServicePriority.CRITICAL,
            strategy=InitializationStrategy.EAGER,
            timeout_seconds=5.0,
            dependencies=[],
            initialization_function=_initialize_health_monitor,
            critical_for_health=True,
        )
    )

    optimized_startup_manager.register_service(
        ServiceConfig(
            name="security_manager",
            priority=ServicePriority.CRITICAL,
            strategy=InitializationStrategy.EAGER,
            timeout_seconds=5.0,
            dependencies=[],
            initialization_function=_initialize_security_manager,
            critical_for_health=True,
        )
    )

    # HIGH PRIORITY SERVICES (core business logic)
    optimized_startup_manager.register_service(
        ServiceConfig(
            name="llm_service",
            priority=ServicePriority.HIGH,
            strategy=InitializationStrategy.BACKGROUND,  # Initialize in parallel, not blocking startup
            timeout_seconds=15.0,
            dependencies=[],
            initialization_function=_initialize_llm_service,
            health_check=_health_check_llm_service,
            critical_for_health=True,
        )
    )

    optimized_startup_manager.register_service(
        ServiceConfig(
            name="intent_classifier",
            priority=ServicePriority.HIGH,
            strategy=InitializationStrategy.EAGER,  # Critical service used in every message
            timeout_seconds=10.0,
            dependencies=[],  # No dependencies - can work without LLM using pattern matching
            initialization_function=_initialize_intent_classifier,
            critical_for_health=True,  # Required for message processing
        )
    )

    # REMOVED: SecureConversationWorkflow replaced by CeciliaWorkflow
    # optimized_startup_manager.register_service(
    #     ServiceConfig(
    #         name="secure_workflow",
    #         priority=ServicePriority.HIGH,
    #         strategy=InitializationStrategy.LAZY,  # Loaded on first message
    #         timeout_seconds=10.0,
    #         dependencies=[],
    #         initialization_function=_initialize_secure_workflow,
    #     )
    # )

    optimized_startup_manager.register_service(
        ServiceConfig(
            name="langchain_rag_service",
            priority=ServicePriority.HIGH,
            strategy=InitializationStrategy.BACKGROUND,  # Initialize in background
            timeout_seconds=30.0,
            dependencies=["llm_service"],
            initialization_function=_initialize_langchain_rag,
            health_check=_health_check_rag_service,
        )
    )

    optimized_startup_manager.register_service(
        ServiceConfig(
            name="intent_first_router",
            priority=ServicePriority.HIGH,
            strategy=InitializationStrategy.LAZY,  # Fast loading when needed
            timeout_seconds=5.0,
            dependencies=[],  # No dependencies for fast startup
            initialization_function=_initialize_intent_first_router,
        )
    )

    # MEDIUM PRIORITY SERVICES (enhanced features)
    optimized_startup_manager.register_service(
        ServiceConfig(
            name="cache_manager",
            priority=ServicePriority.MEDIUM,
            strategy=InitializationStrategy.BACKGROUND,
            timeout_seconds=15.0,
            dependencies=[],
            initialization_function=_initialize_cache_manager,
            health_check=_health_check_cache,
        )
    )

    optimized_startup_manager.register_service(
        ServiceConfig(
            name="vector_store",
            priority=ServicePriority.MEDIUM,
            strategy=InitializationStrategy.BACKGROUND,
            timeout_seconds=20.0,
            dependencies=[],
            conditions={"env_var": "QDRANT_URL"},  # Only if Qdrant is configured
            initialization_function=_initialize_vector_store,
        )
    )

    optimized_startup_manager.register_service(
        ServiceConfig(
            name="cost_monitor",
            priority=ServicePriority.MEDIUM,
            strategy=InitializationStrategy.BACKGROUND,
            timeout_seconds=10.0,
            dependencies=[],
            initialization_function=_initialize_cost_monitor,
        )
    )

    # LOW PRIORITY SERVICES (optional features)
    optimized_startup_manager.register_service(
        ServiceConfig(
            name="memory_service",
            priority=ServicePriority.LOW,
            strategy=InitializationStrategy.BACKGROUND,
            timeout_seconds=60.0,  # Can take longer
            dependencies=[],
            conditions={"setting": "MEMORY_ENABLE_SYSTEM"},
            initialization_function=_initialize_memory_service,
            health_check=_health_check_memory,
        )
    )


    optimized_startup_manager.register_service(
        ServiceConfig(
            name="workflow_orchestrator",
            priority=ServicePriority.LOW,
            strategy=InitializationStrategy.BACKGROUND,
            timeout_seconds=10.0,
            dependencies=[],
            initialization_function=_initialize_workflow_orchestrator,
        )
    )

    app_logger.info(
        f"✅ Registered {len(optimized_startup_manager.services)} services for optimized startup"
    )
