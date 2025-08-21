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
import logging

logger = logging.getLogger(__name__)

# Inicializar detectores uma vez
intent_detector = IntentDetector()
condition_checker = ConditionChecker()


def route_from_greeting(
    state: CeciliaState
) -> Literal["qualification", "scheduling", "validation", "handoff", "emergency_progression"]:
    """
    Roteamento após node de saudação COM CIRCUIT BREAKER
    """
    logger.info(f"Routing from greeting for {state['phone_number']}")
    
    # CRÍTICO: Verificar circuit breaker PRIMEIRO
    circuit_check = StateManager.check_circuit_breaker(state)
    
    if circuit_check["should_activate"]:
        logger.warning(f"Circuit breaker activated in greeting for {state['phone_number']}")
        
        action = circuit_check["recommended_action"]
        circuit_updates = StateManager.apply_circuit_breaker_action(state, action)
        StateManager.update_state(state, circuit_updates)
        
        return "emergency_progression"
    
    # 1. PRIORIDADE MÁXIMA: Verificar falha de conversa
    if condition_checker.should_handoff(state):
        return "handoff"
    
    # 2. GLOBAL: Detectar intenção de agendamento direto
    if intent_detector.detect_booking_intent(state["last_user_message"]):
        logger.info(f"Booking intent detected in greeting for {state['phone_number']}")
        return "scheduling"
    
    # 3. GLOBAL: Detectar pulo de perguntas
    if intent_detector.detect_skip_questions(state["last_user_message"]):
        logger.info(f"Skip questions intent detected for {state['phone_number']}")
        return "scheduling"
    
    # 4. Fluxo normal: ir para qualificação
    if state["current_stage"] == ConversationStage.QUALIFICATION:
        return "qualification"
    
    # 5. Precisa validação?
    if state.get("needs_validation", False):
        return "validation"
    
    # Default: qualificação
    return "qualification"


def route_from_qualification(
    state: CeciliaState
) -> Literal["information", "scheduling", "validation", "handoff", "emergency_progression"]:
    """Roteamento após qualificação COM CIRCUIT BREAKER"""
    logger.info(f"Routing from qualification for {state['phone_number']}")
    
    # Circuit breaker check
    circuit_check = StateManager.check_circuit_breaker(state)
    
    if circuit_check["should_activate"]:
        action = circuit_check["recommended_action"]
        circuit_updates = StateManager.apply_circuit_breaker_action(state, action)
        StateManager.update_state(state, circuit_updates)
        return "emergency_progression"
    
    # Verificar handoff
    if condition_checker.should_handoff(state):
        return "handoff"
    
    # Detectar agendamento direto
    if intent_detector.detect_booking_intent(state["last_user_message"]):
        return "scheduling"
    
    # Verificar se completou qualificação
    required_data = ["student_age", "education_level"]
    has_required = all(get_collected_field(state, field) for field in required_data)
    
    if has_required:
        return "information"
    
    # Continuar qualificação ou validar
    return "validation" if state.get("needs_validation") else "qualification"


def route_from_information(
    state: CeciliaState
) -> Literal["information", "scheduling", "validation", "handoff", "emergency_progression"]:
    """Roteamento após node de informações"""
    logger.info(f"Routing from information for {state['phone_number']}")
    
    # Circuit breaker check
    circuit_check = StateManager.check_circuit_breaker(state)
    
    if circuit_check["should_activate"]:
        action = circuit_check["recommended_action"]
        circuit_updates = StateManager.apply_circuit_breaker_action(state, action)
        StateManager.update_state(state, circuit_updates)
        return "emergency_progression"
    
    # Verificar handoff
    if condition_checker.should_handoff(state):
        return "handoff"
    
    # Detectar agendamento direto
    if intent_detector.detect_booking_intent(state["last_user_message"]):
        return "scheduling"
    
    # Detectar pulo de perguntas
    if intent_detector.detect_skip_questions(state["last_user_message"]):
        return "scheduling"
    
    # Verificar se deve sugerir agendamento
    should_suggest = _should_suggest_appointment(state)
    if should_suggest:
        return "scheduling"
    
    # Continuar com informações ou validar
    return "validation" if state.get("needs_validation") else "information"


