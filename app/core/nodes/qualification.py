import copy
import logging
from typing import Any, Dict

from ..delivery import send_text
from ..state.models import ConversationStage, ConversationStep

logger = logging.getLogger(__name__)

# 🎯 SOURCE OF TRUTH: Sequential qualification variables order
QUALIFICATION_VARS_SEQUENCE = [
    "parent_name",
    "beneficiary_type",
    "student_name",
    "student_age",
    "program_interests",
]


async def qualification_node(state: Dict[str, Any]) -> Dict[str, Any]:
    print("DEBUG|qualification_node_executed|CALLED!")
    print(f"DEBUG|qualification_node|state_type={type(state)}")
    print(f"DEBUG|qualification_node|state_keys={list(state.keys()) if isinstance(state, dict) else 'NOT_DICT'}")
    """
    🧠 QUALIFICATION ORCHESTRATOR - NEW ARCHITECTURE

    Pure orchestration node that relies exclusively on GeminiClassifier for entity extraction.

    ARCHITECTURE PRINCIPLES:
    - 🎯 ZERO entity extraction logic - trusts GeminiClassifier 100%
    - 🎭 Pure orchestrator: consumes pre-extracted entities, generates questions
    - 🔄 Sequential flow: determines next missing variable and asks for it
    - 🚀 Simplified: no complex abstractions, direct state manipulation

    WORKFLOW:
    1. Process entities already extracted by GeminiClassifier contextual
    2. Determine next variable to collect based on sequence
    3. Generate appropriate question or complete qualification
    4. Return updated state with response sent via Evolution API
    """

    # 1. GARANTA A SEGURANÇA DO ESTADO
    state = copy.deepcopy(state)

    logger.info(
        f"Processing qualification for {_get_phone_from_state(state)} - simplified sequential mode"
    )

    state["text"]

    # 2. NOVA ARQUITETURA: Use entidades já extraídas pelo GeminiClassifier
    _process_nlu_entities(state)

    # 3. DETERMINE O PRÓXIMO PASSO
    next_var_to_collect = None
    collected = state["collected_data"]

    for var in QUALIFICATION_VARS_SEQUENCE:
        if var not in collected or not collected.get(var):
            # Handle conditional logic: skip student_name if beneficiary is self
            if var == "student_name" and collected.get("beneficiary_type") == "self":
                continue
            next_var_to_collect = var
            break

    # 🎥 LOG DE DEPURAÇÃO: Identificação da próxima variável
    logger.info(
        f"QUALIFICATION_DEBUG|Next missing variable identified: {next_var_to_collect}"
    )
    logger.info(f"QUALIFICATION_DEBUG|Current collected data: {collected}")

    # 4. GERE A RESPOSTA
    if next_var_to_collect:
        # Generate question for next variable
        response_text = _generate_question_for_variable(state, next_var_to_collect)

        # 🎥 LOG DE DEPURAÇÃO: Resposta gerada (simulando prompt LLM)
        logger.info(
            f"QUALIFICATION_DEBUG|Generated response for {next_var_to_collect}: '{response_text}'"
        )
        logger.info(
            f"QUALIFICATION_DEBUG|Final prompt to LLM: "
            f"System='Direct response generation', User='{response_text}'"
        )

        state["last_bot_response"] = response_text

        # Send message via Evolution API
        phone = _get_phone_from_state(state)
        instance = state.get("instance", "kumon_assistant")
        await send_text(phone, response_text, instance)

        # Update conversation step
        state["current_step"] = _get_step_for_variable(next_var_to_collect)

        logger.info(f"Asking for {next_var_to_collect}: {response_text[:50]}...")

    else:
        # A qualificação está completa
        logger.info("All qualification variables collected - generating summary")

        collected = state["collected_data"]
        parent_name = collected.get("parent_name", "")
        beneficiary_type = collected.get("beneficiary_type", "")
        student_name = collected.get("student_name", "")
        student_age = collected.get("student_age", "")
        interests = collected.get("program_interests", [])

        # Generate summary
        if beneficiary_type == "self":
            student_ref = parent_name if parent_name else "você"
        else:
            student_ref = student_name if student_name else "a criança"

        interests_text = (
            " e ".join(interests) if interests else "as matérias de interesse"
        )

        response_text = (
            f"Perfeito, {parent_name}! ✨\n\n"
            f"📋 **Resumo da Qualificação:**\n"
            f"👤 Aluno(a): {student_ref} ({student_age} anos)\n"
            f"📚 Interesse: {interests_text}\n\n"
            f"Agora posso explicar melhor como o Kumon funcionaria para {student_ref}. "
            f"Gostaria de conhecer nossa metodologia e valores?"
        )

        state["last_bot_response"] = response_text

        # Send message via Evolution API
        phone = _get_phone_from_state(state)
        instance = state.get("instance", "kumon_assistant")
        await send_text(phone, response_text, instance)

        state["current_stage"] = ConversationStage.INFORMATION_GATHERING
        state["current_step"] = ConversationStep.METHODOLOGY_EXPLANATION

        logger.info("Qualification complete - transitioned to information gathering")

    # 5. RETORNE O ESTADO ATUALIZADO
    return state


