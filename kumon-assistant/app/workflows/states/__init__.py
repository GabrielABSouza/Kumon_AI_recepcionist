"""
Workflow States Package

Enhanced state management for LangGraph workflows with business compliance:
- Compliance State: Business rule compliance tracking in conversation state
- Progress Tracking: Lead qualification and conversation progress monitoring
- Integration with CeciliaState: Seamless state enhancement and updates
"""

# Import from the core state system to avoid circular imports
from ...core.state.models import (
    CeciliaState as ConversationState,
    ConversationStage as WorkflowStage,
    ConversationStep,
    create_initial_cecilia_state as create_initial_state
)

# Legacy state types - create simple compatibility classes
class AgentState(dict):
    """Legacy compatibility for AgentState - simple dict wrapper"""
    pass

class UserContext:
    """Legacy compatibility for UserContext"""
    def __init__(self, state=None):
        self._state = state or {}

# Import ConversationMetrics from the legacy states file
try:
    from ..states import ConversationMetricsLegacy as ConversationMetrics
except ImportError:
    # Fallback simple class
    class ConversationMetrics:
        def __init__(self, state=None):
            self._state = state or {}
        
        @property
        def message_count(self):
            return getattr(self._state, 'get', lambda k, d: d)("message_count", 0)
        
        @property
        def failed_attempts(self):
            return getattr(self._state, 'get', lambda k, d: d)("failed_attempts", 0)

from .compliance_state import (
    BusinessRuleComplianceState,
    QualificationProgressState,
    PricingDiscussionState,
    HandoffTrackingState,
    enhance_cecilia_state_with_compliance,
    update_compliance_state,
    get_compliance_summary
)

__all__ = [
    'ConversationState',
    'WorkflowStage',
    'ConversationStep',
    'create_initial_state',
    'AgentState',
    'UserContext',
    'ConversationMetrics',
    'BusinessRuleComplianceState',
    'QualificationProgressState',
    'PricingDiscussionState',
    'HandoffTrackingState',
    'enhance_cecilia_state_with_compliance',
    'update_compliance_state',
    'get_compliance_summary'
]