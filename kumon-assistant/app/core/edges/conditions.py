"""
Condition Checker for Workflow Routing

Verifica condições específicas para determinar roteamento entre nodes.
Implementa verificações de handoff, retry, e outras condições críticas.
"""

from typing import Optional
from ..state.models import CeciliaState
from .intent_detection import IntentDetector
import logging

logger = logging.getLogger(__name__)


class ConditionChecker:
    """
    Verifica condições para roteamento
    MIGRAR: Todas as funções de verificação do conversation_flow.py
    """
    
    def __init__(self):
        self.intent_detector = IntentDetector()
    
    def should_handoff(self, state: CeciliaState, stage_context: Optional[str] = None) -> bool:
        """
        Verifica se deve fazer handoff para humano
        MIGRAR: _should_handoff_to_human() linha 800 aprox
        """
        logger.debug(f"Checking handoff conditions for {state['phone_number']}")
        
        # Verificar solicitação explícita
        if state.get("human_handoff_requested", False):
            logger.info(f"Explicit handoff requested for {state['phone_number']}")
            return True
        
        # Detectar na mensagem atual
        if self.intent_detector.detect_human_help_request(state["last_user_message"]):
            logger.info(f"Human help request detected for {state['phone_number']}")
            return True
        
        # Handoff por falha de conversa
        handoff_conditions = [
            # Tentativas excessivas
            state.get("failed_attempts", 0) >= 5,
            state.get("consecutive_confusion", 0) >= 3,
            state.get("clarification_attempts", 0) >= 4,
            
            # Validação problemática
            state.get("validation_failed_count", 0) >= 3,
            state.get("validation_attempts", 0) >= 5,
            
            # Indicadores de frustração
            len(state.get("dissatisfaction_indicators", [])) >= 2,
            state.get("low_quality_responses", 0) >= 3
        ]
        
        if any(handoff_conditions):
            logger.warning(f"Handoff triggered by conversation failure for {state['phone_number']}")
            return True
        
        # Contexto específico para scheduling (mais tolerante)
        if stage_context == "scheduling":
            # No agendamento, só handoff se muito problemático
            scheduling_handoff_conditions = [
                state.get("failed_attempts", 0) >= 8,  # Mais tolerante
                state.get("consecutive_confusion", 0) >= 4,
                state.get("scheduling_attempts", 0) >= 5
            ]
            return any(scheduling_handoff_conditions)
        
        return False
    
    def should_handoff_immediately(self, state: CeciliaState) -> bool:
        """
        Verifica se precisa handoff imediato
        MIGRAR: Lógica para casos críticos
        """
        immediate_conditions = [
            # Solicitação explícita
            state.get("human_handoff_requested", False),
            
            # Falhas críticas
            state["failed_attempts"] >= 5,
            state["validation_attempts"] >= 5,
            
            # Conversa completamente travada
            state["message_count"] > 20
        ]
        
        return any(immediate_conditions)
    
    def should_retry_validation(self, state: CeciliaState) -> bool:
        """Determina se deve tentar validação novamente"""
        return (
            state.get("needs_validation", False) and
            state.get("validation_attempts", 0) < 3 and
            not self.should_handoff(state)
        )
    
    def has_minimum_info_for_scheduling(self, state: CeciliaState) -> bool:
        """Verifica se tem info mínima para agendamento"""
        required_fields = ["parent_name"]
        optional_helpful = ["child_name", "student_age"]
        
        # Campos obrigatórios
        has_required = all(state.get(field) for field in required_fields)
        
        # Pelo menos um campo útil adicional
        has_helpful = any(state.get(field) for field in optional_helpful)
        
        return has_required and has_helpful
    
    def should_continue_in_stage(self, state: CeciliaState) -> bool:
        """Verifica se deve continuar no estágio atual"""
        stage = state["current_stage"]
        
        if stage == "greeting":
            # Continuar até ter nome e determinar para quem é
            return not (state.get("parent_name") and state.get("is_for_self") is not None)
        
        elif stage == "qualification":
            # Continuar até ter idade e nível escolar
            return not (state.get("student_age") and state.get("education_level"))
        
        elif stage == "information_gathering":
            # Continuar até responder perguntas suficientes ou detectar interesse
            questions_answered = len(state.get("questions_answered", []))
            gathering_count = state.get("info_gathering_count", 0)
            
            return not (questions_answered >= 2 or gathering_count >= 3)
        
        elif stage == "scheduling":
            # Continuar até ter agendamento completo
            return not (state.get("selected_slot") and state.get("contact_email"))
        
        return False
    
    def calculate_message_similarity(self, msg1: str, msg2: str) -> float:
        """
        Calcula similaridade entre mensagens
        MIGRAR: _calculate_message_similarity() linha 1150 aprox
        """
        words1 = set(msg1.lower().split())
        words2 = set(msg2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def is_greeting_message(self, user_message: str) -> bool:
        """Verifica se é mensagem de saudação"""
        greeting_patterns = [
            "oi", "olá", "hello", "hi", "ola", "bom dia", "boa tarde", "boa noite",
            "e aí", "eai", "oiii", "oie", "alo", "alô"
        ]
        
        message_lower = user_message.lower().strip()
        return any(pattern in message_lower for pattern in greeting_patterns)