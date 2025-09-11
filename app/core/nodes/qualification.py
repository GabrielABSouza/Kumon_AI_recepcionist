import copy
import logging
import re

from ..state.models import CeciliaState, ConversationStage, ConversationStep

logger = logging.getLogger(__name__)

# 🎯 SOURCE OF TRUTH: Sequential qualification variables order
QUALIFICATION_VARS_SEQUENCE = [
    "parent_name",
    "beneficiary_type",
    "student_name",
    "student_age",
    "program_interests",
]


async def qualification_node(state: CeciliaState) -> CeciliaState:
    """
    🚀 SIMPLIFIED SEQUENTIAL QUALIFICATION NODE

    Radical simplification that eliminates complex class abstractions:
    - Direct state manipulation with copy.deepcopy safety
    - Consolidated logic in single function
    - Clear, debuggable sequential flow
    - No complex transformation chains

    Follows TDD requirements:
    1. Extract data from current user message
    2. Determine next variable to collect
    3. Generate appropriate question or complete qualification
    4. Return updated state directly
    """
    # 🎥 FORENSIC AUDIT: Version Fingerprint
    logging.warning(
        "RUNTIME_AUDIT|Executing new qualification_node version: v2.0_simplified"
    )

    # 1. GARANTA A SEGURANÇA DO ESTADO
    state = copy.deepcopy(state)

    logger.info(
        f"Processing qualification for {state['phone_number']} - simplified sequential mode"
    )

    user_message = state["last_user_message"]

    # 2. EXTRAIA NOVAS INFORMAÇÕES (se houver)
    _extract_data_from_current_message(state, user_message)

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

    # 🎥 FORENSIC AUDIT: Internal reasoning logs
    logging.warning(f"RUNTIME_AUDIT|State before prompt gen: {state}")
    logging.warning(
        f"RUNTIME_AUDIT|Logic identified next missing var as: '{next_var_to_collect}'"
    )
    logging.warning(f"RUNTIME_AUDIT|Current collected data: {collected}")
    logging.warning(
        f"RUNTIME_AUDIT|Full QUALIFICATION_VARS_SEQUENCE: {QUALIFICATION_VARS_SEQUENCE}"
    )

    # 🎥 LOG DE DEPURAÇÃO: Identificação da próxima variável
    logger.info(
        f"QUALIFICATION_DEBUG|Next missing variable identified: {next_var_to_collect}"
    )
    logger.info(f"QUALIFICATION_DEBUG|Current collected data: {collected}")

    # 4. GERE A RESPOSTA
    if next_var_to_collect:
        # Generate question for next variable
        response_text = _generate_question_for_variable(state, next_var_to_collect)

        # 🎥 FORENSIC AUDIT: Final prompt being sent
        logging.warning(
            f"RUNTIME_AUDIT|Final prompt being sent to LLM: {response_text}"
        )

        # 🎥 LOG DE DEPURAÇÃO: Resposta gerada (simulando prompt LLM)
        logger.info(
            f"QUALIFICATION_DEBUG|Generated response for {next_var_to_collect}: '{response_text}'"
        )
        logger.info(
            f"QUALIFICATION_DEBUG|Final prompt to LLM: System='Direct response generation', User='{response_text}'"
        )

        state["last_bot_response"] = response_text

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
        state["current_stage"] = ConversationStage.INFORMATION_GATHERING
        state["current_step"] = ConversationStep.METHODOLOGY_EXPLANATION

        logger.info("Qualification complete - transitioned to information gathering")

    # 5. RETORNE O ESTADO ATUALIZADO
    return state


