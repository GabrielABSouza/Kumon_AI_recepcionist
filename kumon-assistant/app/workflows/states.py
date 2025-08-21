"""
Compatibility Bridge: Legacy States → CeciliaState Migration
URGENT: Creates missing states module to bridge legacy workflows to CeciliaState
"""

# Import the actual CeciliaState components
from ..core.state.models import (
    CeciliaState,
    ConversationStage as CoreConversationStage,
    ConversationStep as CoreConversationStep,
    CollectedData,
    ConversationMetrics,
    DataValidation,
    DecisionTrail,
    create_initial_cecilia_state,
    get_collected_field,
    set_collected_field,
    increment_metric,
    add_decision_to_trail
)

# ============ COMPATIBILITY ALIASES ============
# Bridge legacy naming to CeciliaState system

# Main state type
ConversationState = CeciliaState

# Stage and step enums (keeping legacy names for compatibility)
WorkflowStage = CoreConversationStage
ConversationStep = CoreConversationStep

# Utility function aliases
def create_initial_state(phone_number: str, user_message: str = "") -> CeciliaState:
    """Legacy compatibility: create_initial_state → create_initial_cecilia_state"""
    return create_initial_cecilia_state(phone_number, user_message)

# ============ LEGACY COMPATIBILITY CLASSES ============
# For files that expect different class structures

class UserContext:
    """Legacy compatibility: UserContext as dict-like access to collected_data"""
    def __init__(self, state: CeciliaState):
        self._state = state
    
    @property
    def parent_name(self):
        return get_collected_field(self._state, "parent_name")
    
    @property
    def child_name(self):
        return get_collected_field(self._state, "child_name")
    
    @property
    def student_age(self):
        return get_collected_field(self._state, "student_age")
    
    @property
    def contact_email(self):
        return get_collected_field(self._state, "contact_email")
    
    def to_dict(self):
        return dict(self._state["collected_data"])

class ConversationMetricsLegacy:
    """Legacy compatibility: ConversationMetrics wrapper"""
    def __init__(self, state: CeciliaState):
        self._metrics = state["conversation_metrics"]
    
    @property
    def message_count(self):
        return self._metrics["message_count"]
    
    @property
    def failed_attempts(self):
        return self._metrics["failed_attempts"]
    
    @property
    def consecutive_confusion(self):
        return self._metrics["consecutive_confusion"]
    
    def to_dict(self):
        return dict(self._metrics)

# ============ LEGACY STATE MANAGEMENT ============

class AgentState:
    """Legacy compatibility: AgentState wrapper around CeciliaState"""
    def __init__(self, cecilia_state: CeciliaState):
        self._state = cecilia_state
    
    @property
    def phone_number(self):
        return self._state["phone_number"]
    
    @property
    def current_stage(self):
        return self._state["current_stage"]
    
    @property
    def current_step(self):
        return self._state["current_step"]
    
    @property
    def last_user_message(self):
        return self._state["last_user_message"]
    
    @property
    def collected_data(self):
        return self._state["collected_data"]
    
    @property
    def conversation_metrics(self):
        return self._state["conversation_metrics"]
    
    def update_stage(self, stage: WorkflowStage):
        self._state["current_stage"] = stage
    
    def update_step(self, step: ConversationStep):
        self._state["current_step"] = step
    
    def set_collected_field(self, field: str, value):
        set_collected_field(self._state, field, value)
    
    def get_collected_field(self, field: str):
        return get_collected_field(self._state, field)

# ============ MIGRATION HELPERS ============

def migrate_legacy_state_to_cecilia(legacy_data: dict) -> CeciliaState:
    """Convert legacy state dictionary to CeciliaState"""
    phone_number = legacy_data.get("phone_number", "unknown")
    user_message = legacy_data.get("last_user_message", "")
    
    # Create new CeciliaState
    cecilia_state = create_initial_cecilia_state(phone_number, user_message)
    
    # Migrate stage and step if present
    if "current_stage" in legacy_data:
        cecilia_state["current_stage"] = legacy_data["current_stage"]
    if "current_step" in legacy_data:
        cecilia_state["current_step"] = legacy_data["current_step"]
    
    # Migrate collected data
    if "collected_data" in legacy_data:
        for key, value in legacy_data["collected_data"].items():
            set_collected_field(cecilia_state, key, value)
    
    return cecilia_state

def extract_legacy_compatible_data(cecilia_state: CeciliaState) -> dict:
    """Extract data from CeciliaState in legacy format for compatibility"""
    return {
        "phone_number": cecilia_state["phone_number"],
        "current_stage": cecilia_state["current_stage"],
        "current_step": cecilia_state["current_step"],
        "last_user_message": cecilia_state["last_user_message"],
        "collected_data": dict(cecilia_state["collected_data"]),
        "conversation_metrics": dict(cecilia_state["conversation_metrics"])
    }

# ============ EXPORT LEGACY INTERFACE ============

__all__ = [
    # Core types (bridged to CeciliaState)
    "ConversationState",
    "WorkflowStage", 
    "ConversationStep",
    "CollectedData",
    "ConversationMetrics",
    "DataValidation",
    "DecisionTrail",
    
    # Utility functions
    "create_initial_state",
    "get_collected_field",
    "set_collected_field",
    "increment_metric",
    "add_decision_to_trail",
    
    # Legacy compatibility classes
    "UserContext",
    "ConversationMetricsLegacy",
    "AgentState",
    
    # Migration helpers
    "migrate_legacy_state_to_cecilia",
    "extract_legacy_compatible_data"
]