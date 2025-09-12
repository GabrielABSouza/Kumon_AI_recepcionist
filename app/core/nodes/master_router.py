# app/core/routing/master_router.py

import copy
import logging
from typing import Any, Dict

from app.core.gemini_classifier import classifier
from app.core.state_manager import get_conversation_history, get_conversation_state
from app.utils.formatters import safe_phone_display

logger = logging.getLogger(__name__)


def _map_intent_to_node(intent: str) -> str:
    """Mapeia a string de intenção para o nome do nó correspondente."""
    intent_map = {
        "greeting": "greeting_node",
        "qualification": "qualification_node",
        "information": "information_node",
        "scheduling": "scheduling_node",
        "fallback": "fallback_node",
    }
    return intent_map.get(intent, "fallback_node")


def _get_continuation_decision(state: Dict[str, Any]) -> str | None:
    """
    Verifica se uma regra de negócio para continuação de fluxo deve ser aplicada.
    Retorna o nome do nó de destino ou None.
    """
    # REGRA 1: Se acabamos de saudar, a próxima etapa é a qualificação.
    if state.get("greeting_sent") and not state.get("collected_data", {}).get(
        "parent_name"
    ):
        logger.info("ROUTER|Rule|Applying post-greeting continuation to qualification.")
        return "qualification_node"

    # REGRA 2: Se a qualificação já começou, continue nela.
    QUALIFICATION_REQUIRED_VARS = [
        "parent_name",
        "beneficiary_type",
        "student_name",
        "student_age",
        "program_interests",
    ]
    collected_data = state.get("collected_data", {})
    if collected_data.get(
        "parent_name"
    ):  # Um bom indicador de que a qualificação começou
        missing_vars = [
            var for var in QUALIFICATION_REQUIRED_VARS if not collected_data.get(var)
        ]
        if missing_vars:
            logger.info(
                f"ROUTER|Rule|Applying qualification continuation. Missing {len(missing_vars)} vars."
            )
            return "qualification_node"

    # Nenhuma regra de continuação se aplica
    return None


async def master_router(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    NÓ DECISOR (ASSÍNCRONO)

    1. Carrega e unifica o contexto.
    2. Chama a IA para análise (NLU).
    3. Aplica a hierarquia de decisão (Interrupção > Continuação > Novo Fluxo).
    4. **Escreve** a decisão final no `state`.
    5. **Retorna** o `state` modificado.
    """
    print(f"DEBUG|master_router_executed|phone={state.get('phone')}")
    print(f"DEBUG|master_router_executed|text='{state.get('text')}'")
    print(f"DEBUG|master_router_executed|message_id={state.get('message_id')}")

    # Proteger o estado recebido
    state = copy.deepcopy(state)
    phone = state.get("phone")
    text = state.get("text", "")
    logger.info(
        f"MASTER_ROUTER|Start|phone={safe_phone_display(phone)}|text_len={len(text)}"
    )

    try:
        # 1. Carregar e Unificar o Estado
        context = None
        if phone:
            persisted_state = get_conversation_state(phone)
            history = get_conversation_history(phone, limit=4)
            if persisted_state:
                state = {**persisted_state, **state}
            context = {"state": state, "history": history}

        if "collected_data" not in state:
            state["collected_data"] = {}

        # 2. Obter Análise da IA
        nlu_result = await classifier.classify(text, context=context)
        state["nlu_result"] = nlu_result
        primary_intent = nlu_result.get("primary_intent", "fallback")

        logger.info(
            f"MASTER_ROUTER|NLU Result|intent={primary_intent}|entities={nlu_result.get('entities')}"
        )

        # 3. Aplicar Hierarquia de Decisão
        final_decision = ""
        interrupt_intents = ["information", "scheduling", "help"]

        # Prioridade 1: Interrupções explícitas do usuário
        if primary_intent in interrupt_intents:
            final_decision = _map_intent_to_node(primary_intent)
            logger.info(
                f"MASTER_ROUTER|Decision|Priority 1: User Interruption -> {final_decision}"
            )
        else:
            # Prioridade 2: Regras de continuação de negócio
            continuation_node = _get_continuation_decision(state)
            if continuation_node:
                final_decision = continuation_node
                logger.info(
                    f"MASTER_ROUTER|Decision|Priority 2: Business Continuation -> {final_decision}"
                )
            else:
                # Prioridade 3: Novo fluxo baseado na IA
                final_decision = _map_intent_to_node(primary_intent)
                logger.info(
                    f"MASTER_ROUTER|Decision|Priority 3: New Flow -> {final_decision}"
                )

        # 4. Escrever a decisão no "memorando" do estado
        state["routing_decision"] = final_decision
        print(f"DEBUG|master_router_decision_written|routing_decision={final_decision}")

    except Exception as e:
        logger.error(f"MASTER_ROUTER|Error|error={str(e)}", exc_info=True)
        state["routing_decision"] = "fallback_node"

    # 5. Retornar o estado completo e modificado
    return state
