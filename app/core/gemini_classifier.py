"""
Comprehensive NLU (Natural Language Understanding) engine using Gemini Flash.
Returns structured output with primary/secondary intents and extracted entities.
"""
import json
import logging
import os
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)


class GeminiClassifier:
    """Comprehensive NLU engine using Gemini Flash for structured intent classification."""

    def __init__(self):
        # Configure Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        self.enabled = bool(api_key)

        if self.enabled:
            genai.configure(api_key=api_key)
            # ATUALIZADO: Usando um modelo mais recente e especificando a geração de JSON
            self.model = genai.GenerativeModel(
                "gemini-1.5-flash",
                generation_config={"response_mime_type": "application/json"},
            )
        else:
            self.model = None

    async def classify(self, text: str, context: Optional[dict] = None) -> dict:
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
        print(
            f"DEBUG|gemini_classifier|classify_called|text='{text}'|enabled={self.enabled}"
        )

        if not self.enabled:
            print("DEBUG|gemini_classifier|api_not_configured|returning_fallback")
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
            print(f"DEBUG|gemini_classifier|calling_api|prompt_len={len(prompt)}")
            # ATUALIZADO: Usando `generate_content_async` para performance
            response = await self.model.generate_content_async(prompt)
            result = response.text.strip()
            print(f"DEBUG|gemini_classifier|api_response|result_len={len(result)}")

            # Parse structured JSON response
            structured_result = self._parse_structured_response(result)
            intent_name = structured_result.get("primary_intent")
            print(f"DEBUG|gemini_classifier|parsed_result|intent={intent_name}")
            return structured_result

        except Exception as e:
            logger.error(f"Gemini classification error: {e}")
            return {
                "primary_intent": "fallback",
                "secondary_intent": None,
                "entities": {},
                "confidence": 0.0,
            }

    def _build_nlu_prompt(self, text: str, context: Optional[dict] = None) -> str:
        """
        Constrói um prompt de NLU unificado, focado em contexto e exemplos.
        Esta versão é mais elegante e confia no raciocínio do LLM.
        """

        conversation_history = self._format_conversation_history(context)
        missing_vars = self._get_missing_qualification_vars(context)

        # O novo prompt elegante
        return f"""Você é o cérebro de NLU da Cecília, assistente virtual do Kumon.
Analise a MENSAGEM ATUAL DO USUÁRIO no contexto da CONVERSA e preencha um JSON.

**OBJETIVO PRINCIPAL:**
Ajude a Cecília a ter uma conversa natural. Interprete a mensagem do usuário
como resposta à última fala do assistente. Se a conversa for coleta de dados
(indicado por "Variáveis Faltando"), priorize extrair essas informações.
Se o usuário fizer pergunta explícita, priorize responder essa pergunta.

---
**EXEMPLO DE UM BOM TRABALHO:**

**Histórico:**
Assistente: Entendido, Gabriel. O Kumon é para você mesmo ou para outra pessoa?
**Mensagem Atual do Usuário:** 
"É para o meu filho João. A propósito, quais são os horários de funcionamento?"

**Seu Output JSON Ideal:**
{{
  "primary_intent": "qualification",
  "secondary_intent": "information",
  "entities": {{
    "beneficiary_type": "child",
    "student_name": "João"
  }},
  "confidence": 0.95
}}
---

**TAREFA ATUAL:**

**CONTEXTO DA CONVERSA:**
- Histórico (últimas 4 mensagens):
{conversation_history}
- Estado Atual da Qualificação (variáveis que ainda faltam): {missing_vars}

**MENSAGEM ATUAL DO USUÁRIO:**
"{text}"

**SEU RELATÓRIO JSON (retorne APENAS o objeto JSON, sem nenhum texto adicional ou markdown):**
"""

    def _parse_structured_response(self, response: str) -> dict:
        """Parse Gemini JSON response into structured dict with robust error handling."""
        try:
            # O modelo agora está configurado para retornar JSON, o parse deve ser direto
            parsed = json.loads(response)

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

            if not isinstance(result["entities"], dict):
                result["entities"] = {}

            result["confidence"] = max(0.0, min(1.0, result["confidence"]))

            return result

        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error(f"JSON parsing error: {e}. Response was: {response}")
            return {
                "primary_intent": "fallback",
                "secondary_intent": None,
                "entities": {},
                "confidence": 0.0,
            }

    def _format_conversation_history(self, context: Optional[dict]) -> str:
        """Format conversation history for prompt."""
        if not context:
            return "Nenhum histórico anterior (conversa iniciando)"

        history = context.get("history", [])
        if not history:
            return "Nenhum histórico anterior (conversa iniciando)"

        formatted_lines = []
        for entry in history[-4:]:  # Last 4 messages
            role = entry.get("role", "unknown").replace(
                "ai", "assistant"
            )  # Normaliza role
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

    def _get_missing_qualification_vars(self, context: Optional[dict]) -> str:
        """Get missing qualification variables for NLU prompt."""
        if not context:
            return "Nenhuma"

        state_data = context.get("state", {})

        qualification_vars = [
            "parent_name",
            "beneficiary_type",
            "student_name",
            "student_age",
            "program_interests",
        ]

        # Usa o `collected_data` dentro do state, que é a fonte da verdade
        collected_data = state_data.get("collected_data", {})
        missing = [var for var in qualification_vars if not collected_data.get(var)]

        return ", ".join(missing) if missing else "Nenhuma"


# Global instance
classifier = GeminiClassifier()
