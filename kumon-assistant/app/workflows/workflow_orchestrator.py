"""
Workflow Orchestrator

Centralized workflow management and orchestration system for the Kumon Assistant.
Provides unified workflow execution, monitoring, and coordination across all system components.

Features:
- Centralized workflow definition and execution
- Cross-component workflow coordination
- Workflow state management and persistence
- Performance monitoring integration
- Error handling and recovery mechanisms
- Workflow analytics and optimization
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from ..core.logger import app_logger
from ..core.config import settings
# Temporarily disable monitoring imports until dependencies are installed
# from ..monitoring.performance_monitor import performance_monitor
# from ..monitoring.alert_manager import alert_manager


class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class WorkflowPriority(Enum):
    """Workflow priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class WorkflowStep:
    """Individual workflow step definition"""
    step_id: str
    name: str
    description: str
    handler: Callable
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    retry_count: int = 3
    retry_delay_seconds: int = 5
    required: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowDefinition:
    """Workflow definition and configuration"""
    workflow_id: str
    name: str
    description: str
    version: str
    steps: List[WorkflowStep]
    priority: WorkflowPriority = WorkflowPriority.NORMAL
    timeout_seconds: int = 1800  # 30 minutes default
    max_concurrent_steps: int = 5
    retry_policy: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecution:
    """Workflow execution instance"""
    execution_id: str
    workflow_id: str
    status: WorkflowStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    current_step: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    step_results: Dict[str, Any] = field(default_factory=dict)
    error_messages: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)


