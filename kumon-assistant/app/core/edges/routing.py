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


def route_from_greeting(
    state: CeciliaState
) -> Literal["qualification", "scheduling", "validation", "handoff", "emergency_progression"]:
    """
    Roteamento após node de saudação COM CIRCUIT BREAKER + SmartRouter Integration
    
    New Architecture: Core safety checks + Modular SmartRouter for intelligent routing
    """
    logger.info(f"Routing from greeting for {state['phone_number']}")
    
    # CRÍTICO: Verificar circuit breaker PRIMEIRO (mantém segurança do core)
    circuit_check = StateManager.check_circuit_breaker(state)
    
    if circuit_check["should_activate"]:
        logger.warning(f"Circuit breaker activated in greeting for {state['phone_number']}")
        
        action = circuit_check["recommended_action"]
        circuit_updates = StateManager.apply_circuit_breaker_action(state, action)
        StateManager.update_state(state, circuit_updates)
        
        return "emergency_progression"
    
    # PRIORIDADE MÁXIMA: Verificar falha de conversa (mantém lógica de segurança)
    if condition_checker.should_handoff(state):
        return "handoff"
    
    # NEW: Use SmartRouter for intelligent routing decisions
    try:
        # Run async SmartRouter in sync context (LangGraph compatibility)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        routing_decision = loop.run_until_complete(
            smart_router_adapter.decide_route(state, "route_from_greeting")
        )
        
        # NEW: Plan and generate response BEFORE routing to node
        loop.run_until_complete(
            response_planner.plan_and_generate(state, routing_decision)
        )
        
        # Map decision to valid return values for this edge
        target = routing_decision.target_node
        
        # Ensure target is valid for this edge
        valid_targets = ["qualification", "scheduling", "validation", "handoff", "emergency_progression"]
        if target not in valid_targets:
            logger.warning(f"SmartRouter returned invalid target '{target}' for greeting, defaulting to qualification")
            target = "qualification"
        
        logger.info(
            f"SmartRouter decision for greeting: {target} (confidence: {routing_decision.confidence:.2f})"
        )
        
        return target
        
    except Exception as e:
        logger.error(f"SmartRouter failed in route_from_greeting: {e}, using fallback")
        
        # FALLBACK: Maintain critical legacy logic for safety
        if intent_detector.detect_booking_intent(state.get("last_user_message", "")):
            logger.info(f"Fallback: Booking intent detected for {state['phone_number']}")
            return "scheduling"
        
        # Intelligent validation routing
        if should_route_to_validation(state):
            return "validation"
        
        # Default: qualificação
        return "qualification"


def route_from_qualification(
    state: CeciliaState
) -> Literal["information", "scheduling", "validation", "handoff", "emergency_progression"]:
    """Roteamento após qualificação COM CIRCUIT BREAKER + SmartRouter Integration"""
    logger.info(f"Routing from qualification for {state['phone_number']}")
    
    # CRÍTICO: Verificar circuit breaker PRIMEIRO
    circuit_check = StateManager.check_circuit_breaker(state)
    
    if circuit_check["should_activate"]:
        action = circuit_check["recommended_action"]
        circuit_updates = StateManager.apply_circuit_breaker_action(state, action)
        StateManager.update_state(state, circuit_updates)
        return "emergency_progression"
    
    # PRIORIDADE MÁXIMA: Verificar falha de conversa
    if condition_checker.should_handoff(state):
        return "handoff"
    
    # NEW: Use SmartRouter for intelligent routing decisions
    try:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        routing_decision = loop.run_until_complete(
            smart_router_adapter.decide_route(state, "route_from_qualification")
        )
        
        # NEW: Plan and generate response BEFORE routing to node
        loop.run_until_complete(
            response_planner.plan_and_generate(state, routing_decision)
        )
        
        target = routing_decision.target_node
        
        # Ensure target is valid for this edge
        valid_targets = ["information", "scheduling", "validation", "handoff", "emergency_progression"]
        if target not in valid_targets:
            logger.warning(f"SmartRouter returned invalid target '{target}' for qualification, defaulting to information")
            target = "information"
        
        logger.info(
            f"SmartRouter decision for qualification: {target} (confidence: {routing_decision.confidence:.2f})"
        )
        
        return target
        
    except Exception as e:
        logger.error(f"SmartRouter failed in route_from_qualification: {e}, using fallback")
        
        # FALLBACK: Maintain critical legacy logic
        if intent_detector.detect_booking_intent(state.get("last_user_message", "")):
            return "scheduling"
        
        # Check completion status
        required_data = ["student_age", "education_level"]
        has_required = all(get_collected_field(state, field) for field in required_data)
        
        if has_required:
            return "information"
        
        return "validation" if should_route_to_validation(state) else "information"


