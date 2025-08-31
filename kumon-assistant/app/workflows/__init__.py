"""
Workflow management package for Kumon Assistant

This package contains the modular SmartRouter system:
- intent_classifier: Intent classification with confidence scoring
- pattern_scorer: Stage-aware pattern matching and scoring
- intelligent_threshold_system: Threshold-based routing decisions
- smart_router: Main routing orchestrator combining all components
- context_manager: Conversation context and reference management
- workflow_orchestrator: Legacy workflow orchestrator (being phased out)
"""

# Core SmartRouter components
from .smart_router import smart_router
from .intent_classifier import IntentClassifier
from .pattern_scorer import PatternScorer
from .intelligent_threshold_system import ThresholdEngine
from .context_manager import context_manager

# Legacy orchestrator (being phased out)
from .workflow_orchestrator import workflow_orchestrator

__all__ = [
    # SmartRouter system
    "smart_router",
    "IntentClassifier",
    "PatternScorer", 
    "ThresholdEngine",
    "context_manager",
    
    # Legacy
    "workflow_orchestrator"
]