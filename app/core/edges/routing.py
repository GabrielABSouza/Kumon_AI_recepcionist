"""
Routing Functions for LangGraph Workflow

Implementa todas as funções de roteamento que determinam o próximo node
baseado no estado atual da conversa e nas condições de circuit breaker.

Segue rigorosamente a documentação langgraph_orquestration.md
"""

from typing import Literal
from datetime import datetime, timezone
from ..state.models import CeciliaState, ConversationStage, ConversationStep, get_collected_field, set_collected_field, add_decision_to_trail
from ..state.managers import StateManager
from .intent_detection import IntentDetector
from .conditions import ConditionChecker
from .validation_routing import kumon_validation_router
import logging

logger = logging.getLogger(__name__)

# Inicializar detectores uma vez
intent_detector = IntentDetector()
condition_checker = ConditionChecker()


def should_route_to_validation(state: CeciliaState) -> bool:
    """
    Intelligent validation routing using hybrid Score-Based + Rule Engine system
    
    Replaces primitive if/else logic with sophisticated validation decision engine.
    
    Returns:
        bool: True if validation_node should be activated
    """
    try:
        # Use intelligent validation router
        validation_decision = kumon_validation_router.should_validate_response(state)
        
        should_validate = validation_decision["should_validate"]
        
        if should_validate:
            # Store validation decision context in state for validation_node
            state["validation_decision_context"] = {
                "method": validation_decision["primary_method"],
                "confidence": validation_decision["combined_confidence"],
                "reasoning": validation_decision["decision_reasoning"],
                "triggered_at": datetime.now().isoformat()
            }
            
            logger.info(
                f"🎯 Routing to validation: {validation_decision['decision_reasoning']}"
            )
        
        return should_validate
        
    except Exception as e:
        logger.error(f"Error in intelligent validation routing: {e}")
        # Fail-safe: route to validation on error
        state["validation_decision_context"] = {
            "method": "error_fallback", 
            "confidence": 0.5,
            "reasoning": "Validation required due to routing error",
            "error": str(e)
        }
        return True


def universal_edge_router(
    state: CeciliaState,
    current_node: str,
    valid_targets: list
) -> str:
    """
    Universal Edge Router - Always plans response and returns DELIVERY
    
    Architecture: Stage Node → Universal Edge Router → DELIVERY Node
    
    This router executes SmartRouter + ResponsePlanner and always returns "DELIVERY".
    The DeliveryService will update stage/step canonically after sending the message.
    
    Args:
        state: Current conversation state (after Stage Node execution)
        current_node: Stage Node we're routing from  
        valid_targets: Valid target nodes (should include "DELIVERY")
        
    Returns:
        Always "DELIVERY" after planning response
    """
    phone_number = state.get("phone_number", "unknown")
    
    logger.info(f"🎯 Universal Edge Router: {current_node} → DELIVERY for {phone_number[-4:]}")
    # Zero side-effects: DELIVERY node centralizes routing/planning/sending
    state["last_node"] = current_node
    return "DELIVERY"


async def route_from_greeting(
    state: CeciliaState
) -> Literal["DELIVERY"]:
    """Route from greeting node - always goes to DELIVERY after planning response"""
    valid_targets = ["DELIVERY"]
    return universal_edge_router(state, "greeting", valid_targets)


async def route_from_qualification(
    state: CeciliaState
) -> Literal["DELIVERY"]:
    """Route from qualification node - always goes to DELIVERY after planning response"""
    valid_targets = ["DELIVERY"]
    return universal_edge_router(state, "qualification", valid_targets)


async def route_from_information(
    state: CeciliaState
) -> Literal["DELIVERY"]:
    """Route from information node - always goes to DELIVERY after planning response"""
    valid_targets = ["DELIVERY"]
    return universal_edge_router(state, "information", valid_targets)


async def route_from_scheduling(
    state: CeciliaState
) -> Literal["DELIVERY"]:
    """Route from scheduling node - always goes to DELIVERY after planning response"""
    valid_targets = ["DELIVERY"]
    return universal_edge_router(state, "scheduling", valid_targets)


async def route_from_validation(
    state: CeciliaState
) -> Literal["DELIVERY"]:
    """Route from validation node - always goes to DELIVERY after planning response"""
    valid_targets = ["DELIVERY"]
    return universal_edge_router(state, "validation", valid_targets)


async def route_from_emergency_progression(
    state: CeciliaState
) -> Literal["DELIVERY"]:
    """Route from emergency progression node - always goes to DELIVERY after planning response"""
    valid_targets = ["DELIVERY"]
    return universal_edge_router(state, "emergency_progression", valid_targets)


async def route_from_confirmation(
    state: CeciliaState
) -> Literal["DELIVERY"]:
    """Route from confirmation node - always goes to DELIVERY after planning response"""
    valid_targets = ["DELIVERY"]
    return universal_edge_router(state, "confirmation", valid_targets)




def _should_suggest_appointment(state: CeciliaState) -> bool:
    """
    Determina se deve sugerir agendamento baseado no contexto
    MIGRAR: Lógica de sugestão do conversation_flow.py
    """
    # Usar metrics para determinar progressão
    metrics = state["conversation_metrics"]
    message_count = metrics["message_count"]
    
    # Tem interesse demonstrado?
    programs_interest = get_collected_field(state, "programs_of_interest") or []
    
    # Detecta engajamento na mensagem atual?
    has_engagement = intent_detector.detect_engagement_question(state["last_user_message"])
    
    suggest_conditions = [
        message_count >= 4,  # Já teve várias mensagens
        len(programs_interest) > 0,  # Mostrou interesse em programas
        has_engagement  # Pergunta de engajamento detectada
    ]
    
    return any(suggest_conditions)
