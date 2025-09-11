"""
Comprehensive NLU (Natural Language Understanding) engine using Gemini Flash.
Returns structured output with primary/secondary intents and extracted entities.
"""
import os

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

    def classify(self, text: str, context: dict = None):
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
            # Simple fallback classification for testing with context support
            print(f"GeminiClassifier fallback mode: text='{text}', context={context}")
            result = self._simple_classify_structured(text, context)
            print(f"GeminiClassifier result: {result}")
            return result

        # Build structured NLU prompt
        if context:
            prompt = self._build_structured_nlu_prompt(text, context)
        else:
            prompt = self._build_basic_nlu_prompt(text)

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

    def _simple_classify_structured(self, text: str, context: dict = None) -> dict:
        """Intelligent contextual classification with enhanced entity extraction."""
        text_lower = text.lower()

        # Enhanced entity extraction with context awareness
        entities = self._extract_entities_contextual(text, context)

        # Check if we need to merge with context entities
        if context and "state" in context:
            state_data = context["state"]
            # Don't override entities already extracted from current message
            for key in [
                "parent_name",
                "student_name",
                "student_age",
                "beneficiary_type",
                "program_interests",
            ]:
                if key not in entities and key in state_data and state_data[key]:
                    entities[key] = state_data[key]

        # Check for multi-intent patterns first
        has_qualification_answer = any(
            pattern in text_lower
            for pattern in ["meu filho", "minha filha", "para o", "para a", "para mim"]
        )

        has_info_question = any(
            pattern in text_lower
            for pattern in [
                "horário",
                "funciona",
                "método",
                "valores",
                "preços",
                "como",
            ]
        )

        # Multi-intent detection: qualification answer + info question
        if has_qualification_answer and has_info_question:
            return {
                "primary_intent": "qualification",
                "secondary_intent": "information",
                "entities": entities,
                "confidence": 0.85,
            }

        # Single intent classification
        if any(word in text_lower for word in ["oi", "olá", "bom dia", "boa tarde"]):
            return {
                "primary_intent": "greeting",
                "secondary_intent": None,
                "entities": entities,
                "confidence": 0.9,
            }
        elif (
            any(word in text_lower for word in ["matricular", "matrícula", "inscrever"])
            or has_qualification_answer
        ):
            return {
                "primary_intent": "qualification",
                "secondary_intent": None,
                "entities": entities,
                "confidence": 0.85,
            }
        elif any(word in text_lower for word in ["método", "funciona", "kumon"]):
            return {
                "primary_intent": "information",
                "secondary_intent": None,
                "entities": entities,
                "confidence": 0.8,
            }
        elif any(word in text_lower for word in ["agendar", "visita", "horário"]):
            return {
                "primary_intent": "scheduling",
                "secondary_intent": None,
                "entities": entities,
                "confidence": 0.85,
            }
        else:
            return {
                "primary_intent": "fallback",
                "secondary_intent": None,
                "entities": entities,
                "confidence": 0.5,
            }

    def _extract_entities_contextual(self, text: str, context: dict = None) -> dict:
        """
        🧠 INTELIGÊNCIA CONTEXTUAL: Extract entities based on conversation context.

        Esta é a inteligência principal do novo sistema - usa o contexto da conversa
        para extrair entidades de forma muito mais precisa que regex simples.
        """
        import re

        text_lower = text.lower().strip()
        entities = {}

        # Get missing variables from context to know what to extract
        missing_vars = []
        if context and "state" in context:
            state_data = context["state"]
            qualification_vars = [
                "parent_name",
                "student_name",
                "student_age",
                "beneficiary_type",
                "program_interests",
            ]
            missing_vars = [
                var for var in qualification_vars if not state_data.get(var)
            ]

        print(
            f"_extract_entities_contextual: text='{text}', missing_vars={missing_vars}"
        )

        # 🎯 CONTEXTO: Se esperamos parent_name e recebemos um nome isolado
        if "parent_name" in missing_vars:
            # Padrões para nome do responsável
            parent_patterns = [
                r"(?:meu nome é|me chamo|sou)\s+([A-ZÀ-Ÿ][a-záêçõàâéíóúô\s]+)",
                r"^([A-ZÀ-Ÿ][a-záêçõàâéíóúô]+(?:\s+[A-ZÀ-Ÿ][a-záêçõàâéíóúô]+)?)$",  # Nome isolado
            ]

            for pattern in parent_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    # Filtro de palavras comuns que não são nomes
                    blacklist = {
                        "olá",
                        "ola",
                        "oi",
                        "bom",
                        "dia",
                        "tarde",
                        "noite",
                        "sim",
                        "não",
                        "obrigado",
                        "obrigada",
                        "por",
                        "favor",
                        "gostaria",
                        "quero",
                        "preciso",
                        "meu",
                        "minha",
                        "para",
                        "nome",
                        "sou",
                        "chamo",
                        "ele",
                        "ela",
                    }
                    if name.lower() not in blacklist and len(name) > 2:
                        entities["parent_name"] = name
                        break

        # 🎯 CONTEXTO: Se esperamos beneficiary_type após coletar parent_name
        if "beneficiary_type" in missing_vars and "parent_name" not in missing_vars:
            if any(
                word in text_lower
                for word in ["para mim", "para eu", "é para mim", "pra mim", "eu mesmo"]
            ):
                entities["beneficiary_type"] = "self"
            elif any(
                word in text_lower
                for word in [
                    "para meu",
                    "para minha",
                    "meu filho",
                    "minha filha",
                    "filho",
                    "filha",
                    "criança",
                    "para outra pessoa",
                ]
            ):
                entities["beneficiary_type"] = "child"

        # 🎯 CONTEXTO: Se esperamos student_name após definir beneficiary_type=child
        if (
            "student_name" in missing_vars
            and context
            and context.get("state", {}).get("beneficiary_type") == "child"
        ):
            # Padrões para nome do estudante
            student_patterns = [
                r"(?:nome dele é|nome dela é|se chama|chama)\s+([A-ZÀ-Ÿ][a-záêçõàâéíóúô]+)",
                r"(?:é o|é a)\s+([A-ZÀ-Ÿ][a-záêçõàâéíóúô]+)",
                r"^([A-ZÀ-Ÿ][a-záêçõàâéíóúô]+)$",  # Nome isolado quando perguntado especificamente
            ]

            for pattern in student_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    # Mesmo blacklist do parent_name
                    blacklist = {
                        "nome",
                        "ele",
                        "ela",
                        "filho",
                        "filha",
                        "criança",
                        "tem",
                        "anos",
                        "olá",
                        "ola",
                        "oi",
                        "sim",
                        "não",
                    }
                    if name.lower() not in blacklist and len(name) > 2:
                        entities["student_name"] = name
                        break

        # 🎯 CONTEXTO: Se esperamos student_age após coletar student_name
        if "student_age" in missing_vars:
            age_patterns = [
                r"(?:tem|idade|anos?)\s+(\d{1,2})\s*anos?",
                r"(\d{1,2})\s*anos?",
                r"^(\d{1,2})$",  # Apenas número quando perguntado especificamente
            ]

            for pattern in age_patterns:
                match = re.search(pattern, text)
                if match:
                    age = int(match.group(1))
                    if 2 <= age <= 25:  # Faixa etária válida para Kumon
                        entities["student_age"] = age
                        break

        # 🎯 CONTEXTO: Se esperamos program_interests após coletar informações básicas
        if "program_interests" in missing_vars:
            interests = []
            if any(
                word in text_lower
                for word in ["matemática", "matematica", "math", "números", "cálculo"]
            ):
                interests.append("Matemática")
            if any(
                word in text_lower
                for word in ["português", "portugues", "redação", "leitura", "escrita"]
            ):
                interests.append("Português")
            if any(
                word in text_lower for word in ["inglês", "ingles", "english", "idioma"]
            ):
                interests.append("Inglês")

            if interests:
                entities["program_interests"] = interests

        return entities

    # Legacy _simple_classify() method removed - all code now uses structured format

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

    def _build_structured_nlu_prompt(self, text: str, context: dict) -> str:
        """Build sophisticated NLU prompt for structured analysis."""
        # Extract context information
        conversation_history = self._format_conversation_history(context)
        missing_vars = self._get_missing_qualification_vars(context)

        # Build the sophisticated NLU prompt
        prompt = f"""Você é um motor de NLU (Natural Language Understanding) para um
chbot de atendimento do Kumon. Sua tarefa é analisar a mensagem do usuário
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
        return prompt

    def _build_basic_nlu_prompt(self, text: str) -> str:
        """Build basic NLU prompt without context."""
        prompt = f"""Você é um motor de NLU para um chatbot do Kumon.
