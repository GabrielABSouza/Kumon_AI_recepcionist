"""
Workflow State Repository - Wave 3 Implementation
PostgreSQL persistence for workflow state with recovery capabilities
"""

import asyncio
import json
import uuid
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

import asyncpg
from ..core.config import settings
from ..core.logger import app_logger


class WorkflowStage(Enum):
    """Workflow stage enumeration"""
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    INFORMATION = "information"
    SCHEDULING = "scheduling"
    VALIDATION = "validation"
    CONFIRMATION = "confirmation"
    HANDOFF = "handoff"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class WorkflowState:
    """Workflow state data structure"""
    id: Optional[str] = None
    phone_number: str = ""
    thread_id: str = ""
    current_stage: str = WorkflowStage.GREETING.value
    current_step: Optional[str] = None
    state_data: Dict[str, Any] = None
    conversation_history: List[Dict[str, Any]] = None
    user_profile: Dict[str, Any] = None
    detected_intent: Optional[str] = None
    scheduling_data: Dict[str, Any] = None
    validation_status: Optional[str] = None
    last_activity: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message_count: int = 0
    total_processing_time_ms: float = 0.0
    
    def __post_init__(self):
        if self.state_data is None:
            self.state_data = {}
        if self.conversation_history is None:
            self.conversation_history = []
        if self.user_profile is None:
            self.user_profile = {}
        if self.scheduling_data is None:
            self.scheduling_data = {}


@dataclass
class WorkflowCheckpoint:
    """Workflow checkpoint for recovery"""
    id: Optional[str] = None
    thread_id: str = ""
    stage: str = ""
    checkpoint_data: Dict[str, Any] = None
    checkpoint_type: str = "auto"
    checkpoint_reason: Optional[str] = None
    is_recoverable: bool = True
    recovery_attempts: int = 0
    last_recovery_attempt: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.checkpoint_data is None:
            self.checkpoint_data = {}


