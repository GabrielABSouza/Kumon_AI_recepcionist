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
    Universal edge router - SINGLE source of routing truth via SmartRouter
    
    All routing decisions flow through SmartRouter:
    1. SmartRouter makes decision (includes circuit breaker, handoff logic)
    2. ResponsePlanner generates response if needed
    3. Return target node
    
    Args:
        state: Current conversation state
        current_node: Node we're routing from
        valid_targets: Valid target nodes for this edge
    """
    logger.info(f"Universal routing from {current_node} for {state['phone_number']}")
    
    try:
        # Run async SmartRouter in sync context (LangGraph compatibility)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # SmartRouter is the ONLY decision maker
        routing_decision = loop.run_until_complete(
            smart_router_adapter.decide_route(state, f"route_from_{current_node}")
        )
        
        # Store routing decision in state for later use
        state["routing_decision"] = {
            "target_node": routing_decision.target_node,
            "threshold_action": routing_decision.threshold_action,
            "confidence": routing_decision.confidence,
            "reasoning": routing_decision.reasoning,
            "from_node": current_node,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # ResponsePlanner will generate response based on threshold_action later
        # (only if needed - when threshold_action != "enhance_with_llm")
        
        target = routing_decision.target_node
        
        # Validate target is allowed for this edge
        if target not in valid_targets:
            logger.warning(
                f"SmartRouter returned '{target}' which is not valid for {current_node}. "
                f"Valid targets: {valid_targets}. Defaulting to {valid_targets[0]}"
            )
            target = valid_targets[0]
        
        logger.info(
            f"SmartRouter decision: {current_node} → {target} "
            f"(confidence: {routing_decision.confidence:.2f}, action: {routing_decision.threshold_action})"
        )
        
        return target
        
    except Exception as e:
        logger.error(f"SmartRouter failed in universal router: {e}, using safe fallback")
        
        # CRITICAL FALLBACK: If SmartRouter completely fails, safe default
        # This should rarely happen as SmartRouter has its own fallbacks
        if "handoff" in valid_targets:
            return "handoff"  # Safest option when system fails
        return valid_targets[0]  # First valid target as last resort


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