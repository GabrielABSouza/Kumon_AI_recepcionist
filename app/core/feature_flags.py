"""
Feature Flags for Kumon Assistant

Centralized feature flag system for gradual rollouts and A/B testing.
"""

import os
import logging
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
        }
        
        logger.info(f"FeatureFlagManager initialized with {len(self.flags)} flags")
        self._log_enabled_flags()
    
    def _get_env_bool(self, env_var: str, default: bool) -> bool:
        """Get boolean value from environment variable"""
        value = os.environ.get(env_var, str(default)).lower()
        return value in ("true", "1", "yes", "on")
    
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


# Global feature flag manager
feature_flags = FeatureFlagManager()


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