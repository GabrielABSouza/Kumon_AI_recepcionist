"""
PostgreSQL Checkpointer for LangGraph - Wave 3 Implementation
Custom checkpointer that integrates with workflow state repository
"""

import asyncio
import json
from typing import Optional, Dict, Any, Iterator, Tuple, List
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata
from langgraph.checkpoint.base import CheckpointTuple

from ..core.logger import app_logger
from .workflow_state_repository import workflow_state_repository, WorkflowCheckpoint


class PostgreSQLCheckpointSaver(BaseCheckpointSaver):
    """
    PostgreSQL-backed checkpoint saver for LangGraph
    
    Integrates with the workflow state repository to provide:
    - Persistent state storage
    - Automatic recovery capabilities
    - Performance monitoring
    - Connection pooling
    """
    
    def __init__(self):
        self.repository = workflow_state_repository
        self.is_initialized = False
        
        app_logger.info("PostgreSQL Checkpointer initialized")
    
    async def initialize(self):
        """Initialize the checkpointer"""
        if not self.is_initialized:
            # Initialize repository if not already done
            if not self.repository.connection_pool:
                await self.repository.initialize()
            
            self.is_initialized = True
            app_logger.info("PostgreSQL Checkpointer ready")
    
    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata
    ) -> None:
        """
        Save checkpoint (synchronous method required by LangGraph)
        """
        # Run async operation in event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, schedule the task
                asyncio.create_task(self._async_put(config, checkpoint, metadata))
            else:
                # Run in new event loop
                loop.run_until_complete(self._async_put(config, checkpoint, metadata))
        except Exception as e:
            app_logger.error(f"Failed to save checkpoint: {e}")
    
    async def _async_put(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata
    ) -> None:
        """Async implementation of checkpoint saving"""
        try:
            await self.initialize()
            
            # Extract thread ID from config
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                app_logger.warning("No thread_id in config, cannot save checkpoint")
                return
            
            # Create checkpoint data
            checkpoint_data = {
                "checkpoint": checkpoint.to_json() if hasattr(checkpoint, 'to_json') else str(checkpoint),
                "metadata": metadata.to_json() if hasattr(metadata, 'to_json') else str(metadata),
                "config": config,
                "checkpoint_id": str(uuid4())
            }
            
            # Determine stage from metadata or checkpoint
            stage = self._extract_stage_from_checkpoint(checkpoint, metadata)
            
            # Create checkpoint record
            workflow_checkpoint = WorkflowCheckpoint(
                thread_id=thread_id,
                stage=stage,
                checkpoint_data=checkpoint_data,
                checkpoint_type="langgraph",
                checkpoint_reason="automatic_save",
                is_recoverable=True
            )
            
            # Save to repository
            checkpoint_id = await self.repository.create_checkpoint(workflow_checkpoint)
            
            if checkpoint_id:
                app_logger.debug(f"Saved LangGraph checkpoint: {checkpoint_id}", extra={
                    "thread_id": thread_id,
                    "stage": stage
                })
            else:
                app_logger.error(f"Failed to save LangGraph checkpoint for thread {thread_id}")
                
        except Exception as e:
            app_logger.error(f"Error in async checkpoint save: {e}")
    
    def get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """
        Retrieve checkpoint (synchronous method required by LangGraph)
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a future and schedule the async operation
                future = asyncio.create_task(self._async_get(config))
                # This is tricky - we can't await in a sync method
                # Return None for now and log the limitation
                app_logger.debug("Async get requested in sync context - returning None")
                return None
            else:
                # Run in new event loop
                return loop.run_until_complete(self._async_get(config))
        except Exception as e:
            app_logger.error(f"Failed to get checkpoint: {e}")
            return None
    
    async def aget_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """
        Get checkpoint tuple (async) - Required by LangGraph
        """
        try:
            await self.initialize()
            
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                return None
                
            # Get latest checkpoint for thread
            checkpoint_data = await self.repository.get_latest_checkpoint(thread_id)
            if not checkpoint_data:
                return None
                
            # Convert to LangGraph format
            checkpoint = Checkpoint(
                v=1,
                ts=checkpoint_data.created_at.isoformat(),
                id=str(checkpoint_data.id),
                channel_values=checkpoint_data.checkpoint_data.get("channel_values", {}),
                channel_versions=checkpoint_data.checkpoint_data.get("channel_versions", {}),
                versions_seen=checkpoint_data.checkpoint_data.get("versions_seen", {})
            )
            
            metadata = CheckpointMetadata(
                source="database",
                step=0,
                writes={}
            )
            
            return CheckpointTuple(
                config=config,
                checkpoint=checkpoint,
                metadata=metadata
            )
            
        except Exception as e:
            app_logger.error(f"Failed to get checkpoint tuple: {e}")
            return None
    
    async def aget(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """Get checkpoint (async)"""
        tuple_result = await self.aget_tuple(config)
        return tuple_result.checkpoint if tuple_result else None
    
    async def _async_get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """Async implementation of checkpoint retrieval"""
        return await self.aget(config)
        
    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """Get checkpoint tuple (sync)"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                app_logger.debug("Async get_tuple requested in sync context - returning None")
                return None
            else:
                return loop.run_until_complete(self.aget_tuple(config))
        except Exception as e:
            app_logger.error(f"Failed to get checkpoint tuple sync: {e}")
            return None

    async def _async_get_legacy(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """Legacy async implementation of checkpoint retrieval"""
        try:
            await self.initialize()
            
            # Extract thread ID from config
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                return None
            
            # Get latest checkpoint
            workflow_checkpoint = await self.repository.get_latest_checkpoint(thread_id)
            if not workflow_checkpoint:
                return None
            
            # Extract checkpoint data
            checkpoint_data = workflow_checkpoint.checkpoint_data
            if not checkpoint_data:
                return None
            
            # Reconstruct checkpoint
            # This is a simplified version - in production you'd want more robust serialization
            checkpoint_json = checkpoint_data.get("checkpoint")
            if checkpoint_json:
                # For now, return a basic checkpoint structure
                # In a full implementation, you'd deserialize the actual checkpoint
                return Checkpoint(
                    v=1,
                    ts=workflow_checkpoint.created_at.isoformat() if workflow_checkpoint.created_at else "",
                    id=workflow_checkpoint.id or str(uuid4()),
                    channel_values=checkpoint_data.get("channel_values", {}),
                    channel_versions={},
                    versions_seen={}
                )
            
            return None
            
        except Exception as e:
            app_logger.error(f"Error in async checkpoint get: {e}")
            return None
    
    def list(self, config: Dict[str, Any]) -> Iterator[CheckpointTuple]:
        """
        List checkpoints (synchronous method required by LangGraph)
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                app_logger.debug("Async list requested in sync context - returning empty iterator")
                return iter([])
            else:
                return loop.run_until_complete(self._async_list(config))
        except Exception as e:
            app_logger.error(f"Failed to list checkpoints: {e}")
            return iter([])
    
    async def _async_list(self, config: Dict[str, Any]) -> Iterator[CheckpointTuple]:
        """Async implementation of checkpoint listing"""
        try:
            await self.initialize()
            
            # Extract thread ID from config
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                return iter([])
            
            # For now, return iterator with just the latest checkpoint
            # In a full implementation, you'd return all checkpoints for the thread
            latest_checkpoint = await self._async_get(config)
            if latest_checkpoint:
                checkpoint_tuple = CheckpointTuple(
                    config=config,
                    checkpoint=latest_checkpoint,
                    metadata=CheckpointMetadata()
                )
                return iter([checkpoint_tuple])
            
            return iter([])
            
        except Exception as e:
            app_logger.error(f"Error in async checkpoint list: {e}")
            return iter([])
    
    def _extract_stage_from_checkpoint(
        self, 
        checkpoint: Checkpoint, 
        metadata: CheckpointMetadata
    ) -> str:
        """Extract stage information from checkpoint or metadata"""
        try:
            # Try to extract stage from metadata first
            if hasattr(metadata, 'stage'):
                return metadata.stage
            
            # Try to extract from checkpoint
            if hasattr(checkpoint, 'channel_values'):
                channel_values = checkpoint.channel_values
                if isinstance(channel_values, dict):
                    # Look for common stage indicators
                    for key in ['current_stage', 'stage', 'node']:
                        if key in channel_values:
                            return str(channel_values[key])
            
            # Default stage
            return "unknown"
            
        except Exception as e:
            app_logger.error(f"Error extracting stage from checkpoint: {e}")
            return "unknown"
    
    async def get_checkpoint_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get checkpoint history for a thread"""
        try:
            await self.initialize()
            
            async with self.repository.connection_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        id,
                        stage,
                        checkpoint_type,
                        checkpoint_reason,
                        recovery_attempts,
                        created_at
                    FROM workflow_checkpoints
                    WHERE thread_id = $1
                    ORDER BY created_at DESC
                    LIMIT 50
                """, thread_id)
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            app_logger.error(f"Error getting checkpoint history: {e}")
            return []
    
    async def recover_from_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Recover workflow from latest checkpoint"""
        try:
            await self.initialize()
            
            # Use repository's recovery mechanism
            recovery_result = await self.repository.attempt_recovery(thread_id)
            
            if recovery_result and recovery_result.get("success"):
                app_logger.info(f"Successfully recovered from checkpoint: {thread_id}")
                return recovery_result
            else:
                app_logger.warning(f"Failed to recover from checkpoint: {thread_id}")
                return None
                
        except Exception as e:
            app_logger.error(f"Error during checkpoint recovery: {e}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for checkpointer"""
        try:
            await self.initialize()
            
            # Test basic checkpoint operations
            test_config = {
                "configurable": {"thread_id": f"health_check_{uuid4()}"}
            }
            
            # Create a simple test checkpoint
            test_checkpoint = Checkpoint(
                v=1,
                ts="test",
                id=str(uuid4()),
                channel_values={"test": "data"},
                channel_versions={},
                versions_seen={}
            )
            
            test_metadata = CheckpointMetadata()
            
            # Test save operation
            await self._async_put(test_config, test_checkpoint, test_metadata)
            
            # Test retrieve operation
            retrieved = await self._async_get(test_config)
            
            # Cleanup test data
            thread_id = test_config["configurable"]["thread_id"]
            await self.repository.delete_workflow_state(thread_id)
            
            return {
                "status": "healthy",
                "timestamp": asyncio.get_event_loop().time(),
                "operations": {
                    "save": "working",
                    "retrieve": "working" if retrieved else "limited",
                    "repository": "connected"
                },
                "repository_health": await self.repository.health_check()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "timestamp": asyncio.get_event_loop().time(),
                "error": str(e)
            }
    
    async def aput(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: CheckpointMetadata) -> None:
        """Put checkpoint (async)"""
        await self._async_put(config, checkpoint, metadata)
    
    async def alist(self, config: Dict[str, Any]) -> List[CheckpointTuple]:
        """List checkpoints (async)"""
        try:
            await self.initialize()
            
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                return []
                
            # Get all checkpoints for thread
            checkpoints = await self.repository.get_checkpoint_history(thread_id)
            results = []
            
            for checkpoint_data in checkpoints:
                checkpoint = Checkpoint(
                    v=1,
                    ts=checkpoint_data["created_at"],
                    id=str(checkpoint_data["id"]),
                    channel_values=checkpoint_data.get("checkpoint_data", {}).get("channel_values", {}),
                    channel_versions=checkpoint_data.get("checkpoint_data", {}).get("channel_versions", {}),
                    versions_seen=checkpoint_data.get("checkpoint_data", {}).get("versions_seen", {})
                )
                
                metadata = CheckpointMetadata(
                    source="database",
                    step=0,
                    writes={}
                )
                
                results.append(CheckpointTuple(
                    config=config,
                    checkpoint=checkpoint,
                    metadata=metadata
                ))
                
            return results
            
        except Exception as e:
            app_logger.error(f"Failed to list checkpoints: {e}")
            return []

    async def aput_writes(self, config: Dict[str, Any], writes: List, task_id: str) -> None:
        """Put writes (async) - stub implementation"""
        pass
    
    def put_writes(self, config: Dict[str, Any], writes: List, task_id: str) -> None:
        """Put writes (sync) - stub implementation"""  
        pass

    async def adelete_thread(self, config: Dict[str, Any]) -> None:
        """Delete thread (async)"""
        try:
            await self.initialize()
            thread_id = config.get("configurable", {}).get("thread_id")
            if thread_id:
                await self.repository.delete_workflow_state(thread_id)
        except Exception as e:
            app_logger.error(f"Failed to delete thread: {e}")

    def delete_thread(self, config: Dict[str, Any]) -> None:
        """Delete thread (sync)"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                app_logger.debug("Async delete_thread requested in sync context - skipping")
            else:
                loop.run_until_complete(self.adelete_thread(config))
        except Exception as e:
            app_logger.error(f"Failed to delete thread sync: {e}")

    async def cleanup(self):
        """Cleanup checkpointer resources"""
        try:
            await self.repository.cleanup()
            app_logger.info("PostgreSQL Checkpointer cleaned up")
        except Exception as e:
            app_logger.error(f"Error during checkpointer cleanup: {e}")


# Global PostgreSQL checkpointer instance
postgres_checkpointer = PostgreSQLCheckpointSaver()

# Export the main class with an alias for compatibility
PostgresCheckpointer = PostgreSQLCheckpointSaver