def _extract_data_from_current_message(state: CeciliaState, user_message: str) -> None:
    """
    🔍 Extract data from user message based on what we're currently collecting.

    Simplified extraction logic with direct state modification.
    """
    collected = state["collected_data"]
    message_lower = user_message.lower()

    # Determine what we're currently trying to collect
    current_var = None
    for var in QUALIFICATION_VARS_SEQUENCE:
        if var not in collected or not collected.get(var):
            if var == "student_name" and collected.get("beneficiary_type") == "self":
                continue
            current_var = var
            break

    if not current_var:
        return  # Nothing to extract

    # Extract based on current variable
    if current_var == "parent_name":
        # Look for names in the message
        # Improved extraction: look for "nome é", "sou", "me chamo" patterns
        name_patterns = [
            r"nome (?:é|eh) ([A-Z][a-záêçõàâáéíóúô]+(?:\s+[A-Z][a-záêçõàâáéíóúô]+)*)",
            r"(?:sou|me chamo) ([A-Z][a-záêçõàâáéíóúô]+(?:\s+[A-Z][a-záêçõàâáéíóúô]+)*)",
            r"^([A-Z][a-záêçõàâáéíóúô]+(?:\s+[A-Z][a-záêçõàâáéíóúô]+)*)$",  # Just name
        ]

        for pattern in name_patterns:
            match = re.search(pattern, user_message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Avoid extracting common words as names
                if name.lower() not in ["meu", "minha", "para", "nome", "sou", "chamo"]:
                    collected["parent_name"] = name
                    logger.info(f"Extracted parent_name: {name}")
                    break

    elif current_var == "beneficiary_type":
        # Extract beneficiary type
        if any(
            word in message_lower
            for word in ["para mim", "para eu", "é para mim", "pra mim"]
        ):
            collected["beneficiary_type"] = "self"
        elif any(
            word in message_lower
            for word in ["para meu", "para minha", "meu filho", "minha filha"]
        ):
            collected["beneficiary_type"] = "child"
        elif any(
            word in message_lower
            for word in ["filho", "filha", "criança", "menino", "menina"]
        ):
            collected["beneficiary_type"] = "child"
        elif any(
            word in message_lower for word in ["para você", "você mesmo", "para si"]
        ):
            collected["beneficiary_type"] = "self"
        elif any(word in message_lower for word in ["outra pessoa"]):
            collected["beneficiary_type"] = "child"

        if "beneficiary_type" in collected:
            logger.info(f"Extracted beneficiary_type: {collected['beneficiary_type']}")

    elif current_var == "student_name":
        # Extract student name - simplified and more robust approach
        # Find all capitalized words in the message
        capitalized_words = re.findall(r"\b[A-Z][a-záêçõàâáéíóúô]+\b", user_message)

        # Filter out common non-name words
        non_names = {
            "O",
            "A",
            "E",
            "É",
            "Eh",
            "Nome",
            "Dele",
            "Dela",
            "Filho",
            "Filha",
            "Criança",
            "Tem",
            "Ele",
            "Ela",
        }
        potential_names = [word for word in capitalized_words if word not in non_names]

        if potential_names:
            # Take the first potential name
            collected["student_name"] = potential_names[0]
            logger.info(f"Extracted student_name: {potential_names[0]}")
        else:
            # Fallback: try simple patterns
            name_patterns = [
                r"(?:nome|chama)\s+(?:é|eh|dele|dela)?\s*([A-Z][a-z]+)",
                r"é\s+([A-Z][a-z]+)",
                r"^([A-Z][a-z]+)$",
            ]

            for pattern in name_patterns:
                match = re.search(pattern, user_message, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    if name.lower() not in [
                        "nome",
                        "ele",
                        "ela",
                        "filho",
                        "filha",
                        "criança",
                        "tem",
                    ]:
                        collected["student_name"] = name
                        logger.info(f"Extracted student_name via pattern: {name}")
                        break

    elif current_var == "student_age":
        # Extract age
        age_pattern = r"\b(\d{1,2})\s*anos?"
        age_match = re.search(age_pattern, user_message)
        if age_match:
            age = int(age_match.group(1))
            if 2 <= age <= 25:  # Reasonable age range
                collected["student_age"] = age
                logger.info(f"Extracted student_age: {age}")

    elif current_var == "program_interests":
        # Extract program interests
        interests = []
        if any(
            word in message_lower
            for word in ["matemática", "matematica", "math", "números", "calculo"]
        ):
            interests.append("Matemática")
        if any(
            word in message_lower
            for word in ["português", "portugues", "redação", "leitura", "escrita"]
        ):
            interests.append("Português")
        if any(
            word in message_lower for word in ["inglês", "ingles", "english", "idioma"]
        ):
            interests.append("Inglês")

        if interests:
            collected["program_interests"] = interests
            logger.info(f"Extracted program_interests: {interests}")


def _generate_question_for_variable(state: CeciliaState, variable: str) -> str:
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
