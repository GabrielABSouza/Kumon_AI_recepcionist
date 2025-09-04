"""
Feature Flags for Kumon Assistant

Centralized feature flag system for gradual rollouts and A/B testing.
"""

import os
import logging
import copy
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FeatureFlag:
    """Feature flag configuration"""
    name: str
    enabled: bool
    description: str
    rollout_percentage: int = 100  # 0-100
    environment_restriction: Optional[str] = None  # "staging", "production", etc.


class FeatureFlagManager:
    """Feature flag management system"""
    
    def __init__(self):
        self.flags: Dict[str, FeatureFlag] = {
            # Enum Normalization Feature Flags
            "STRICT_ENUM_STAGESTEP": FeatureFlag(
                name="STRICT_ENUM_STAGESTEP",
                enabled=self._get_env_bool("STRICT_ENUM_STAGESTEP", True),  # Default true in staging
                description="Enforce strict enum types for current_stage/current_step",
                rollout_percentage=100,
                environment_restriction=None
            ),
            
            "ENUM_VIOLATION_TELEMETRY": FeatureFlag(
                name="ENUM_VIOLATION_TELEMETRY", 
                enabled=self._get_env_bool("ENUM_VIOLATION_TELEMETRY", True),
                description="Enable telemetry collection for enum type violations",
                rollout_percentage=100
            ),
            
            "ENUM_AUTO_CORRECTION": FeatureFlag(
                name="ENUM_AUTO_CORRECTION",
                enabled=self._get_env_bool("ENUM_AUTO_CORRECTION", True),
                description="Automatically correct string values to enums when possible",
                rollout_percentage=100
            ),
            
            # Template System Feature Flags
            "TEMPLATE_VARIABLE_POLICY_V2": FeatureFlag(
                name="TEMPLATE_VARIABLE_POLICY_V2",
                enabled=self._get_env_bool("TEMPLATE_VARIABLE_POLICY_V2", True),
                description="Use V2 variable resolution policy system",
                rollout_percentage=100
            ),
            
            # Outbox V2 Feature Flags
            "OUTBOX_V2_ENFORCED": FeatureFlag(
                name="OUTBOX_V2_ENFORCED",
                enabled=self._get_env_bool("OUTBOX_V2_ENFORCED", True),
                description="Enforce V2 outbox handoff with type-safe MessageEnvelope",
                rollout_percentage=100
            ),
            
            # Shadow Traffic Feature Flags
            "ROUTER_V2_ENABLED": FeatureFlag(
                name="ROUTER_V2_ENABLED",
                enabled=self._get_env_bool("ROUTER_V2_ENABLED", False),
                description="Enable V2 router for live traffic",
                rollout_percentage=self._get_env_int("ROUTER_V2_PERCENTAGE", 0)
            ),
            
            "ROUTER_V2_SHADOW": FeatureFlag(
                name="ROUTER_V2_SHADOW",
                enabled=self._get_env_bool("ROUTER_V2_SHADOW", True),
                description="Enable V2 shadow traffic for comparison",
                rollout_percentage=100
            ),
        }
        
        logger.info(f"FeatureFlagManager initialized with {len(self.flags)} flags")
        self._log_enabled_flags()
    
    def _get_env_bool(self, env_var: str, default: bool) -> bool:
        """Get boolean value from environment variable"""
        value = os.environ.get(env_var, str(default)).lower()
        return value in ("true", "1", "yes", "on")
    
    def _get_env_int(self, env_var: str, default: int) -> int:
        """Get integer value from environment variable"""
        try:
            return int(os.environ.get(env_var, str(default)))
        except ValueError:
            logger.warning(f"Invalid integer value for {env_var}, using default: {default}")
            return default
    
    def _log_enabled_flags(self):
        """Log currently enabled flags for debugging"""
        enabled_flags = [name for name, flag in self.flags.items() if flag.enabled]
        logger.info(f"Enabled feature flags: {enabled_flags}")
    
    def is_enabled(self, flag_name: str, default: bool = False) -> bool:
        """Check if a feature flag is enabled"""
        flag = self.flags.get(flag_name)
        
        if not flag:
            logger.warning(f"Unknown feature flag: {flag_name}, returning default: {default}")
            return default
        
        if not flag.enabled:
            return False
        
        # Check environment restriction
        if flag.environment_restriction:
            current_env = os.environ.get("ENVIRONMENT", "development").lower()
            if current_env != flag.environment_restriction.lower():
                return False
        
        # TODO: Add rollout percentage logic if needed for gradual rollouts
        return True
    
    def get_flag_status(self, flag_name: str) -> Dict[str, Any]:
        """Get detailed status of a feature flag"""
        flag = self.flags.get(flag_name)
        
        if not flag:
            return {"exists": False, "flag_name": flag_name}
        
        return {
            "exists": True,
            "name": flag.name,
            "enabled": flag.enabled,
            "description": flag.description,
            "rollout_percentage": flag.rollout_percentage,
            "environment_restriction": flag.environment_restriction,
            "current_environment": os.environ.get("ENVIRONMENT", "development")
        }
    
    def get_all_flags(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all feature flags"""
        return {
            name: self.get_flag_status(name)
            for name in self.flags.keys()
        }
    
    def set_flag(self, flag_name: str, enabled: bool) -> bool:
        """Dynamically set a feature flag (for testing)"""
        if flag_name not in self.flags:
            logger.error(f"Cannot set unknown flag: {flag_name}")
            return False
        
        self.flags[flag_name].enabled = enabled
        logger.info(f"Feature flag {flag_name} set to {enabled}")
        return True
    
    # Shadow traffic management methods
    @property
    def router_v2_enabled(self) -> bool:
        """Check if V2 router is enabled for live traffic"""
        return self.is_enabled("ROUTER_V2_ENABLED", default=False)
    
    @property
    def router_v2_shadow(self) -> bool:
        """Check if V2 shadow traffic is enabled"""
        return self.is_enabled("ROUTER_V2_SHADOW", default=True)
    
    @property
    def router_v2_percentage(self) -> int:
        """Get V2 router rollout percentage"""
        flag = self.flags.get("ROUTER_V2_ENABLED")
        return flag.rollout_percentage if flag else 0
    
    @property
    def v2_timeout_ms(self) -> int:
        """Get V2 shadow execution timeout in milliseconds"""
        return self._get_env_int("V2_TIMEOUT_MS", 500)
    
    @property
    def v2_max_latency_ms(self) -> int:
        """Get maximum acceptable V2 latency in milliseconds"""
        return self._get_env_int("V2_MAX_LATENCY_MS", 1000)
    
    def get_architecture_mode(self, session_id: str) -> str:
        """Determine architecture mode for a session"""
        if self.router_v2_enabled:
            # Simple hash-based distribution for now
            hash_val = hash(session_id) % 100
            if hash_val < self.router_v2_percentage:
                return "v2_live"
        
        if self.router_v2_shadow:
            return "v2_shadow"
        
        return "v1_only"


class ShadowTrafficManager:
    """Manager for shadow traffic operations and state management"""
    
    def __init__(self, feature_flags_manager: FeatureFlagManager):
        self.feature_flags = feature_flags_manager
        
    def _deep_copy_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create a deep copy of state for shadow execution"""
        try:
            return copy.deepcopy(state)
        except Exception as e:
            logger.warning(f"Failed to deep copy state, using shallow copy: {e}")
            return state.copy()
    
    def is_shadow_enabled(self, session_id: str) -> bool:
        """Check if shadow traffic is enabled for this session"""
        architecture_mode = self.feature_flags.get_architecture_mode(session_id)
        return architecture_mode in ["v2_shadow", "v2_live"]
    
    def should_use_v2_live(self, session_id: str) -> bool:
        """Check if session should use V2 live architecture"""
        return self.feature_flags.get_architecture_mode(session_id) == "v2_live"
    
    def get_shadow_config(self) -> Dict[str, Any]:
        """Get shadow traffic configuration"""
        return {
            "router_v2_enabled": self.feature_flags.router_v2_enabled,
            "router_v2_shadow": self.feature_flags.router_v2_shadow,
            "router_v2_percentage": self.feature_flags.router_v2_percentage,
            "v2_timeout_ms": self.feature_flags.v2_timeout_ms,
            "v2_max_latency_ms": self.feature_flags.v2_max_latency_ms
        }


# Global feature flag manager
feature_flags = FeatureFlagManager()

# Global shadow traffic manager
shadow_traffic_manager = ShadowTrafficManager(feature_flags)


def is_strict_enum_enforcement() -> bool:
    """Check if strict enum enforcement is enabled"""
    return feature_flags.is_enabled("STRICT_ENUM_STAGESTEP", default=True)


def is_enum_telemetry_enabled() -> bool:
    """Check if enum violation telemetry is enabled"""
    return feature_flags.is_enabled("ENUM_VIOLATION_TELEMETRY", default=True)


def is_enum_auto_correction_enabled() -> bool:
    """Check if enum auto-correction is enabled"""
    return feature_flags.is_enabled("ENUM_AUTO_CORRECTION", default=True)


def is_variable_policy_v2_enabled() -> bool:
    """Check if V2 variable resolution policy is enabled"""
    return feature_flags.is_enabled("TEMPLATE_VARIABLE_POLICY_V2", default=True)


def is_outbox_v2_enforced() -> bool:
    """Check if V2 outbox handoff enforcement is enabled"""
    return feature_flags.is_enabled("OUTBOX_V2_ENFORCED", default=True)


# ========== CANONICAL API ==========

def get_feature_flags() -> 'FeatureFlagManager':
    """
    Canonical API for accessing feature flags
    
    Returns:
        FeatureFlagManager: Global feature flag manager instance
    """
    return feature_flags


class FeatureFlags:
    """Static API for feature flags (alternative interface)"""
    
    @staticmethod
    def current() -> 'FeatureFlagManager':
        """Get current feature flags manager"""
        return feature_flags
    
    @staticmethod 
    def is_enabled(flag_name: str, default: bool = False) -> bool:
        """Check if a feature flag is enabled"""
        return feature_flags.is_enabled(flag_name, default)
    
    @staticmethod
    def get_all() -> dict:
        """Get all feature flags status"""
        return feature_flags.get_all_flags()