class WorkflowStateRepository:
    """
    PostgreSQL repository for workflow state management
    
    Provides:
    - Async CRUD operations for workflow states
    - Checkpoint management for recovery
    - Performance tracking and analytics
    - Connection pooling and health monitoring
    """
    
    def __init__(self):
        self.connection_pool: Optional[asyncpg.Pool] = None
        self.pool_config = {
            "min_size": settings.MEMORY_POSTGRES_MIN_POOL_SIZE,
            "max_size": settings.MEMORY_POSTGRES_MAX_POOL_SIZE,
            "command_timeout": settings.MEMORY_POSTGRES_COMMAND_TIMEOUT,
            "server_settings": {
                "jit": "off",
                "statement_timeout": "30s"
            }
        }
        
        # Performance metrics
        self.metrics = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "avg_operation_time_ms": 0.0,
            "checkpoints_created": 0,
            "recoveries_attempted": 0,
            "successful_recoveries": 0
        }
        
        app_logger.info("Workflow State Repository initializing...")
    
    async def initialize(self) -> bool:
        """Initialize database connection pool"""
        try:
            # Extract connection details from URL
            db_url = settings.MEMORY_POSTGRES_URL
            
            # Create connection pool
            self.connection_pool = await asyncpg.create_pool(
                db_url,
                **self.pool_config
            )
            
            # Test connection
            async with self.connection_pool.acquire() as conn:
                await conn.execute("SELECT 1")
            
            app_logger.info("Workflow State Repository initialized successfully", extra={
                "pool_min_size": self.pool_config["min_size"],
                "pool_max_size": self.pool_config["max_size"]
            })
            
            return True
            
        except Exception as e:
            app_logger.error(f"Failed to initialize state repository: {e}")
            return False
    
    # ==================== WORKFLOW STATE OPERATIONS ====================
    
    async def create_workflow_state(self, state: WorkflowState) -> Optional[str]:
        """Create new workflow state"""
        start_time = asyncio.get_event_loop().time()
        self.metrics["total_operations"] += 1
        
        try:
            state.id = str(uuid.uuid4())
            state.created_at = datetime.now()
            state.updated_at = datetime.now()
            state.last_activity = datetime.now()
            
            async with self.connection_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO workflow_states (
                        id, phone_number, thread_id, current_stage, current_step,
                        state_data, conversation_history, user_profile,
                        detected_intent, scheduling_data, validation_status,
                        last_activity, created_at, updated_at,
                        message_count, total_processing_time_ms
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                """, 
                    state.id, state.phone_number, state.thread_id,
                    state.current_stage, state.current_step,
                    json.dumps(state.state_data),
                    json.dumps(state.conversation_history),
                    json.dumps(state.user_profile),
                    state.detected_intent,
                    json.dumps(state.scheduling_data),
                    state.validation_status,
                    state.last_activity, state.created_at, state.updated_at,
                    state.message_count, state.total_processing_time_ms
                )
            
            # Update metrics
            operation_time = (asyncio.get_event_loop().time() - start_time) * 1000
            self._update_operation_metrics(True, operation_time)
            
            app_logger.debug(f"Created workflow state: {state.id}", extra={
                "thread_id": state.thread_id,
                "phone_number": state.phone_number
            })
            
            return state.id
            
        except Exception as e:
            self._update_operation_metrics(False, 0)
            app_logger.error(f"Failed to create workflow state: {e}")
            return None
    
    async def get_workflow_state(self, thread_id: str) -> Optional[WorkflowState]:
        """Get workflow state by thread ID"""
        start_time = asyncio.get_event_loop().time()
        self.metrics["total_operations"] += 1
        
        try:
            async with self.connection_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM workflow_states 
                    WHERE thread_id = $1
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, thread_id)
            
            if row:
                state = WorkflowState(
                    id=row["id"],
                    phone_number=row["phone_number"],
                    thread_id=row["thread_id"],
                    current_stage=row["current_stage"],
                    current_step=row["current_step"],
                    state_data=json.loads(row["state_data"]) if row["state_data"] else {},
                    conversation_history=json.loads(row["conversation_history"]) if row["conversation_history"] else [],
                    user_profile=json.loads(row["user_profile"]) if row["user_profile"] else {},
                    detected_intent=row["detected_intent"],
                    scheduling_data=json.loads(row["scheduling_data"]) if row["scheduling_data"] else {},
                    validation_status=row["validation_status"],
                    last_activity=row["last_activity"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    message_count=row["message_count"],
                    total_processing_time_ms=row["total_processing_time_ms"]
                )
                
                # Update metrics
                operation_time = (asyncio.get_event_loop().time() - start_time) * 1000
                self._update_operation_metrics(True, operation_time)
                
                return state
            
            return None
            
        except Exception as e:
            self._update_operation_metrics(False, 0)
            app_logger.error(f"Failed to get workflow state for {thread_id}: {e}")
            return None
    
    async def update_workflow_state(
        self,
        thread_id: str,
        updates: Dict[str, Any],
        processing_time_ms: float = 0.0
    ) -> bool:
        """Update workflow state"""
        start_time = asyncio.get_event_loop().time()
        self.metrics["total_operations"] += 1
        
        try:
            # Build dynamic update query
            set_clauses = []
            params = []
            param_index = 1
            
            for key, value in updates.items():
                if key in ["state_data", "conversation_history", "user_profile", "scheduling_data"]:
                    set_clauses.append(f"{key} = ${param_index}")
                    params.append(json.dumps(value))
                else:
                    set_clauses.append(f"{key} = ${param_index}")
                    params.append(value)
                param_index += 1
            
            # Always update these fields
            set_clauses.extend([
                f"updated_at = ${param_index}",
                f"last_activity = ${param_index + 1}",
                f"message_count = message_count + 1"
            ])
            params.extend([datetime.now(), datetime.now()])
            param_index += 2
            
            # Add processing time if provided
            if processing_time_ms > 0:
                set_clauses.append(f"total_processing_time_ms = total_processing_time_ms + ${param_index}")
                params.append(processing_time_ms)
                param_index += 1
            
            # Add thread_id as final parameter
            params.append(thread_id)
            
            query = f"""
                UPDATE workflow_states 
                SET {', '.join(set_clauses)}
                WHERE thread_id = ${param_index}
            """
            
            async with self.connection_pool.acquire() as conn:
                result = await conn.execute(query, *params)
            
            success = result.split()[-1] == "1"  # Check if one row was updated
            
            # Update metrics
            operation_time = (asyncio.get_event_loop().time() - start_time) * 1000
            self._update_operation_metrics(success, operation_time)
            
            if success:
                app_logger.debug(f"Updated workflow state: {thread_id}")
            
            return success
            
        except Exception as e:
            self._update_operation_metrics(False, 0)
            app_logger.error(f"Failed to update workflow state for {thread_id}: {e}")
            return False
    
    async def delete_workflow_state(self, thread_id: str) -> bool:
        """Delete workflow state"""
        try:
            async with self.connection_pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM workflow_states WHERE thread_id = $1
                """, thread_id)
            
            success = result.split()[-1] != "0"
            
            if success:
                app_logger.debug(f"Deleted workflow state: {thread_id}")
            
            return success
            
        except Exception as e:
            app_logger.error(f"Failed to delete workflow state for {thread_id}: {e}")
            return False
    
    # ==================== CHECKPOINT OPERATIONS ====================
    
    async def create_checkpoint(self, checkpoint: WorkflowCheckpoint) -> Optional[str]:
        """Create workflow checkpoint"""
        try:
            checkpoint.id = str(uuid.uuid4())
            checkpoint.created_at = datetime.now()
            
            async with self.connection_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO workflow_checkpoints (
                        id, thread_id, stage, checkpoint_data,
                        checkpoint_type, checkpoint_reason,
                        is_recoverable, recovery_attempts, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                    checkpoint.id, checkpoint.thread_id, checkpoint.stage,
                    json.dumps(checkpoint.checkpoint_data),
                    checkpoint.checkpoint_type, checkpoint.checkpoint_reason,
                    checkpoint.is_recoverable, checkpoint.recovery_attempts,
                    checkpoint.created_at
                )
            
            self.metrics["checkpoints_created"] += 1
            
            app_logger.debug(f"Created checkpoint: {checkpoint.id}", extra={
                "thread_id": checkpoint.thread_id,
                "stage": checkpoint.stage
            })
            
            return checkpoint.id
            
        except Exception as e:
            app_logger.error(f"Failed to create checkpoint: {e}")
            return None
    
    async def get_latest_checkpoint(self, thread_id: str) -> Optional[WorkflowCheckpoint]:
        """Get latest recoverable checkpoint"""
        try:
            async with self.connection_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM workflow_checkpoints
                    WHERE thread_id = $1 AND is_recoverable = true
                    ORDER BY created_at DESC
                    LIMIT 1
                """, thread_id)
            
            if row:
                return WorkflowCheckpoint(
                    id=row["id"],
                    thread_id=row["thread_id"],
                    stage=row["stage"],
                    checkpoint_data=json.loads(row["checkpoint_data"]) if row["checkpoint_data"] else {},
                    checkpoint_type=row["checkpoint_type"],
                    checkpoint_reason=row["checkpoint_reason"],
                    is_recoverable=row["is_recoverable"],
                    recovery_attempts=row["recovery_attempts"],
                    last_recovery_attempt=row["last_recovery_attempt"],
                    created_at=row["created_at"]
                )
            
            return None
            
        except Exception as e:
            app_logger.error(f"Failed to get latest checkpoint for {thread_id}: {e}")
            return None
    
    async def attempt_recovery(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Attempt workflow recovery from checkpoint"""
        self.metrics["recoveries_attempted"] += 1
        
        try:
            # Get latest checkpoint
            checkpoint = await self.get_latest_checkpoint(thread_id)
            if not checkpoint:
                return None
            
            # Update recovery attempt count
            async with self.connection_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE workflow_checkpoints
                    SET recovery_attempts = recovery_attempts + 1,
                        last_recovery_attempt = $1
                    WHERE id = $2
                """, datetime.now(), checkpoint.id)
            
            # Get current state
            current_state = await self.get_workflow_state(thread_id)
            if current_state:
                # Merge checkpoint data with current state
                recovery_updates = {
                    "current_stage": checkpoint.stage,
                    "state_data": {**current_state.state_data, **checkpoint.checkpoint_data}
                }
                
                # Update state with recovery data
                await self.update_workflow_state(thread_id, recovery_updates)
            
            self.metrics["successful_recoveries"] += 1
            
            app_logger.info(f"Successfully recovered workflow: {thread_id}", extra={
                "checkpoint_id": checkpoint.id,
                "stage": checkpoint.stage
            })
            
            return {
                "success": True,
                "checkpoint_id": checkpoint.id,
                "stage": checkpoint.stage,
                "data": checkpoint.checkpoint_data
            }
            
        except Exception as e:
            app_logger.error(f"Failed to recover workflow {thread_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== ANALYTICS & MONITORING ====================
    
    async def get_active_sessions(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get active sessions in the last N hours"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            async with self.connection_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        phone_number,
                        thread_id,
                        current_stage,
                        current_step,
                        EXTRACT(EPOCH FROM (NOW() - last_activity))::INT as seconds_inactive,
                        message_count,
                        total_processing_time_ms
                    FROM workflow_states
                    WHERE last_activity > $1
                      AND current_stage NOT IN ('completed', 'error')
                    ORDER BY last_activity DESC
                """, cutoff_time)
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            app_logger.error(f"Failed to get active sessions: {e}")
            return []
    
    async def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance metrics for the last N hours"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            async with self.connection_pool.acquire() as conn:
                # Get operation performance metrics
                perf_row = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as operation_count,
                        AVG(duration_ms) as avg_duration_ms,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms,
                        MAX(duration_ms) as max_duration_ms
                    FROM workflow_performance
                    WHERE recorded_at > $1
                """, cutoff_time)
                
                # Get session statistics
                session_row = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_sessions,
                        COUNT(DISTINCT phone_number) as unique_users,
                        AVG(message_count) as avg_messages_per_session,
                        AVG(total_processing_time_ms / NULLIF(message_count, 0)) as avg_response_time_ms
                    FROM workflow_states
                    WHERE last_activity > $1
                """, cutoff_time)
            
            return {
                "time_period_hours": hours,
                "operation_metrics": dict(perf_row) if perf_row else {},
                "session_metrics": dict(session_row) if session_row else {},
                "repository_metrics": self.metrics
            }
            
        except Exception as e:
            app_logger.error(f"Failed to get performance metrics: {e}")
            return {"error": str(e)}
    
    async def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """Cleanup old workflow data"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            
            async with self.connection_pool.acquire() as conn:
                # Cleanup old states
                states_result = await conn.execute("""
                    DELETE FROM workflow_states
                    WHERE last_activity < $1
                      AND current_stage IN ('completed', 'error')
                """, cutoff_time)
                
                # Cleanup old checkpoints
                checkpoints_result = await conn.execute("""
                    DELETE FROM workflow_checkpoints
                    WHERE created_at < $1
                """, cutoff_time)
                
                # Cleanup old performance data
                perf_result = await conn.execute("""
                    DELETE FROM workflow_performance
                    WHERE recorded_at < $1
                """, cutoff_time)
            
            states_deleted = int(states_result.split()[-1])
            checkpoints_deleted = int(checkpoints_result.split()[-1])
            perf_deleted = int(perf_result.split()[-1])
            
            app_logger.info(f"Cleaned up old data", extra={
                "states_deleted": states_deleted,
                "checkpoints_deleted": checkpoints_deleted,
                "performance_records_deleted": perf_deleted
            })
            
            return {
                "states_deleted": states_deleted,
                "checkpoints_deleted": checkpoints_deleted,
                "performance_records_deleted": perf_deleted
            }
            
        except Exception as e:
            app_logger.error(f"Failed to cleanup old data: {e}")
            return {"error": str(e)}
    
    def _update_operation_metrics(self, success: bool, operation_time_ms: float):
        """Update operation metrics"""
        if success:
            self.metrics["successful_operations"] += 1
            
            # Update average operation time
            total_successful = self.metrics["successful_operations"]
            current_avg = self.metrics["avg_operation_time_ms"]
            self.metrics["avg_operation_time_ms"] = (
                (current_avg * (total_successful - 1) + operation_time_ms) / total_successful
            )
        else:
            self.metrics["failed_operations"] += 1
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Test basic connectivity
            async with self.connection_pool.acquire() as conn:
                await conn.execute("SELECT 1")
                
                # Test table access
                await conn.fetchval("SELECT COUNT(*) FROM workflow_states")
                await conn.fetchval("SELECT COUNT(*) FROM workflow_checkpoints")
                await conn.fetchval("SELECT COUNT(*) FROM workflow_performance")
            
            health_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Get pool status
            pool_status = {
                "size": self.connection_pool.get_size(),
                "idle": self.connection_pool.get_idle_size(),
                "active": self.connection_pool.get_size() - self.connection_pool.get_idle_size()
            }
            
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "health_check_time_ms": health_time_ms,
                "connection_pool": pool_status,
                "metrics": self.metrics,
                "database_tables": {
                    "workflow_states": "accessible",
                    "workflow_checkpoints": "accessible", 
                    "workflow_performance": "accessible"
                }
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "connection_pool": "unavailable"
            }
    
    async def cleanup(self):
        """Cleanup repository resources"""
        try:
            if self.connection_pool:
                await self.connection_pool.close()
            
            app_logger.info("Workflow State Repository cleaned up")
            
        except Exception as e:
            app_logger.error(f"Error during repository cleanup: {e}")


# Global workflow state repository
workflow_state_repository = WorkflowStateRepository()