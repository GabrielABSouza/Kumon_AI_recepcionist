# app/core/routing/master_router.py

import copy
import logging
from typing import Any, Dict

from app.core.gemini_classifier import GeminiClassifier
from app.utils.formatters import safe_phone_display

logger = logging.getLogger(__name__)


def _map_intent_to_node(intent: str) -> str:
    """Map primary intent to node name."""
    intent_mapping = {
        "greeting": "greeting_node",
        "qualification": "qualification_node",
        "information": "information_node",
        "scheduling": "scheduling_node",
        "help": "information_node",
        "fallback": "fallback_node",
    }
    return intent_mapping.get(intent, "fallback_node")


def _get_continuation_decision(state: Dict[str, Any]) -> str:
    """Determine if conversation should continue based on state."""
    # Se já enviamos greeting, continue com qualification
    if state.get("greeting_sent"):
        return "qualification_node"

    # Caso contrário, sem decisão específica de continuação
    return ""


async def master_router(
    state: Dict[str, Any], classifier: GeminiClassifier
) -> Dict[str, Any]:
    """
    NÓ DECISOR (ASSÍNCRONO) - VERSÃO FINAL E CORRIGIDA

    Confia 100% no estado fornecido pelo LangGraph Checkpoints.
    """
    # Proteger o estado recebido
    state = copy.deepcopy(state)
    phone = state.get("phone")
    text = state.get("text", "")
    logger.info(
        f"MASTER_ROUTER|Start|phone={safe_phone_display(phone)}|text_len={len(text)}"
    )

    try:
        # A CORREÇÃO CRÍTICA ESTÁ AQUI:
        # Não criamos mais um 'context' manual. O 'state' que o LangGraph nos dá
        # já é o contexto completo e persistido.
        # Nós o passamos DIRETAMENTE para o classificador.

        # 1. Obter Análise da IA com o contexto completo
        nlu_result = await classifier.classify(text, context=state)
        state["nlu_result"] = nlu_result
        primary_intent = nlu_result.get("primary_intent", "fallback")

        logger.info(
            f"MASTER_ROUTER|NLU Result|intent={primary_intent}|"
            f"entities={nlu_result.get('entities')}"
        )

        # 2. Aplicar Hierarquia de Decisão (esta parte estava correta)
        final_decision = ""
        interrupt_intents = ["information", "scheduling", "help"]

        if primary_intent in interrupt_intents:
            final_decision = _map_intent_to_node(primary_intent)
        else:
            continuation_node = _get_continuation_decision(state)
            if continuation_node:
                final_decision = continuation_node
            else:
                final_decision = _map_intent_to_node(primary_intent)

        # 3. Escrever a decisão no "memorando" do estado
        state["routing_decision"] = final_decision

    except Exception as e:
        logger.error(f"MASTER_ROUTER|Error|error={str(e)}", exc_info=True)
        state["routing_decision"] = "fallback_node"

    # 4. Retornar o estado completo e modificado
    return state