Analise a mensagem e retorne um objeto JSON.

**MENSAGEM DO USUÁRIO:**
"{text}"

**ANÁLISE REQUERIDA:**
1. **primary_intent:** greeting, qualification, information, scheduling, ou fallback
2. **entities:** Extraia nomes, idades, tipo de beneficiário se presentes
3. **confidence:** Confiança na classificação (0.0 a 1.0)

**OUTPUT (APENAS JSON):**
{{
  "primary_intent": "string",
  "secondary_intent": null,
  "entities": {{}},
  "confidence": 0.0
}}"""
        return prompt

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

        # Support both old format (direct) and new format (nested)
        if "state" in context:
            # New format: {'state': {...}, 'history': [...]}
            greeting_sent = context.get("state", {}).get("greeting_sent", False)
        else:
            # Old format: greeting_sent directly in context
            greeting_sent = context.get("greeting_sent", False)

        # Fill template
        return template.format(
            conversation_history=conversation_history,
            collected_vars=collected_vars,
            missing_vars=missing_vars,
            greeting_sent=greeting_sent,
            user_message=text,
        )

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

    def _format_qualification_state(self, context: dict) -> tuple[str, str]:
        """Format current qualification state for prompt."""
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

        collected = []
        missing = []

        for var in qualification_vars:
            value = state_data.get(var)
            if value:
                # Include both variable name and value for better context
                collected.append(f"{var}={value}")
            else:
                missing.append(var)

        collected_str = ", ".join(collected) if collected else "Nenhuma"
        missing_str = ", ".join(missing) if missing else "Nenhuma"

        return collected_str, missing_str

    def _get_missing_qualification_vars(self, context: dict) -> str:
        """Get missing qualification variables for NLU prompt."""
        collected_str, missing_str = self._format_qualification_state(context)
        return missing_str


# Global instance
classifier = GeminiClassifier()
