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


def universal_edge_router(state: CeciliaState) -> str:
    """
    V2 Universal Edge Router - Decides route and persists state BEFORE delivery
    
    V2 Architecture: UNIVERSAL_EDGE_ROUTER → SmartRouter + ResponsePlanner → DELIVERY
    
    This function:
    1. Executes SmartRouter to decide next route
    2. Executes ResponsePlanner to generate delivery payload  
    3. Persists routing_decision and intent_result to state
    4. Returns next node (usually DELIVERY)
    
    Args:
        state: Current conversation state (CeciliaState)
        
    Returns:
        str: Next node to route to (usually "DELIVERY")
    """
    from ..router.smart_router_adapter import SmartRouterAdapter
    from ..router.response_planner import ResponsePlanner
    from ..router.normalizers import normalize_routing_decision, normalize_intent_result
    
    phone_number = state.get("phone_number", "unknown")
    logger.info(f"🎯 Universal Edge Router: routing & planning for {phone_number[-4:]}")
    
    try:
        # Step 1: Execute SmartRouter to get routing decision
        logger.info(f"🔍 Step 1: SmartRouter deciding route")
        
        # Garantir instância do adapter e passar state corretamente
        adapter = SmartRouterAdapter()
        decision_raw = adapter.decide_route(state)  # 👈 PASSAR state
        
        # Normalizar e persistir routing decision
        state["routing_decision"] = normalize_routing_decision(decision_raw)
        
        logger.info(f"✅ Step 1 complete: routing decision = {state['routing_decision'].get('target_node', 'unknown')}")
        
        # Step 2: Execute ResponsePlanner to generate response
        logger.info(f"🔍 Step 2: ResponsePlanner generating response")
        
        # Planejar resposta
        intent_res_raw = ResponsePlanner.plan(state)
        
        # Normalizar e persistir intent result
        state["intent_result"] = (normalize_intent_result(intent_res_raw) 
                                 if intent_res_raw is not None else None)
        
        logger.info(f"✅ Step 2 complete: response planned for category={state['intent_result'].get('category', 'unknown') if state['intent_result'] else 'none'}")
        
    except Exception as router_error:
        logger.error(f"❌ Universal Edge Router error: {router_error}")
        # Create emergency fallback
        state["routing_decision"] = {
            "target_node": "delivery",
            "threshold_action": "fallback_level2",
            "confidence": 0.3,
            "reasoning": f"Router error: {str(router_error)}",
            "rule_applied": "emergency_fallback"
        }
        state["intent_result"] = {
            "category": "emergency",
            "delivery_payload": {
                "channel": "whatsapp", 
                "content": {"text": "Desculpe, houve um problema técnico. Nossa equipe entrará em contato em breve."}
            }
        }
    
    # Definir próximo nó com base na decisão já persistida
    routing_decision = state.get("routing_decision", {})
    next_stage = routing_decision.get("next_stage") or routing_decision.get("target_node", "delivery")
    
    # Route decision: direct to DELIVERY for V2 flow
    logger.info(f"🎯 Universal Edge Router: → DELIVERY (routing & planning complete)")
    return "DELIVERY"


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
