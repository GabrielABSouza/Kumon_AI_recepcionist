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
    Universal Edge Router - Routes and plans BEFORE going to DELIVERY
    
    Architecture: Stage Node → Universal Edge Router → DELIVERY Node
    
    This router executes SmartRouter + ResponsePlanner BEFORE delivery.
    The DeliveryService only sends messages, not routing/planning.
    
    Args:
        state: Current conversation state (after Stage Node execution)
        current_node: Stage Node we're routing from  
        valid_targets: Valid target nodes (should include "DELIVERY")
        
    Returns:
        Always "DELIVERY" after routing and planning
    """
    import asyncio
    from ..router import smart_router_adapter
    
    phone_number = state.get("phone_number", "unknown")
    logger.info(f"🎯 Universal Edge Router: {current_node} → routing & planning for {phone_number[-4:]}")
    
    # Create local loop for async calls
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        # Step 1: Execute SmartRouter to get routing decision
        logger.info(f"🔍 Step 1: SmartRouter deciding route from {current_node}")
        routing_decision = loop.run_until_complete(
            smart_router_adapter.decide_route(state, f"universal_edge_router_from_{current_node}")
        )
        
        # Store routing decision in state for DELIVERY consumption
        state["routing_decision"] = {
            "target_node": routing_decision.target_node,
            "threshold_action": routing_decision.threshold_action,
            "final_confidence": routing_decision.confidence,
            "intent_confidence": routing_decision.intent_confidence,
            "pattern_confidence": routing_decision.pattern_confidence,
            "rule_applied": routing_decision.rule_applied,
            "reasoning": routing_decision.reasoning,
            "timestamp": datetime.now().isoformat(),
            "mandatory_data_override": routing_decision.mandatory_data_override
        }
        
        logger.info(f"✅ Step 1 complete: routing decision = {routing_decision.target_node} (confidence: {routing_decision.confidence:.2f})")
        
        # Step 2: Execute ResponsePlanner to generate response
        logger.info(f"🔍 Step 2: ResponsePlanner generating response")
        try:
            from ...workflows.response_planner import response_planner
            
            # Plan response based on routing decision
            intent_result = loop.run_until_complete(
                response_planner.plan_and_generate(state, routing_decision)
            )
            
            # Store intent result in state for DELIVERY consumption
            state["intent_result"] = {
                "category": intent_result.get("category", ""),
                "subcategory": intent_result.get("subcategory"),
                "confidence": intent_result.get("confidence", 0.0),
                "context_entities": intent_result.get("context_entities", {}),
                "delivery_payload": intent_result.get("delivery_payload", {}),
                "policy_action": intent_result.get("policy_action"),
                "slots": intent_result.get("slots", {})
            }
            
            logger.info(f"✅ Step 2 complete: response planned for category={intent_result.get('category', 'unknown')}")
            
        except ImportError as e:
            logger.error(f"❌ Step 2 failed: ResponsePlanner not available: {e}")
            # Create fallback intent_result
            state["intent_result"] = {
                "category": "fallback",
                "delivery_payload": {
                    "channel": "whatsapp",
                    "content": {"text": "Obrigada pelo seu contato! Nossa equipe retornará em breve."}
                }
            }
        
    except Exception as e:
        logger.error(f"❌ Universal Edge Router error: {e}")
        # Create emergency fallback
        state["routing_decision"] = {
            "target_node": "fallback",
            "threshold_action": "fallback_level2",
            "confidence": 0.3,
            "reasoning": f"Router error: {str(e)}",
            "rule_applied": "emergency_fallback"
        }
        state["intent_result"] = {
            "category": "emergency",
            "delivery_payload": {
                "channel": "whatsapp", 
                "content": {"text": "Desculpe, houve um problema técnico. Nossa equipe entrará em contato em breve."}
            }
        }
    
    # Check routing decision to see if we should go to a different stage instead of DELIVERY
    routing_decision = state.get("routing_decision", {})
    target_node = routing_decision.get("target_node", "delivery")
    
    # If routing decision suggests going to a different stage node, honor it
    if target_node != "delivery" and target_node != "fallback" and target_node in valid_targets:
        logger.info(f"🎯 Universal Edge Router: {current_node} → {target_node} (stage transition required)")
        state["last_node"] = current_node
        return target_node.upper() if target_node in ["greeting", "qualification", "information", "scheduling", "validation", "confirmation"] else target_node
    
    # Mark the last node for telemetry
    state["last_node"] = current_node
    
    logger.info(f"🎯 Universal Edge Router: {current_node} → DELIVERY (routing & planning complete)")
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
