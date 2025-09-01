"""
Stage Mapping Utility - Canonical target_node → Stage/Step mapping

Centralized mapping logic for converting routing decisions (target_node)
to proper ConversationStage and ConversationStep updates.

Used by DeliveryService as single source of truth for stage progression.
"""

from typing import Tuple
from .models import ConversationStage, ConversationStep


def map_target_to_stage_step(target_node: str, current_stage: ConversationStage) -> Tuple[ConversationStage, ConversationStep]:
    """
    Map target_node to appropriate ConversationStage and ConversationStep
    
    Args:
        target_node: Routing decision target (e.g., "qualification", "scheduling")
        current_stage: Current conversation stage for context
        
    Returns:
        Tuple of (new_stage, new_step)
    """
    
    # Canonical mapping: target_node -> (Stage, Step)
    target_mappings = {
        # Stage progression mappings
        "qualification": (ConversationStage.QUALIFICATION, ConversationStep.PARENT_NAME_COLLECTION),
        "information": (ConversationStage.INFORMATION_GATHERING, ConversationStep.PROGRAM_EXPLANATION),
        "scheduling": (ConversationStage.SCHEDULING, ConversationStep.SLOT_PRESENTATION),
        "validation": (ConversationStage.VALIDATION, ConversationStep.CONTACT_CONFIRMATION),
        "confirmation": (ConversationStage.CONFIRMATION, ConversationStep.FINAL_CONFIRMATION),
        
        # Special routing targets
        "handoff": (ConversationStage.HANDOFF, ConversationStep.HUMAN_TRANSFER),
        "emergency_progression": (ConversationStage.QUALIFICATION, ConversationStep.PARENT_NAME_COLLECTION),
        
        # Fallback handling - stay in current stage but reset to welcome step
        "fallback": (current_stage, ConversationStep.WELCOME),
    }
    
    # Get mapping with fallback
    if target_node in target_mappings:
        return target_mappings[target_node]
    
    # Fallback for unknown targets - progressive advancement
    fallback_progression = {
        ConversationStage.GREETING: (ConversationStage.QUALIFICATION, ConversationStep.PARENT_NAME_COLLECTION),
        ConversationStage.QUALIFICATION: (ConversationStage.INFORMATION_GATHERING, ConversationStep.PROGRAM_EXPLANATION),
        ConversationStage.INFORMATION_GATHERING: (ConversationStage.SCHEDULING, ConversationStep.SLOT_PRESENTATION),
        ConversationStage.SCHEDULING: (ConversationStage.VALIDATION, ConversationStep.CONTACT_CONFIRMATION),
        ConversationStage.VALIDATION: (ConversationStage.CONFIRMATION, ConversationStep.FINAL_CONFIRMATION),
        ConversationStage.CONFIRMATION: (ConversationStage.CONFIRMATION, ConversationStep.FINAL_CONFIRMATION),
        ConversationStage.HANDOFF: (ConversationStage.HANDOFF, ConversationStep.HUMAN_TRANSFER),
    }
    
    return fallback_progression.get(current_stage, (ConversationStage.GREETING, ConversationStep.WELCOME))


def get_valid_targets_for_stage(stage: ConversationStage) -> list[str]:
    """
    Get valid target_node options for a given stage
    
    Used by edges for validation and fallback mapping.
    
    Args:
        stage: Current conversation stage
        
    Returns:
        List of valid target_node strings
    """
    
    stage_valid_targets = {
        ConversationStage.GREETING: ["qualification", "scheduling", "validation", "handoff", "emergency_progression"],
        ConversationStage.QUALIFICATION: ["information", "scheduling", "validation", "handoff"],
        ConversationStage.INFORMATION_GATHERING: ["scheduling", "validation", "handoff"],
        ConversationStage.SCHEDULING: ["validation", "confirmation", "handoff"],
        ConversationStage.VALIDATION: ["confirmation", "handoff"],
        ConversationStage.CONFIRMATION: ["handoff"],
        ConversationStage.HANDOFF: ["handoff"],
    }
    
    return stage_valid_targets.get(stage, ["qualification"])


def validate_target_for_stage(target_node: str, current_stage: ConversationStage) -> str:
    """
    Validate and correct target_node for current stage
    
    Used by edges to ensure valid transitions before returning target_node.
    
    Args:
        target_node: Proposed target node
        current_stage: Current conversation stage
        
    Returns:
        Valid target_node (corrected if necessary)
    """
    
    valid_targets = get_valid_targets_for_stage(current_stage)
    
    if target_node in valid_targets:
        return target_node
    
    # Fallback corrections by stage
    stage_fallbacks = {
        ConversationStage.GREETING: "qualification",
        ConversationStage.QUALIFICATION: "information", 
        ConversationStage.INFORMATION_GATHERING: "scheduling",
        ConversationStage.SCHEDULING: "validation",
        ConversationStage.VALIDATION: "confirmation",
        ConversationStage.CONFIRMATION: "confirmation",
        ConversationStage.HANDOFF: "handoff",
    }
    
    return stage_fallbacks.get(current_stage, "qualification")