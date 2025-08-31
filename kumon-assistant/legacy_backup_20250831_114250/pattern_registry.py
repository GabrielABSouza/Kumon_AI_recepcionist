"""
Wave 6: Workflow Pattern Registry
Central registry for managing and coordinating workflow patterns
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ..core.config import settings
from ..core.logger import app_logger
from .conversation_workflow_patterns import (
    ConversationInput,
    ConversationResult,
    create_basic_conversation_pattern,
    create_fallback_conversation_pattern,
    create_high_priority_conversation_pattern,
)
from .enhanced_workflow_patterns import (
    ExecutionStrategy,
    NodeResult,
    WorkflowContext,
    WorkflowPriority,
    enhanced_workflow_engine,
)


class PatternType(Enum):
    """Types of workflow patterns"""

    CONVERSATION = "conversation"
    SYSTEM = "system"
    MAINTENANCE = "maintenance"
    MONITORING = "monitoring"


@dataclass
class PatternRegistration:
    """Pattern registration information"""

    pattern_id: str
    pattern_type: PatternType
    priority: WorkflowPriority
    enabled: bool = True
    created_at: float = 0.0
    last_used: Optional[float] = None
    usage_count: int = 0
    success_rate: float = 1.0
    avg_execution_time: float = 0.0
    description: str = ""

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


class WorkflowPatternRegistry:
    """Central registry for managing workflow patterns"""

    def __init__(self):
        self.registrations: Dict[str, PatternRegistration] = {}
        self.execution_history: List[Dict[str, Any]] = []
        self.pattern_cache: Dict[str, Any] = {}
        self.pattern_locks: Dict[str, asyncio.Lock] = {}
        self.health_check_interval = 300.0  # 5 minutes
        self.last_health_check = 0.0
        self.system_metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_execution_time": 0.0,
            "patterns_registered": 0,
            "patterns_enabled": 0,
        }

    async def initialize(self):
        """Initialize the pattern registry with default patterns"""
        app_logger.info("🔄 Initializing Workflow Pattern Registry...")

        try:
            # Register conversation patterns
            await self._register_conversation_patterns()

            # Register system patterns
            await self._register_system_patterns()

            # Start background health monitoring
            asyncio.create_task(self._health_monitor_loop())

            app_logger.info(
                f"✅ Pattern Registry initialized with {len(self.registrations)} patterns"
            )

        except Exception as e:
            app_logger.error(f"❌ Failed to initialize Pattern Registry: {e}")
            raise

    async def _register_conversation_patterns(self):
        """Register conversation-specific patterns"""

        # Basic conversation pattern
        basic_pattern = create_basic_conversation_pattern()
        enhanced_workflow_engine.register_pattern(basic_pattern)
        self._register_pattern_info(
            pattern_id="basic_conversation",
            pattern_type=PatternType.CONVERSATION,
            priority=WorkflowPriority.MEDIUM,
            description="Standard conversation processing workflow",
        )

        # High priority conversation pattern
        high_priority_pattern = create_high_priority_conversation_pattern()
        enhanced_workflow_engine.register_pattern(high_priority_pattern)
        self._register_pattern_info(
            pattern_id="high_priority_conversation",
            pattern_type=PatternType.CONVERSATION,
            priority=WorkflowPriority.HIGH,
            description="Optimized conversation processing for urgent messages",
        )

        # Fallback conversation pattern
        fallback_pattern = create_fallback_conversation_pattern()
        enhanced_workflow_engine.register_pattern(fallback_pattern)
        self._register_pattern_info(
            pattern_id="fallback_conversation",
            pattern_type=PatternType.CONVERSATION,
            priority=WorkflowPriority.LOW,
            description="Fallback conversation processing when services unavailable",
        )

        app_logger.info("✅ Conversation patterns registered")

    async def _register_system_patterns(self):
        """Register system-specific patterns"""

        # Health check pattern (placeholder for future implementation)
        # System patterns can be added here as they are developed

        app_logger.info("✅ System patterns registered")

    def _register_pattern_info(
        self,
        pattern_id: str,
        pattern_type: PatternType,
        priority: WorkflowPriority,
        description: str = "",
        enabled: bool = True,
    ):
        """Register pattern information"""
        registration = PatternRegistration(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            priority=priority,
            enabled=enabled,
            description=description,
        )

        self.registrations[pattern_id] = registration
        self.pattern_locks[pattern_id] = asyncio.Lock()
        self.system_metrics["patterns_registered"] += 1

        if enabled:
            self.system_metrics["patterns_enabled"] += 1

    async def execute_conversation_pattern(
        self,
        message_text: str,
        user_id: str,
        unit_id: Optional[str] = None,
        phone_number: str = "",
        priority: WorkflowPriority = WorkflowPriority.MEDIUM,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute conversation pattern with automatic pattern selection"""

        # Determine pattern based on priority and system health
        pattern_id = await self._select_conversation_pattern(priority)

        # Create conversation input
        conversation_input = ConversationInput(
            user_id=user_id,
            unit_id=unit_id,
            message_text=message_text,
            phone_number=phone_number,
            context=kwargs,
        )

        # Create workflow context
        execution_id = str(uuid.uuid4())
        workflow_context = WorkflowContext(
            workflow_id=pattern_id,
            execution_id=execution_id,
            user_id=user_id,
            unit_id=unit_id,
            priority=priority,
            metadata={"pattern_type": "conversation", "phone_number": phone_number, **kwargs},
        )

        # Execute pattern
        return await self._execute_pattern_with_monitoring(
            pattern_id, conversation_input, workflow_context
        )

    async def _select_conversation_pattern(self, priority: WorkflowPriority) -> str:
        """Select appropriate conversation pattern based on priority and system health"""

        # Check system health
        system_healthy = await self._check_system_health()

        if not system_healthy:
            app_logger.warning("System unhealthy, using fallback pattern")
            return "fallback_conversation"

        # Select pattern based on priority
        if priority == WorkflowPriority.CRITICAL or priority == WorkflowPriority.HIGH:
            pattern_id = "high_priority_conversation"
        else:
            pattern_id = "basic_conversation"

        # Check if selected pattern is enabled and healthy
        if not self._is_pattern_healthy(pattern_id):
            app_logger.warning(f"Pattern {pattern_id} unhealthy, using fallback")
            return "fallback_conversation"

        return pattern_id

    async def _execute_pattern_with_monitoring(
        self, pattern_id: str, input_data: Any, context: WorkflowContext
    ) -> Dict[str, Any]:
        """Execute pattern with comprehensive monitoring and error handling"""

        start_time = time.time()
        execution_successful = False
        error_message = None

        async with self.pattern_locks[pattern_id]:
            try:
                # Update pattern usage
                if pattern_id in self.registrations:
                    self.registrations[pattern_id].usage_count += 1
                    self.registrations[pattern_id].last_used = start_time

                # Execute pattern
                results = await enhanced_workflow_engine.execute_pattern(
                    pattern_id, input_data, context
                )

                # Check if execution was successful
                failed_nodes = [r for r in results.values() if r.status.name == "FAILED"]
                execution_successful = len(failed_nodes) == 0

                # Extract conversation result if available
                conversation_result = self._extract_conversation_result(results)

                execution_time = time.time() - start_time

                # Update metrics
                self._update_pattern_metrics(pattern_id, execution_successful, execution_time)

                # Store execution history
                self._store_execution_history(
                    pattern_id, context, execution_time, execution_successful, results
                )

                # Return structured response
                return {
                    "success": execution_successful,
                    "pattern_id": pattern_id,
                    "execution_id": context.execution_id,
                    "execution_time": execution_time,
                    "results": conversation_result,
                    "node_results": {k: self._serialize_node_result(v) for k, v in results.items()},
                    "failed_nodes": len(failed_nodes),
                    "metadata": {
                        "user_id": context.user_id,
                        "unit_id": context.unit_id,
                        "priority": context.priority.value,
                    },
                }

            except Exception as e:
                execution_time = time.time() - start_time
                error_message = str(e)

                app_logger.error(f"Pattern execution failed: {pattern_id} - {e}")

                # Update metrics
                self._update_pattern_metrics(pattern_id, False, execution_time)

                # Store failed execution
                self._store_execution_history(
                    pattern_id, context, execution_time, False, {}, error_message
                )

                # Try fallback pattern if original pattern failed and it's not already fallback
                if pattern_id != "fallback_conversation":
                    app_logger.info("Attempting fallback pattern...")

                    try:
                        fallback_context = context.with_metadata(fallback_reason=error_message)
                        return await self._execute_pattern_with_monitoring(
                            "fallback_conversation", input_data, fallback_context
                        )
                    except Exception as fallback_error:
                        app_logger.error(f"Fallback pattern also failed: {fallback_error}")

                # Return error response
                return {
                    "success": False,
                    "pattern_id": pattern_id,
                    "execution_id": context.execution_id,
                    "execution_time": execution_time,
                    "error": error_message,
                    "results": {
                        "response_text": "Desculpe, estou enfrentando dificuldades técnicas no momento. Tente novamente em alguns instantes.",
                        "response_type": "text",
                        "intent": "error",
                        "confidence": 0.0,
                        "metadata": {"error": True, "fallback": True},
                    },
                }

    def _extract_conversation_result(self, results: Dict[str, NodeResult]) -> Dict[str, Any]:
        """Extract conversation result from workflow execution results"""

        # Look for response postprocessing result first
        if "response_postprocessing" in results:
            result = results["response_postprocessing"]
            if result.status.name == "COMPLETED" and isinstance(result.data, ConversationResult):
                return {
                    "response_text": result.data.response_text,
                    "response_type": result.data.response_type,
                    "intent": result.data.intent,
                    "confidence": result.data.confidence,
                    "metadata": result.data.metadata,
                }

        # Fallback to response generation result
        if "response_generation" in results:
            result = results["response_generation"]
            if result.status.name == "COMPLETED" and isinstance(result.data, ConversationResult):
                return {
                    "response_text": result.data.response_text,
                    "response_type": result.data.response_type,
                    "intent": result.data.intent,
                    "confidence": result.data.confidence,
                    "metadata": result.data.metadata,
                }

        # Fallback response
        return {
            "response_text": "Desculpe, não foi possível processar sua mensagem no momento.",
            "response_type": "text",
            "intent": "error",
            "confidence": 0.0,
            "metadata": {"error": True},
        }

    def _serialize_node_result(self, result: NodeResult) -> Dict[str, Any]:
        """Serialize node result for JSON response"""
        return {
            "node_id": result.node_id,
            "status": result.status.name,
            "execution_time": result.execution_time,
            "retry_count": result.retry_count,
            "has_error": result.error is not None,
            "error_message": str(result.error) if result.error else None,
            "metadata": result.metadata,
        }

    def _update_pattern_metrics(self, pattern_id: str, success: bool, execution_time: float):
        """Update pattern and system metrics"""

        # Update system metrics
        self.system_metrics["total_executions"] += 1
        self.system_metrics["total_execution_time"] += execution_time

        if success:
            self.system_metrics["successful_executions"] += 1
        else:
            self.system_metrics["failed_executions"] += 1

        # Update pattern metrics
        if pattern_id in self.registrations:
            registration = self.registrations[pattern_id]

            # Calculate new success rate
            total_executions = registration.usage_count
            if total_executions > 0:
                successful_executions = int(registration.success_rate * (total_executions - 1))
                if success:
                    successful_executions += 1

                registration.success_rate = successful_executions / total_executions
            else:
                registration.success_rate = 1.0 if success else 0.0

            # Calculate new average execution time
            if total_executions > 0:
                total_time = registration.avg_execution_time * (total_executions - 1)
                registration.avg_execution_time = (total_time + execution_time) / total_executions
            else:
                registration.avg_execution_time = execution_time

    def _store_execution_history(
        self,
        pattern_id: str,
        context: WorkflowContext,
        execution_time: float,
        success: bool,
        results: Dict[str, NodeResult],
        error_message: Optional[str] = None,
    ):
        """Store execution history for analytics"""

        history_entry = {
            "pattern_id": pattern_id,
            "execution_id": context.execution_id,
            "user_id": context.user_id,
            "unit_id": context.unit_id,
            "priority": context.priority.value,
            "execution_time": execution_time,
            "success": success,
            "node_count": len(results),
            "failed_nodes": len([r for r in results.values() if r.status.name == "FAILED"]),
            "timestamp": time.time(),
            "error_message": error_message,
            "metadata": context.metadata,
        }

        self.execution_history.append(history_entry)

        # Keep history size manageable
        if len(self.execution_history) > 2000:
            self.execution_history = self.execution_history[-1000:]

    async def _check_system_health(self) -> bool:
        """Check overall system health"""
        try:
            from ..core import dependencies

            # Check critical services
            services_healthy = (
                dependencies.llm_service is not None and dependencies.intent_classifier is not None
            )

            # Check pattern success rates
            patterns_healthy = True
            for registration in self.registrations.values():
                if registration.enabled and registration.success_rate < 0.5:
                    patterns_healthy = False
                    break

            return services_healthy and patterns_healthy

        except Exception as e:
            app_logger.warning(f"Health check failed: {e}")
            return False

    def _is_pattern_healthy(self, pattern_id: str) -> bool:
        """Check if a specific pattern is healthy"""
        if pattern_id not in self.registrations:
            return False

        registration = self.registrations[pattern_id]
        return (
            registration.enabled
            and registration.success_rate > 0.7
            and registration.avg_execution_time < 120.0  # 2 minutes
        )

    async def _health_monitor_loop(self):
        """Background health monitoring loop"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)

                current_time = time.time()
                self.last_health_check = current_time

                # Perform health checks
                system_healthy = await self._check_system_health()

                if not system_healthy:
                    app_logger.warning("System health check failed")

                # Update pattern health status
                for pattern_id, registration in self.registrations.items():
                    healthy = self._is_pattern_healthy(pattern_id)
                    if not healthy and registration.enabled:
                        app_logger.warning(f"Pattern {pattern_id} is unhealthy")

                app_logger.debug("Pattern registry health check completed")

            except Exception as e:
                app_logger.error(f"Health monitor loop error: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    def get_pattern_info(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific pattern"""
        if pattern_id not in self.registrations:
            return None

        registration = self.registrations[pattern_id]
        engine_metrics = enhanced_workflow_engine.get_pattern_metrics(pattern_id)

        return {
            **registration.__dict__,
            "engine_metrics": engine_metrics,
            "healthy": self._is_pattern_healthy(pattern_id),
        }

    def list_patterns(self, pattern_type: Optional[PatternType] = None) -> List[Dict[str, Any]]:
        """List all registered patterns"""
        patterns = []

        for pattern_id, registration in self.registrations.items():
            if pattern_type is None or registration.pattern_type == pattern_type:
                pattern_info = self.get_pattern_info(pattern_id)
                if pattern_info:
                    patterns.append(pattern_info)

        return patterns

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get overall system metrics"""
        engine_metrics = enhanced_workflow_engine.get_system_metrics()

        return {
            **self.system_metrics,
            "engine_metrics": engine_metrics,
            "last_health_check": self.last_health_check,
            "execution_history_size": len(self.execution_history),
            "avg_execution_time": (
                self.system_metrics["total_execution_time"]
                / self.system_metrics["total_executions"]
                if self.system_metrics["total_executions"] > 0
                else 0.0
            ),
            "success_rate": (
                self.system_metrics["successful_executions"]
                / self.system_metrics["total_executions"]
                if self.system_metrics["total_executions"] > 0
                else 0.0
            ),
        }

    def enable_pattern(self, pattern_id: str) -> bool:
        """Enable a pattern"""
        if pattern_id in self.registrations:
            if not self.registrations[pattern_id].enabled:
                self.registrations[pattern_id].enabled = True
                self.system_metrics["patterns_enabled"] += 1
                app_logger.info(f"Pattern {pattern_id} enabled")
            return True
        return False

    def disable_pattern(self, pattern_id: str) -> bool:
        """Disable a pattern"""
        if pattern_id in self.registrations:
            if self.registrations[pattern_id].enabled:
                self.registrations[pattern_id].enabled = False
                self.system_metrics["patterns_enabled"] -= 1
                app_logger.info(f"Pattern {pattern_id} disabled")
            return True
        return False


# Global pattern registry instance
workflow_pattern_registry = WorkflowPatternRegistry()
