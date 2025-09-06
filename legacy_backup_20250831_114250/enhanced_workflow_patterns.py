"""
Wave 6: Enhanced Workflow Patterns System
Advanced workflow orchestration with pattern-based execution, adaptive routing, and intelligent caching
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Set, TypeVar, Union

from ..core.config import settings
from ..core.logger import app_logger

T = TypeVar("T")
R = TypeVar("R")


class WorkflowPriority(Enum):
    """Workflow execution priority levels"""

    CRITICAL = "critical"  # Immediate execution (health checks, security)
    HIGH = "high"  # User-facing operations (message processing)
    MEDIUM = "medium"  # Background processing (analytics, optimization)
    LOW = "low"  # Maintenance tasks (cleanup, reports)


class ExecutionStrategy(Enum):
    """Workflow execution strategies"""

    SEQUENTIAL = "sequential"  # Execute nodes one by one
    PARALLEL = "parallel"  # Execute independent nodes concurrently
    ADAPTIVE = "adaptive"  # Dynamic strategy based on conditions
    PIPELINE = "pipeline"  # Stream processing with overlapping execution


class NodeStatus(Enum):
    """Workflow node execution status"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


@dataclass
class WorkflowContext:
    """Enhanced workflow execution context"""

    workflow_id: str
    execution_id: str
    user_id: Optional[str] = None
    unit_id: Optional[str] = None
    priority: WorkflowPriority = WorkflowPriority.MEDIUM
    strategy: ExecutionStrategy = ExecutionStrategy.ADAPTIVE
    max_retries: int = 3
    timeout_seconds: float = 120.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def with_metadata(self, **kwargs) -> "WorkflowContext":
        """Create a new context with additional metadata"""
        new_metadata = {**self.metadata, **kwargs}
        return WorkflowContext(
            workflow_id=self.workflow_id,
            execution_id=self.execution_id,
            user_id=self.user_id,
            unit_id=self.unit_id,
            priority=self.priority,
            strategy=self.strategy,
            max_retries=self.max_retries,
            timeout_seconds=self.timeout_seconds,
            metadata=new_metadata,
            created_at=self.created_at,
        )


@dataclass
class NodeResult:
    """Workflow node execution result"""

    node_id: str
    status: NodeStatus
    data: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowNode(ABC, Generic[T, R]):
    """Abstract base class for workflow nodes"""

    def __init__(
        self,
        node_id: str,
        name: str,
        description: str = "",
        timeout: float = 60.0,
        retries: int = 3,
        dependencies: Optional[List[str]] = None,
    ):
        self.node_id = node_id
        self.name = name
        self.description = description
        self.timeout = timeout
        self.retries = retries
        self.dependencies = dependencies or []
        self.execution_count = 0
        self.total_execution_time = 0.0
        self.success_count = 0
        self.failure_count = 0

    @abstractmethod
    async def execute(self, input_data: T, context: WorkflowContext) -> R:
        """Execute the node logic"""
        pass

    async def validate_input(self, input_data: T, context: WorkflowContext) -> bool:
        """Validate input data before execution"""
        return True

    async def handle_error(self, error: Exception, context: WorkflowContext) -> Optional[R]:
        """Handle execution errors with potential recovery"""
        app_logger.error(f"Node {self.node_id} error: {error}")
        return None

    def get_metrics(self) -> Dict[str, Any]:
        """Get node performance metrics"""
        avg_execution_time = (
            self.total_execution_time / self.execution_count if self.execution_count > 0 else 0.0
        )
        success_rate = (
            self.success_count / self.execution_count if self.execution_count > 0 else 0.0
        )

        return {
            "node_id": self.node_id,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": success_rate,
            "avg_execution_time": avg_execution_time,
            "total_execution_time": self.total_execution_time,
        }


