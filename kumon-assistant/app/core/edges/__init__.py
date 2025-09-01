"""
Edge Functions for LangGraph Routing

Este módulo contém as funções de roteamento que determinam o próximo node
baseado no estado atual da conversa e nas condições de circuit breaker.

Migrado da lógica de decisão do conversation_flow.py conforme documentação.
"""

from .routing import (
    route_from_greeting,
    route_from_qualification,
    route_from_information,
    route_from_scheduling,
    route_from_validation,
    route_from_confirmation,
    route_from_emergency_progression
)
from .intent_detection import IntentDetector
from .conditions import ConditionChecker

__all__ = [
    "route_from_greeting",
    "route_from_qualification",
    "route_from_information",
    "route_from_scheduling", 
    "route_from_validation",
    "route_from_confirmation",
    "route_from_emergency_progression",
    "IntentDetector",
    "ConditionChecker"
]