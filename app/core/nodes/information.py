import logging
from typing import Any, Dict, List

from ...core.service_factory import get_langchain_rag_service  # FAQ Qdrant integration
from ..state.managers import StateManager
from ..state.models import (
    CeciliaState,
    ConversationStage,
    ConversationStep,
    get_collected_field,
    increment_metric,
    safe_update_state,
    set_collected_field,
)

logger = logging.getLogger(__name__)


class InformationNode:
    """
    Node de coleta de informações - INTEGRAÇÃO com FAQ Qdrant
    """

    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """
        🧠 INTELLIGENT INFORMATION NODE WITH FEW-SHOT LEARNING

        Clean architecture using only OpenAI with sophisticated blended responses:
        1. Load few-shot examples for consistent response style
        2. Determine next qualification question based on missing data
        3. Build sophisticated prompt combining information + qualification
        4. Generate contextual response with OpenAI
        """

        user_message = state["last_user_message"]
        logger.info(
            f"🧠 Processing information request with intelligent blending for {state['phone_number']}"
        )

        try:
            # Use sophisticated blended response generation
            answer = await self._execute_blended_response_with_few_shot(state)
            question_category = self._categorize_question(user_message)

            logger.info(
                f"✅ Intelligent response generated for {state['phone_number']}: {question_category}"
            )

        except Exception as e:
            logger.error(f"Intelligent response generation failed: {str(e)}")
            # Simple fallback
            answer = "Desculpe, estou com dificuldades técnicas. Por favor, entre em contato pelo telefone (51) 99692-1999."
            question_category = "fallback"

        # Process response (tracking via conversation_metrics)
        increment_metric(state, "message_count")

        # Track question category for analytics
        if not state["collected_data"].get("question_categories"):
            state["collected_data"]["question_categories"] = []
        state["collected_data"]["question_categories"].append(question_category)

        # Extract program interest if not already collected
        if not get_collected_field(state, "programs_of_interest"):
            program_interest = self._extract_program_interest(user_message)
            if program_interest:
                set_collected_field(state, "programs_of_interest", program_interest)

        # Check if should suggest scheduling
        should_suggest = self._should_suggest_scheduling(state)

        if should_suggest:
            # Check if can progress to scheduling (all data collected)
            scheduling_check = self._can_progress_to_scheduling(state)

            if scheduling_check["can_progress"]:
                # All data collected - can schedule
                response = (
                    f"{answer}\n\n"
                    "---\n\n"
                    "Vejo que você está interessado! Que tal agendar uma apresentação? 😊\n\n"
                    "Na nossa unidade você poderá:\n"
                    "• Ver os materiais na prática 📚\n"
                    "• Fazer uma avaliação diagnóstica gratuita 📝\n"
                    "• Conversar com nossa equipe pedagógica 👨‍🏫\n\n"
                    "Qual período prefere: **manhã** ou **tarde**? 🕐"
                )

                updates = {
                    "current_stage": ConversationStage.SCHEDULING,
                    "current_step": ConversationStep.DATE_PREFERENCE,
                }
            else:
                # Missing data - collect before scheduling
                missing_data_msg = self._get_missing_data_message(
                    scheduling_check["missing_fields"], state
                )

                response = f"{answer}\n\n---\n\n{missing_data_msg}"
                updates = {}
        else:
            # Continue gathering information
            follow_up = self._get_natural_follow_up(question_category, [])
            response = f"{answer}\n\n{follow_up}"
            updates = {}

        return self._create_response(state, response, updates)

    def _categorize_question_from_rag(self, user_message: str, rag_result) -> str:
        """Categoriza pergunta baseada no resultado RAG"""
        answer_lower = rag_result.answer.lower()

        # Inferir categoria baseada no conteúdo da resposta
        if any(word in answer_lower for word in ["matemática", "cálculo", "números"]):
            return "programa_matematica"
        elif any(word in answer_lower for word in ["português", "redação", "leitura"]):
            return "programa_portugues"
        elif any(word in answer_lower for word in ["inglês", "english"]):
            return "programa_ingles"
        elif any(word in answer_lower for word in ["material", "didático"]):
            return "material"
        elif any(word in answer_lower for word in ["preço", "valor", "investimento"]):
            return "preco"
        elif any(word in answer_lower for word in ["metodologia", "método"]):
            return "metodologia"
        else:
            return "geral"

    async def _get_specific_answer_fallback(
        self, user_message: str, state: CeciliaState
    ) -> str:
        """Respostas específicas como fallback quando RAG falha"""
        message_lower = user_message.lower()

        # Verificar se SmartRouter permite uso de templates
        routing_info = state.get("routing_info", {})
        threshold_action = routing_info.get("threshold_action", "fallback_level1")

        # BUSINESS CRITICAL: Updated pricing per PROJECT_SCOPE.md (R$ 375,00 + R$ 100,00)
        if any(
            word in message_lower
            for word in ["preço", "valor", "custa", "mensalidade", "investimento"]
        ):
            if threshold_action in ["proceed", "enhance_with_llm"]:
                try:
                    response = await prompt_manager.get_prompt(
                        name="kumon:information:pricing:complete_pricing",
                        variables={},
                        conversation_state=state,
                    )
                    logger.info(
                        f"✅ Using PromptManager for pricing_info (threshold_action={threshold_action})"
                    )
                    return response
                except Exception as e:
                    logger.warning(
                        f"⚠️ PromptManager failed for information:pricing, using fallback: {e}"
                    )
                    return self._get_hardcoded_pricing_info()
            else:
                logger.info(
                    f"⚡ Using hardcoded pricing (threshold_action={threshold_action})"
                )
                return self._get_hardcoded_pricing_info()

        # Adicionar outras respostas críticas conforme necessário
        return None

    async def _handle_unknown_question(
        self, state: CeciliaState, user_message: str
    ) -> Dict[str, Any]:
        """Trata perguntas que não conseguimos responder"""

        # Tentar extrair intenção de agendamento mesmo sem resposta específica
        if self._detect_booking_intent(user_message):
            response = (
                "Entendo sua pergunta! Para dar uma resposta completa e personalizada, "
                "que tal agendar uma conversa com nossa equipe? Eles poderão esclarecer "
                "todas as suas dúvidas com detalhes específicos! 📅\n\n"
                "Gostaria de agendar uma apresentação?"
            )
        else:
            # Marcar como falha e sugerir contato direto
            failed_attempts = state["conversation_metrics"]["failed_attempts"] + 1

            if failed_attempts >= 2:
                # BUSINESS CRITICAL: Update human handoff with contact (51) 99692-1999
                response = (
                    "Percebo que suas perguntas são bem específicas! 🤔\n\n"
                    "Para que você tenha todas as informações detalhadas que precisa, "
                    "recomendo falar diretamente com nossa equipe especializada da **Kumon Vila A**:\n\n"
                    "📞 **WhatsApp Direto**: **(51) 99692-1999**\n"
                    "🕐 **Horário de Atendimento**: Segunda a Sexta, 8h às 18h\n"
                    "📍 **Unidade**: Vila A - Porto Alegre/RS\n\n"
                    "Nossa equipe pedagógica poderá esclarecer tudo com muito mais detalhes e "
                    "agendar uma avaliação diagnóstica gratuita! ✨"
                )
            else:
                response = (
                    "Essa é uma ótima pergunta! 😊\n\n"
                    "Para dar uma resposta mais precisa, poderia reformular de uma forma diferente? "
                    "Ou se preferir, posso agendar uma conversa com nossa equipe para que você "
                    "tenha todas as informações detalhadas!"
                )

        updates = (
            {"failed_attempts": failed_attempts}
            if "failed_attempts" in locals()
            else {}
        )
        return self._create_response(state, response, updates)

    def _should_suggest_scheduling(self, state: CeciliaState) -> bool:
        """Determina se deve sugerir agendamento"""
        return state["conversation_metrics"][
            "message_count"
        ] >= 3 or self._is_engagement_question(  # 3+ mensagens
            state["last_user_message"]
        )

    def _extract_program_interest(self, user_message: str) -> List[str]:
        """Extrai interesse em programas da mensagem"""
        programs = []
        message_lower = user_message.lower()

        if any(
            word in message_lower
            for word in ["matemática", "matematica", "mat", "cálculo"]
        ):
            programs.append("Matemática")
        if any(
            word in message_lower
            for word in ["português", "portugues", "redação", "português"]
        ):
            programs.append("Português")
        if any(word in message_lower for word in ["inglês", "ingles", "english"]):
            programs.append("Inglês")

        return programs

    def _detect_booking_intent(self, user_message: str) -> bool:
        """Detecta intenção de agendamento"""
        booking_keywords = [
            "agendar",
            "marcar",
            "visita",
            "horário",
            "quando posso",
            "disponibilidade",
            "quero conhecer",
            "gostaria de ver",
        ]

        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in booking_keywords)

    def _is_engagement_question(self, user_message: str) -> bool:
        """Verifica se indica alto engajamento"""
        engagement_indicators = [
            "quando",
            "como começar",
            "matrícula",
            "inscrição",
            "interesse",
            "quero saber mais",
            "gostaria de",
            "preciso de",
            "como funciona na prática",
        ]

        message_lower = user_message.lower()
        return any(indicator in message_lower for indicator in engagement_indicators)

    def _get_natural_follow_up(
        self, answered_category: str, previous_answers: list
    ) -> str:
        """Gera follow-up natural baseado no contexto"""

        if (
            answered_category == "programa_matematica"
            and "preco" not in previous_answers
        ):
            return "Gostaria de saber sobre nossos valores de investimento? 💰"
        elif (
            answered_category == "programa_portugues"
            and "metodologia" not in previous_answers
        ):
            return "Quer entender melhor como nossa metodologia funciona na prática? 📖"
        elif answered_category == "preco" and "material" not in previous_answers:
            return "Quer conhecer nosso material didático exclusivo? 📚"
        else:
            return "Tem mais alguma dúvida específica? Ou gostaria de agendar uma visita para conhecer tudo na prática? 😊"

    def _categorize_question(self, user_message: str) -> str:
        """Categoriza pergunta para tracking"""
        message_lower = user_message.lower()

        if any(word in message_lower for word in ["matemática", "matematica"]):
            return "programa_matematica"
        elif any(word in message_lower for word in ["português", "portugues"]):
            return "programa_portugues"
        elif any(word in message_lower for word in ["inglês", "ingles"]):
            return "programa_ingles"
        elif any(word in message_lower for word in ["preço", "valor"]):
            return "preco"
        elif any(word in message_lower for word in ["material", "didático"]):
            return "material"
        else:
            return "geral"

    def _can_progress_to_scheduling(self, state: CeciliaState) -> Dict[str, Any]:
        """Verifica se pode progredir para agendamento - Legacy logic migrated"""
        required_fields = ["parent_name", "child_name", "student_age"]
        missing_fields = []

        collected_data = state["collected_data"]

        for field in required_fields:
            if not collected_data.get(field):
                missing_fields.append(field)

        return {
            "can_progress": len(missing_fields) == 0,
            "missing_fields": missing_fields,
        }

    def _get_missing_data_message(
        self, missing_fields: List[str], state: CeciliaState
    ) -> str:
        """Generate message for missing required data - Legacy logic migrated"""

        if "parent_name" in missing_fields:
            return (
                "Para personalizar melhor nosso atendimento, como posso chamá-lo(a)? 😊\n\n"
                "É para você mesmo ou para seu filho(a)?"
            )

        if "child_name" in missing_fields:
            return (
                "Perfeito! E qual é o nome do seu filho(a)? 👶\n\n"
                "Assim posso dar orientações mais específicas!"
            )

        if "student_age" in missing_fields:
            return (
                "Entendi! Quantos anos o(a) {child_name} tem? 🎂\n\n"
                "A idade ajuda a escolher o programa mais adequado!"
            ).format(child_name=get_collected_field(state, "child_name") or "estudante")

        # Default fallback
        return (
            "Para continuar, preciso de algumas informações básicas. "
            "Poderia me contar um pouco sobre o estudante? "
            "(nome, idade, série escolar) 📝"
        )

    def _create_response(
        self, state: CeciliaState, response: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria resposta padronizada"""
        updated_state = StateManager.update_state(state, updates)

        return {
            "response": response,
            "updated_state": updated_state,
            "stage": updated_state["current_stage"],
            "step": updated_state["current_step"],
            "intent": "information_gathering",
        }

    def _get_hardcoded_pricing_info(self) -> str:
        """Resposta hardcoded segura para informações de preço"""
        return (
            "💰 **Investimento Kumon Vila A:**\n\n"
            "• **Matemática ou Português**: R$ 375,00/mês por disciplina\n"
            "• **Inglês**: R$ 375,00/mês\n"
            "• **Taxa de matrícula**: R$ 100,00 (única vez)\n\n"
            "**Incluso em todos os planos:**\n"
            "• Material didático exclusivo Kumon 📚\n"
            "• Acompanhamento pedagógico personalizado 👨‍🏫\n"
            "• Relatórios de progresso detalhados 📊\n"
            "• 2 aulas semanais na unidade (Segunda a Sexta, 8h às 18h) 🕐\n\n"
            "🎓 **É um investimento no futuro do seu filho!**\n"
            "📅 Quer agendar uma apresentação gratuita?"
        )

    async def _execute_blended_response_with_few_shot(self, state: CeciliaState) -> str:
        """
        🧠 SOPHISTICATED BLENDED RESPONSE GENERATION

        This method implements the intelligent few-shot learning approach:
        1. Load few-shot examples for consistent response style
        2. Determine next qualification question based on missing data
        3. Build sophisticated prompt combining information + qualification
        4. Generate contextual response with OpenAI
        """
        try:
            # 1. Load few-shot examples for response style guidance
            from app.utils.prompt_utils import (
                format_few_shot_examples_for_prompt,
                load_few_shot_examples,
            )

            few_shot_examples = load_few_shot_examples()
            formatted_examples = format_few_shot_examples_for_prompt(few_shot_examples)

            # 2. Determine next qualification question based on missing variables
            next_qualification_question = self._get_next_qualification_question(state)

            # 3. Build sophisticated prompt with few-shot learning
            user_question = (
                state.get("last_user_message", "")
                if isinstance(state, dict)
                else state.last_user_message
            )
            collected_data = (
                state.get("collected_data", {})
                if isinstance(state, dict)
                else state.collected_data
            )

            # Create the sophisticated prompt template
            system_prompt = f"""Você é Cecília, uma assistente virtual prestativa e eficiente do Kumon Vila A.

Sua tarefa é gerar uma resposta combinada: primeiro responda à dúvida do usuário e depois, se aplicável, continue o processo de qualificação com a próxima pergunta. Siga o estilo dos exemplos abaixo.

---
**EXEMPLOS DE RESPOSTAS IDEAIS:**
{formatted_examples}
---

**INFORMAÇÕES KUMON VILA A:**
- Método individualizado de ensino que respeita o ritmo de cada aluno
- Programas: Matemática e Português (individual R$ 375,00/mês, combinado R$ 750,00/mês)
- Taxa de matrícula: R$ 100,00 (única vez)
- Idade: A partir de 3 anos
- Horários: Segunda a Sexta, 8h às 18h
- Endereço: Vila A - Porto Alegre/RS
- Telefone: (51) 99692-1999

**CONTEXTO DA CONVERSA:**
- Responsável: {collected_data.get('parent_name', 'Não informado')}
- Beneficiário: {collected_data.get('beneficiary_type', 'Não informado')}
- Nome do aluno: {collected_data.get('child_name', 'Não informado')}
- Idade do aluno: {collected_data.get('student_age', 'Não informado')}
- Interesses: {collected_data.get('programs_of_interest', 'Não informado')}

**TAREFA ATUAL:**

**DÚVIDA DO USUÁRIO:**
"{user_question}"

**PRÓXIMA PERGUNTA PARA QUALIFICAÇÃO (se houver):**
"{next_qualification_question if next_qualification_question else 'Nenhuma - qualificação completa'}"

**SUA RESPOSTA COMBINADA E NATURAL:**"""

            user_prompt = user_question

            # 4. Generate response with OpenAI
            from app.core.llm.openai_adapter import OpenAIClient

            openai_client = OpenAIClient()
            reply_text = await openai_client.chat(
                model="gpt-3.5-turbo",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=500,  # Increased for blended responses
            )

            return reply_text

        except Exception as e:
            logger.error(f"Blended response generation error: {str(e)}")
            # Fallback to hardcoded response
            return "Desculpe, estou com dificuldades técnicas. Por favor, entre em contato pelo telefone (51) 99692-1999."

    def _get_next_qualification_question(self, state: CeciliaState) -> str:
        """
        🎯 INTELLIGENT QUALIFICATION SEQUENCING

        Determine the next qualification question based on missing data.
        """
        # Required qualification variables that must be collected
        QUALIFICATION_REQUIRED_VARS = [
            "parent_name",
            "child_name",
            "student_age",
            "programs_of_interest",
        ]

        # Check which qualification variables are missing
        collected_data = (
            state.get("collected_data", {})
            if isinstance(state, dict)
            else state.collected_data
        )
        missing_vars = []
        for var in QUALIFICATION_REQUIRED_VARS:
            if not collected_data.get(var):
                missing_vars.append(var)

        # If no variables missing, no qualification question needed
        if not missing_vars:
            return ""

        # Get first missing variable and generate appropriate question
        first_missing = missing_vars[0]
        parent_name = collected_data.get("parent_name", "")

        # Personalize with parent name if available
        name_prefix = f"{parent_name}, " if parent_name else ""

        if first_missing == "parent_name":
            return "Para personalizar melhor nosso atendimento, como posso chamá-lo(a)?"
        elif first_missing == "child_name":
            return f"{name_prefix}qual é o nome da criança para quem será o curso?"
        elif first_missing == "student_age":
            child_name = collected_data.get("child_name", "")
            if child_name:
                return f"{name_prefix}qual é a idade do(a) {child_name}?"
            else:
                return f"{name_prefix}qual é a idade da criança?"
        elif first_missing == "programs_of_interest":
            return f"{name_prefix}você tem interesse em algum programa específico? Matemática, Português ou ambos?"

        return ""

    def _get_business_updates_for_information(
        self, state: CeciliaState
    ) -> Dict[str, Any]:
        """
        Aplica apenas updates de negócio para information gathering.
        Não gera resposta - apenas atualiza collected_data, stage/step, métricas.
        """
        user_message = state.get("last_user_message", "")

        # Increment message count for metrics
        from ..state.models import increment_metric

        increment_metric(state, "message_count")

        # Extract program interest if not already collected
        if not get_collected_field(state, "programs_of_interest"):
            program_interest = self._extract_program_interest(user_message)
            if program_interest:
                set_collected_field(state, "programs_of_interest", program_interest)

        # Track question category for analytics
        question_category = self._categorize_question(user_message)
        if not state.get("collected_data", {}).get("question_categories"):
            state.setdefault("collected_data", {})["question_categories"] = []
        state["collected_data"]["question_categories"].append(question_category)

        # Check if should suggest scheduling
        should_suggest = self._should_suggest_scheduling(state)

        if should_suggest:
            scheduling_check = self._can_progress_to_scheduling(state)

            if scheduling_check["can_progress"]:
                # Can progress to scheduling - return only business updates (no response)
                return {
                    "current_stage": ConversationStage.SCHEDULING,
                    "current_step": ConversationStep.DATE_PREFERENCE,
                }
            else:
                # Need more data - stay in information gathering, return only business updates
                return {
                    "current_stage": ConversationStage.INFORMATION_GATHERING,
                    "current_step": ConversationStep.INFORMATION_GATHERING,
                }
        else:
            # Continue with information gathering - return only business updates
            return {
                "current_stage": ConversationStage.INFORMATION_GATHERING,
                "current_step": ConversationStep.INFORMATION_GATHERING,
            }


# Entry point para LangGraph
async def information_node(state: CeciliaState) -> CeciliaState:
    """Entry point para LangGraph com integração FAQ Qdrant"""
    node = InformationNode()
    result = await node(state)

    # CRITICAL FIX: Use safe_update_state to preserve CeciliaState structure
    safe_update_state(state, result["updated_state"])
    state["last_bot_response"] = result["response"]

    return state
