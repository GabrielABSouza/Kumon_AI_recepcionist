"""
Handoff Node for Human Escalation

Este node lida com a transferência para atendimento humano em cenários como:
- Circuit breaker activation
- Frustração do usuário detectada
- Solicitação explícita de atendimento humano
- Falhas persistentes no sistema automatizado
"""

from typing import Dict, Any
from ..state.models import CeciliaState, ConversationStage, ConversationStep, get_collected_field, set_collected_field
from ..state.managers import StateManager
from ..state.models import safe_update_state
import logging

logger = logging.getLogger(__name__)


class HandoffNode:
    """
    Node dedicado para transferência de atendimento humano
    """
    
    def __init__(self):
        self.handoff_scenarios = self._load_handoff_scenarios()
    
    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """Processa handoff para atendimento humano"""
        logger.info(f"Handoff requested for {state['phone_number']}")
        
        # Determinar cenário de handoff para personalizar resposta
        handoff_reason = self._determine_handoff_reason(state)
        
        # Gerar resposta personalizada baseada no cenário
        response = self._generate_handoff_response(state, handoff_reason)
        
        # Registrar handoff para analytics
        self._record_handoff_analytics(state, handoff_reason)
        
        updates = {
            "current_stage": ConversationStage.COMPLETED,
            "current_step": ConversationStep.CONVERSATION_ENDED,
            "handoff_reason": handoff_reason
        }
        
        return self._create_response(state, response, updates)
    
    def _determine_handoff_reason(self, state: CeciliaState) -> str:
        """
        Determina o motivo do handoff baseado no estado da conversa
        """
        metrics = state["conversation_metrics"]
        validation = state["data_validation"]
        
        # Circuit breaker activation
        if metrics["failed_attempts"] >= 5:
            return "circuit_breaker_failures"
        
        # Validation loops
        if len(validation["validation_history"]) >= 4:
            return "validation_loops"
        
        # High confusion
        if metrics["consecutive_confusion"] >= 3:
            return "confusion_escalation"
        
        # Long conversation without progress
        if metrics["message_count"] > 15:
            return "conversation_too_long"
        
        # Complex questions not handled
        if len(metrics["problematic_fields"]) >= 3:
            return "complex_requirements"
        
        # User explicitly requested human
        last_message = state["last_user_message"].lower()
        if any(keyword in last_message for keyword in [
            "falar com", "atendente", "humano", "pessoa", "supervisor",
            "gerente", "responsável", "não entendi", "não funciona"
        ]):
            return "explicit_human_request"
        
        # Default
        return "general_assistance"
    
    def _generate_handoff_response(self, state: CeciliaState, reason: str) -> str:
        """
        Gera resposta personalizada baseada no motivo do handoff
        """
        parent_name = get_collected_field(state, "parent_name") or ""
        name_greeting = f", {parent_name}" if parent_name else ""
        
        responses = {
            "circuit_breaker_failures": (
                f"Entendo que estamos enfrentando algumas dificuldades{name_greeting}! 😔\n\n"
                "Para garantir que você receba o melhor atendimento, vou conectá-lo "
                "diretamente com nossa equipe especializada:\n\n"
                "📞 **(51) 99692-1999**\n"
                "📧 **kumonvilaa@gmail.com**\n\n"
                "Eles poderão resolver tudo rapidamente! 🚀"
            ),
            
            "explicit_human_request": (
                f"Claro{name_greeting}! Entendo que prefere falar com nossa equipe! 👩‍💼\n\n"
                "📞 **(51) 99692-1999**\n"
                "📧 **kumonvilaa@gmail.com**\n\n"
                "**Horário de atendimento:**\n"
                "🕗 Segunda a Sexta: 8h às 18h\n\n"
                "Nossa equipe terá todo o prazer em ajudá-lo pessoalmente! 😊✨"
            ),
            
            "confusion_escalation": (
                f"Percebo que posso não estar sendo clara o suficiente{name_greeting}! 🤔\n\n"
                "Para que você receba todas as informações detalhadas que precisa, "
                "recomendo falar diretamente com nossa equipe:\n\n"
                "📞 **(51) 99692-1999**\n"
                "📧 **kumonvilaa@gmail.com**\n\n"
                "Eles poderão esclarecer tudo com muito mais detalhes! ✨"
            ),
            
            "complex_requirements": (
                f"Vejo que suas necessidades são bem específicas{name_greeting}! 🎯\n\n"
                "Para um atendimento mais personalizado e detalhado, nossa equipe "
                "especializada poderá ajudar melhor:\n\n"
                "📞 **(51) 99692-1999**\n"
                "📧 **kumonvilaa@gmail.com**\n\n"
                "Eles têm experiência com casos similares! 👨‍🏫"
            ),
            
            "conversation_too_long": (
                f"Obrigada pela paciência{name_greeting}! ⏰\n\n"
                "Para agilizar e garantir que você tenha todas as respostas que precisa, "
                "nossa equipe poderá atendê-lo de forma mais eficiente:\n\n"
                "📞 **(51) 99692-1999**\n"
                "📧 **kumonvilaa@gmail.com**\n\n"
                "Ligação direta é sempre mais rápida! 📞✨"
            )
        }
        
        return responses.get(reason, responses["explicit_human_request"])
    
    def _record_handoff_analytics(self, state: CeciliaState, reason: str) -> None:
        """
        Registra analytics do handoff para melhoria do sistema
        """
        metrics = state["conversation_metrics"]
        
        # Adicionar ao decision trail para analytics
        from ..state.models import add_decision_to_trail
        add_decision_to_trail(state, {
            "type": "human_handoff",
            "reason": reason,
            "conversation_duration_messages": metrics["message_count"],
            "failed_attempts": metrics["failed_attempts"],
            "confusion_count": metrics["consecutive_confusion"],
            "collected_data_completeness": len(state["collected_data"]),
            "problematic_fields": metrics["problematic_fields"]
        })
        
        logger.info(f"Handoff analytics recorded: {reason} for {state['phone_number']}")
    
    def _load_handoff_scenarios(self) -> Dict[str, Any]:
        """
        Carrega configuração de cenários de handoff
        """
        return {
            "triggers": {
                "failed_attempts_threshold": 5,
                "confusion_threshold": 3,
                "validation_loops_threshold": 4,
                "message_count_threshold": 15,
                "problematic_fields_threshold": 3
            },
            "keywords": {
                "explicit_human": [
                    "falar com", "atendente", "humano", "pessoa", "supervisor",
                    "gerente", "responsável", "não entendi", "não funciona",
                    "não está funcionando", "problema", "dificuldade",
                    "transferir", "outro atendimento"
                ]
            }
        }
    
    def _create_response(self, state: CeciliaState, response: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Cria resposta padronizada"""
        updated_state = StateManager.update_state(state, updates)
        
        return {
            "response": response,
            "updated_state": updated_state,
            "stage": updated_state["current_stage"],
            "step": updated_state["current_step"],
            "intent": "human_handoff"
        }


# Entry point para LangGraph
async def handoff_node(state: CeciliaState) -> CeciliaState:
    """Entry point para LangGraph"""
    node = HandoffNode()
    result = await node(state)
    
    # CRITICAL FIX: Use safe_update_state to preserve CeciliaState structure
    safe_update_state(state, result["updated_state"])
    state["last_bot_response"] = result["response"]
    
    return state