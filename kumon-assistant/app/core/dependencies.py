# app/core/dependencies.py

"""
Centralized dependency management for the application.

This module holds global instances of services that are initialized once at startup
and shared across the application to avoid re-instantiation on every request.
"""

from typing import Optional

# Import service classes, not instances
from app.services.production_llm_service import ProductionLLMService
from app.workflows.intent_classifier import AdvancedIntentClassifier
from app.workflows.secure_conversation_workflow import SecureConversationWorkflow

# Global instances, will be initialized on startup in main.py
llm_service: Optional[ProductionLLMService] = None
intent_classifier: Optional[AdvancedIntentClassifier] = None
secure_workflow: Optional[SecureConversationWorkflow] = None