def _process_nlu_entities(state: Dict[str, Any]) -> None:
    """
    🧠 NOVA ARQUITETURA: Processa entidades já extraídas pelo GeminiClassifier contextual.

    O GeminiClassifier é agora o cérebro principal da extração - ele tem memória de curto prazo
    através do histórico da conversa e extrai entidades de forma muito mais precisa.

    Esta função apenas valida e salva as entidades que já foram extraídas.
    """
    nlu_entities = state.get("nlu_entities", {})
    collected = state["collected_data"]

    # Processar cada entidade extraída pelo NLU
    for entity_key, entity_value in nlu_entities.items():
        if entity_value is not None and entity_key in QUALIFICATION_VARS_SEQUENCE:
            # Validação adicional se necessário
            if entity_key == "student_age":
                # Validar idade
                if isinstance(entity_value, int) and 2 <= entity_value <= 25:
                    collected[entity_key] = entity_value
                    logger.info(f"NLU extracted {entity_key}: {entity_value}")
            elif entity_key == "program_interests":
                # Validar interesses
                if isinstance(entity_value, list) and entity_value:
                    collected[entity_key] = entity_value
                    logger.info(f"NLU extracted {entity_key}: {entity_value}")
            else:
                # Para strings simples (names, beneficiary_type)
                if isinstance(entity_value, str) and len(entity_value.strip()) > 0:
                    collected[entity_key] = entity_value.strip()
                    logger.info(f"NLU extracted {entity_key}: {entity_value}")

    logger.info(f"NLU processing complete. Collected: {collected}")


# 🗑️ REMOVED: _extract_data_from_current_message_legacy function
# This legacy function has been eliminated as part of the new architecture.
# The qualification_node now relies exclusively on entities extracted by GeminiClassifier.


def _generate_question_for_variable(state: Dict[str, Any], variable: str) -> str:
    """
    🗣️ Generate contextual question for the specified variable.

    Creates personalized questions based on already collected data.
    """
    collected = state["collected_data"]

    if variable == "parent_name":
        return "Olá! Para começarmos, qual é o seu nome?"

    elif variable == "beneficiary_type":
        parent_name = collected.get("parent_name", "")
        greeting = f"{parent_name}, " if parent_name else ""
        return f"{greeting}o Kumon é para você mesmo ou para outra pessoa?"

    elif variable == "student_name":
        return "Qual é o nome da criança?"

    elif variable == "student_age":
        student_name = collected.get("student_name", "")
        beneficiary_type = collected.get("beneficiary_type", "")

        if beneficiary_type == "self":
            return "Qual é a sua idade?"
        elif student_name:
            return f"Quantos anos {student_name} tem?"
        else:
            return "Qual é a idade da criança?"

    elif variable == "program_interests":
        student_name = collected.get("student_name", "")
        beneficiary_type = collected.get("beneficiary_type", "")

        if beneficiary_type == "self":
            subject_ref = "você gostaria"
        elif student_name:
            subject_ref = f"{student_name} gostaria"
        else:
            subject_ref = "gostaria"

        return (
            f"Qual matéria {subject_ref} de estudar no Kumon?\n\n"
            "📊 **Matemática** - Raciocínio lógico e cálculos\n"
            "📝 **Português** - Leitura, escrita e interpretação\n"
            "🗣️ **Inglês** - Comunicação global"
        )

    return "Poderia me contar mais sobre isso?"


def _get_phone_from_state(state: Dict[str, Any]) -> str:
    """
    🔧 HELPER: Get phone number from state with compatibility for both formats.

    Handles both 'phone_number' (test format) and 'phone' (production format).
    """
    return state.get("phone_number", state.get("phone", "unknown"))


def _get_step_for_variable(variable: str) -> ConversationStep:
    """
    📍 Map qualification variables to conversation steps.
    """
    step_mapping = {
        "parent_name": ConversationStep.PARENT_NAME_COLLECTION,
        "beneficiary_type": ConversationStep.CHILD_NAME_COLLECTION,
        "student_name": ConversationStep.CHILD_NAME_COLLECTION,
        "student_age": ConversationStep.CHILD_AGE_INQUIRY,
        "program_interests": ConversationStep.CURRENT_SCHOOL_GRADE,
    }
    return step_mapping.get(variable, ConversationStep.PARENT_NAME_COLLECTION)
