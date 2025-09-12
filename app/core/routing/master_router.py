"""
Master Router: Async Native Implementation.

🚀 CLEAN ASYNC ARCHITECTURE
Native async implementation from end to end without wrappers or thread isolation.

Architecture: Prioritizes explicit user intent over rigid continuation rules.
Hierarchy:
1. Get AI analysis first (always) - using await
2. Honor explicit interruption intents (information, scheduling, help)
3. Apply continuation rules only if no explicit intent
4. Use AI classification for new flows
"""
import logging
from typing import Any, Dict

from app.core.gemini_classifier import classifier
from app.core.state_manager import get_conversation_history, get_conversation_state
from app.utils.formatters import safe_phone_display

logger = logging.getLogger(__name__)


def map_intent_to_node(intent: str) -> str:
    """Map intent string to corresponding node name."""
    intent_to_node = {
        "greeting": "greeting_node",
        "qualification": "qualification_node",
        "information": "information_node",
        "scheduling": "scheduling_node",
        "fallback": "fallback_node",
        "help": "fallback_node",  # Help routes to fallback for now
    }
    return intent_to_node.get(intent, "fallback_node")


def check_for_continuation_rule(state: Dict[str, Any]) -> str:
    """
    Check if there's a continuation rule that should override AI intent.

    Priority 2: Continuation rules for flows in progress.
    Only applies if no explicit interruption intent was detected.

    Returns:
        str: Node name to continue to, or None if no continuation needed
    """
    # REGRA 1: Post-greeting response - coletou greeting, agora precisa coletar nome
    if state.get("greeting_sent") and not state.get("parent_name"):
        print("ROUTER|continuation_rule|post_greeting|collect_parent_name")
        return "qualification_node"

    # Required qualification variables that must be collected
    QUALIFICATION_REQUIRED_VARS = [
        "parent_name",
        "student_name",
        "student_age",
        "program_interests",
    ]

    # REGRA 2: Check if qualification is incomplete and should continue
    if state.get("parent_name"):  # User has started qualification
        missing_vars = []
        for var in QUALIFICATION_REQUIRED_VARS:
            if var not in state or not state[var]:
                missing_vars.append(var)

        if missing_vars:
            qualification_attempts = state.get("qualification_attempts", 0)
            # Continue qualification if not at escape hatch limit
            if qualification_attempts < 4:
                print(
                    f"ROUTER|continuation_rule|qualification|missing={len(missing_vars)}|"
                    f"attempts={qualification_attempts}"
                )
                return "qualification_node"

    # Check if scheduling is incomplete and should continue
    SCHEDULING_REQUIRED_VARS = ["availability_preferences"]
    for var in SCHEDULING_REQUIRED_VARS:
        if var not in state or not state[var]:
            # Only continue scheduling if qualification is complete
            missing_qualification = []
            for qual_var in QUALIFICATION_REQUIRED_VARS:
                if qual_var not in state or not state[qual_var]:
                    missing_qualification.append(qual_var)

            if not missing_qualification:  # Qualification complete, can do scheduling
                print(f"ROUTER|continuation_rule|scheduling|missing={var}")
                return "scheduling_node"

    return None


# A CORREÇÃO CRÍTICA: a função PRECISA ser 'async def' para usar await
async def master_router(state: Dict[str, Any]) -> str:
    """
    Roteador principal que orquestra a classificação de intenção.
    DEVE ser assíncrono para chamar o classificador corretamente.
    """
    phone = state.get("phone")
    text = state.get("text", "")
    logger.info(
        f"MASTER_ROUTER|Start|phone={safe_phone_display(phone)}|text_len={len(text)}"
    )

    try:
        # 1. Carregar contexto (estado e histórico)
        context = None
        if phone:
            saved_state = get_conversation_state(phone)
            history = get_conversation_history(phone, limit=4)
            context = {"state": saved_state or {}, "history": history}
            # Unifica o estado salvo com o estado atual do turno
            if saved_state:
                state = {**saved_state, **state}

        # 2. Chamar o classificador de forma assíncrona
        # A CORREÇÃO CRÍTICA É AQUI: 'await' é obrigatório
        nlu_result = await classifier.classify(text, context=context)
        state["nlu_result"] = nlu_result
        state["nlu_entities"] = nlu_result.get("entities", {})

        primary_intent = nlu_result.get("primary_intent", "fallback")
        confidence = nlu_result.get("confidence", 0.0)

        logger.info(
            f"MASTER_ROUTER|NLU|intent={primary_intent}|confidence={confidence:.2f}|"
            f"entities={len(nlu_result.get('entities', {}))}"
        )

        # 3. STEP A: Priority 1 - Honor Explicit Interruption Intents
        interrupt_intents = ["information", "scheduling", "help"]
        if primary_intent in interrupt_intents:
            decision = map_intent_to_node(primary_intent)
            logger.info(
                f"MASTER_ROUTER|Interruption|decision={decision}|intent={primary_intent}"
            )
            return decision

        # 4. STEP B: Priority 2 - Apply Continuation Rules
        continuation_node = check_for_continuation_rule(state)
        if continuation_node:
            logger.info(
                f"MASTER_ROUTER|Continuation|decision={continuation_node}|intent={primary_intent}"
            )
            return continuation_node

        # 5. STEP C: Priority 3 - Use AI Classification for New Flows
        decision = map_intent_to_node(primary_intent)
        logger.info(
            f"MASTER_ROUTER|NewFlow|decision={decision}|intent={primary_intent}"
        )
        return decision

    except Exception as e:
        logger.error(f"MASTER_ROUTER|Error|error={str(e)}", exc_info=True)
        return "fallback_node"


# Export single async router - no more wrappers needed!
master_router_for_langgraph = master_router
