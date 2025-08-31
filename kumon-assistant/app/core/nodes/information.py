from typing import Dict, Any, List
import time
from ..state.models import CeciliaState, ConversationStage, ConversationStep, get_collected_field, set_collected_field, increment_metric
from ..state.managers import StateManager
from ...core.service_factory import get_langchain_rag_service  # FAQ Qdrant integration
from ...services.intent_first_router import intent_first_router, IntentCategory
import logging

logger = logging.getLogger(__name__)

class InformationNode:
    """
    Node de coleta de informações - INTEGRAÇÃO com FAQ Qdrant
    """
    
    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """
        Processa perguntas usando INTENT-FIRST ROUTING para performance otimizada
        
        NEW ARCHITECTURE (Wave 2):
        1. INTENT-FIRST: Fast template matching (<100ms)
        2. RAG FALLBACK: Complex queries only when templates don't match
        3. PERFORMANCE TARGET: 80% queries answered in <1s, 70% reduction in RAG calls
        """
        
        # NEW ARCHITECTURE: Check if response is pre-planned by ResponsePlanner
        if state.get("planned_response"):
            response = state["planned_response"]
            # Clear planned_response to avoid reuse
            del state["planned_response"]
            
            # Apply business logic updates only (no response generation)
            updates = self._get_business_updates_for_information(state)
            
            logger.info(f"✅ Using pre-planned response for information (ResponsePlanner)")
            return self._create_response(state, response, updates)
        
        # LEGACY PATH: Original logic (will be removed in Fase 2)
        logger.info(f"⚠️ Using legacy information logic (planned_response not found)")
        
        user_message = state["last_user_message"]
        start_time = time.time()
        
        # Tracking é agora gerenciado pelo StateManager via metrics
        # info_gathering_count será incrementado via conversation_metrics
        
        # ========== WAVE 2: INTENT-FIRST ROUTING ==========
        try:
            # 1. INTENT-FIRST CLASSIFICATION (target: <50ms)
            context = self._extract_context_for_router(state)
            route_result = await intent_first_router.route_message(
                message=user_message,
                context=context,
                phone_number=state["phone_number"]
            )
            
            # 2. TEMPLATE MATCH FOUND - Use hardcoded response (target: <100ms total)
            if route_result.matched:
                template_time_ms = (time.time() - start_time) * 1000
                
                logger.info(
                    f"Template response delivered in {template_time_ms:.0f}ms",
                    extra={
                        "phone_number": state["phone_number"],
                        "template_id": route_result.template_id,
                        "intent_category": route_result.intent_category.value,
                        "confidence": route_result.confidence,
                        "performance_target_met": template_time_ms < 100
                    }
                )
                
                return self._create_template_response(
                    state, 
                    route_result.response, 
                    route_result.context_updates,
                    route_result.template_id
                )
            
            # 3. NO TEMPLATE MATCH - Fallback to RAG (complex queries)
            logger.debug(
                f"No template match - falling back to RAG for complex query",
                extra={
                    "phone_number": state["phone_number"], 
                    "processing_time_ms": route_result.processing_time_ms
                }
            )
            
        except Exception as template_error:
            logger.error(
                f"Intent routing failed, falling back to RAG: {template_error}",
                extra={"phone_number": state["phone_number"]},
                exc_info=True
            )
        
        # ========== RAG FALLBACK (only for unmatched or error cases) ==========
        try:
            # Consultar FAQ vetorizada apenas para queries complexas
            langchain_rag_service = await get_langchain_rag_service()
            rag_result = await langchain_rag_service.query(
                question=user_message,
                search_kwargs={
                    "score_threshold": 0.3,  # Threshold mais baixo para melhor cobertura
                    "k": 3  # Top 3 resultados mais relevantes
                },
                include_sources=False
            )
            
            # 2. Verificar qualidade da resposta RAG
            if rag_result.answer and len(rag_result.answer) > 50:
                # Resposta RAG de qualidade encontrada
                answer = rag_result.answer
                question_category = self._categorize_question_from_rag(user_message, rag_result)
                
                logger.info(f"FAQ answer found for {state['phone_number']}: {question_category}")
                
            else:
                # Fallback para respostas específicas hardcoded
                answer = await self._get_specific_answer_fallback(user_message, state)
                question_category = self._categorize_question(user_message)
                
                if not answer:
                    # Nem RAG nem fallback funcionaram
                    logger.warning(f"No answer found for question: {user_message}")
                    return await self._handle_unknown_question(state, user_message)
        
        except Exception as e:
            logger.error(f"RAG query error: {str(e)}")
            # Fallback para respostas hardcoded em caso de erro RAG
            answer = await self._get_specific_answer_fallback(user_message, state)
            question_category = self._categorize_question(user_message)
            
            if not answer:
                return await self._handle_unknown_question(state, user_message)
        
        # 3. Processar resposta encontrada (tracking via conversation_metrics)
        increment_metric(state, "message_count")
        
        # Track question category for analytics
        if not state["collected_data"].get("question_categories"):
            state["collected_data"]["question_categories"] = []
        state["collected_data"]["question_categories"].append(question_category)
        
        # 4. Verificar se deve coletar disciplina de interesse
        if not get_collected_field(state, "programs_of_interest"):
            program_interest = self._extract_program_interest(user_message)
            if program_interest:
                set_collected_field(state, "programs_of_interest", program_interest)
        
        # 5. Verificar se deve sugerir agendamento ou continuar informações
        should_suggest = self._should_suggest_scheduling(state)
        
        if should_suggest:
            # Verificar se pode agendar (todos os dados coletados)
            scheduling_check = self._can_progress_to_scheduling(state)
            
            if scheduling_check["can_progress"]:
                # Todos os dados coletados - pode agendar
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
                    "current_step": ConversationStep.DATE_PREFERENCE
                }
            else:
                # Dados faltando - coletar antes de agendar
                missing_data_msg = self._get_missing_data_message(
                    scheduling_check["missing_fields"], 
                    state
                )
                
                response = f"{answer}\n\n---\n\n{missing_data_msg}"
                updates = {}
        else:
            # Continuar coletando informações
            follow_up = self._get_natural_follow_up(question_category, [])
            response = f"{answer}\n\n{follow_up}"
            updates = {}
        
        return self._create_response(state, response, updates)
    
    def _extract_context_for_router(self, state: CeciliaState) -> Dict[str, Any]:
        """Extract context from CeciliaState for IntentFirstRouter personalization"""
        collected_data = state.get("collected_data", {})
        
        return {
            "parent_name": collected_data.get("parent_name", ""),
            "child_name": collected_data.get("child_name", ""),
            "student_age": collected_data.get("student_age"),
            "programs_of_interest": collected_data.get("programs_of_interest", []),
            "phone_number": state.get("phone_number", ""),
            "conversation_stage": state.get("current_stage"),
            "message_count": state.get("conversation_metrics", {}).get("message_count", 0),
            "previous_templates": collected_data.get("previous_templates", [])
        }
    
    def _create_template_response(
        self, 
        state: CeciliaState, 
        response: str, 
        context_updates: Dict[str, Any],
        template_id: str
    ) -> Dict[str, Any]:
        """Create response for template matches with performance optimizations"""
        
        # Track template usage in collected_data
        if not state["collected_data"].get("template_usage_history"):
            state["collected_data"]["template_usage_history"] = []
        
        state["collected_data"]["template_usage_history"].append({
            "template_id": template_id,
            "timestamp": time.time(),
            "message": state["last_user_message"]
        })
        
        # Apply context updates from template router
        for key, value in context_updates.items():
            if key.startswith("showed_") or key.startswith("handled_") or key == "last_template_used":
                state["collected_data"][key] = value
        
        # Increment message count for metrics
        increment_metric(state, "message_count")
        
        # Determine if should suggest scheduling after template response
        should_suggest = self._should_suggest_scheduling_after_template(state, template_id)
        
        if should_suggest:
            # Add scheduling suggestion to template response
            scheduling_suggestion = self._get_scheduling_suggestion(state, template_id)
            if scheduling_suggestion:
                response = f"{response}\n\n---\n\n{scheduling_suggestion}"
                
                # Check if can progress directly to scheduling
                scheduling_check = self._can_progress_to_scheduling(state)
                if scheduling_check["can_progress"]:
                    updates = {
                        "current_stage": ConversationStage.SCHEDULING,
                        "current_step": ConversationStep.DATE_PREFERENCE
                    }
                else:
                    updates = {}
            else:
                updates = {}
        else:
            updates = {}
        
        return self._create_response(state, response, updates)
    
    def _should_suggest_scheduling_after_template(self, state: CeciliaState, template_id: str) -> bool:
        """Determine if should suggest scheduling after specific template responses"""
        
        # Business critical templates that often lead to scheduling
        scheduling_trigger_templates = [
            "pricing", "contact", "methodology", "benefits", "availability"
        ]
        
        message_count = state.get("conversation_metrics", {}).get("message_count", 0)
        template_history = state.get("collected_data", {}).get("template_usage_history", [])
        
        # Suggest scheduling if:
        # 1. High engagement templates (pricing, methodology, benefits)
        # 2. Multiple templates used (user is engaged)
        # 3. 3+ messages exchanged
        
        return (
            template_id in scheduling_trigger_templates or
            len(template_history) >= 2 or
            message_count >= 3
        )
    
    def _get_scheduling_suggestion(self, state: CeciliaState, template_id: str) -> str:
        """Get context-appropriate scheduling suggestion based on template used"""
        
        parent_name = state.get("collected_data", {}).get("parent_name", "")
        name_prefix = f"{parent_name}, " if parent_name else ""
        
        if template_id == "pricing":
            return (
                f"{name_prefix}vejo que você está interessado no investimento! 💰\n\n"
                "Que tal conhecer nossa unidade na prática? Na apresentação você poderá:\n"
                "• Ver os materiais didáticos exclusivos 📚\n"
                "• Fazer uma avaliação diagnóstica gratuita 📝\n"
                "• Conversar com nossa equipe pedagógica 👨‍🏫\n\n"
                "Gostaria de agendar uma visita? Qual período prefere: **manhã** ou **tarde**? 🕐"
            )
        
        elif template_id == "methodology" or template_id == "benefits":
            return (
                f"{name_prefix}que bom saber do seu interesse na metodologia Kumon! 📚\n\n"
                "Para ver como funciona na prática e fazer uma avaliação personalizada, "
                "que tal agendar uma apresentação gratuita?\n\n"
                "Qual período é melhor para você: **manhã** ou **tarde**? 🕐"
            )
        
        elif template_id == "contact" or template_id == "hours":
            return (
                f"{name_prefix}se preferir, posso agendar uma conversa presencial! 😊\n\n"
                "Nossa equipe pode esclarecer todas as dúvidas com muito mais detalhes. "
                "Gostaria de agendar uma apresentação?"
            )
        
        else:
            # Generic scheduling suggestion
            return (
                f"{name_prefix}vejo que você está interessado! 😊\n\n"
                "Que tal conhecer nossa unidade pessoalmente? "
                "Posso agendar uma apresentação gratuita para você. "
                "Qual período prefere: **manhã** ou **tarde**? 🕐"
            )
    
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
    
    async def _get_specific_answer_fallback(self, user_message: str, state: CeciliaState) -> str:
        """Respostas específicas como fallback quando RAG falha"""
        message_lower = user_message.lower()
        
        # Verificar se SmartRouter permite uso de templates
        routing_info = state.get("routing_info", {})
        threshold_action = routing_info.get("threshold_action", "fallback_level1")
        
        # BUSINESS CRITICAL: Updated pricing per PROJECT_SCOPE.md (R$ 375,00 + R$ 100,00)
        if any(word in message_lower for word in ["preço", "valor", "custa", "mensalidade", "investimento"]):
            if threshold_action in ["proceed", "enhance_with_llm"]:
                try:
                    response = await prompt_manager.get_prompt(
                        name="kumon:information:pricing:complete_pricing",
                        variables={},
                        conversation_state=state
                    )
                    logger.info(f"✅ Using PromptManager for pricing_info (threshold_action={threshold_action})")
                    return response
                except Exception as e:
                    logger.warning(f"⚠️ PromptManager failed for information:pricing, using fallback: {e}")
                    return self._get_hardcoded_pricing_info()
            else:
                logger.info(f"⚡ Using hardcoded pricing (threshold_action={threshold_action})")
                return self._get_hardcoded_pricing_info()
        
        # Adicionar outras respostas críticas conforme necessário
        return None
    
    async def _handle_unknown_question(self, state: CeciliaState, user_message: str) -> Dict[str, Any]:
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
        
        updates = {"failed_attempts": failed_attempts} if 'failed_attempts' in locals() else {}
        return self._create_response(state, response, updates)
    
    def _should_suggest_scheduling(self, state: CeciliaState) -> bool:
        """Determina se deve sugerir agendamento"""
        return (
            state["conversation_metrics"]["message_count"] >= 3 or     # 3+ mensagens
            self._is_engagement_question(state["last_user_message"])
        )
    
    def _extract_program_interest(self, user_message: str) -> List[str]:
        """Extrai interesse em programas da mensagem"""
        programs = []
        message_lower = user_message.lower()
        
        if any(word in message_lower for word in ['matemática', 'matematica', 'mat', 'cálculo']):
            programs.append('Matemática')
        if any(word in message_lower for word in ['português', 'portugues', 'redação', 'português']):
            programs.append('Português')
        if any(word in message_lower for word in ['inglês', 'ingles', 'english']):
            programs.append('Inglês')
        
        return programs
    
    def _detect_booking_intent(self, user_message: str) -> bool:
        """Detecta intenção de agendamento"""
        booking_keywords = [
            "agendar", "marcar", "visita", "horário", "quando posso",
            "disponibilidade", "quero conhecer", "gostaria de ver"
        ]
        
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in booking_keywords)
    
    def _is_engagement_question(self, user_message: str) -> bool:
        """Verifica se indica alto engajamento"""
        engagement_indicators = [
            "quando", "como começar", "matrícula", "inscrição", "interesse",
            "quero saber mais", "gostaria de", "preciso de", "como funciona na prática"
        ]
        
        message_lower = user_message.lower()
        return any(indicator in message_lower for indicator in engagement_indicators)
    
    def _get_natural_follow_up(self, answered_category: str, previous_answers: list) -> str:
        """Gera follow-up natural baseado no contexto"""
        
        if answered_category == "programa_matematica" and "preco" not in previous_answers:
            return "Gostaria de saber sobre nossos valores de investimento? 💰"
        elif answered_category == "programa_portugues" and "metodologia" not in previous_answers:
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
            "missing_fields": missing_fields
        }
    
    def _get_missing_data_message(self, missing_fields: List[str], state: CeciliaState) -> str:
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
            ).format(
                child_name=get_collected_field(state, "child_name") or "estudante"
            )
        
        # Default fallback
        return (
            "Para continuar, preciso de algumas informações básicas. "
            "Poderia me contar um pouco sobre o estudante? "
            "(nome, idade, série escolar) 📝"
        )
    
    def _create_response(self, state: CeciliaState, response: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Cria resposta padronizada"""
        updated_state = StateManager.update_state(state, updates)
        
        return {
            "response": response,
            "updated_state": updated_state,
            "stage": updated_state["current_stage"],
            "step": updated_state["current_step"],
            "intent": "information_gathering"
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
    
    def _get_business_updates_for_information(self, state: CeciliaState) -> Dict[str, Any]:
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
                # Can progress to scheduling
                return {
                    "current_stage": ConversationStage.SCHEDULING,
                    "current_step": ConversationStep.DATE_PREFERENCE
                }
            else:
                # Need more data - stay in information gathering
                response = "Entendo! Me conte mais sobre o que você gostaria de saber sobre o Kumon. 🤔"
                return self._create_response(state, response, {})
        else:
            # Continue with information gathering
            response = "Que bom saber mais sobre seu interesse no Kumon! Como posso te ajudar com mais informações? 😊"
            return self._create_response(state, response, {})
        
        # Fallback - should not reach here but ensure we always have a response
        logger.warning("Information node reached unexpected fallback")
        response = "Estou aqui para te ajudar com informações sobre o Kumon. O que você gostaria de saber?"
        return self._create_response(state, response, {})

# Entry point para LangGraph
async def information_node(state: CeciliaState) -> CeciliaState:
    """Entry point para LangGraph com integração FAQ Qdrant"""
    node = InformationNode()
    result = await node(state)
    
    state.update(result["updated_state"])
    state["last_bot_response"] = result["response"]
    
    return state