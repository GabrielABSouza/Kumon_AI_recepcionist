"""
Comprehensive NLU (Natural Language Understanding) engine using Gemini Flash.
Returns structured output with primary/secondary intents and extracted entities.
"""
import os
from typing import Optional

import google.generativeai as genai


class GeminiClassifier:
    """Comprehensive NLU engine using Gemini Flash for structured intent classification."""

    def __init__(self):
        # Configure Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        self.enabled = bool(api_key)

        if self.enabled:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.model = None

    def classify(self, text: str, context: Optional[dict] = None):
        """
        Classify user message into structured NLU output with optional context.
        Returns structured dict with primary_intent, secondary_intent, entities, confidence.

        Args:
            text: Current user message
            context: Optional context dict with conversation history and state

        Returns:
            dict: {
                "primary_intent": str,
                "secondary_intent": str|None,
                "entities": dict,
                "confidence": float
            }
        """
        if not self.enabled:
            # Simple "dumb" fallback when Gemini API not configured
            return {
                "primary_intent": "fallback",
                "secondary_intent": None,
                "entities": {},
                "confidence": 0.0,
                "error": "Gemini API not configured",
            }

        # Build unified NLU prompt
        prompt = self._build_nlu_prompt(text, context)

        try:
            response = self.model.generate_content(prompt)
            result = response.text.strip()

            # Parse structured JSON response
            structured_result = self._parse_structured_response(result)
            return structured_result

        except Exception as e:
            print(f"Classification error: {e}")
            return {
                "primary_intent": "fallback",
                "secondary_intent": None,
                "entities": {},
                "confidence": 0.0,
            }

    # Legacy _simple_classify() method removed - all code now uses structured format

    def _build_nlu_prompt(self, text: str, context: Optional[dict] = None) -> str:
        """Build unified NLU prompt with optional context.

        If context is provided, renders sophisticated template with history and state.
        If no context, renders simplified version of the same base template.
        """
        if context:
            # Sophisticated version with context
            conversation_history = self._format_conversation_history(context)
            missing_vars = self._get_missing_qualification_vars(context)

            return f"""Você é um motor de NLU (Natural Language Understanding) para um
chatbot de atendimento do Kumon. Sua tarefa é analisar a mensagem do usuário
dentro do contexto da conversa e retornar um objeto JSON estruturado.

**CONTEXTO DA CONVERSA:**
- Histórico (últimas 4 mensagens):
{conversation_history}
- Estado Atual da Qualificação (variáveis que ainda faltam): {missing_vars}

**MENSAGEM ATUAL DO USUÁRIO:**
"{text}"

**TAREFAS DE ANÁLISE:**
1. **primary_intent:** Determine a intenção principal. Se a mensagem responde a uma
pergunta anterior, a intenção é 'qualification'. Se introduz um tópico novo, a
intenção é esse novo tópico (ex: 'information', 'scheduling').
2. **secondary_intent:** Se a mensagem contiver um pedido secundário (ex: responder
E fazer uma nova pergunta), identifique-o aqui. Caso contrário, retorne null.
3. **entities:** Extraia as seguintes entidades do texto, se presentes:
   - parent_name (string)
   - beneficiary_type (string, valores possíveis: 'self' ou 'child')
   - student_name (string)
   - student_age (integer)
   - program_interests (list[string])
4. **confidence:** Sua confiança na classificação da intenção primária (de 0.0 a 1.0).

**OUTPUT (retorne APENAS o objeto JSON, sem nenhum texto adicional):**
{{
  "primary_intent": "qualification|information|scheduling|greeting|fallback",
  "secondary_intent": "information|scheduling|qualification|null",
  "entities": {{
    "parent_name": "string ou null",
    "beneficiary_type": "self|child ou null",
    "student_name": "string ou null",
    "student_age": "integer ou null",
    "program_interests": ["string"] ou null
  }},
  "confidence": 0.0
}}"""
        else:
            # Simplified version without context
            return f"""Você é um motor de NLU para um chatbot do Kumon.
Analise a mensagem e retorne um objeto JSON.

**MENSAGEM DO USUÁRIO:**
"{text}"

**TAREFAS DE ANÁLISE:**
1. **primary_intent:** greeting, qualification, information, scheduling, ou fallback
2. **entities:** Extraia nomes, idades, tipo de beneficiário se presentes
3. **confidence:** Confiança na classificação (0.0 a 1.0)

**OUTPUT (retorne APENAS o objeto JSON, sem nenhum texto adicional):**
{{
  "primary_intent": "qualification|information|scheduling|greeting|fallback",
  "secondary_intent": null,
  "entities": {{
    "parent_name": "string ou null",
    "beneficiary_type": "self|child ou null",
    "student_name": "string ou null",
    "student_age": "integer ou null",
    "program_interests": ["string"] ou null
  }},
  "confidence": 0.0
}}"""

    # Legacy _parse_response() method removed - replaced by _parse_structured_response()

    def _parse_structured_response(self, response: str) -> dict:
        """Parse Gemini JSON response into structured dict with robust error handling."""
        import json
        import re

        try:
            # Try to extract JSON from response (in case there's extra text)
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
            else:
                json_str = response

            # Parse JSON
            parsed = json.loads(json_str)

            # Validate and normalize the structure
            result = {
                "primary_intent": str(parsed.get("primary_intent", "fallback")).lower(),
                "secondary_intent": parsed.get("secondary_intent"),
                "entities": parsed.get("entities", {}),
                "confidence": float(parsed.get("confidence", 0.0)),
            }

            # Normalize secondary_intent null/None values
            if result["secondary_intent"] in [None, "null", ""]:
                result["secondary_intent"] = None
            else:
                result["secondary_intent"] = str(result["secondary_intent"]).lower()

            # Ensure entities is a dict
            if not isinstance(result["entities"], dict):
                result["entities"] = {}

            # Validate confidence range
            result["confidence"] = max(0.0, min(1.0, result["confidence"]))

            return result

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"JSON parsing error: {e}. Response was: {response}")
            # Return fallback structure
            return {
                "primary_intent": "fallback",
                "secondary_intent": None,
                "entities": {},
                "confidence": 0.0,
            }

    def _format_conversation_history(self, context: dict) -> str:
        """Format conversation history for prompt."""
        # Support both old format (direct) and new format (nested)
        if "history" in context:
            # New format: {'state': {...}, 'history': [...]}
            history = context.get("history", [])
        else:
            # Old format: {'conversation_history': [...]}
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

    def _get_missing_qualification_vars(self, context: dict) -> str:
        """Get missing qualification variables for NLU prompt."""
        # Support both old format (direct) and new format (nested)
        if "state" in context:
            # New format: {'state': {...}, 'history': [...]}
            state_data = context.get("state", {})
        else:
            # Old format: state variables directly in context
            state_data = context

        # Standard qualification variables
        qualification_vars = [
            "parent_name",
            "student_name",
            "student_age",
            "program_interests",
        ]

        missing = []
        for var in qualification_vars:
            if var not in state_data or not state_data.get(var):
                missing.append(var)

        return ", ".join(missing) if missing else "Nenhuma"


# Global instance
classifier = GeminiClassifier()
