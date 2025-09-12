 # app/core/routing/master_router.py

import logging
from typing import Any, Dict
import copy # Importar o copy

from app.core.gemini_classifier import classifier
from app.core.state_manager import get_conversation_history, get_conversation_state
from app.utils.formatters import safe_phone_display

logger = logging.getLogger(__name__)


def map_intent_to_node(intent: str) -> str:
    # ... (esta função está correta, mantenha como está) ...
    intent_to_node = {
        "greeting": "greeting_node",
        "qualification": "qualification_node",
        "information": "information_node",
        "scheduling": "scheduling_node",
        "fallback": "fallback_node",
        "help": "fallback_node",
    }
    return intent_to_node.get(intent, "fallback_node")


def check_for_continuation_rule(state: Dict[str, Any]) -> str:
    # ... (esta função está correta, mantenha como está) ...
    # REGRA 1: Post-greeting response
    if state.get("greeting_sent") and not state.get("collected_data", {}).get("parent_name"):
        logger.info("ROUTER|continuation_rule|post_greeting|collect_parent_name")
        return "qualification_node"

    # Required qualification variables
    QUALIFICATION_REQUIRED_VARS = [
        "parent_name",
        "beneficiary_type",
        "student_name",
        "student_age",
        "program_interests",
    ]

    # REGRA 2: Check if qualification is incomplete
    collected_data = state.get("collected_data", {})
    if collected_data.get("parent_name"):
        missing_vars = [var for var in QUALIFICATION_REQUIRED_VARS if not collected_data.get(var)]
        if missing_vars:
            logger.info(f"ROUTER|continuation_rule|qualification|missing={len(missing_vars)}")
            return "qualification_node"
            
    return None


async def master_router(state: Dict[str, Any]) -> str:
    """
    Roteador principal que orquestra a classificação de intenção de forma segura.
    """
    # 1. Proteger o estado recebido
    # Garante que as modificações aqui não afetem outros lugares
    state = copy.deepcopy(state)
    
    phone = state.get("phone")
    text = state.get("text", "")
    logger.info(f"MASTER_ROUTER|Start|phone={safe_phone_display(phone)}|text_len={len(text)}")

    try:
        # 2. Carregar e Unificar o Estado de Forma Segura
        context = None
        if phone:
            persisted_state = get_conversation_state(phone)
            history = get_conversation_history(phone, limit=4)
            
            # A CORREÇÃO CRÍTICA ESTÁ AQUI:
            # Unifica o estado de forma explícita e segura.
            # O estado persistido serve como base, e o estado do turno atual
            # (com a nova mensagem 'text') é colocado por cima.
            if persisted_state:
                # Mantém 'collected_data' e outras chaves importantes do estado antigo
                state = {**persisted_state, **state}

            context = {"state": state, "history": history}

        # Garante que a chave 'collected_data' sempre exista para os nós
        if "collected_data" not in state:
            state["collected_data"] = {}

        # 3. Chamar o classificador com o estado unificado e correto
        nlu_result = await classifier.classify(text, context=context)
        state["nlu_result"] = nlu_result # Disponibiliza para os nós

        primary_intent = nlu_result.get("primary_intent", "fallback")
        
        logger.info(
            f"MASTER_ROUTER|NLU|intent={primary_intent}|"
            f"entities={len(nlu_result.get('entities', {}))}"
        )

        # 4. Hierarquia de Decisão (sem alterações, esta parte estava correta)
        interrupt_intents = ["information", "scheduling", "help"]
        if primary_intent in interrupt_intents:
            return map_intent_to_node(primary_intent)

        continuation_node = check_for_continuation_rule(state)
        if continuation_node:
            return continuation_node

        return map_intent_to_node(primary_intent)

    except Exception as e:
        logger.error(f"MASTER_ROUTER|Error|error={str(e)}", exc_info=True)
        return "fallback_node"