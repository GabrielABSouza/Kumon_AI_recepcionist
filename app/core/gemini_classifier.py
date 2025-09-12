"""
Comprehensive NLU (Natural Language Understanding) engine using Gemini Flash.
Returns structured output with primary/secondary intents and extracted entities.
"""
import os
from typing import Optional
import json
import re
import logging

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
        print(f"DEBUG|gemini_classifier|classify_called|text='{text}'|enabled={self.enabled}")
        
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
            print(f"DEBUG|gemini_classifier|parsed_result|intent={structured_result.get('primary_intent')}")
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
        """Build unified NLU prompt with optional context."""
        
        conversation_history = self._format_conversation_history(context)
        missing_vars = self._get_missing_qualification_vars(context)

        # 🚀 CORREÇÃO PRINCIPAL: Adicionando Regras Imperativas ao Prompt
        return f"""Você é um motor de NLU (Natural Language Understanding) para um chatbot de atendimento do Kumon. Sua tarefa é analisar a mensagem do usuário dentro do contexto da conversa e retornar um objeto JSON estruturado.

**REGRAS DE PRIORIDADE MÁXIMA (SIGA-AS RIGOROSAMENTE):**
1.  **SE** o histórico mostrar que a última pergunta do assistente foi "Qual é o seu nome?" E a mensagem atual do usuário for um nome, a `primary_intent` **DEVE SER** `qualification` e você **DEVE** extrair o nome como `parent_name`.
2.  **SE** o estado atual indicar que uma qualificação está em andamento (variáveis faltando) E a mensagem do usuário parecer uma resposta a uma pergunta anterior, a `primary_intent` **DEVE SER** `qualification`.
3.  **SE** a mensagem do usuário contiver uma pergunta explícita sobre "horários", "preço", "agendar", ou "informações", a `primary_intent` **DEVE SER** `information` ou `scheduling`, mesmo que uma qualificação esteja em andamento.

**CONTEXTO DA CONVERSA:**
- Histórico (últimas 4 mensagens):
{conversation_history}
- Estado Atual da Qualificação (variáveis que ainda faltam): {missing_vars}

**MENSAGEM ATUAL DO USUÁRIO:**
"{text}"

**TAREFAS DE ANÁLISE (siga as regras de prioridade acima):**
1.  **primary_intent:** Determine a intenção principal.
2.  **secondary_intent:** Se a mensagem contiver um pedido secundário (ex: responder E fazer uma nova pergunta), identifique-o aqui. Caso contrário, retorne null.
3.  **entities:** Extraia as seguintes entidades do texto, se presentes:
   - parent_name (string)
   - beneficiary_type (string, valores possíveis: 'self' ou 'child')
   - student_name (string)
   - student_age (integer)
   - program_interests (list[string])
4.  **confidence:** Sua confiança na classificação da intenção primária (de 0.0 a 1.0).

**OUTPUT (retorne APENAS o objeto JSON, sem nenhum texto adicional ou markdown):**
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
            role = entry.get("role", "unknown").replace("ai", "assistant") # Normaliza role
            content = entry.get("content", "")

            if role == "assistant":
                formatted_lines.append(f"Assistente: {content}")
            elif role == "user":
                formatted_lines.append(f"Usuário: {content}")

        return "\n".join(formatted_lines) if formatted_lines else "Nenhum histórico disponível"

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