class ConditionalNode(WorkflowNode[T, R]):
    """Node with conditional execution logic"""

    def __init__(
        self,
        node_id: str,
        name: str,
        condition_func: Callable[[T, WorkflowContext], bool],
        true_node: WorkflowNode[T, R],
        false_node: Optional[WorkflowNode[T, R]] = None,
        **kwargs,
    ):
        super().__init__(node_id, name, **kwargs)
        self.condition_func = condition_func
        self.true_node = true_node
        self.false_node = false_node

    async def execute(self, input_data: T, context: WorkflowContext) -> R:
        """Execute conditional logic"""
        try:
            condition_result = self.condition_func(input_data, context)

            if condition_result:
                return await self.true_node.execute(input_data, context)
            elif self.false_node:
                return await self.false_node.execute(input_data, context)
            else:
                # Return input data unchanged if no false branch
                return input_data

        except Exception as e:
            app_logger.error(f"Conditional node {self.node_id} error: {e}")
            raise


class ParallelNode(WorkflowNode[List[T], List[R]]):
    """Node that executes multiple sub-nodes in parallel"""

    def __init__(
        self,
        node_id: str,
        name: str,
        sub_nodes: List[WorkflowNode[T, R]],
        max_concurrent: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(node_id, name, **kwargs)
        self.sub_nodes = sub_nodes
        self.max_concurrent = max_concurrent or len(sub_nodes)

    async def execute(self, input_data: List[T], context: WorkflowContext) -> List[R]:
        """Execute sub-nodes in parallel with concurrency control"""
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def execute_with_semaphore(node: WorkflowNode[T, R], data: T) -> R:
            async with semaphore:
                return await node.execute(data, context)

        tasks = [
            execute_with_semaphore(node, data) for node, data in zip(self.sub_nodes, input_data)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                app_logger.error(f"Parallel node {self.node_id} sub-node {i} failed: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)

        return processed_results


class CachedNode(WorkflowNode[T, R]):
    """Node with intelligent caching capabilities"""

    def __init__(
        self,
        node_id: str,
        name: str,
        cache_ttl: float = 300.0,  # 5 minutes default
        cache_key_func: Optional[Callable[[T, WorkflowContext], str]] = None,
        **kwargs,
    ):
        super().__init__(node_id, name, **kwargs)
        self.cache_ttl = cache_ttl
        self.cache_key_func = cache_key_func or self._default_cache_key
        self.cache: Dict[str, tuple] = {}  # (data, timestamp)

    def _default_cache_key(self, input_data: T, context: WorkflowContext) -> str:
        """Default cache key generation"""
        return f"{self.node_id}:{hash(str(input_data))}"

    async def execute(self, input_data: T, context: WorkflowContext) -> R:
        """Execute with caching logic"""
        cache_key = self.cache_key_func(input_data, context)
        current_time = time.time()

        # Check cache
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if current_time - cached_time < self.cache_ttl:
                app_logger.debug(f"Cache hit for node {self.node_id}")
                return cached_data
            else:
                # Remove expired entry
                del self.cache[cache_key]

        # Execute and cache result
        result = await self._execute_impl(input_data, context)
        self.cache[cache_key] = (result, current_time)

        return result

    @abstractmethod
    async def _execute_impl(self, input_data: T, context: WorkflowContext) -> R:
        """Implementation-specific execution logic"""
        pass


class WorkflowPattern:
    """Base class for reusable workflow patterns"""

    def __init__(self, pattern_id: str, name: str, description: str = ""):
        self.pattern_id = pattern_id
        self.name = name
        self.description = description
        self.nodes: Dict[str, WorkflowNode] = {}
        self.execution_order: List[str] = []
        self.node_dependencies: Dict[str, Set[str]] = {}

    def add_node(self, node: WorkflowNode, dependencies: Optional[List[str]] = None):
        """Add a node to the workflow pattern"""
        self.nodes[node.node_id] = node
        self.node_dependencies[node.node_id] = set(dependencies or [])

        # Update execution order based on dependencies
        self._update_execution_order()

    def _update_execution_order(self):
        """Update execution order using topological sort"""
        # Simplified topological sort for dependency ordering
        visited = set()
        temp_visited = set()
        order = []

        def visit(node_id: str):
            if node_id in temp_visited:
                raise ValueError(f"Circular dependency detected involving {node_id}")
            if node_id in visited:
                return

            temp_visited.add(node_id)

            for dep in self.node_dependencies.get(node_id, set()):
                if dep in self.nodes:
                    visit(dep)

            temp_visited.remove(node_id)
            visited.add(node_id)
            order.append(node_id)

        for node_id in self.nodes:
            if node_id not in visited:
                visit(node_id)

        self.execution_order = order

    async def execute(self, input_data: Any, context: WorkflowContext) -> Dict[str, NodeResult]:
        """Execute the workflow pattern"""
        results: Dict[str, NodeResult] = {}
        node_outputs: Dict[str, Any] = {"input": input_data}

        for node_id in self.execution_order:
            node = self.nodes[node_id]
            start_time = time.time()

            try:
                # Check if dependencies are satisfied
                for dep_id in self.node_dependencies[node_id]:
                    if dep_id not in results or results[dep_id].status != NodeStatus.COMPLETED:
                        # Dependency failed, skip this node
                        results[node_id] = NodeResult(
                            node_id=node_id,
                            status=NodeStatus.SKIPPED,
                            metadata={"reason": f"Dependency {dep_id} not satisfied"},
                        )
                        continue

                # Validate input
                node_input = self._get_node_input(node_id, node_outputs, context)
                if not await node.validate_input(node_input, context):
                    results[node_id] = NodeResult(
                        node_id=node_id,
                        status=NodeStatus.FAILED,
                        error=ValueError("Input validation failed"),
                    )
                    continue

                # Execute node with timeout and retries
                result_data = await self._execute_node_with_retry(node, node_input, context)

                execution_time = time.time() - start_time

                # Store successful result
                results[node_id] = NodeResult(
                    node_id=node_id,
                    status=NodeStatus.COMPLETED,
                    data=result_data,
                    execution_time=execution_time,
                )

                # Store output for next nodes
                node_outputs[node_id] = result_data

                # Update node metrics
                node.execution_count += 1
                node.total_execution_time += execution_time
                node.success_count += 1

            except Exception as e:
                execution_time = time.time() - start_time

                results[node_id] = NodeResult(
                    node_id=node_id,
                    status=NodeStatus.FAILED,
                    error=e,
                    execution_time=execution_time,
                )

                # Update node metrics
                node.execution_count += 1
                node.total_execution_time += execution_time
                node.failure_count += 1

                app_logger.error(f"Workflow pattern {self.pattern_id} node {node_id} failed: {e}")

        return results

    def _get_node_input(
        self, node_id: str, outputs: Dict[str, Any], context: WorkflowContext
    ) -> Any:
        """Get input data for a specific node"""
        dependencies = self.node_dependencies[node_id]

        if not dependencies:
            # No dependencies, use original input
            return outputs.get("input")
        elif len(dependencies) == 1:
            # Single dependency, use its output
            dep_id = list(dependencies)[0]
            return outputs.get(dep_id)
        else:
            # Multiple dependencies, combine outputs
            return {dep_id: outputs.get(dep_id) for dep_id in dependencies}

    async def _execute_node_with_retry(
        self, node: WorkflowNode, input_data: Any, context: WorkflowContext
    ) -> Any:
        """Execute node with retry logic"""
        last_exception = None

        for attempt in range(context.max_retries + 1):
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    node.execute(input_data, context), timeout=node.timeout
                )
                return result

            except asyncio.TimeoutError as e:
                last_exception = e
                app_logger.warning(f"Node {node.node_id} timeout on attempt {attempt + 1}")

            except Exception as e:
                last_exception = e
                app_logger.warning(f"Node {node.node_id} failed on attempt {attempt + 1}: {e}")

                # Try node-specific error handling
                recovery_result = await node.handle_error(e, context)
                if recovery_result is not None:
                    return recovery_result

            # Wait before retry (exponential backoff)
            if attempt < context.max_retries:
                wait_time = min(2**attempt, 30)  # Max 30 seconds
                await asyncio.sleep(wait_time)

        # All retries failed
        raise last_exception


class EnhancedWorkflowEngine:
    """Advanced workflow engine with pattern support and optimization"""

    def __init__(self, max_concurrent_workflows: int = 10):
        self.patterns: Dict[str, WorkflowPattern] = {}
        self.active_workflows: Dict[str, asyncio.Task] = {}
        self.workflow_history: List[Dict[str, Any]] = []
        self.max_concurrent = max_concurrent_workflows
        self.semaphore = asyncio.Semaphore(max_concurrent_workflows)
        self.metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_execution_time": 0.0,
        }

    def register_pattern(self, pattern: WorkflowPattern):
        """Register a workflow pattern"""
        self.patterns[pattern.pattern_id] = pattern
        app_logger.info(f"Registered workflow pattern: {pattern.pattern_id}")

    async def execute_pattern(
        self, pattern_id: str, input_data: Any, context: WorkflowContext
    ) -> Dict[str, NodeResult]:
        """Execute a registered workflow pattern"""
        if pattern_id not in self.patterns:
            raise ValueError(f"Workflow pattern '{pattern_id}' not found")

        pattern = self.patterns[pattern_id]

        async with self.semaphore:
            start_time = time.time()

            try:
                # Execute pattern
                results = await pattern.execute(input_data, context)

                # Update metrics
                execution_time = time.time() - start_time
                self.metrics["total_executions"] += 1
                self.metrics["total_execution_time"] += execution_time

                # Check if execution was successful
                failed_nodes = [r for r in results.values() if r.status == NodeStatus.FAILED]
                if not failed_nodes:
                    self.metrics["successful_executions"] += 1
                else:
                    self.metrics["failed_executions"] += 1

                # Store in history
                self.workflow_history.append(
                    {
                        "pattern_id": pattern_id,
                        "execution_id": context.execution_id,
                        "execution_time": execution_time,
                        "success": len(failed_nodes) == 0,
                        "node_count": len(results),
                        "failed_nodes": len(failed_nodes),
                        "timestamp": time.time(),
                    }
                )

                # Keep history size manageable
                if len(self.workflow_history) > 1000:
                    self.workflow_history = self.workflow_history[-500:]

                return results

            except Exception as e:
                execution_time = time.time() - start_time
                self.metrics["total_executions"] += 1
                self.metrics["failed_executions"] += 1
                self.metrics["total_execution_time"] += execution_time

                app_logger.error(f"Workflow pattern {pattern_id} execution failed: {e}")
                raise

    def get_pattern_metrics(self, pattern_id: str) -> Dict[str, Any]:
        """Get metrics for a specific pattern"""
        if pattern_id not in self.patterns:
            return {}

        pattern = self.patterns[pattern_id]
        node_metrics = {node_id: node.get_metrics() for node_id, node in pattern.nodes.items()}

        # Calculate pattern-level metrics
        pattern_executions = [h for h in self.workflow_history if h["pattern_id"] == pattern_id]

        if pattern_executions:
            success_rate = sum(1 for h in pattern_executions if h["success"]) / len(
                pattern_executions
            )
            avg_execution_time = sum(h["execution_time"] for h in pattern_executions) / len(
                pattern_executions
            )
        else:
            success_rate = 0.0
            avg_execution_time = 0.0

        return {
            "pattern_id": pattern_id,
            "pattern_name": pattern.name,
            "total_executions": len(pattern_executions),
            "success_rate": success_rate,
            "avg_execution_time": avg_execution_time,
            "node_metrics": node_metrics,
        }

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get overall system metrics"""
        return {
            **self.metrics,
            "registered_patterns": len(self.patterns),
            "active_workflows": len(self.active_workflows),
            "avg_execution_time": (
                self.metrics["total_execution_time"] / self.metrics["total_executions"]
                if self.metrics["total_executions"] > 0
                else 0.0
            ),
        }


# Global workflow engine instance
enhanced_workflow_engine = EnhancedWorkflowEngine()