def route_from_information(
    state: CeciliaState
) -> Literal["information", "scheduling", "validation", "handoff", "emergency_progression"]:
    """Roteamento após node de informações + SmartRouter Integration"""
    logger.info(f"Routing from information for {state['phone_number']}")
    
    # CRÍTICO: Verificar circuit breaker PRIMEIRO
    circuit_check = StateManager.check_circuit_breaker(state)
    
    if circuit_check["should_activate"]:
        action = circuit_check["recommended_action"]
        circuit_updates = StateManager.apply_circuit_breaker_action(state, action)
        StateManager.update_state(state, circuit_updates)
        return "emergency_progression"
    
    # PRIORIDADE MÁXIMA: Verificar falha de conversa
    if condition_checker.should_handoff(state):
        return "handoff"
    
    # NEW: Use SmartRouter for intelligent routing decisions
    try:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        routing_decision = loop.run_until_complete(
            smart_router_adapter.decide_route(state, "route_from_information")
        )
        
        # NEW: Plan and generate response BEFORE routing to node
        loop.run_until_complete(
            response_planner.plan_and_generate(state, routing_decision)
        )
        
        target = routing_decision.target_node
        
        # Ensure target is valid for this edge
        valid_targets = ["information", "scheduling", "validation", "handoff", "emergency_progression"]
        if target not in valid_targets:
            logger.warning(f"SmartRouter returned invalid target '{target}' for information, defaulting to scheduling")
            target = "scheduling"
        
        logger.info(
            f"SmartRouter decision for information: {target} (confidence: {routing_decision.confidence:.2f})"
        )
        
        return target
        
    except Exception as e:
        logger.error(f"SmartRouter failed in route_from_information: {e}, using fallback")
        
        # FALLBACK: Maintain critical legacy logic
        if intent_detector.detect_booking_intent(state.get("last_user_message", "")):
            return "scheduling"
        
        return "validation" if should_route_to_validation(state) else "scheduling"
        return "scheduling"
    
    # Detectar pulo de perguntas
    if intent_detector.detect_skip_questions(state["last_user_message"]):
        return "scheduling"
    
    # Verificar se deve sugerir agendamento
    should_suggest = _should_suggest_appointment(state)
    if should_suggest:
        return "scheduling"
    
    # Continuar com informações ou validar
    return "validation" if should_route_to_validation(state) else "information"


def route_from_scheduling(
    state: CeciliaState
) -> Literal["scheduling", "confirmation", "validation", "handoff", "emergency_progression"]:
    """Roteamento após scheduling + SmartRouter Integration"""
    logger.info(f"Routing from scheduling for {state['phone_number']}")
    
    # CRÍTICO: Verificar circuit breaker PRIMEIRO
    circuit_check = StateManager.check_circuit_breaker(state)
    
    if circuit_check["should_activate"]:
        action = circuit_check["recommended_action"]
        circuit_updates = StateManager.apply_circuit_breaker_action(state, action)
        StateManager.update_state(state, circuit_updates)
        return "emergency_progression"
    
    # PRIORIDADE MÁXIMA: Verificar falha de conversa (mais tolerante no scheduling)
    if condition_checker.should_handoff(state, stage_context="scheduling"):
        return "handoff"
    
    # NEW: Use SmartRouter for intelligent routing decisions
    try:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        routing_decision = loop.run_until_complete(
            smart_router_adapter.decide_route(state, "route_from_scheduling")
        )
        
        # NEW: Plan and generate response BEFORE routing to node
        loop.run_until_complete(
            response_planner.plan_and_generate(state, routing_decision)
        )
        
        target = routing_decision.target_node
        
        # Ensure target is valid for this edge
        valid_targets = ["scheduling", "confirmation", "validation", "handoff", "emergency_progression"]
        if target not in valid_targets:
            logger.warning(f"SmartRouter returned invalid target '{target}' for scheduling, defaulting to confirmation")
            target = "confirmation"
        
        logger.info(
            f"SmartRouter decision for scheduling: {target} (confidence: {routing_decision.confidence:.2f})"
        )
        
        return target
        
    except Exception as e:
        logger.error(f"SmartRouter failed in route_from_scheduling: {e}, using fallback")
        
        # FALLBACK: Maintain critical legacy logic
        if get_collected_field(state, "selected_slot") and get_collected_field(state, "contact_email"):
            return "confirmation"
        
        return "validation" if should_route_to_validation(state) else "scheduling"


