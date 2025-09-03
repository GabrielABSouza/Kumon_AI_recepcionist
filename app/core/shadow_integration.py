# app/core/shadow_integration.py
"""
Shadow Integration - Transparently Integrate V2 Shadow Traffic

Middleware to run V2 architecture in shadow mode alongside V1 production
without affecting user responses. Collects comparison metrics.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from .feature_flags import feature_flags, shadow_traffic_manager
from .telemetry_migration import emit_telemetry_event
from .shadow_metrics_collector import shadow_metrics_collector

logger = logging.getLogger(__name__)


class ShadowIntegrationMiddleware:
    """
    Middleware to integrate shadow V2 execution with V1 production
    
    Wraps existing workflow nodes to run shadow V2 alongside
    """
    
    def __init__(self):
        self.shadow_enabled = True
        self.shadow_timeout_ms = feature_flags.v2_timeout_ms
        self.max_latency_ms = feature_flags.v2_max_latency_ms
    
    async def wrap_node_execution(
        self, 
        node_name: str,
        node_func: Callable,
        state: Dict[str, Any],
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Wrap node execution with shadow V2 capability
        
        Executes V1 (production) and optionally V2 (shadow) in parallel
        """
        session_id = state.get("session_id", "unknown")
        architecture_mode = feature_flags.get_architecture_mode(session_id)
        
        if architecture_mode == "v2_live":
            # Use V2 architecture for live traffic
            return await self._execute_v2_live(node_name, node_func, state, *args, **kwargs)
        
        elif architecture_mode == "v2_shadow":
            # Execute V1 + V2 shadow in parallel
            return await self._execute_with_shadow(node_name, node_func, state, *args, **kwargs)
        
        else:
            # V1 only
            return await self._execute_v1_only(node_name, node_func, state, *args, **kwargs)
    
    async def _execute_v1_only(
        self, 
        node_name: str, 
        node_func: Callable, 
        state: Dict[str, Any],
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute V1 architecture only"""
        try:
            result = await node_func(state, *args, **kwargs)
            
            # Emit V1 telemetry
            self._emit_v1_telemetry(node_name, state, result)
            
            return result
            
        except Exception as e:
            logger.error(f"V1 node {node_name} failed: {e}")
            raise
    
    async def _execute_v2_live(
        self,
        node_name: str,
        node_func: Callable,
        state: Dict[str, Any], 
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute V2 architecture for live traffic"""
        try:
            # Route to V2 implementation if available
            v2_func = self._get_v2_node_function(node_name)
            
            if v2_func:
                result = v2_func(state, *args, **kwargs)
                
                # Emit V2 telemetry
                self._emit_v2_telemetry(node_name, state, result, mode="live")
                
                return result
            else:
                # Fallback to V1 if V2 not available
                logger.warning(f"V2 implementation not found for {node_name}, using V1 fallback")
                return await self._execute_v1_only(node_name, node_func, state, *args, **kwargs)
                
        except Exception as e:
            logger.error(f"V2 live node {node_name} failed: {e}")
            
            # Fallback to V1 on V2 failure
            logger.info(f"Falling back to V1 for {node_name}")
            return await self._execute_v1_only(node_name, node_func, state, *args, **kwargs)
    
    async def _execute_with_shadow(
        self,
        node_name: str,
        node_func: Callable, 
        state: Dict[str, Any],
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute V1 (production) + V2 (shadow) in parallel"""
        
        # Start V1 execution (primary)
        v1_task = asyncio.create_task(
            self._execute_v1_only(node_name, node_func, state, *args, **kwargs)
        )
        
        # Start V2 shadow execution (secondary)
        v2_shadow_task = asyncio.create_task(
            self._execute_v2_shadow(node_name, state)
        )
        
        try:
            # Wait for V1 (primary) - this determines the response
            v1_result = await v1_task
            
            # Try to get V2 shadow result (don't wait if taking too long)
            try:
                v2_shadow_result = await asyncio.wait_for(
                    v2_shadow_task, 
                    timeout=self.shadow_timeout_ms / 1000
                )
                
                # Compare and log results
                self._log_shadow_comparison(node_name, state, v1_result, v2_shadow_result)
                
                # Collect structured metrics for calibration
                self._collect_shadow_metrics(node_name, state, v1_result, v2_shadow_result)
                
            except asyncio.TimeoutError:
                logger.warning(f"V2 shadow timeout for {node_name}")
                v2_shadow_task.cancel()
                
            except Exception as e:
                logger.warning(f"V2 shadow failed for {node_name}: {e}")
            
            # Return V1 result (production traffic unaffected)
            return v1_result
            
        except Exception as e:
            logger.error(f"V1 execution failed for {node_name}: {e}")
            
            # Cancel shadow task if V1 fails
            v2_shadow_task.cancel()
            raise
    
    async def _execute_v2_shadow(self, node_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute V2 node in shadow mode"""
        try:
            # Get V2 implementation
            v2_func = self._get_v2_node_function(node_name)
            
            if not v2_func:
                return {"shadow_status": "not_implemented", "node_name": node_name}
            
            # Create shadow state copy
            shadow_state = shadow_traffic_manager._deep_copy_state(state)
            shadow_state["_shadow_mode"] = True
            
            start_time = datetime.now()
            
            # Execute V2 function
            shadow_result = v2_func(shadow_state)
            
            end_time = datetime.now()
            latency_ms = (end_time - start_time).total_seconds() * 1000
            
            # Add shadow metadata
            shadow_result["_shadow_latency_ms"] = latency_ms
            shadow_result["_shadow_node"] = node_name
            shadow_result["_shadow_status"] = "success"
            shadow_result["_shadow_timestamp"] = end_time.isoformat()
            
            # Emit V2 shadow telemetry
            self._emit_v2_telemetry(node_name, state, shadow_result, mode="shadow")
            
            return shadow_result
            
        except Exception as e:
            logger.warning(f"V2 shadow execution failed for {node_name}: {e}")
            
            return {
                "_shadow_status": "error",
                "_shadow_error": str(e),
                "_shadow_error_type": type(e).__name__,
                "_shadow_node": node_name,
                "_shadow_timestamp": datetime.now().isoformat()
            }
    
    def _get_v2_node_function(self, node_name: str) -> Optional[Callable]:
        """Get V2 implementation for node"""
        
        # Map V1 node names to V2 implementations
        v2_node_mapping = {
            "greeting": self._get_greeting_v2,
            "qualification": self._get_qualification_v2,
            "information": self._get_information_v2,
            "scheduling": self._get_scheduling_v2
        }
        
        return v2_node_mapping.get(node_name)
    
    def _get_greeting_v2(self) -> Callable:
        """Get V2 greeting node implementation"""
        try:
            from .nodes.greeting_migrated import greeting_node_migrated
            return greeting_node_migrated
        except ImportError:
            return None
    
    def _get_qualification_v2(self) -> Callable:
        """Get V2 qualification node implementation"""
        try:
            from .nodes.qualification_migrated import qualification_node_migrated
            return qualification_node_migrated
        except ImportError:
            return None
    
    def _get_information_v2(self) -> Callable:
        """Get V2 information node implementation (placeholder)"""
        return None  # Not yet migrated
    
    def _get_scheduling_v2(self) -> Callable:
        """Get V2 scheduling node implementation (placeholder)"""
        return None  # Not yet migrated
    
    def _log_shadow_comparison(
        self, 
        node_name: str,
        original_state: Dict[str, Any], 
        v1_result: Dict[str, Any],
        v2_result: Dict[str, Any]
    ):
        """Log comparison between V1 and V2 results"""
        
        session_id = original_state.get("session_id", "unknown")
        
        # Compare key fields
        comparison = {
            "node_name": node_name,
            "session_id": session_id,
            "v1_current_step": v1_result.get("current_step"),
            "v2_current_step": v2_result.get("current_step"),
            "v1_stage": v1_result.get("current_stage"),
            "v2_stage": v2_result.get("current_stage"),
            "v2_latency_ms": v2_result.get("_shadow_latency_ms"),
            "v2_status": v2_result.get("_shadow_status"),
            "steps_match": v1_result.get("current_step") == v2_result.get("current_step"),
            "stages_match": v1_result.get("current_stage") == v2_result.get("current_stage"),
            "timestamp": datetime.now().isoformat()
        }
        
        # Log structured comparison
        logger.info(f"SHADOW_COMPARISON: {comparison}")
        
        # Emit telemetry event
        emit_telemetry_event("shadow_comparison", comparison)
    
    def _collect_shadow_metrics(
        self, 
        node_name: str,
        original_state: Dict[str, Any],
        v1_result: Dict[str, Any],
        v2_result: Dict[str, Any]
    ):
        """Collect structured shadow metrics for calibration"""
        
        try:
            session_id = original_state.get("session_id", "unknown")
            user_message = original_state.get("last_user_message", "")
            
            # Extract routing decision if available
            routing_decision = original_state.get("routing_decision")
            
            # Calculate latencies
            v2_latency = v2_result.get("_shadow_latency_ms", 0.0)
            latencies = {
                "routing_ms": 0.0,  # Would be measured in router
                "node_ms": v2_latency, 
                "delivery_ms": 0.0,  # Would be measured in delivery
                "total_ms": v2_latency
            }
            
            # Collect comprehensive metrics
            shadow_metrics_collector.collect_interaction_metrics(
                session_id=session_id,
                user_message=user_message,
                v1_result=v1_result,
                v2_result=v2_result,
                routing_decision=routing_decision,
                latencies=latencies
            )
            
            logger.debug(f"Shadow metrics collected for node {node_name}, session {session_id}")
            
        except Exception as e:
            logger.warning(f"Failed to collect shadow metrics for {node_name}: {e}")
    
    def _emit_v1_telemetry(self, node_name: str, state: Dict[str, Any], result: Dict[str, Any]):
        """Emit V1 telemetry"""
        emit_telemetry_event("v1_node_execution", {
            "node_name": node_name,
            "session_id": state.get("session_id", "unknown"),
            "architecture": "v1_production",
            "current_step": result.get("current_step"),
            "current_stage": result.get("current_stage")
        })
    
    def _emit_v2_telemetry(
        self, 
        node_name: str, 
        state: Dict[str, Any], 
        result: Dict[str, Any],
        mode: str
    ):
        """Emit V2 telemetry"""
        emit_telemetry_event("v2_node_execution", {
            "node_name": node_name,
            "session_id": state.get("session_id", "unknown"),
            "architecture": f"v2_{mode}",
            "current_step": result.get("current_step"),
            "current_stage": result.get("current_stage"),
            "latency_ms": result.get("_shadow_latency_ms"),
            "status": result.get("_shadow_status")
        })


# Global middleware instance
shadow_integration = ShadowIntegrationMiddleware()


# ========== DECORATOR FOR EASY INTEGRATION ==========

def with_shadow_v2(node_name: str):
    """
    Decorator to add shadow V2 execution to existing nodes
    
    Usage:
        @with_shadow_v2("greeting")
        async def greeting_node(state):
            # existing V1 implementation
            return result
    """
    def decorator(func: Callable):
        async def wrapper(state: Dict[str, Any], *args, **kwargs):
            return await shadow_integration.wrap_node_execution(
                node_name, func, state, *args, **kwargs
            )
        return wrapper
    return decorator