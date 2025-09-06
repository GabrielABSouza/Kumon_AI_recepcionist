"""
Confirmation Node for Final Appointment Confirmation

Este node lida com a confirmação final do agendamento e encerramento da conversa.
"""

from typing import Dict, Any
from ..state.models import CeciliaState, ConversationStage, ConversationStep, get_collected_field, set_collected_field
from ..state.managers import StateManager
from ..state.models import safe_update_state
import logging

logger = logging.getLogger(__name__)


class ConfirmationNode:
    """
    Node de confirmação final do agendamento
    """
    
    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """Processa confirmação final"""
        logger.info(f"Processing confirmation for {state['phone_number']}")
        
        # Obter dados do agendamento
        selected_slot = get_collected_field(state, "selected_slot") or {}
        parent_name = get_collected_field(state, "parent_name") or ""
        child_name = get_collected_field(state, "child_name") or ""
        child_age = get_collected_field(state, "student_age") or ""
        email = get_collected_field(state, "contact_email") or ""
        is_for_self = get_collected_field(state, "is_for_self") or False
        
        student_info = f"você ({child_age} anos)" if is_for_self else f"{child_name} ({child_age} anos)"
        
        response = (
            f"🎉 **AGENDAMENTO CONFIRMADO COM SUCESSO!** 🎉\n\n"
            f"📋 **Resumo da sua visita:**\n\n"
            f"👤 **Responsável:** {parent_name}\n"
            f"👶 **Aluno(a):** {student_info}\n"
            f"📅 **Data:** {selected_slot.get('date_formatted', '')}\n"
            f"🕐 **Horário:** {selected_slot.get('time_formatted', '')}\n"
            f"📧 **Email:** {email}\n\n"
            f"📍 **Local da visita:**\n"
            f"**Kumon Vila A**\n"
            f"Rua Amoreira, 571 - Salas 6 e 7\n"
            f"Jardim das Laranjeiras\n\n"
            f"📞 **Contato:** (51) 99692-1999\n\n"
            f"✅ **O que você pode esperar:**\n"
            f"• Apresentação da metodologia Kumon\n"
            f"• Avaliação diagnóstica gratuita\n"
            f"• Conversa com nossa orientadora\n"
            f"• Conhecer nossos materiais didáticos\n\n"
            f"📧 **Confirmação por email:** Enviada!\n"
            f"⏰ **Lembre-se:** Chegue 10 min antes\n"
            f"🆔 **Traga:** Documento de identidade\n\n"
            f"Estamos ansiosos para recebê-los! 😊✨\n\n"
            f"**Até breve no Kumon Vila A!** 🎓"
        )
        
        updates = {
            "current_stage": ConversationStage.COMPLETED,
            "current_step": ConversationStep.CONVERSATION_ENDED
        }
        
        return self._create_response(state, response, updates)
    
    def _create_response(self, state: CeciliaState, response: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Cria resposta padronizada"""
        updated_state = StateManager.update_state(state, updates)
        
        return {
            "response": response,
            "updated_state": updated_state,
            "stage": updated_state["current_stage"],
            "step": updated_state["current_step"],
            "intent": "confirmation_complete"
        }


# Entry point para LangGraph
async def confirmation_node(state: CeciliaState) -> CeciliaState:
    """Entry point para LangGraph"""
    node = ConfirmationNode()
    result = await node(state)
    
    # CRITICAL FIX: Use safe_update_state to preserve CeciliaState structure
    safe_update_state(state, result["updated_state"])
    state["last_bot_response"] = result["response"]
    
    return state