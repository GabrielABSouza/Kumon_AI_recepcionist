"""
Instance Resolver - Canonical WhatsApp instance resolution

This module provides the single source of truth for resolving
WhatsApp instance names, preventing invalid patterns like thread_*.
"""

import logging
import re
from typing import Dict, Any, Optional, Set

logger = logging.getLogger(__name__)

# Valid instances - expand via configuration
VALID_INSTANCES: Set[str] = {
    "kumon_assistant",
    "kumonvilaa",  # Legacy compatibility
    "kumon-assistant",  # Alternative format
}

# Invalid patterns that should NEVER be used
INVALID_PATTERNS = [
    r'^thread_.*',      # thread_555195211999 etc
    r'^default$',       # generic default
    r'^\d+$',          # pure numbers
]


def is_valid_instance(instance: str) -> bool:
    """
    Check if an instance name is valid
    
    Args:
        instance: Instance name to validate
        
    Returns:
        bool: True if valid, False if invalid
    """
    if not instance:
        return False
    
    # Check against invalid patterns
    for pattern in INVALID_PATTERNS:
        if re.match(pattern, instance):
            return False
    
    # Check if it's in the valid set
    return instance in VALID_INSTANCES


def resolve_instance(state: Dict[str, Any], envelope: Optional[Dict[str, Any]] = None) -> str:
    """
    Resolve WhatsApp instance using canonical hierarchy
    
    Priority order:
    1. state["delivery"]["instance"] - Delivery-specific override
    2. envelope.meta["instance"] - Message-specific instance
    3. state["channel"]["instance"] - Channel configuration
    4. state["instance"] - Global state instance
    5. Fallback to "kumon_assistant"
    
    Args:
        state: Conversation state
        envelope: Optional message envelope with meta
        
    Returns:
        str: Valid instance name
        
    Raises:
        ValueError: If no valid instance can be resolved
    """
    candidates = []
    
    # Priority 1: Delivery-specific instance
    delivery_config = state.get("delivery", {})
    if isinstance(delivery_config, dict) and delivery_config.get("instance"):
        candidates.append(("delivery", delivery_config["instance"]))
    
    # Priority 2: Envelope meta instance
    if envelope and isinstance(envelope, dict):
        meta = envelope.get("meta", {})
        if meta.get("instance"):
            candidates.append(("envelope_meta", meta["instance"]))
    
    # Priority 3: Channel configuration instance
    channel_config = state.get("channel", {})
    if isinstance(channel_config, dict) and channel_config.get("instance"):
        candidates.append(("channel", channel_config["instance"]))
    
    # Priority 4: Global state instance
    if state.get("instance"):
        candidates.append(("state", state["instance"]))
    
    # Try each candidate in order
    for source, instance in candidates:
        if is_valid_instance(instance):
            logger.info(
                "INSTANCE_RESOLVED|source=%s|instance=%s|conv=%s",
                source, instance, state.get("conversation_id", "unknown")
            )
            return instance
        else:
            logger.warning(
                "INSTANCE_INVALID|source=%s|instance=%s|pattern=%s|conv=%s",
                source, instance, "invalid", state.get("conversation_id", "unknown")
            )
    
    # Fallback to default valid instance
    fallback = "kumon_assistant"
    logger.info(
        "INSTANCE_FALLBACK|instance=%s|conv=%s",
        fallback, state.get("conversation_id", "unknown")
    )
    return fallback


def inject_instance_to_state(state: Dict[str, Any], instance: str) -> None:
    """
    Inject a valid instance into state at multiple levels
    
    This ensures the instance is available throughout the pipeline.
    
    Args:
        state: Conversation state to modify
        instance: Instance name to inject
    """
    if not is_valid_instance(instance):
        logger.error(
            "INSTANCE_INJECTION_FAILED|instance=%s|reason=invalid",
            instance
        )
        instance = "kumon_assistant"  # Force valid fallback
    
    # Inject at multiple levels for redundancy
    state["instance"] = instance
    
    # Ensure delivery config exists
    if "delivery" not in state:
        state["delivery"] = {}
    state["delivery"]["instance"] = instance
    
    # Ensure channel config exists
    if "channel" not in state:
        state["channel"] = {}
    state["channel"]["instance"] = instance
    
    logger.info(
        "INSTANCE_INJECTED|instance=%s|conv=%s",
        instance, state.get("conversation_id", "unknown")
    )