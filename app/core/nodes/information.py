import copy
import logging
from typing import Any, Dict

from ..delivery import send_text

logger = logging.getLogger(__name__)


# Utility function to get next qualification question from qualification logic
def get_next_qualification_question_from_state(state: Dict[str, Any]) -> str:
    """
    Get the next qualification question by delegating to qualification node logic.
    This avoids duplicating qualification logic in information node.
    """
    # Import here to avoid circular imports
    from .qualification import QUALIFICATION_VARS_SEQUENCE

    collected = state.get("collected_data", {})

    # Find first missing variable
    for var in QUALIFICATION_VARS_SEQUENCE:
        if var not in collected or not collected.get(var):
            # Handle conditional logic: skip student_name if beneficiary is self
            if var == "student_name" and collected.get("beneficiary_type") == "self":
                continue

            # Generate question for this variable (simplified)
            parent_name = collected.get("parent_name", "")
            name_prefix = f"{parent_name}, " if parent_name else ""

            if var == "parent_name":
                return "Para personalizar melhor nosso atendimento, como posso chamá-lo(a)?"
            elif var == "beneficiary_type":
                return f"{name_prefix}o Kumon é para você mesmo ou para outra pessoa?"
            elif var == "student_name":
                return "Qual é o nome da criança?"
            elif var == "student_age":
                student_name = collected.get("student_name", "")
                if student_name:
                    return f"Quantos anos {student_name} tem?"
                else:
                    return "Qual é a idade da criança?"
            elif var == "program_interests":
                return (
                    f"{name_prefix}tem interesse em algum programa específico? "
                    "Matemática, Português ou ambos?"
                )

    return ""  # No qualification needed


def build_blended_response_prompt(user_question: str, next_q_question: str) -> str:
    """Build prompt for blended response (information + qualification)."""
    system_prompt = f"""Você é Cecília, assistente virtual do Kumon Vila A.

TAREFA: Responda à pergunta do usuário e, se houver, faça a próxima pergunta " \
                        "de qualificação de forma natural.

INFORMAÇÕES KUMON VILA A:
- Matemática ou Português: R$ 375,00/mês cada
- Taxa de matrícula: R$ 100,00 (única vez)
- Idade: A partir de 3 anos
- Horários: Segunda a Sexta, 8h às 18h
- Telefone: (51) 99692-1999

PERGUNTA DO USUÁRIO: "{user_question}"
PRÓXIMA PERGUNTA DE QUALIFICAÇÃO: "{next_q_question if next_q_question else 'Nenhuma'}"

Responda de forma natural e amigável:"""

    return system_prompt


async def information_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    🧠 SIMPLIFIED INFORMATION NODE - NEW ARCHITECTURE

    Pure orchestration node that relies exclusively on GeminiClassifier for NLU.

    ARCHITECTURE PRINCIPLES:
    - 🎯 ZERO NLU logic - trusts GeminiClassifier 100%
    - 🎭 Pure orchestrator: answers questions + continues qualification
    - 🔄 Delegates qualification logic to qualification_node utilities
    - 🚀 Simplified: direct state manipulation, focused responsibility

    WORKFLOW:
    1. Get user question from state
    2. Get next qualification question from shared logic
    3. Build blended response prompt
    4. Generate response with LLM
    5. Send response and return updated state
    """
    print("DEBUG|information_node_executed|CALLED!")
    print(f"DEBUG|information_node|state_type={type(state)}")
    # 1. GUARANTEE STATE SAFETY
    state = copy.deepcopy(state)

    logger.info(
        f"Processing information request for {state.get('phone_number')} - simplified mode"
    )

    # 2. PROCESS NLU ENTITIES INTO COLLECTED_DATA (transfer from nlu_entities)
    nlu_entities = state.get("nlu_entities", {})
    collected_data = state.get("collected_data", {})

    # Transfer entities to collected_data if they exist
    for entity_key, entity_value in nlu_entities.items():
        if entity_value:  # Only transfer non-empty values
            collected_data[entity_key] = entity_value

    state["collected_data"] = collected_data

    # 3. GET USER QUESTION (already in state)
    user_question = state.get("text", "")

    # 4. GET NEXT QUALIFICATION QUESTION (from shared qualification logic)
    next_q_question = get_next_qualification_question_from_state(state)

    # 5. BUILD BLENDED RESPONSE PROMPT
    prompt = build_blended_response_prompt(user_question, next_q_question)

    # 6. GENERATE RESPONSE WITH LLM
    try:
        from ..llm.openai_adapter import OpenAIClient

        openai_client = OpenAIClient()
        response_text = await openai_client.chat(
            model="gpt-3.5-turbo",
            system_prompt=prompt,
            user_prompt=user_question,
            temperature=0.7,
            max_tokens=400,
        )

        logger.info(f"Generated blended response for {state.get('phone_number')}")

    except Exception as e:
        logger.error(f"LLM generation failed: {str(e)}")
        # Simple fallback
        response_text = (
            "Desculpe, estou com dificuldades técnicas. "
            "Por favor, entre em contato pelo telefone (51) 99692-1999."
        )

    # 7. SEND RESPONSE AND UPDATE STATE
    phone = state.get("phone")
    instance = state.get("instance", "kumon_assistant")

    if phone:
        await send_text(phone, response_text, instance)

    state["last_bot_response"] = response_text

    logger.info(f"Information response sent for {state.get('phone_number')}")

    # 8. RETURN UPDATED STATE
    return state
