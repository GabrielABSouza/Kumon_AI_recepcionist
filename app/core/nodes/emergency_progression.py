"""
Emergency Progression Node

Este node é acionado pelo circuit breaker quando há falhas persistentes
na conversa e implementa estratégias de progressão de emergência para
destravar o fluxo conversacional.
"""

from typing import Dict, Any
from ..state.models import CeciliaState, ConversationStage, ConversationStep, get_collected_field, set_collected_field
from ..state.managers import StateManager
from ..state.models import safe_update_state
import logging

logger = logging.getLogger(__name__)


class EmergencyProgressionNode:
    """
    Node de progressão de emergência acionado pelo circuit breaker
    
    Aplica estratégias para destravar conversas com problemas persistentes:
    - Direct scheduling bypass
    - Information gathering skip
    - Handoff escalation
    - Conversation simplification
    """
    
    def __init__(self):
        self.emergency_strategies = self._load_emergency_strategies()
    
    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """Aplica progressão de emergência baseada no contexto"""
        logger.warning(f"Emergency progression activated for {state['phone_number']}")
        
        # Determine strategy based on conversation state
        strategy = self._determine_emergency_strategy(state)
        
        # Apply the emergency strategy
        response, updates = self._apply_emergency_strategy(state, strategy)
        
        # Record emergency progression for analytics
        self._record_emergency_analytics(state, strategy)
        
        return self._create_response(state, response, updates)
    
    def _determine_emergency_strategy(self, state: CeciliaState) -> str:
        """
        Determina estratégia de emergência baseada no estado atual
        """
        metrics = state["conversation_metrics"]
        current_stage = state["current_stage"]
        collected_data = state["collected_data"]
        
        # Strategy 1: Direct scheduling if has minimum info
        has_name = bool(get_collected_field(state, "parent_name"))
        has_interest = bool(get_collected_field(state, "programs_of_interest"))
        
        if (has_name and 
            current_stage in [ConversationStage.QUALIFICATION, ConversationStage.INFORMATION_GATHERING] and
            metrics["failed_attempts"] >= 3):
            return "direct_scheduling"
        
        # Strategy 2: Information bypass if stuck in qualification
        elif (current_stage == ConversationStage.QUALIFICATION and
              metrics["failed_attempts"] >= 2):
            return "information_bypass"
        
        # Strategy 3: Handoff escalation for critical failures  
        elif (metrics["failed_attempts"] >= 5 or
              metrics["validation_failures"] >= 3):
            return "handoff_escalation"
        
        # Strategy 4: Conversation simplification
        else:
            return "conversation_simplification"
            return "direct_scheduling_bypass"
        
        # Strategy 2: Information bypass if stuck in early stages
        if (current_stage == ConversationStage.GREETING and 
            metrics["consecutive_confusion"] >= 2):
            return "information_bypass"
        
        # Strategy 3: Simplified conversation reset
        if (metrics["message_count"] > 10 and 
            len(collected_data) == 0):
            return "conversation_simplification"
        
        # Strategy 4: Handoff escalation for complex scenarios
        if (metrics["failed_attempts"] >= 5 or 
            metrics["consecutive_confusion"] >= 3 or
            len(metrics["problematic_fields"]) >= 3):
            return "handoff_escalation"
        
        # Default: Try to progress forward
        return "progressive_advancement"
    
    def _apply_emergency_strategy(self, state: CeciliaState, strategy: str) -> tuple[str, Dict[str, Any]]:
        """
        Aplica estratégia de emergência específica
        
        Returns:
            tuple: (response_text, state_updates)
        """
        parent_name = get_collected_field(state, "parent_name") or ""
        name_greeting = f", {parent_name}" if parent_name else ""
        
        if strategy == "direct_scheduling_bypass":
            response = (
                f"Vou simplificar nosso processo{name_greeting}! 😊\n\n"
                "Que tal agendarmos uma visita para você conhecer o Kumon na prática? "
                "Assim nossa equipe poderá esclarecer todas as suas dúvidas pessoalmente!\n\n"
                "Qual período é melhor para você?\n"
                "**🌅 MANHÃ** (9h às 12h) ou **🌆 TARDE** (14h às 17h)?"
            )
            
            updates = {
                "current_stage": ConversationStage.SCHEDULING,
                "current_step": ConversationStep.DATE_PREFERENCE,
                "failed_attempts": 0,
                "consecutive_confusion": 0
            }
            
        elif strategy == "information_bypass":
            response = (
                f"Deixe-me compartilhar as informações essenciais sobre o Kumon{name_greeting}! 📚\n\n"
                "**💰 Investimento:**\n"
                "• Matemática ou Português: R$ 375,00/mês\n"
                "• Inglês: R$ 375,00/mês\n\n"
                "**🎯 Benefícios:**\n"
                "• Desenvolvimento da autodisciplina\n"
                "• Autonomia nos estudos\n"
                "• Avanço além da série escolar\n\n"
                "Quer agendar uma visita para conhecer melhor?"
            )
            
            updates = {
                "current_stage": ConversationStage.INFORMATION_GATHERING,
                "current_step": ConversationStep.METHODOLOGY_EXPLANATION,
                "failed_attempts": 0,
                "consecutive_confusion": 0
            }
            
        elif strategy == "conversation_simplification":
            response = (
                "Vou facilitar nosso atendimento! 😊\n\n"
                "Escolha uma opção:\n\n"
                "**1️⃣ Quero agendar uma visita**\n"
                "**2️⃣ Quero saber sobre valores**\n"
                "**3️⃣ Quero falar com a equipe**\n\n"
                "Digite apenas o **número** da opção! 👆"
            )
            
            updates = {
                "current_stage": ConversationStage.INFORMATION_GATHERING,
                "current_step": ConversationStep.METHODOLOGY_EXPLANATION,
                "failed_attempts": 0,
                "consecutive_confusion": 0
            }
            
        elif strategy == "handoff_escalation":
            response = (
                f"Entendo que você precisa de um atendimento mais personalizado{name_greeting}! 👩‍💼\n\n"
                "Nossa equipe especializada poderá ajudá-lo melhor:\n\n"
                "📞 **(51) 99692-1999**\n"
                "📧 **kumonvilaa@gmail.com**\n\n"
                "**Horário:** Segunda a Sexta, 8h às 18h\n\n"
                "Eles terão todo o prazer em atendê-lo! 😊✨"
            )
            
            updates = {
                "current_stage": ConversationStage.COMPLETED,
                "current_step": ConversationStep.CONVERSATION_ENDED,
                "emergency_handoff": True
            }
            
        else:  # progressive_advancement
            response = (
                f"Vou ajudá-lo de forma mais direta{name_greeting}! 🎯\n\n"
                "Para um atendimento mais eficiente, me conte:\n"
                "**Qual é seu principal interesse no Kumon?**\n\n"
                "• Reforço escolar\n"
                "• Desenvolvimento pessoal\n"
                "• Preparação para vestibular\n"
                "• Outro objetivo específico"
            )
            
            updates = {
                "current_stage": ConversationStage.QUALIFICATION,
                "current_step": ConversationStep.CHILD_AGE_INQUIRY,
                "failed_attempts": 0,
                "consecutive_confusion": 0
            }
        
        return response, updates
    
    def _record_emergency_analytics(self, state: CeciliaState, strategy: str) -> None:
        """
        Registra analytics da progressão de emergência
        """
        metrics = state["conversation_metrics"]
        
        from ..state.models import add_decision_to_trail
        add_decision_to_trail(state, {
            "type": "emergency_progression",
            "strategy": strategy,
            "trigger_metrics": {
                "failed_attempts": metrics["failed_attempts"],
                "consecutive_confusion": metrics["consecutive_confusion"],
                "message_count": metrics["message_count"],
                "problematic_fields_count": len(metrics["problematic_fields"])
            },
            "current_stage": state["current_stage"],
            "collected_data_count": len(state["collected_data"])
        })
        
        logger.info(f"Emergency progression analytics recorded: {strategy} for {state['phone_number']}")
    
    def _load_emergency_strategies(self) -> Dict[str, Any]:
        """
        Carrega configuração de estratégias de emergência
        """
        return {
            "direct_scheduling_bypass": {
                "required_data": ["parent_name"],
                "trigger_conditions": {
                    "failed_attempts": 3,
                    "stages": [ConversationStage.QUALIFICATION, ConversationStage.INFORMATION_GATHERING]
                }
            },
            "information_bypass": {
                "required_data": [],
                "trigger_conditions": {
                    "consecutive_confusion": 2,
                    "stages": [ConversationStage.GREETING]
                }
            },
            "conversation_simplification": {
                "required_data": [],
                "trigger_conditions": {
                    "message_count": 10,
                    "empty_collected_data": True
                }
            },
            "handoff_escalation": {
                "required_data": [],
                "trigger_conditions": {
                    "failed_attempts": 5,
                    "consecutive_confusion": 3,
                    "problematic_fields": 3
                }
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
            "intent": "emergency_progression"
        }


# Entry point para LangGraph
async def emergency_progression_node(state: CeciliaState) -> CeciliaState:
    """Entry point para LangGraph"""
    node = EmergencyProgressionNode()
    result = await node(state)
    
    # CRITICAL FIX: Use safe_update_state to preserve CeciliaState structure
    safe_update_state(state, result["updated_state"])
    state["last_bot_response"] = result["response"]
    
    return state