def route_from_scheduling(
    state: CeciliaState
) -> Literal["scheduling", "confirmation", "validation", "handoff", "emergency_progression"]:
    """Roteamento após scheduling"""
    logger.info(f"Routing from scheduling for {state['phone_number']}")
    
    # Circuit breaker check
    circuit_check = StateManager.check_circuit_breaker(state)
    
    if circuit_check["should_activate"]:
        action = circuit_check["recommended_action"]
        circuit_updates = StateManager.apply_circuit_breaker_action(state, action)
        StateManager.update_state(state, circuit_updates)
        return "emergency_progression"
    
    # Verificar handoff (mais tolerante no scheduling)
    if condition_checker.should_handoff(state, stage_context="scheduling"):
        return "handoff"
    
    # Verificar se agendamento foi completado
    if get_collected_field(state, "selected_slot") and get_collected_field(state, "contact_email"):
        return "confirmation"
    
    # Continuar scheduling ou validar
    return "validation" if state.get("needs_validation") else "scheduling"


def route_from_validation(
    state: CeciliaState
) -> Literal["greeting", "qualification", "information", "scheduling", "confirmation", "handoff", "retry_validation", "emergency_progression"]:
    """Roteamento após validação"""
    logger.info(f"Routing from validation for {state['phone_number']}")
    
    # Circuit breaker check
    circuit_check = StateManager.check_circuit_breaker(state)
    
    if circuit_check["should_activate"]:
        action = circuit_check["recommended_action"]
        circuit_updates = StateManager.apply_circuit_breaker_action(state, action)
        StateManager.update_state(state, circuit_updates)
        return "emergency_progression"
    
    # Verificar handoff
    if condition_checker.should_handoff(state):
        return "handoff"
    
    # Se validação passou, voltar para estágio atual
    if not state.get("needs_validation", False):
        current_stage = state["current_stage"]
        
        if current_stage == ConversationStage.GREETING:
            return "greeting"
        elif current_stage == ConversationStage.QUALIFICATION:
            return "qualification"
        elif current_stage == ConversationStage.INFORMATION_GATHERING:
            return "information"
        elif current_stage == ConversationStage.SCHEDULING:
            return "scheduling"
        elif current_stage == ConversationStage.CONFIRMATION:
            return "confirmation"
    
    # Se ainda precisa validação e não excedeu tentativas
    if condition_checker.should_retry_validation(state):
        return "retry_validation"
    
    # Default: voltar para greeting
    return "greeting"


def route_from_emergency_progression(
    state: CeciliaState
) -> Literal["information", "scheduling", "handoff", "END"]:
    """Roteamento após emergency progression do circuit breaker"""
    logger.info(f"Emergency progression routing for {state['phone_number']}")
    
    # Get the last circuit breaker action from decision trail
    last_decisions = state["decision_trail"]["last_decisions"]
    circuit_breaker_action = None
    
    # Find the most recent circuit breaker action
    for decision in reversed(last_decisions):
        if decision.get("type") == "circuit_breaker_action":
            circuit_breaker_action = decision.get("action")
            break
    
    logger.info(f"Found circuit breaker action: {circuit_breaker_action}")
    
    # Route based on circuit breaker action
    if circuit_breaker_action == "handoff":
        logger.info(f"Emergency progression → handoff for {state['phone_number']}")
        return "handoff"
    elif circuit_breaker_action == "emergency_scheduling":
        logger.info(f"Emergency progression → scheduling for {state['phone_number']}")
        return "scheduling"
    elif circuit_breaker_action == "information_bypass":
        logger.info(f"Emergency progression → information for {state['phone_number']}")
        return "information"
    
    # Fallback logic based on conversation state
    collected_data = state["collected_data"]
    metrics = state["conversation_metrics"]
    
    # If conversation has been going on too long, handoff
    if metrics["message_count"] > 20:
        logger.warning(f"Emergency progression → handoff (message count exceeded): {state['phone_number']}")
        return "handoff"
    
    # If we have basic info, try scheduling
    has_basic_info = any([
        collected_data.get("parent_name"),
        collected_data.get("child_name"),
        collected_data.get("student_age")
    ])
    
    if has_basic_info:
        logger.info(f"Emergency progression → scheduling (has basic info): {state['phone_number']}")
        return "scheduling"
    
    # If no info collected and many failures, handoff
    if metrics["failed_attempts"] >= 4:
        logger.warning(f"Emergency progression → handoff (too many failures): {state['phone_number']}")
        return "handoff"
    
    # Default: try to collect information first
    logger.info(f"Emergency progression → information (default): {state['phone_number']}")
    return "information"


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
) -> Literal["completed", "validation"]:
    """Roteamento após confirmação final"""
    logger.info(f"Routing from confirmation for {state['phone_number']}")
    
    # Se ainda precisa validação, validar primeiro
    if state.get("needs_validation", False):
        return "validation"
    
    # Caso contrário, conversa completa
    return "completed"




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