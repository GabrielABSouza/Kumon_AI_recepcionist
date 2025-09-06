"""
Instance Resolver - Canonical WhatsApp instance resolution

This module provides the single source of truth for resolving
WhatsApp instance names, preventing invalid patterns like thread_*.
"""

import logging
import re
from typing import Dict, Any, Optional, Set

logger = logging.getLogger(__name__)

# Default instance - NEVER generate thread_* patterns
DEFAULT_INSTANCE = "kumon_assistant"

# Valid instances - expand via configuration
VALID_INSTANCES: Set[str] = {
    DEFAULT_INSTANCE,
    "kumonvilaa",  # Legacy compatibility
    "kumon-assistant",  # Alternative format
}

# Invalid patterns that should NEVER be used
INVALID_PATTERNS = [
    r'^thread_.*',      # thread_555195211999 etc
    r'^default$',       # generic default
    r'^\d+$',          # pure numbers
]


def is_valid_instance(value: str) -> bool:
    """
    Check if an instance name is valid and type-safe
    
    Args:
        value: Instance name to validate
        
    Returns:
        bool: True if valid, False if invalid
    """
    if not isinstance(value, str):
        return False
        
    if not value or value.strip() == "":
        return False
    
    # NEVER allow thread_* patterns
    if value.startswith("thread_"):
        return False
        
    # NEVER allow fallback patterns
    if value in ("default", "", "None"):
        return False
    
    # Check against invalid patterns
    for pattern in INVALID_PATTERNS:
        if re.match(pattern, value):
            return False
    
    # Check if it's in the valid set
    return value in VALID_INSTANCES


def _set_instance(obj: Any, value: str) -> bool:
    """
    Type-safe instance setting helper
    
    Args:
        obj: Object to set instance on (dict, dataclass, etc)
        value: Instance value to set
        
    Returns:
        bool: True if successfully set, False otherwise
    """
    if not obj:
        return False
        
    # Handle dataclass with instance attribute
    if hasattr(obj, "instance"):
        setattr(obj, "instance", value)
        return True
    
    # Handle dict-like objects
    if isinstance(obj, dict):
        obj["instance"] = value
        return True
    
    # Handle dataclass with meta dict
    if hasattr(obj, "meta") and isinstance(obj.meta, dict):
        obj.meta["instance"] = value
        return True
        
    return False


def inject_instance_to_state(state: Dict[str, Any], envelope_instance: Optional[str]) -> None:
    """
    Type-safe instance injection that NEVER generates thread_* patterns
    
    Args:
        state: State dictionary to inject instance into
        envelope_instance: Optional instance from envelope
    """
    # Determine candidate - NEVER generate thread_* as fallback
    candidate = envelope_instance if is_valid_instance(envelope_instance or "") else DEFAULT_INSTANCE
    
    # Ensure state shapes are normalized before injection
    # This prevents 'str' object does not support item assignment errors
    from ..workflow import _normalize_state_shapes
    _normalize_state_shapes(state)
    
    # Try to set instance at multiple levels
    injection_success = False
    
    # Try delivery context
    delivery = state.get("delivery")
    if _set_instance(delivery, candidate):
        injection_success = True
    
    # Try envelope context
    envelope = state.get("envelope")
    if _set_instance(envelope, candidate):
        injection_success = True
    
    # Try channel context  
    channel = state.get("channel")
    if _set_instance(channel, candidate):
        injection_success = True
    
    # Fallback: store in state directly
    if not injection_success:
        state["resolved_instance"] = candidate
    
    logger.info(
        "INSTANCE_INJECTED|instance=%s|conv=%s",
        candidate, state.get("conversation_id", "unknown")
    )


def resolve_instance(state: Dict[str, Any]) -> str:
    """
    Type-safe instance resolution that NEVER returns thread_* patterns
    
    Priority order:
    1. delivery.instance - Delivery-specific override
    2. envelope.meta.instance - Message-specific instance
    3. channel.instance - Channel configuration
    4. resolved_instance - Fallback storage
    5. DEFAULT_INSTANCE - Final fallback
    
    Args:
        state: Conversation state
        
    Returns:
        str: Valid instance name (never thread_*)
    """
    sources = [
        # Priority 1: delivery.instance
        getattr(state.get("delivery"), "instance", None) if hasattr(state.get("delivery", {}), "instance") else state.get("delivery", {}).get("instance"),
        
        # Priority 2: envelope.meta.instance
        (getattr(state.get("envelope"), "meta", {}) if hasattr(state.get("envelope", {}), "meta") else state.get("envelope", {}).get("meta", {})).get("instance") if state.get("envelope") else None,
        
        # Priority 3: channel.instance
        getattr(state.get("channel"), "instance", None) if hasattr(state.get("channel", {}), "instance") else state.get("channel", {}).get("instance"),
        
        # Priority 4: resolved_instance fallback
        state.get("resolved_instance"),
    ]
    
    # Find first valid instance
    for source_value in sources:
        if is_valid_instance(source_value or ""):
            return source_value
    
    # Final fallback - NEVER thread_*
    return DEFAULT_INSTANCE


# Legacy function kept for compatibility but redirects to new type-safe version
def inject_instance_to_state_legacy(state: Dict[str, Any], instance: str) -> None:
    """
    Legacy injection method - redirects to type-safe version
    
    Args:
        state: Conversation state to modify
        instance: Instance name to inject
    """
    inject_instance_to_state(state, instance)