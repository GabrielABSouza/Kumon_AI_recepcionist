from typing import Dict, Any
from ..state.models import CeciliaState, ConversationStage, ConversationStep, get_collected_field, set_collected_field
from ..state.managers import StateManager
import logging

logger = logging.getLogger(__name__)

class GreetingNode:
    """
    Node de saudação - MIGRAR lógica de _handle_greeting_stage()
    """
    
    def __init__(self):
        pass
    
    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """
        Processa estágio de saudação
        MIGRAR: conversation_flow.py linha 2000-2200 aprox
        """
        logger.info(f"Processing greeting for {state['phone_number']} - step: {state['current_step']}")
        
        user_message = state["last_user_message"]
        current_step = state["current_step"]
        
        # ========== WELCOME - Primeira interação ==========
        if current_step == ConversationStep.WELCOME:
            response = (
                "Olá! Bem-vindo ao Kumon Vila A! 😊\n\n"
                "Sou Cecília do Kumon Vila A, e estou aqui para ajudá-lo com "
                "informações sobre nossa metodologia de ensino.\n\n"
                "Para começar, qual é o seu nome? 😊"
            )
            
            # Atualizar para próximo passo
            updates = {
                "current_step": ConversationStep.PARENT_NAME_COLLECTION
            }
            
            return self._create_response(state, response, updates)
        
        # ========== PARENT_NAME_COLLECTION ==========
        elif current_step == ConversationStep.PARENT_NAME_COLLECTION:
            parent_name = user_message.strip()
            
            response = (
                f"Prazer em conhecê-lo, {parent_name}! 😊\n\n"
                "Agora me conte: você está buscando o Kumon para você mesmo ou para outra pessoa? 🤔"
            )
            
            updates = {
                "parent_name": parent_name,
                "current_step": ConversationStep.INITIAL_RESPONSE
            }
            
            return self._create_response(state, response, updates)
        
        # ========== INITIAL_RESPONSE - Determinar se é para si ou filho ==========
        elif current_step == ConversationStep.INITIAL_RESPONSE:
            user_message_lower = user_message.lower()
            parent_name = state["parent_name"]
            
            # Detectar se é para filho/filha
            if any(word in user_message_lower for word in [
                "filho", "filha", "criança", "filho(a)", "outra pessoa", "outra"
            ]):
                is_for_self = False
                relationship = "responsável por filho(a)"
                
                response = (
                    f"Que legal, {parent_name}! É maravilhoso ver pais investindo na "
                    "educação dos filhos! 👨‍👩‍👧‍👦\n\n"
                    "Qual é o nome do seu filho(a) que faria o Kumon?"
                )
                
                updates = {
                    "is_for_self": is_for_self,
                    "relationship": relationship,
                    "current_step": ConversationStep.CHILD_NAME_COLLECTION,
                    "last_bot_response": response,
                    "data": {
                        **state["data"], 
                        "is_for_self": is_for_self, 
                        "relationship": relationship
                    }
                }
                
                return self._create_response(state, response, updates)
            
            # Detectar se é para si mesmo
            elif any(word in user_message_lower for word in [
                "eu", "mim", "mesmo", "mesma", "para mim"
            ]):
                is_for_self = True
                relationship = "próprio interessado"
                
                response = (
                    f"Perfeito, {parent_name}! É ótimo ver seu interesse em aprender conosco! 🎯\n\n"
                    "Qual é a sua idade? Isso me ajudará a entender melhor suas necessidades de aprendizado."
                )
                
                updates = {
                    "is_for_self": is_for_self,
                    "child_name": parent_name,
                    "current_stage": ConversationStage.QUALIFICATION,
                    "current_step": ConversationStep.CHILD_AGE_INQUIRY
                }
                
                return self._create_response(state, response, updates)
            
            # Não conseguiu determinar
            else:
                response = (
                    "Entendi! Poderia me dizer um pouco mais claro? "
                    "É para você mesmo(a) ou para outra pessoa (como seu filho ou filha)?"
                )
                
                updates = {
                    "failed_attempts": 1  # Incrementar através do StateManager
                }
                
                return self._create_response(state, response, updates)
        
        # ========== CHILD_NAME_COLLECTION ==========
        elif current_step == ConversationStep.CHILD_NAME_COLLECTION:
            user_message_lower = user_message.lower().strip()
            parent_name = get_collected_field(state, "parent_name")
            
            # Detectar correção de nome
            correction_patterns = [
                "na verdade", "na real", "não", "melhor", "correção", "corrigir",
                "desculpa", "desculpe", "erro", "errado", "na verdade é", "é",
                "chama", "nome dele", "nome dela", "se chama"
            ]
            
            is_correction = any(pattern in user_message_lower for pattern in correction_patterns)
            
            # Extrair nome
            if is_correction:
                import re
                name_match = re.search(r'\b(?:é|chama|nome)\s+([A-Za-zÀ-ÿ]+)', user_message, re.IGNORECASE)
                if name_match:
                    child_name = name_match.group(1).strip().title()
                else:
                    words = user_message.split()
                    child_name = next((word.title() for word in reversed(words)
                                     if word.istitle() or word[0].isupper()), user_message.strip().title())
            else:
                child_name = user_message.strip().title()
            
            # Gerar resposta baseada em correção ou não
            if is_correction:
                response = (
                    f"Ah, entendi! Obrigada pela correção, {parent_name}! 😊\n\n"
                    f"É um prazer conhecer o {child_name}! Agora me conte: quantos anos tem o {child_name}? "
                    "Isso me ajudará a explicar melhor nossos programas."
                )
            else:
                response = (
                    f"Perfeito! É um prazer conhecer você, {parent_name}, e saber sobre o {child_name}! 😊\n\n"
                    f"Agora me conte: quantos anos tem o {child_name}? Isso me ajudará a explicar melhor nossos programas."
                )
            
            updates = {
                "child_name": child_name,
                "current_stage": WorkflowStage.QUALIFICATION,
                "current_step": ConversationStep.CHILD_AGE_INQUIRY,
                "last_bot_response": response,
                "data": {**state["data"], "child_name": child_name}
            }
            
            return self._create_response(state, response, updates)
        
        # Default response
        response = "Como posso ajudá-lo hoje? 😊"
        return self._create_response(state, response, {})
    
    def _create_response(
        self, 
        state: CeciliaState, 
        response: str, 
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria resposta padronizada do node"""
        # Atualizar estado
        updated_state = StateManager.update_state(state, updates)
        
        return {
            "response": response,
            "updated_state": updated_state,
            "stage": updated_state["current_stage"],
            "step": updated_state["current_step"],
            "intent": "greeting_flow"
        }

# Função para uso no LangGraph
async def greeting_node(state: CeciliaState) -> CeciliaState:
    """Entry point para LangGraph"""
    node = GreetingNode()
    result = await node(state)
    
    # Atualizar estado com resposta
    state.update(result["updated_state"])
    state["last_bot_response"] = result["response"]
    
    return state