class WorkflowOrchestrator:
    """
    Centralized workflow orchestration system
    
    Features:
    - Workflow definition management
    - Parallel and sequential step execution
    - Dependency resolution and management
    - Error handling and recovery
    - Performance monitoring integration
    - Workflow analytics and optimization
    """
    
    def __init__(self):
        # Workflow management
        self.workflow_definitions: Dict[str, WorkflowDefinition] = {}
        self.active_executions: Dict[str, WorkflowExecution] = {}
        self.execution_history: List[WorkflowExecution] = []
        
        # Orchestrator configuration
        self.config = {
            "max_concurrent_workflows": 10,
            "execution_timeout_seconds": 3600,  # 1 hour
            "cleanup_history_days": 7,
            "performance_monitoring": True,
            "enable_workflow_analytics": True,
            "auto_retry_failed_workflows": True,
            "retry_delay_minutes": 30
        }
        
        # Execution state
        self.orchestrator_active = True
        self.execution_semaphore = asyncio.Semaphore(self.config["max_concurrent_workflows"])
        
        # Initialize core workflows
        self._initialize_core_workflows()
        
        app_logger.info("Workflow Orchestrator initialized with centralized coordination")
    
    def _initialize_core_workflows(self):
        """Initialize core system workflows"""
        
        # 1. Message Processing Workflow
        message_workflow = WorkflowDefinition(
            workflow_id="message_processing",
            name="WhatsApp Message Processing",
            description="Complete message processing pipeline from webhook to response",
            version="1.0.0",
            steps=[
                WorkflowStep(
                    step_id="validate_message",
                    name="Message Validation",
                    description="Validate incoming message format and content",
                    handler=self._validate_message_step,
                    timeout_seconds=10
                ),
                WorkflowStep(
                    step_id="extract_intent",
                    name="Intent Extraction",
                    description="Extract user intent from message",
                    handler=self._extract_intent_step,
                    dependencies=["validate_message"],
                    timeout_seconds=30
                ),
                WorkflowStep(
                    step_id="process_conversation",
                    name="Conversation Processing",
                    description="Process conversation context and history",
                    handler=self._process_conversation_step,
                    dependencies=["extract_intent"],
                    timeout_seconds=60
                ),
                WorkflowStep(
                    step_id="generate_response",
                    name="Response Generation",
                    description="Generate AI response using RAG engine",
                    handler=self._generate_response_step,
                    dependencies=["process_conversation"],
                    timeout_seconds=120
                ),
                WorkflowStep(
                    step_id="send_response",
                    name="Response Delivery",
                    description="Send response back to user",
                    handler=self._send_response_step,
                    dependencies=["generate_response"],
                    timeout_seconds=30
                )
            ],
            priority=WorkflowPriority.HIGH,
            timeout_seconds=300
        )
        
        # 2. System Health Check Workflow
        health_check_workflow = WorkflowDefinition(
            workflow_id="system_health_check",
            name="System Health Verification",
            description="Comprehensive system health check and monitoring",
            version="1.0.0",
            steps=[
                WorkflowStep(
                    step_id="check_api_health",
                    name="API Health Check",
                    description="Verify API endpoints are responding",
                    handler=self._check_api_health_step,
                    timeout_seconds=30
                ),
                WorkflowStep(
                    step_id="check_database_health",
                    name="Database Health Check",
                    description="Verify database connectivity and performance",
                    handler=self._check_database_health_step,
                    timeout_seconds=60
                ),
                WorkflowStep(
                    step_id="check_services_health",
                    name="Services Health Check",
                    description="Verify all system services are operational",
                    handler=self._check_services_health_step,
                    timeout_seconds=90
                ),
                WorkflowStep(
                    step_id="generate_health_report",
                    name="Health Report Generation",
                    description="Generate comprehensive health report",
                    handler=self._generate_health_report_step,
                    dependencies=["check_api_health", "check_database_health", "check_services_health"],
                    timeout_seconds=30
                )
            ],
            priority=WorkflowPriority.NORMAL,
            timeout_seconds=300,
            max_concurrent_steps=3
        )
        
        # 3. Performance Optimization Workflow
        optimization_workflow = WorkflowDefinition(
            workflow_id="performance_optimization",
            name="Performance Optimization",
            description="Automated performance monitoring and optimization",
            version="1.0.0",
            steps=[
                WorkflowStep(
                    step_id="collect_metrics",
                    name="Metrics Collection",
                    description="Collect current performance metrics",
                    handler=self._collect_metrics_step,
                    timeout_seconds=60
                ),
                WorkflowStep(
                    step_id="analyze_performance",
                    name="Performance Analysis",
                    description="Analyze performance trends and bottlenecks",
                    handler=self._analyze_performance_step,
                    dependencies=["collect_metrics"],
                    timeout_seconds=120
                ),
                WorkflowStep(
                    step_id="identify_optimizations",
                    name="Optimization Identification",
                    description="Identify potential performance optimizations",
                    handler=self._identify_optimizations_step,
                    dependencies=["analyze_performance"],
                    timeout_seconds=90
                ),
                WorkflowStep(
                    step_id="apply_optimizations",
                    name="Apply Optimizations",
                    description="Apply safe performance optimizations",
                    handler=self._apply_optimizations_step,
                    dependencies=["identify_optimizations"],
                    timeout_seconds=180
                ),
                WorkflowStep(
                    step_id="validate_improvements",
                    name="Improvement Validation",
                    description="Validate performance improvements",
                    handler=self._validate_improvements_step,
                    dependencies=["apply_optimizations"],
                    timeout_seconds=120
                )
            ],
            priority=WorkflowPriority.NORMAL,
            timeout_seconds=900
        )
        
        # Store workflow definitions
        self.workflow_definitions = {
            message_workflow.workflow_id: message_workflow,
            health_check_workflow.workflow_id: health_check_workflow,
            optimization_workflow.workflow_id: optimization_workflow
        }
        
        app_logger.info(f"Initialized {len(self.workflow_definitions)} core workflows")
    
    def register_workflow(self, workflow: WorkflowDefinition):
        """Register a new workflow definition"""
        self.workflow_definitions[workflow.workflow_id] = workflow
        app_logger.info(f"Registered workflow: {workflow.name} (v{workflow.version})")
    
    async def execute_workflow(
        self,
        workflow_id: str,
        context: Optional[Dict[str, Any]] = None,
        priority: Optional[WorkflowPriority] = None
    ) -> str:
        """
        Execute a workflow and return execution ID
        
        Args:
            workflow_id: ID of workflow to execute
            context: Execution context data
            priority: Override workflow priority
            
        Returns:
            Execution ID for tracking
        """
        
        if workflow_id not in self.workflow_definitions:
            raise ValueError(f"Workflow '{workflow_id}' not found")
        
        workflow_def = self.workflow_definitions[workflow_id]
        execution_id = str(uuid.uuid4())
        
        # Create execution instance
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status=WorkflowStatus.PENDING,
            start_time=datetime.now(),
            context=context or {},
            metrics={"steps_planned": len(workflow_def.steps)}
        )
        
        # Override priority if specified
        if priority:
            workflow_def.priority = priority
        
        # Store execution
        self.active_executions[execution_id] = execution
        
        # Start execution in background
        asyncio.create_task(self._execute_workflow_internal(execution_id))
        
        app_logger.info(f"Started workflow execution: {workflow_def.name} (ID: {execution_id})")
        return execution_id
    
    async def _execute_workflow_internal(self, execution_id: str):
        """Internal workflow execution logic"""
        
        try:
            async with self.execution_semaphore:
                execution = self.active_executions[execution_id]
                workflow_def = self.workflow_definitions[execution.workflow_id]
                
                execution.status = WorkflowStatus.RUNNING
                app_logger.info(f"Executing workflow: {workflow_def.name}")
                
                # Track execution start
                start_time = datetime.now()
                execution.metrics["execution_start"] = start_time.isoformat()
                
                # Execute workflow steps
                await self._execute_workflow_steps(execution, workflow_def)
                
                # Calculate execution time
                end_time = datetime.now()
                execution.end_time = end_time
                execution_time = (end_time - start_time).total_seconds()
                execution.metrics["execution_time_seconds"] = execution_time
                
                # Determine final status
                if len(execution.failed_steps) == 0:
                    execution.status = WorkflowStatus.COMPLETED
                    app_logger.info(f"Workflow completed successfully: {workflow_def.name} ({execution_time:.1f}s)")
                else:
                    execution.status = WorkflowStatus.FAILED
                    app_logger.error(f"Workflow failed: {workflow_def.name} - {len(execution.failed_steps)} failed steps")
                
                # Move to history
                self.execution_history.append(execution)
                del self.active_executions[execution_id]
                
                # Send performance metrics
                if self.config["performance_monitoring"]:
                    await self._send_workflow_metrics(execution, workflow_def)
        
        except Exception as e:
            app_logger.error(f"Workflow execution error: {e}")
            if execution_id in self.active_executions:
                execution = self.active_executions[execution_id]
                execution.status = WorkflowStatus.FAILED
                execution.error_messages.append(str(e))
                execution.end_time = datetime.now()
                
                self.execution_history.append(execution)
                del self.active_executions[execution_id]
    
    async def _execute_workflow_steps(self, execution: WorkflowExecution, workflow_def: WorkflowDefinition):
        """Execute workflow steps with dependency resolution"""
        
        completed_steps = set()
        step_semaphore = asyncio.Semaphore(workflow_def.max_concurrent_steps)
        
        while len(completed_steps) < len(workflow_def.steps):
            # Find executable steps (dependencies satisfied)
            executable_steps = []
            for step in workflow_def.steps:
                if (step.step_id not in completed_steps and 
                    step.step_id not in execution.failed_steps and
                    all(dep in completed_steps for dep in step.dependencies)):
                    executable_steps.append(step)
            
            if not executable_steps:
                # Check for failed required steps
                required_failed = [s for s in workflow_def.steps 
                                 if s.step_id in execution.failed_steps and s.required]
                if required_failed:
                    execution.error_messages.append(f"Required steps failed: {[s.step_id for s in required_failed]}")
                    break
                
                # No more executable steps
                break
            
            # Execute steps in parallel
            tasks = []
            for step in executable_steps:
                task = asyncio.create_task(
                    self._execute_step_with_semaphore(step_semaphore, step, execution)
                )
                tasks.append((step.step_id, task))
            
            # Wait for completion
            for step_id, task in tasks:
                try:
                    success = await task
                    if success:
                        completed_steps.add(step_id)
                        execution.completed_steps.append(step_id)
                    else:
                        execution.failed_steps.append(step_id)
                except Exception as e:
                    app_logger.error(f"Step execution error ({step_id}): {e}")
                    execution.failed_steps.append(step_id)
                    execution.error_messages.append(f"{step_id}: {str(e)}")
    
    async def _execute_step_with_semaphore(self, semaphore: asyncio.Semaphore, step: WorkflowStep, execution: WorkflowExecution) -> bool:
        """Execute a single step with concurrency control"""
        
        async with semaphore:
            return await self._execute_step(step, execution)
    
    async def _execute_step(self, step: WorkflowStep, execution: WorkflowExecution) -> bool:
        """Execute a single workflow step"""
        
        app_logger.debug(f"Executing step: {step.name}")
        execution.current_step = step.step_id
        
        step_start_time = datetime.now()
        
        for attempt in range(step.retry_count + 1):
            try:
                # Execute step handler
                result = await asyncio.wait_for(
                    step.handler(execution.context, step.metadata),
                    timeout=step.timeout_seconds
                )
                
                # Store result
                execution.step_results[step.step_id] = result
                
                # Track step timing
                step_time = (datetime.now() - step_start_time).total_seconds()
                execution.metrics[f"step_{step.step_id}_time"] = step_time
                
                app_logger.debug(f"Step completed: {step.name} ({step_time:.1f}s)")
                return True
                
            except asyncio.TimeoutError:
                app_logger.warning(f"Step timeout: {step.name} (attempt {attempt + 1})")
                if attempt < step.retry_count:
                    await asyncio.sleep(step.retry_delay_seconds)
                else:
                    execution.error_messages.append(f"{step.step_id}: Timeout after {step.retry_count} retries")
                    
            except Exception as e:
                app_logger.error(f"Step error: {step.name} - {e} (attempt {attempt + 1})")
                if attempt < step.retry_count:
                    await asyncio.sleep(step.retry_delay_seconds)
                else:
                    execution.error_messages.append(f"{step.step_id}: {str(e)}")
        
        return False
    
    async def _send_workflow_metrics(self, execution: WorkflowExecution, workflow_def: WorkflowDefinition):
        """Send workflow execution metrics to monitoring system"""
        
        try:
            metrics = {
                "workflow_id": workflow_def.workflow_id,
                "execution_id": execution.execution_id,
                "status": execution.status.value,
                "execution_time": execution.metrics.get("execution_time_seconds", 0),
                "steps_completed": len(execution.completed_steps),
                "steps_failed": len(execution.failed_steps),
                "priority": workflow_def.priority.value
            }
            
            # Send to performance monitor (if available)
            await performance_monitor.track_workflow_execution(metrics)
            
        except Exception as e:
            app_logger.error(f"Failed to send workflow metrics: {e}")
    
    async def track_conversation_metrics(self, metrics: Dict[str, Any]):
        """
        Track conversation-specific metrics for LangGraph integration
        
        Args:
            metrics: Conversation metrics to track
        """
        try:
            # Store conversation metrics for analysis
            conversation_metrics = {
                "timestamp": datetime.now().isoformat(),
                "workflow_type": "langgraph_conversation",
                **metrics
            }
            
            # Send to performance monitor if available
            if hasattr(performance_monitor, 'track_conversation'):
                await performance_monitor.track_conversation(conversation_metrics)
            
            app_logger.info(f"Tracked conversation metrics for {metrics.get('phone_number')}")
            
        except Exception as e:
            app_logger.error(f"Failed to track conversation metrics: {e}")
    
    # Step Handler Methods (placeholder implementations)
    
    async def _validate_message_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Validate incoming message"""
        # Implementation would validate message format, content, etc.
        return {"valid": True, "message_type": "text"}
    
    async def _extract_intent_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user intent from message"""
        # Implementation would use intent classification
        return {"intent": "book_appointment", "confidence": 0.85}
    
    async def _process_conversation_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process conversation context"""
        # Implementation would handle conversation flow
        return {"conversation_state": "active", "context_updated": True}
    
    async def _generate_response_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI response"""
        # Implementation would use RAG engine
        return {"response": "Claro! Vou te ajudar a agendar uma avaliação.", "tokens_used": 150}
    
    async def _send_response_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Send response to user"""
        # Implementation would send via WhatsApp API
        return {"sent": True, "message_id": "msg_123"}
    
    async def _check_api_health_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Check API health"""
        return {"api_healthy": True, "response_time_ms": 45}
    
    async def _check_database_health_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Check database health"""
        return {"database_healthy": True, "connection_time_ms": 12}
    
    async def _check_services_health_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Check services health"""
        return {"services_healthy": True, "services_count": 8}
    
    async def _generate_health_report_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Generate health report"""
        return {"report_generated": True, "overall_health": "good"}
    
    async def _collect_metrics_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Collect performance metrics"""
        return {"metrics_collected": True, "data_points": 125}
    
    async def _analyze_performance_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance"""
        return {"analysis_complete": True, "bottlenecks_found": 2}
    
    async def _identify_optimizations_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Identify optimizations"""
        return {"optimizations_identified": True, "optimization_count": 3}
    
    async def _apply_optimizations_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Apply optimizations"""
        return {"optimizations_applied": True, "success_count": 2}
    
    async def _validate_improvements_step(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Validate improvements"""
        return {"validation_complete": True, "improvement_percentage": 15.5}
    
    # Workflow Management Methods
    
    def get_workflow_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow execution status"""
        
        # Check active executions
        if execution_id in self.active_executions:
            execution = self.active_executions[execution_id]
            workflow_def = self.workflow_definitions[execution.workflow_id]
            
            return {
                "execution_id": execution_id,
                "workflow_name": workflow_def.name,
                "status": execution.status.value,
                "progress": len(execution.completed_steps) / len(workflow_def.steps),
                "current_step": execution.current_step,
                "completed_steps": execution.completed_steps,
                "failed_steps": execution.failed_steps,
                "start_time": execution.start_time.isoformat(),
                "elapsed_time": (datetime.now() - execution.start_time).total_seconds()
            }
        
        # Check execution history
        for execution in self.execution_history:
            if execution.execution_id == execution_id:
                workflow_def = self.workflow_definitions[execution.workflow_id]
                
                return {
                    "execution_id": execution_id,
                    "workflow_name": workflow_def.name,
                    "status": execution.status.value,
                    "progress": len(execution.completed_steps) / len(workflow_def.steps),
                    "completed_steps": execution.completed_steps,
                    "failed_steps": execution.failed_steps,
                    "start_time": execution.start_time.isoformat(),
                    "end_time": execution.end_time.isoformat() if execution.end_time else None,
                    "total_time": execution.metrics.get("execution_time_seconds", 0)
                }
        
        return None
    
    def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get all active workflow executions"""
        
        active_workflows = []
        for execution_id, execution in self.active_executions.items():
            workflow_def = self.workflow_definitions[execution.workflow_id]
            
            active_workflows.append({
                "execution_id": execution_id,
                "workflow_name": workflow_def.name,
                "status": execution.status.value,
                "progress": len(execution.completed_steps) / len(workflow_def.steps),
                "start_time": execution.start_time.isoformat(),
                "elapsed_time": (datetime.now() - execution.start_time).total_seconds(),
                "priority": workflow_def.priority.value
            })
        
        return active_workflows
    
    def get_workflow_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Get workflow execution analytics"""
        
        cutoff_time = datetime.now() - timedelta(days=days)
        recent_executions = [
            e for e in self.execution_history
            if e.start_time > cutoff_time
        ]
        
        if not recent_executions:
            return {"message": "No recent executions"}
        
        # Calculate analytics
        total_executions = len(recent_executions)
        successful_executions = len([e for e in recent_executions if e.status == WorkflowStatus.COMPLETED])
        failed_executions = len([e for e in recent_executions if e.status == WorkflowStatus.FAILED])
        
        success_rate = (successful_executions / total_executions) * 100 if total_executions > 0 else 0
        
        # Execution times
        execution_times = [e.metrics.get("execution_time_seconds", 0) for e in recent_executions if e.metrics.get("execution_time_seconds")]
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
        
        # Workflow distribution
        workflow_counts = {}
        for execution in recent_executions:
            workflow_id = execution.workflow_id
            workflow_counts[workflow_id] = workflow_counts.get(workflow_id, 0) + 1
        
        return {
            "period_days": days,
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate_percent": round(success_rate, 1),
            "average_execution_time_seconds": round(avg_execution_time, 1),
            "workflow_distribution": workflow_counts,
            "active_workflows_count": len(self.active_executions)
        }
    
    async def cancel_workflow(self, execution_id: str) -> bool:
        """Cancel an active workflow execution"""
        
        if execution_id in self.active_executions:
            execution = self.active_executions[execution_id]
            execution.status = WorkflowStatus.CANCELLED
            execution.end_time = datetime.now()
            
            # Move to history
            self.execution_history.append(execution)
            del self.active_executions[execution_id]
            
            app_logger.info(f"Cancelled workflow execution: {execution_id}")
            return True
        
        return False
    
    async def cleanup_old_executions(self):
        """Cleanup old execution history"""
        
        cutoff_time = datetime.now() - timedelta(days=self.config["cleanup_history_days"])
        
        old_count = len(self.execution_history)
        self.execution_history = [
            e for e in self.execution_history
            if e.start_time > cutoff_time
        ]
        new_count = len(self.execution_history)
        
        if old_count > new_count:
            app_logger.info(f"Cleaned up {old_count - new_count} old workflow executions")


# Global workflow orchestrator instance
workflow_orchestrator = WorkflowOrchestrator()