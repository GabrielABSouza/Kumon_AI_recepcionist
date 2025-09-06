"""
Router Normalizers - Normalize routing decisions and intent results

Ensures consistent data structures between SmartRouter/ResponsePlanner outputs
and state persistence.
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def normalize_routing_decision(decision_raw: Any) -> Dict[str, Any]:
    """
    Normalize routing decision from SmartRouter output to dict format
    
    Args:
        decision_raw: Raw decision from SmartRouter (could be dataclass, dict, etc.)
        
    Returns:
        Dict[str, Any]: Normalized routing decision
    """
    if decision_raw is None:
        return {
            "target_node": "delivery",
            "threshold_action": "fallback_level2",
            "confidence": 0.3,
            "reasoning": "No routing decision available",
            "rule_applied": "fallback"
        }
    
    # If already a dict, return as-is with defaults
    if isinstance(decision_raw, dict):
        return {
            "target_node": decision_raw.get("target_node", "delivery"),
            "threshold_action": decision_raw.get("threshold_action", "fallback_level1"),
            "confidence": decision_raw.get("confidence", 0.5),
            "intent_confidence": decision_raw.get("intent_confidence", 0.5),
            "pattern_confidence": decision_raw.get("pattern_confidence", 0.5),
            "rule_applied": decision_raw.get("rule_applied", "unknown"),
            "reasoning": decision_raw.get("reasoning", "No reasoning provided"),
            "next_stage": decision_raw.get("next_stage"),
            "mandatory_data_override": decision_raw.get("mandatory_data_override", False)
        }
    
    # If dataclass or object, use getattr
    return {
        "target_node": getattr(decision_raw, "target_node", "delivery"),
        "threshold_action": getattr(decision_raw, "threshold_action", "fallback_level1"),
        "confidence": getattr(decision_raw, "confidence", 0.5),
        "intent_confidence": getattr(decision_raw, "intent_confidence", 0.5),
        "pattern_confidence": getattr(decision_raw, "pattern_confidence", 0.5),
        "rule_applied": getattr(decision_raw, "rule_applied", "unknown"),
        "reasoning": getattr(decision_raw, "reasoning", "No reasoning provided"),
        "next_stage": getattr(decision_raw, "next_stage", None),
        "mandatory_data_override": getattr(decision_raw, "mandatory_data_override", False)
    }


def normalize_intent_result(intent_result_raw: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize intent result from ResponsePlanner output to dict format
    
    Args:
        intent_result_raw: Raw intent result from ResponsePlanner
        
    Returns:
        Optional[Dict[str, Any]]: Normalized intent result or None
    """
    if intent_result_raw is None:
        return None
    
    # If already a dict, return as-is with defaults
    if isinstance(intent_result_raw, dict):
        return {
            "category": intent_result_raw.get("category", "fallback"),
            "subcategory": intent_result_raw.get("subcategory"),
            "confidence": intent_result_raw.get("confidence", 0.5),
            "context_entities": intent_result_raw.get("context_entities", {}),
            "delivery_payload": intent_result_raw.get("delivery_payload", {}),
            "policy_action": intent_result_raw.get("policy_action"),
            "slots": intent_result_raw.get("slots", {})
        }
    
    # If dataclass or object, use getattr
    return {
        "category": getattr(intent_result_raw, "category", "fallback"),
        "subcategory": getattr(intent_result_raw, "subcategory", None),
        "confidence": getattr(intent_result_raw, "confidence", 0.5),
        "context_entities": getattr(intent_result_raw, "context_entities", {}),
        "delivery_payload": getattr(intent_result_raw, "delivery_payload", {}),
        "policy_action": getattr(intent_result_raw, "policy_action", None),
        "slots": getattr(intent_result_raw, "slots", {})
    }