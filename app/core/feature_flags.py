# app/core/feature_flags.py
"""
Feature Flags System - Shadow Traffic Control

Controls migration rollout with shadow traffic capabilities:
- ROUTER_V2_ENABLED: Enable new architecture in production  
- ROUTER_V2_SHADOW: Log V2 decisions without affecting responses
- ROUTER_V2_PERCENTAGE: Gradual rollout percentage
"""

import os
import logging
import random
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class FeatureFlags:
    """
    Feature flag management for architecture migration
    
    Controls both live traffic and shadow traffic modes
    """
    
    def __init__(self):
        # Environment variables with defaults
        self.workflow_v2_enabled = self._get_bool_flag("WORKFLOW_V2_ENABLED", True)  # V2 is default now
        self.router_v2_enabled = self._get_bool_flag("ROUTER_V2_ENABLED", True)  # V2 is default now  
        self.router_v2_shadow = self._get_bool_flag("ROUTER_V2_SHADOW", True)  # Default shadow on
        self.router_v2_percentage = self._get_int_flag("ROUTER_V2_PERCENTAGE", 100)  # 100% V2 rollout
        
        # Shadow telemetry
        self.shadow_logging_enabled = self._get_bool_flag("SHADOW_LOGGING", True)
        self.shadow_metrics_enabled = self._get_bool_flag("SHADOW_METRICS", True)
        
        # Performance flags
        self.v2_max_latency_ms = self._get_int_flag("V2_MAX_LATENCY_MS", 2000)
        self.v2_timeout_ms = self._get_int_flag("V2_TIMEOUT_MS", 5000)
        
        logger.info(f"FeatureFlags initialized - V2_enabled: {self.router_v2_enabled}, "
                   f"V2_shadow: {self.router_v2_shadow}, V2_percentage: {self.router_v2_percentage}%")
    
    def _get_bool_flag(self, name: str, default: bool) -> bool:
        """Get boolean flag from environment"""
        value = os.getenv(name, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def _get_int_flag(self, name: str, default: int) -> int:
        """Get integer flag from environment"""
        try:
            return int(os.getenv(name, str(default)))
        except ValueError:
            logger.warning(f"Invalid {name} value, using default {default}")
            return default
    
    def should_use_v2_architecture(self, session_id: str) -> bool:
        """
        Determine if session should use V2 architecture for live traffic
        
        Uses consistent hashing for stable user experience
        """
        if not self.router_v2_enabled:
            return False
            
        if self.router_v2_percentage >= 100:
            return True
            
        if self.router_v2_percentage <= 0:
            return False
        
        # Consistent hashing based on session_id
        hash_input = f"v2_rollout_{session_id}".encode('utf-8')
        hash_value = int(hashlib.md5(hash_input).hexdigest()[:8], 16)
        bucket = hash_value % 100
        
        return bucket < self.router_v2_percentage
    
    def should_run_shadow_v2(self, session_id: str) -> bool:
        """
        Determine if session should run V2 in shadow mode
        
        Shadow mode runs V2 pipeline but doesn't affect responses
        """
        if not self.router_v2_shadow:
            return False
            
        # If already using V2 live, no need for shadow
        if self.should_use_v2_architecture(session_id):
            return False
            
        return True
    
    def get_architecture_mode(self, session_id: str) -> str:
        """
        Get architecture mode for session
        
        Returns:
            "v1_only": Legacy architecture only
            "v2_live": New architecture for live traffic
            "v2_shadow": New architecture in shadow mode
        """
        if self.should_use_v2_architecture(session_id):
            return "v2_live"
        elif self.should_run_shadow_v2(session_id):
            return "v2_shadow"
        else:
            return "v1_only"


class ShadowTrafficManager:
    """
    Shadow Traffic Management - V2 Pipeline in Shadow Mode
    
    Runs new architecture alongside legacy without affecting responses
    Collects comparison metrics for validation
    """
    
    def __init__(self, feature_flags: FeatureFlags):
        self.feature_flags = feature_flags
        self.shadow_results = {}  # In-memory cache for comparison
        
    async def run_shadow_pipeline(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run V2 pipeline in shadow mode
        
        Returns shadow results without affecting main response
        """
        if not self.feature_flags.should_run_shadow_v2(state.get("session_id", "")):
            return {}
            
        try:
            start_time = datetime.now()
            
            # Import V2 pipeline components
            from .workflow_migration import create_migrated_workflow, ensure_state_compatibility
            from .telemetry_migration import create_instrumented_nodes
            
            # Create shadow state (deep copy to avoid mutations)
            shadow_state = self._deep_copy_state(state)
            shadow_state = ensure_state_compatibility(shadow_state)
            
            # Mark as shadow execution
            shadow_state["_shadow_mode"] = True
            shadow_state["_shadow_trace_id"] = f"shadow_{shadow_state.get('_trace_id', 'unknown')}"
            
            # Execute V2 pipeline with timeout
            workflow = create_migrated_workflow()
            
            # Simplified shadow execution (single step to avoid full workflow)
            instrumented_nodes = create_instrumented_nodes()
            
            # Run key components in sequence
            shadow_state = instrumented_nodes["STAGE_RESOLVER"](shadow_state)
            shadow_state = instrumented_nodes["SMART_ROUTER"](shadow_state) 
            shadow_state = instrumented_nodes["RESPONSE_PLANNER"](shadow_state)
            
            # Calculate shadow metrics
            end_time = datetime.now()
            latency_ms = (end_time - start_time).total_seconds() * 1000
            
            # Extract shadow results
            shadow_results = {
                "shadow_routing_decision": shadow_state.get("routing_decision", {}),
                "shadow_outbox": shadow_state.get("outbox", []),
                "shadow_current_stage": shadow_state.get("current_stage"),
                "shadow_required_slots": shadow_state.get("required_slots", []),
                "shadow_latency_ms": latency_ms,
                "shadow_status": "success",
                "shadow_timestamp": end_time.isoformat()
            }
            
            # Log shadow results if enabled
            if self.feature_flags.shadow_logging_enabled:
                self._log_shadow_results(state, shadow_results)
            
            # Store for comparison metrics
            session_id = state.get("session_id")
            if session_id:
                self.shadow_results[session_id] = shadow_results
            
            return shadow_results
            
        except Exception as e:
            logger.warning(f"Shadow V2 pipeline failed: {e}")
            
            # Return failure metrics
            shadow_results = {
                "shadow_status": "error",
                "shadow_error": str(e),
                "shadow_error_type": type(e).__name__,
                "shadow_timestamp": datetime.now().isoformat()
            }
            
            if self.feature_flags.shadow_logging_enabled:
                self._log_shadow_results(state, shadow_results)
            
            return shadow_results
    
    def _deep_copy_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Deep copy state to avoid mutations"""
        import copy
        return copy.deepcopy(state)
    
    def _log_shadow_results(self, original_state: Dict[str, Any], shadow_results: Dict[str, Any]):
        """Log shadow results for analysis"""
        
        session_id = original_state.get("session_id", "unknown")
        user_message_hash = self._hash_message(original_state.get("last_user_message", ""))
        
        # Log structured shadow telemetry
        shadow_log = {
            "event_type": "shadow_v2_execution",
            "session_id": session_id,
            "user_message_hash": user_message_hash,
            "original_stage": original_state.get("current_stage"),
            "shadow_stage": shadow_results.get("shadow_current_stage"),
            "shadow_status": shadow_results.get("shadow_status"),
            "shadow_latency_ms": shadow_results.get("shadow_latency_ms"),
            "timestamp": shadow_results.get("shadow_timestamp")
        }
        
        # Add decision comparison if available
        original_routing = original_state.get("routing_decision", {})
        shadow_routing = shadow_results.get("shadow_routing_decision", {})
        
        if original_routing and shadow_routing:
            shadow_log["decision_comparison"] = {
                "original_target": original_routing.get("target_node"),
                "shadow_target": shadow_routing.get("target_node"),
                "original_action": original_routing.get("threshold_action"),
                "shadow_action": shadow_routing.get("threshold_action"),
                "original_confidence": original_routing.get("final_confidence"),
                "shadow_confidence": shadow_routing.get("final_confidence"),
                "decisions_match": (
                    original_routing.get("target_node") == shadow_routing.get("target_node") and
                    original_routing.get("threshold_action") == shadow_routing.get("threshold_action")
                )
            }
        
        logger.info(f"SHADOW_V2: {shadow_log}")
    
    def _hash_message(self, message: str) -> str:
        """Hash user message for PII-free logging"""
        if not message:
            return "empty"
        return hashlib.sha256(message.encode('utf-8')).hexdigest()[:16]
    
    def get_shadow_metrics(self, session_id: str) -> Dict[str, Any]:
        """Get shadow execution metrics for session"""
        return self.shadow_results.get(session_id, {})


# Global instances
feature_flags = FeatureFlags()
shadow_traffic_manager = ShadowTrafficManager(feature_flags)


# Compatibility shim for legacy imports
class LegacyFeatureFlags:
    def __init__(self):
        def flag(name, default="false"):
            return os.getenv(name, str(default)).lower() in ("1","true","yes","on")
        def percent(name, default="0"):
            try: return int(os.getenv(name, default))
            except: return 0
        
        # Field names that workflow.py expects
        self.workflow_v2_enabled = flag("WORKFLOW_V2_ENABLED", "true")  # V2 default
        self.router_v2_enabled = flag("ROUTER_V2_ENABLED", "true")     # V2 default 
        self.router_v2_shadow = flag("ROUTER_V2_SHADOW", "true")
        self.router_v2_percentage = percent("ROUTER_V2_PERCENTAGE", "100")  # 100% V2
        
        # Dataclass-style attributes for backwards compatibility
        self.WORKFLOW_V2_ENABLED = self.workflow_v2_enabled
        self.ROUTER_V2_ENABLED = self.router_v2_enabled  
        self.ROUTER_V2_SHADOW = self.router_v2_shadow
        self.ROUTER_V2_PERCENTAGE = self.router_v2_percentage
    
    @staticmethod
    def from_env() -> "LegacyFeatureFlags":
        return LegacyFeatureFlags()


def get_feature_flags() -> LegacyFeatureFlags:
    """Legacy compatibility function for workflow.py imports"""
    return LegacyFeatureFlags.from_env()