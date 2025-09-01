# app/core/dependencies.py

"""
Centralized dependency management for the application.

This module holds global instances of services that are initialized once at startup
and shared across the application to avoid re-instantiation on every request.
"""

from typing import Optional

# Global instances, will be initialized on startup in main.py
llm_service: Optional["ProductionLLMService"] = None
intent_classifier: Optional["AdvancedIntentClassifier"] = None
cecilia_workflow: Optional["CeciliaWorkflow"] = None  # UPDATED: Using CeciliaWorkflow instead of secure_workflow
langchain_rag_service: Optional["LangChainRAGService"] = None
intelligent_threshold_system: Optional["IntelligentThresholdSystem"] = None
