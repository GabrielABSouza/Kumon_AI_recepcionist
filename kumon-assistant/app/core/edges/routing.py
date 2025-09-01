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
    PHASE 2.2: Universal Routing Node implementation
    
    Routing Node pattern: Stage Node → Routing Node (this edge) → DeliveryService
    
    Sequence:
    1. smart_router_adapter.decide_route(state, edge_name)
    2. response_planner.plan_and_generate(state, routing_decision) [without sending]
    3. Return target_node for LangGraph progression
    
    Args:
        state: Current conversation state (after Stage Node execution)
        current_node: Stage Node we're routing from
        valid_targets: Valid target nodes for this edge
    """
    logger.info(f"🔄 Routing Node: {current_node} → ? for {state['phone_number']}")
    
    try:
        # Run async operations in sync context (LangGraph compatibility)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # STEP 1: SmartRouter decision
        routing_decision = loop.run_until_complete(
            smart_router_adapter.decide_route(state, f"route_from_{current_node}")
        )
        
        # STEP 2: ResponsePlanner generates planned_response (without sending)
        logger.info(f"🎯 Routing Node calling ResponsePlanner for {current_node}")
        loop.run_until_complete(
            response_planner.plan_and_generate(state, routing_decision)
        )
        # planned_response is now in state["planned_response"]
        
        target = routing_decision.target_node
        
        # PHASE 2.2: Validate and correct invalid targets per edge
        stage_fallbacks = {
            "greeting": "qualification",  # GREETING defaults to qualification
            "qualification": "information",  # QUALIFICATION defaults to information
            "information": "scheduling",  # INFORMATION defaults to scheduling
            "scheduling": "confirmation",  # SCHEDULING defaults to confirmation
        }
        
        if target not in valid_targets:
            # Apply stage-specific fallback mapping
            fallback_target = stage_fallbacks.get(current_node)
            if fallback_target and fallback_target in valid_targets:
                target = fallback_target
                logger.info(f"🔧 Corrected invalid target: {routing_decision.target_node} → {target} for {current_node}")
            else:
                # Generic fallback to first valid target
                target = valid_targets[0]
                logger.warning(f"⚠️ Using generic fallback: {target} for {current_node}")
        
        # Store final routing info for DeliveryService
        state["routing_info"] = {
            "target_node": target,
            "original_target": routing_decision.target_node,
            "threshold_action": routing_decision.threshold_action,
            "confidence": routing_decision.confidence,
            "reasoning": routing_decision.reasoning,
            "from_node": current_node,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage_type": type(state.get("current_stage")).__name__,
            "target_validated": target == routing_decision.target_node
        }
        
        logger.info(
            f"✅ Routing Node: {current_node} → {target} "
            f"(action: {routing_decision.threshold_action}, confidence: {routing_decision.confidence:.2f})"
        )
        
        return target
        
    except Exception as e:
        logger.error(f"🚨 Routing Node error: {e}, using fallback")
        
        # CRITICAL FALLBACK: Apply stage-specific safe defaults
        stage_safe_fallbacks = {
            "greeting": "qualification",
            "qualification": "information", 
            "information": "scheduling",
            "scheduling": "confirmation",
            "validation": "handoff",
            "confirmation": "handoff"
        }
        
        fallback = stage_safe_fallbacks.get(current_node)
        if fallback and fallback in valid_targets:
            return fallback
        elif "handoff" in valid_targets:
            return "handoff"  # Ultimate safety net
        else:
            return valid_targets[0]  # Last resort


def route_from_greeting(
    state: CeciliaState
) -> Literal["qualification", "scheduling", "validation", "handoff", "emergency_progression"]:
    """Route from greeting node - delegates to universal router"""
    valid_targets = ["qualification", "scheduling", "validation", "handoff", "emergency_progression"]
    return universal_edge_router(state, "greeting", valid_targets)


def route_from_qualification(
    state: CeciliaState
) -> Literal["information", "scheduling", "validation", "handoff", "emergency_progression"]:
    """Route from qualification node - delegates to universal router"""
    valid_targets = ["information", "scheduling", "validation", "handoff", "emergency_progression"]
    return universal_edge_router(state, "qualification", valid_targets)


def route_from_information(
    state: CeciliaState
) -> Literal["information", "scheduling", "validation", "handoff", "emergency_progression"]:
    """Route from information node - delegates to universal router"""
    valid_targets = ["information", "scheduling", "validation", "handoff", "emergency_progression"]
    return universal_edge_router(state, "information", valid_targets)


def route_from_scheduling(
    state: CeciliaState
) -> Literal["scheduling", "confirmation", "validation", "handoff", "emergency_progression"]:
    """Route from scheduling node - delegates to universal router"""
    valid_targets = ["scheduling", "confirmation", "validation", "handoff", "emergency_progression"]
    return universal_edge_router(state, "scheduling", valid_targets)


def route_from_validation(
    state: CeciliaState
) -> Literal["greeting", "qualification", "information", "scheduling", "confirmation", "handoff", "retry_validation", "emergency_progression"]:
    """Route from validation node - delegates to universal router"""
    valid_targets = ["greeting", "qualification", "information", "scheduling", "confirmation", "handoff", "retry_validation", "emergency_progression"]
    return universal_edge_router(state, "validation", valid_targets)


def route_from_emergency_progression(
    state: CeciliaState
) -> Literal["information", "scheduling", "handoff", "END"]:
    """Route from emergency progression node - delegates to universal router"""
    valid_targets = ["information", "scheduling", "handoff", "END"]
    return universal_edge_router(state, "emergency_progression", valid_targets)


def emergency_progression_node(state: CeciliaState) -> CeciliaState:
    """
    Node de emergência acionado pelo circuit breaker
    Aplica as ações recomendadas pelo circuit breaker para destravar a conversa
    """
    logger.warning(f"Emergency progression activated for {state['phone_number']}")
    
    # Get the last circuit breaker action from decision trail
    last_decisions = state["decision_trail"]["last_decisions"]
    circuit_breaker_action = None
    
    # Find the most recent circuit breaker action
    for decision in reversed(last_decisions):
        if decision.get("type") == "circuit_breaker_action":
            circuit_breaker_action = decision.get("action")
            break
    
    # Generate appropriate response based on action
    if circuit_breaker_action == "handoff":
        response = (
            "Vou conectar você com nossa equipe para um atendimento mais personalizado! 👩‍💼\n\n"
            "📞 **(51) 99692-1999**\n"
            "📧 **kumonvilaa@gmail.com**\n\n"
            "Nossa equipe terá prazer em ajudá-lo! 😊"
        )
        # Update state for handoff
        state["current_stage"] = ConversationStage.COMPLETED
        state["current_step"] = ConversationStep.CONVERSATION_ENDED
    
    elif circuit_breaker_action == "emergency_scheduling":
        response = (
            "Entendo que você gostaria de agendar uma visita! 📅\n\n"
            "Vou direcioná-lo para nosso agendamento.\n\n"
            "Qual período é melhor para você?\n"
            "**🌅 MANHÃ** ou **🌆 TARDE**?"
        )
        # Update state for scheduling
        state["current_stage"] = ConversationStage.SCHEDULING
        state["current_step"] = ConversationStep.DATE_PREFERENCE
    
    elif circuit_breaker_action == "information_bypass":
        response = (
            "Deixe-me compartilhar informações importantes sobre o Kumon! 📚\n\n"
            "O que você gostaria de saber:\n"
            "• Como funciona nossa metodologia\n"
            "• Valores dos programas\n"
            "• Benefícios para o aluno"
        )
        # Update state for information gathering
        state["current_stage"] = ConversationStage.INFORMATION_GATHERING
        state["current_step"] = ConversationStep.METHODOLOGY_EXPLANATION
    
    else:
        # Default emergency response - reset to a safe state
        response = (
            "Vou simplificar nosso processo para ajudá-lo melhor! 😊\n\n"
            "Como posso ajudar você hoje?\n"
            "• Informações sobre o Kumon\n"
            "• Agendamento de visita\n"
            "• Falar com nossa equipe"
        )
        # Reset to information gathering as safe fallback
        state["current_stage"] = ConversationStage.INFORMATION_GATHERING
        state["current_step"] = ConversationStep.METHODOLOGY_EXPLANATION
    
    # Reset failure metrics to give the conversation a fresh start
    state["conversation_metrics"]["failed_attempts"] = 0
    state["conversation_metrics"]["consecutive_confusion"] = 0
    state["conversation_metrics"]["same_question_count"] = 0
    
    # Add message to conversation
    state["messages"].append({
        "role": "assistant",
        "content": response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "emergency_progression"
    })
    
    # Record decision in trail
    add_decision_to_trail(state, {
        "type": "emergency_progression_completed",
        "action": circuit_breaker_action or "default_reset",
        "new_stage": state["current_stage"],
        "new_step": state["current_step"],
        "response_sent": True
    })
    
    logger.info(f"Emergency progression completed for {state['phone_number']}, action: {circuit_breaker_action}")
    
    return state


def route_from_confirmation(
    state: CeciliaState
) -> Literal["handoff", "END"]:
    """Route from confirmation node - delegates to universal router"""
    valid_targets = ["handoff", "END"]
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