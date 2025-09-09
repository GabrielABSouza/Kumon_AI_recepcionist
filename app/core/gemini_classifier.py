"""
Minimal intent classifier using Gemini Flash.
Maps user message to one of the predefined intents.
"""
import os
from enum import Enum
from typing import Tuple

import google.generativeai as genai


class Intent(Enum):
    """Supported intents for the system."""

    GREETING = "greeting"
    QUALIFICATION = "qualification"
    INFORMATION = "information"
    SCHEDULING = "scheduling"
    FALLBACK = "fallback"


class GeminiClassifier:
    """Simple intent classifier using Gemini Flash."""

    def __init__(self):
        # Configure Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        self.enabled = bool(api_key)

        if self.enabled:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.model = None

    def classify(self, text: str, context: dict = None) -> Tuple[Intent, float]:
        """
        Classify user message into an intent with optional context.
        Returns (intent, confidence).

        Args:
            text: Current user message
            context: Optional context dict with conversation history and state
        """
        if not self.enabled:
            # Simple fallback classification for testing
            return self._simple_classify(text)

        # Build contextual prompt if context provided
        if context:
            prompt = self._build_contextual_prompt(text, context)
        else:
            prompt = self._build_prompt(text)

        try:
            response = self.model.generate_content(prompt)
            result = response.text.strip().lower()

            # Parse response
            intent, confidence = self._parse_response(result)
            return intent, confidence

        except Exception as e:
            print(f"Classification error: {e}")
            return Intent.FALLBACK, 0.0

    def _simple_classify(self, text: str) -> Tuple[Intent, float]:
        """Simple keyword-based classification for testing."""
        text_lower = text.lower()

        if any(word in text_lower for word in ["oi", "olá", "bom dia", "boa tarde"]):
            return Intent.GREETING, 0.9
        elif any(
            word in text_lower for word in ["matricular", "matrícula", "inscrever"]
        ):
            return Intent.QUALIFICATION, 0.85
        elif any(word in text_lower for word in ["método", "funciona", "kumon"]):
            return Intent.INFORMATION, 0.8
        elif any(word in text_lower for word in ["agendar", "visita", "horário"]):
            return Intent.SCHEDULING, 0.85
        else:
            return Intent.FALLBACK, 0.5

    def _build_prompt(self, text: str) -> str:
        """Build classification prompt from template."""
        # Load prompt template
        try:
            from pathlib import Path

            prompt_path = Path(__file__).parent.parent / "prompts" / "gemini_prompt.txt"
            with open(prompt_path, encoding="utf-8") as f:
                template = f.read()
        except Exception:
            # Fallback prompt if file not found
            template = (
                "Classifique a mensagem em: greeting, qualification, "
                "information, scheduling ou fallback.\n"
                "Responda: categoria|confiança"
            )

        return f'{template}\n\nMensagem: "{text}"'

    def _parse_response(self, response: str) -> Tuple[Intent, float]:
        """Parse Gemini response into intent and confidence."""
        try:
            parts = response.split("|")
            if len(parts) != 2:
                return Intent.FALLBACK, 0.0

            intent_str = parts[0].strip()
            confidence = float(parts[1].strip())

            # Map to Intent enum
            intent_map = {
                "greeting": Intent.GREETING,
                "qualification": Intent.QUALIFICATION,
                "information": Intent.INFORMATION,
                "scheduling": Intent.SCHEDULING,
                "fallback": Intent.FALLBACK,
            }

            intent = intent_map.get(intent_str, Intent.FALLBACK)
            return intent, confidence

        except Exception:
            return Intent.FALLBACK, 0.0

    def _build_contextual_prompt(self, text: str, context: dict) -> str:
        """Build contextual classification prompt with conversation history and state."""
        try:
            from pathlib import Path

            # Load contextual prompt template
            prompt_path = (
                Path(__file__).parent.parent
                / "prompts"
                / "contextual_gemini_prompt.txt"
            )
            with open(prompt_path, encoding="utf-8") as f:
                template = f.read()
        except Exception:
            # Fallback contextual template if file not found
            template = (
                "Você é um classificador contextual de intenções.\n\n"
                "**HISTÓRICO DA CONVERSA:**\n{conversation_history}\n\n"
                "**ESTADO ATUAL:**\n{collected_vars} coletadas\n{missing_vars} faltando\n\n"
                '**MENSAGEM ATUAL:** "{user_message}"\n\n'
                "Classifique em: greeting, qualification, information, scheduling ou fallback.\n"
                "Responda: categoria|confiança"
            )

        # Extract context information
        conversation_history = self._format_conversation_history(context)
        collected_vars, missing_vars = self._format_qualification_state(context)

        # Fill template
        return template.format(
            conversation_history=conversation_history,
            collected_vars=collected_vars,
            missing_vars=missing_vars,
            user_message=text,
        )

    def _format_conversation_history(self, context: dict) -> str:
        """Format conversation history for prompt."""
        history = context.get("conversation_history", [])

        if not history:
            return "Nenhum histórico anterior (conversa iniciando)"

        formatted_lines = []
        for entry in history[-5:]:  # Last 5 exchanges
            role = entry.get("role", "unknown")
            content = entry.get("content", "")

            if role == "assistant":
                formatted_lines.append(f"Assistente: {content}")
            elif role == "user":
                formatted_lines.append(f"Usuário: {content}")

        return (
            "\n".join(formatted_lines)
            if formatted_lines
            else "Nenhum histórico disponível"
        )

    def _format_qualification_state(self, context: dict) -> tuple[str, str]:
        """Format current qualification state for prompt."""
        # Standard qualification variables
        qualification_vars = [
            "parent_name",
            "student_name",
            "student_age",
            "program_interests",
        ]

        collected = []
        missing = []

        for var in qualification_vars:
            if context.get(var):
                collected.append(var)
            else:
                missing.append(var)

        collected_str = ", ".join(collected) if collected else "Nenhuma"
        missing_str = ", ".join(missing) if missing else "Nenhuma"

        return collected_str, missing_str


# Global instance
classifier = GeminiClassifier()
