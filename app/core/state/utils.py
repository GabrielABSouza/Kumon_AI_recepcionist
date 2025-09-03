"""
State utilities for CeciliaState normalization and type consistency.

Provides utilities to ensure consistent Enum types throughout the workflow
and prevent AttributeError/TypeError issues with current_stage/current_step.
"""

import logging
from typing import Dict, Any
from .models import ConversationStage, ConversationStep, CeciliaState

logger = logging.getLogger(__name__)


def normalize_state_enums(state: CeciliaState) -> CeciliaState:
    """
    Normalize current_stage and current_step to proper Enums.
    
    Converts string representations back to Enums and sets defaults if missing.
    Safe to call multiple times (idempotent).
    
    Args:
        state: CeciliaState dictionary (mutable)
        
    Returns:
        Normalized CeciliaState with proper Enum types
        
    Handles:
        - current_stage: string → ConversationStage Enum
        - current_step: string → ConversationStep Enum  
        - Missing values: set safe defaults
        - Already-Enums: pass through unchanged
    """
    
    # Normalize current_stage
    current_stage = state.get("current_stage")
    
    if current_stage is None:
        # No stage set - use neutral default (StageResolver will define context)
        state["current_stage"] = ConversationStage.UNSET
        logger.info("🔧 Set neutral current_stage: UNSET (StageResolver will resolve)")
        
    elif isinstance(current_stage, str):
        # String representation - convert to Enum
        try:
            # Handle both "GREETING" and "ConversationStage.GREETING" formats
            stage_name = current_stage.split('.')[-1] if '.' in current_stage else current_stage
            normalized_stage = ConversationStage(stage_name.lower())
            state["current_stage"] = normalized_stage
            logger.debug(f"🔧 Normalized current_stage: {current_stage} → {normalized_stage}")
            
        except ValueError:
            # Invalid stage string - use neutral default (StageResolver will resolve)
            logger.warning(f"⚠️ Invalid current_stage '{current_stage}', using UNSET")
            state["current_stage"] = ConversationStage.UNSET
            
    elif isinstance(current_stage, ConversationStage):
        # Already an Enum - pass through
        logger.debug(f"✅ current_stage already normalized: {current_stage}")
        
    else:
        # Unexpected type - use neutral default (StageResolver will resolve)
        logger.warning(f"⚠️ Unexpected current_stage type {type(current_stage)}, using UNSET")
        state["current_stage"] = ConversationStage.UNSET
    
    
    # Normalize current_step
    current_step = state.get("current_step")
    
    if current_step is None:
        # No step set - use default based on stage
        default_step = _get_default_step_for_stage(state["current_stage"])
        state["current_step"] = default_step
        logger.info(f"🔧 Set default current_step: {default_step}")
        
    elif isinstance(current_step, str):
        # String representation - convert to Enum
        try:
            # Handle both "WELCOME" and "ConversationStep.WELCOME" formats  
            step_name = current_step.split('.')[-1] if '.' in current_step else current_step
            normalized_step = ConversationStep(step_name.lower())
            state["current_step"] = normalized_step
            logger.debug(f"🔧 Normalized current_step: {current_step} → {normalized_step}")
            
        except ValueError:
            # Invalid step string - use default for stage
            default_step = _get_default_step_for_stage(state["current_stage"])
            logger.warning(f"⚠️ Invalid current_step '{current_step}', using {default_step}")
            state["current_step"] = default_step
            
    elif isinstance(current_step, ConversationStep):
        # Already an Enum - pass through
        logger.debug(f"✅ current_step already normalized: {current_step}")
        
    else:
        # Unexpected type - use default
        default_step = _get_default_step_for_stage(state["current_stage"])
        logger.warning(f"⚠️ Unexpected current_step type {type(current_step)}, using {default_step}")
        state["current_step"] = default_step
    
    return state


def _get_default_step_for_stage(stage: ConversationStage) -> ConversationStep:
    """
    Get the default step for a given conversation stage.
    
    Args:
        stage: ConversationStage enum
        
    Returns:
        Appropriate default ConversationStep for the stage
    """
    
    stage_defaults = {
        ConversationStage.GREETING: ConversationStep.WELCOME,
        ConversationStage.QUALIFICATION: ConversationStep.CHILD_AGE_INQUIRY,
        ConversationStage.INFORMATION_GATHERING: ConversationStep.METHODOLOGY_EXPLANATION,
        ConversationStage.SCHEDULING: ConversationStep.AVAILABILITY_CHECK,
        ConversationStage.CONFIRMATION: ConversationStep.APPOINTMENT_CONFIRMED,
        ConversationStage.COMPLETED: ConversationStep.WELCOME  # Fallback
    }
    
    return stage_defaults.get(stage, ConversationStep.WELCOME)


def safe_enum_value(enum_or_str) -> str:
    """
    Safely extract string value from Enum or string.
    
    Args:
        enum_or_str: ConversationStage/ConversationStep enum or string
        
    Returns:
        String representation safe for logging/comparison
        
    Usage:
        stage_str = safe_enum_value(state["current_stage"])
        # Works for both Enum and string inputs
    """
    
    if hasattr(enum_or_str, 'value'):
        return enum_or_str.value
    else:
        return str(enum_or_str)


def validate_state_consistency(state: CeciliaState) -> Dict[str, Any]:
    """
    Validate state consistency and return diagnostic info.
    
    Args:
        state: CeciliaState to validate
        
    Returns:
        Dict with validation results and diagnostics
    """
    
    issues = []
    
    # Check required fields exist
    if "current_stage" not in state:
        issues.append("Missing current_stage")
    if "current_step" not in state:
        issues.append("Missing current_step")
    if "phone_number" not in state:
        issues.append("Missing phone_number")
        
    # Check types
    current_stage = state.get("current_stage")
    if current_stage and not isinstance(current_stage, ConversationStage):
        issues.append(f"current_stage wrong type: {type(current_stage)}")
        
    current_step = state.get("current_step")
    if current_step and not isinstance(current_step, ConversationStep):
        issues.append(f"current_step wrong type: {type(current_step)}")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "current_stage": safe_enum_value(current_stage) if current_stage else None,
        "current_step": safe_enum_value(current_step) if current_step else None,
        "stage_type": str(type(current_stage)),
        "step_type": str(type(current_step))
    }