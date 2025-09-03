"""
Routing Functions for LangGraph Workflow

Implementa todas as funções de roteamento que determinam o próximo node
baseado no estado atual da conversa e nas condições de circuit breaker.

Segue rigorosamente a documentação langgraph_orquestration.md
"""

from typing import Literal
from datetime import datetime, timezone
from ..state.models import CeciliaState, ConversationStage, ConversationStep, get_collected_field, set_collected_field, add_decision_to_trail, safe_update_state
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
            # NOTE: Removed state mutation to maintain edge purity (V2 architecture)
            # validation_node will get context from routing_decision instead
            pass
            
            logger.info(
                f"🎯 Routing to validation: {validation_decision['decision_reasoning']}"
            )
        
        return should_validate
        
    except Exception as e:
        logger.error(f"Error in intelligent validation routing: {e}")
        # Fail-safe: route to validation on error
        # NOTE: Removed state mutation to maintain edge purity (V2 architecture)
        return True


def universal_edge_router(state: CeciliaState) -> str:
    """
    PURE Universal Edge Router - READ-ONLY routing based on existing state
    
    V2 Architecture: NODES handle decisions, EDGES only route
    - SmartRouter and ResponsePlanner decisions are made in separate NODES
    - This edge function is PURE: only reads state, no mutations
    
    This function:
    1. Reads existing routing_decision from state (set by SMART_ROUTER node)
    2. Routes to target_node based on decision
    3. NO STATE MUTATIONS (violates V2 architecture)
    
    Args:
        state: Current conversation state (CeciliaState)
        
    Returns:
        str: Next node to route to based on routing_decision
    """
    phone_number = state.get("phone_number", "unknown")
    logger.info(f"🎯 Pure Universal Edge Router: routing for {phone_number[-4:]}")
    
    # READ-ONLY: Get routing decision (should be set by SMART_ROUTER node)
    routing_decision = state.get("routing_decision", {})
    
    if not routing_decision:
        logger.warning(f"⚠️ No routing_decision found in state - using fallback to DELIVERY")
        return "DELIVERY"
    
    # Extract target from routing decision
    target_node = routing_decision.get("target_node") or routing_decision.get("next_stage", "DELIVERY")
    
    # Normalize target node names (V1 compatibility)
    if target_node.lower() == "delivery":
        target_node = "DELIVERY"
    
    logger.info(f"🎯 Pure Universal Edge Router: → {target_node} (read from routing_decision)")
    return target_node


def route_from_greeting(
    state: CeciliaState
) -> Literal["DELIVERY", "qualification", "information", "scheduling"]:
    """Route from greeting node - may transition to other stages or DELIVERY"""
    valid_targets = ["DELIVERY", "qualification", "information", "scheduling"]
    return universal_edge_router(state, "greeting", valid_targets)


def route_from_qualification(
    state: CeciliaState
) -> Literal["DELIVERY", "information", "scheduling", "greeting"]:
    """Route from qualification node - may transition to other stages or DELIVERY"""
    valid_targets = ["DELIVERY", "information", "scheduling", "greeting"]
    return universal_edge_router(state, "qualification", valid_targets)


def route_from_information(
    state: CeciliaState
) -> Literal["DELIVERY", "scheduling", "qualification", "greeting"]:
    """Route from information node - may transition to other stages or DELIVERY"""
    valid_targets = ["DELIVERY", "scheduling", "qualification", "greeting"]
    return universal_edge_router(state, "information", valid_targets)


def route_from_scheduling(
    state: CeciliaState
) -> Literal["DELIVERY", "confirmation", "validation", "information"]:
    """Route from scheduling node - may transition to other stages or DELIVERY"""
    valid_targets = ["DELIVERY", "confirmation", "validation", "information"]
    return universal_edge_router(state, "scheduling", valid_targets)


def route_from_validation(
    state: CeciliaState
) -> Literal["DELIVERY", "confirmation", "scheduling"]:
    """Route from validation node - may transition to other stages or DELIVERY"""
    valid_targets = ["DELIVERY", "confirmation", "scheduling"]
    return universal_edge_router(state, "validation", valid_targets)


def route_from_emergency_progression(
    state: CeciliaState
) -> Literal["DELIVERY"]:
    """Route from emergency progression node - always goes to DELIVERY after planning response"""
    valid_targets = ["DELIVERY"]
    return universal_edge_router(state, "emergency_progression", valid_targets)


def route_from_confirmation(
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
