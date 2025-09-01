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
from ..router.smart_router_adapter import smart_router_adapter
from ..router.response_planner import response_planner
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
    PHASE 2.5: Simplified Universal Edge Router
    
    Architecture: Stage Node → Simple Edge → ROUTING Node → DELIVERY Node
    
    This edge now checks if the node was already processed by ROUTING to prevent loops.
    If it was, goes to DELIVERY. Otherwise goes to ROUTING for decision making.
    
    Args:
        state: Current conversation state (after Stage Node execution)
        current_node: Stage Node we're routing from  
        valid_targets: Valid target nodes (should include "ROUTING" and "DELIVERY")
        
    Returns:
        "DELIVERY" if node already processed by ROUTING, "ROUTING" otherwise
    """
    phone_number = state.get("phone_number", "unknown")
    
    # Check if this node was already processed by ROUTING to prevent loops
    routing_decision = state.get("routing_decision", {})
    target_node = routing_decision.get("target_node")
    
    if target_node == current_node and state.get("routing_complete"):
        # This node was targeted by ROUTING and routing is complete
        # Go to DELIVERY to send response
        logger.info(f"🎯 Edge Router: {current_node} → DELIVERY (routing complete) for {phone_number[-4:]}")
        return "DELIVERY"
    else:
        # First time processing or need routing decision
        logger.info(f"🔄 Simple Edge Router: {current_node} → ROUTING for {phone_number[-4:]}")
        
        # Store context for ROUTING node to use
        state["last_node"] = current_node
        state["routing_requested_at"] = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"✅ Simple Edge: Routing {current_node} → ROUTING node")
        return "ROUTING"


def route_from_greeting(
    state: CeciliaState
) -> Literal["ROUTING", "DELIVERY"]:
    """Route from greeting node - goes to ROUTING for decision or DELIVERY if already processed"""
    valid_targets = ["ROUTING", "DELIVERY"]
    return universal_edge_router(state, "greeting", valid_targets)


def route_from_qualification(
    state: CeciliaState
) -> Literal["ROUTING", "DELIVERY"]:
    """Route from qualification node - goes to ROUTING for decision or DELIVERY if already processed"""
    valid_targets = ["ROUTING", "DELIVERY"]
    return universal_edge_router(state, "qualification", valid_targets)


def route_from_information(
    state: CeciliaState
) -> Literal["ROUTING", "DELIVERY"]:
    """Route from information node - goes to ROUTING for decision or DELIVERY if already processed"""
    valid_targets = ["ROUTING", "DELIVERY"]
    return universal_edge_router(state, "information", valid_targets)


def route_from_scheduling(
    state: CeciliaState
) -> Literal["ROUTING", "DELIVERY"]:
    """Route from scheduling node - goes to ROUTING for decision or DELIVERY if already processed"""
    valid_targets = ["ROUTING", "DELIVERY"]
    return universal_edge_router(state, "scheduling", valid_targets)


def route_from_validation(
    state: CeciliaState
) -> Literal["ROUTING", "DELIVERY"]:
    """Route from validation node - goes to ROUTING for decision or DELIVERY if already processed"""
    valid_targets = ["ROUTING", "DELIVERY"]
    return universal_edge_router(state, "validation", valid_targets)


def route_from_emergency_progression(
    state: CeciliaState
) -> Literal["ROUTING", "DELIVERY"]:
    """Route from emergency progression node - goes to ROUTING for decision or DELIVERY if already processed"""
    valid_targets = ["ROUTING", "DELIVERY"]
    return universal_edge_router(state, "emergency_progression", valid_targets)


def route_from_confirmation(
    state: CeciliaState
) -> Literal["ROUTING", "DELIVERY"]:
    """Route from confirmation node - goes to ROUTING for decision or DELIVERY if already processed"""
    valid_targets = ["ROUTING", "DELIVERY"]
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