def route_from_validation(
    state: CeciliaState
) -> Literal["greeting", "qualification", "information", "scheduling", "confirmation", "handoff", "retry_validation", "emergency_progression"]:
    """Roteamento após validação + SmartRouter Integration"""
    logger.info(f"Routing from validation for {state['phone_number']}")
    
    # CRÍTICO: Verificar circuit breaker PRIMEIRO
    circuit_check = StateManager.check_circuit_breaker(state)
    
    if circuit_check["should_activate"]:
        action = circuit_check["recommended_action"]
        circuit_updates = StateManager.apply_circuit_breaker_action(state, action)
        StateManager.update_state(state, circuit_updates)
        return "emergency_progression"
    
    # PRIORIDADE MÁXIMA: Verificar falha de conversa
    if condition_checker.should_handoff(state):
        return "handoff"
    
    # NEW: Use SmartRouter for intelligent routing decisions
    try:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        routing_decision = loop.run_until_complete(
            smart_router_adapter.decide_route(state, "route_from_validation")
        )
        
        target = routing_decision.target_node
        
        # Ensure target is valid for this edge
        valid_targets = ["greeting", "qualification", "information", "scheduling", "confirmation", "handoff", "retry_validation", "emergency_progression"]
        if target not in valid_targets:
            logger.warning(f"SmartRouter returned invalid target '{target}' for validation, using stage fallback")
            # Fallback based on current stage
            current_stage = state["current_stage"]
            if current_stage == ConversationStage.GREETING:
                target = "greeting"
            elif current_stage == ConversationStage.QUALIFICATION:
                target = "qualification"
            elif current_stage == ConversationStage.INFORMATION_GATHERING:
                target = "information"
            elif current_stage == ConversationStage.SCHEDULING:
                target = "scheduling"
            else:
                target = "qualification"
        
        logger.info(
            f"SmartRouter decision for validation: {target} (confidence: {routing_decision.confidence:.2f})"
        )
        
        return target
        
    except Exception as e:
        logger.error(f"SmartRouter failed in route_from_validation: {e}, using fallback")
        
        # FALLBACK: Se validação passou, voltar para estágio atual
        if not should_route_to_validation(state):
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
    """Roteamento após emergency progression do circuit breaker + SmartRouter Integration"""
    logger.info(f"Emergency progression routing for {state['phone_number']}")
    
    # NEW: Use SmartRouter for intelligent emergency routing decisions
    try:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        routing_decision = loop.run_until_complete(
            smart_router_adapter.decide_route(state, "route_from_emergency_progression")
        )
        
        target = routing_decision.target_node
        
        # Ensure target is valid for this edge
        valid_targets = ["information", "scheduling", "handoff", "END"]
        if target not in valid_targets:
            logger.warning(f"SmartRouter returned invalid target '{target}' for emergency_progression, defaulting to handoff")
            target = "handoff"
        
        logger.info(
            f"SmartRouter emergency decision: {target} (confidence: {routing_decision.confidence:.2f})"
        )
        
        return target
        
    except Exception as e:
        logger.error(f"SmartRouter failed in route_from_emergency_progression: {e}, using fallback")
        
        # FALLBACK: Get the last circuit breaker action from decision trail
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
    """Roteamento após confirmação final + SmartRouter Integration"""
    logger.info(f"Routing from confirmation for {state['phone_number']}")
    
    # NEW: Use SmartRouter for intelligent routing decisions
    try:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        routing_decision = loop.run_until_complete(
            smart_router_adapter.decide_route(state, "route_from_confirmation")
        )
        
        target = routing_decision.target_node
        
        # Ensure target is valid for this edge (simple case)
        valid_targets = ["completed", "validation"]
        if target not in valid_targets:
            logger.warning(f"SmartRouter returned invalid target '{target}' for confirmation, defaulting to completed")
            target = "completed"
        
        logger.info(
            f"SmartRouter decision for confirmation: {target} (confidence: {routing_decision.confidence:.2f})"
        )
        
        return target
        
    except Exception as e:
        logger.error(f"SmartRouter failed in route_from_confirmation: {e}, using fallback")
        
        # FALLBACK: Se ainda precisa validação, validar primeiro
        if should_route_to_validation(state):
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