"""
Workflow management package for Kumon Assistant

This package contains:
- State definitions for LangGraph workflows
- Node implementations for each conversation stage
- Edge definitions for state transitions
- Validation logic for response quality
- Main workflow graph construction
"""

# Core workflow orchestrator (primary system)
from .workflow_orchestrator import workflow_orchestrator

# Legacy compatibility bridge (for gradual migration)
from .states import ConversationState, WorkflowStage, ConversationStep, create_initial_state

# Optional workflow components (if needed)
# from .intent_classifier import intent_classifier
# from .context_manager import context_manager  
# from .smart_router import smart_router
# from .intelligent_fallback import intelligent_fallback

__all__ = [
    # Core workflow system
    "workflow_orchestrator",
    
    # Legacy compatibility
    "ConversationState",
    "WorkflowStage", 
    "ConversationStep",
    "create_initial_state"
]