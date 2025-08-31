"""
State management module for CeciliaState

This module provides the enhanced state structure and utilities for the
LangGraph-based Kumon Assistant conversation system.
"""

from .models import (
    CeciliaState,
    ConversationStage,
    ConversationStep,
    CollectedData,
    ConversationMetrics,
    DataValidation,
    DecisionTrail,
    create_initial_cecilia_state,
    get_collected_field,
    set_collected_field,
    increment_metric,
    add_decision_to_trail,
    add_validation_failure,
    safe_update_state
)

from .managers import (
    StateManager
)

__all__ = [
    "CeciliaState",
    "ConversationStage",
    "ConversationStep", 
    "CollectedData",
    "ConversationMetrics",
    "DataValidation",
    "DecisionTrail",
    "create_initial_cecilia_state",
    "get_collected_field",
    "set_collected_field",
    "increment_metric",
    "add_decision_to_trail",
    "add_validation_failure",
    "safe_update_state",
    "StateManager"
]