import logging
import re
from typing import Any, Dict

from ..state.managers import StateManager
from ..state.models import (
    CeciliaState,
    ConversationStage,
    ConversationStep,
    safe_update_state,
    set_collected_field,
)

logger = logging.getLogger(__name__)


class QualificationNode:
    """
    🧠 SEQUENTIAL QUALIFICATION NODE - TDD Implementation

    Collects qualification variables in strict sequence:
    1. parent_name
    2. beneficiary_type
    3. student_name (if beneficiary is child)
    4. student_age
    5. program_interests
    """

    # 🎯 SOURCE OF TRUTH: Sequential qualification variables order
    QUALIFICATION_VARS_SEQUENCE = [
        "parent_name",
        "beneficiary_type",
        "student_name",
        "student_age",
        "program_interests",
    ]

    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """
        🧠 INTELLIGENT SEQUENTIAL QUALIFICATION LOGIC

        Follows TDD test requirements:
        - Iterates through QUALIFICATION_VARS_SEQUENCE
        - Finds first missing variable
        - Handles conditional logic (skip student_name if beneficiary_type='self')
        - Generates appropriate prompts for each variable
        """
        logger.info(
            f"Processing qualification for {state['phone_number']} - sequential collection mode"
        )

        user_message = state["last_user_message"]

        # 1. EXTRACT DATA FROM CURRENT MESSAGE
        await self._extract_data_from_message(state, user_message)

        # 2. FIND NEXT VARIABLE TO COLLECT
        next_var = self._get_next_qualification_variable(state)

        if not next_var:
            # All variables collected - move to next stage
            logger.info(
                "All qualification variables collected - transitioning to information gathering"
            )
            return await self._handle_qualification_complete(state)

        # 3. GENERATE PROMPT FOR NEXT VARIABLE
        response = self._generate_question_for_variable(state, next_var)

        # 4. UPDATE STATE AND RETURN
        updates = {"current_step": self._get_step_for_variable(next_var)}

        return self._create_response(state, response, updates)

    def _get_next_qualification_variable(self, state: CeciliaState) -> str:
        """
        🔧 CORE LOGIC: Find the next variable to collect in sequence

        Follows the exact logic from TDD tests:
        - Iterate through QUALIFICATION_VARS_SEQUENCE
        - Return first missing variable
        - Handle conditional logic (skip student_name if beneficiary_type='self')
        """
        collected = state["collected_data"]

        for var in self.QUALIFICATION_VARS_SEQUENCE:
            if var not in collected or not collected.get(var):
                # Handle conditional logic
                if (
                    var == "student_name"
                    and collected.get("beneficiary_type") == "self"
                ):
                    continue  # Skip student_name if beneficiary is self
                return var

        return None  # All variables collected

    async def _extract_data_from_message(
        self, state: CeciliaState, user_message: str
    ) -> None:
        """
        🔍 EXTRACT DATA: Extract relevant data from user message based on context

        This method analyzes the user message and extracts information
        based on what variable we're currently trying to collect.
        """
        current_var = self._get_next_qualification_variable(state)
        message_lower = user_message.lower()

        if current_var == "parent_name":
            # Extract parent name from message
            # Simple heuristic: if message looks like a name (not greeting)
            if not any(
                greeting in message_lower
                for greeting in ["olá", "oi", "bom dia", "boa tarde", "boa noite"]
            ):
                # Extract potential name (words that are capitalized or look like names)
                name_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
                name_matches = re.findall(name_pattern, user_message)
                if (
                    name_matches and len(user_message.strip()) < 50
                ):  # Likely just a name
                    set_collected_field(state, "parent_name", name_matches[0])
                    logger.info(f"Extracted parent_name: {name_matches[0]}")

        elif current_var == "beneficiary_type":
            # Extract beneficiary type from message
            if any(
                word in message_lower
                for word in [
                    "para mim",
                    "para meu",
                    "para eu",
                    "é para mim",
                    "meu",
                    "minha",
                ]
            ):
                if any(
                    word in message_lower
                    for word in ["filho", "filha", "criança", "menino", "menina"]
                ):
                    set_collected_field(state, "beneficiary_type", "child")
                else:
                    set_collected_field(state, "beneficiary_type", "self")
            elif any(
                word in message_lower for word in ["para você", "você mesmo", "para si"]
            ):
                set_collected_field(state, "beneficiary_type", "self")
            elif any(
                word in message_lower
                for word in ["filho", "filha", "criança", "outra pessoa"]
            ):
                set_collected_field(state, "beneficiary_type", "child")

        elif current_var == "student_name":
            # Extract student name
            name_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
            name_matches = re.findall(name_pattern, user_message)
            if name_matches:
                set_collected_field(state, "student_name", name_matches[0])
                logger.info(f"Extracted student_name: {name_matches[0]}")

        elif current_var == "student_age":
            # Extract age from message
            age_match = re.search(r"\b(\d{1,2})\b", user_message)
            if age_match:
                age = int(age_match.group(1))
                if 2 <= age <= 25:  # Reasonable age range
                    set_collected_field(state, "student_age", age)
                    logger.info(f"Extracted student_age: {age}")

        elif current_var == "program_interests":
            # Extract program interests
            interests = []
            if any(
                word in message_lower
                for word in ["matemática", "matematica", "math", "números"]
            ):
                interests.append("Matemática")
            if any(
                word in message_lower
                for word in ["português", "portugues", "redação", "leitura"]
            ):
                interests.append("Português")
            if any(word in message_lower for word in ["inglês", "ingles", "english"]):
                interests.append("Inglês")

            if interests:
                set_collected_field(state, "program_interests", interests)
                logger.info(f"Extracted program_interests: {interests}")

    def _generate_question_for_variable(
        self, state: CeciliaState, variable: str
    ) -> str:
        """
        🗣️ GENERATE QUESTIONS: Create appropriate question for each variable

        This method generates contextual questions based on the variable
        we need to collect and the current conversation state.
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

    def _get_step_for_variable(self, variable: str) -> ConversationStep:
        """
        📍 MAP VARIABLES TO STEPS: Map qualification variables to conversation steps
        """
        step_mapping = {
            "parent_name": ConversationStep.PARENT_NAME_COLLECTION,
            "beneficiary_type": ConversationStep.CHILD_NAME_COLLECTION,
            "student_name": ConversationStep.CHILD_NAME_COLLECTION,
            "student_age": ConversationStep.CHILD_AGE_INQUIRY,
            "program_interests": ConversationStep.CURRENT_SCHOOL_GRADE,
        }
        return step_mapping.get(variable, ConversationStep.PARENT_NAME_COLLECTION)

    async def _handle_qualification_complete(
        self, state: CeciliaState
    ) -> Dict[str, Any]:
        """
        ✅ QUALIFICATION COMPLETE: Handle when all variables are collected
        """
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

        response = (
            f"Perfeito, {parent_name}! ✨\n\n"
            f"📋 **Resumo da Qualificação:**\n"
            f"👤 Aluno(a): {student_ref} ({student_age} anos)\n"
            f"📚 Interesse: {interests_text}\n\n"
            f"Agora posso explicar melhor como o Kumon funcionaria para {student_ref}. "
            f"Gostaria de conhecer nossa metodologia e valores?"
        )

        updates = {
            "current_stage": ConversationStage.INFORMATION_GATHERING,
            "current_step": ConversationStep.METHODOLOGY_EXPLANATION,
        }

        return self._create_response(state, response, updates)

    def _create_response(
        self, state: CeciliaState, response: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria resposta padronizada do node"""
        # Atualizar estado
        updated_state = StateManager.update_state(state, updates)

        return {
            "response": response,
            "updated_state": updated_state,
            "stage": updated_state["current_stage"],
            "step": updated_state["current_step"],
            "intent": "qualification_flow",
        }


# Função para uso no LangGraph
async def qualification_node(state: CeciliaState) -> CeciliaState:
    """Entry point para LangGraph"""
    node = QualificationNode()
    result = await node(state)

    # Atualizar estado com resposta
    # CRITICAL FIX: Use safe_update_state to preserve CeciliaState structure
    safe_update_state(state, result["updated_state"])
    state["last_bot_response"] = result["response"]

    return state
