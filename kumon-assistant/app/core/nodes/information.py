from typing import Dict, Any, List
from ..state.models import CeciliaState, ConversationStage, ConversationStep, get_collected_field, set_collected_field, increment_metric
from ..state.managers import StateManager
from ...services.langchain_rag import langchain_rag_service  # FAQ Qdrant integration
import logging

logger = logging.getLogger(__name__)

class InformationNode:
    """
    Node de coleta de informações - INTEGRAÇÃO com FAQ Qdrant
    """
    
    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """Processa perguntas sobre metodologia Kumon usando FAQ vetorizada"""
        
        user_message = state["last_user_message"]
        
        # Tracking é agora gerenciado pelo StateManager via metrics
        # info_gathering_count será incrementado via conversation_metrics
        
        # ========== INTEGRAÇÃO COM FAQ QDRANT ==========
        try:
            # 1. Consultar FAQ vetorizada primeiro
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
                answer = self._get_specific_answer_fallback(user_message)
                question_category = self._categorize_question(user_message)
                
                if not answer:
                    # Nem RAG nem fallback funcionaram
                    logger.warning(f"No answer found for question: {user_message}")
                    return await self._handle_unknown_question(state, user_message)
        
        except Exception as e:
            logger.error(f"RAG query error: {str(e)}")
            # Fallback para respostas hardcoded em caso de erro RAG
            answer = self._get_specific_answer_fallback(user_message)
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
    
    def _get_specific_answer_fallback(self, user_message: str) -> str:
        """Respostas específicas como fallback quando RAG falha"""
        message_lower = user_message.lower()
        
        # BUSINESS CRITICAL: Updated pricing per PROJECT_SCOPE.md (R$ 375,00 + R$ 100,00)
        if any(word in message_lower for word in ["preço", "valor", "custa", "mensalidade", "investimento"]):
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

# Entry point para LangGraph
async def information_node(state: CeciliaState) -> CeciliaState:
    """Entry point para LangGraph com integração FAQ Qdrant"""
    node = InformationNode()
    result = await node(state)
    
    state.update(result["updated_state"])
    state["last_bot_response"] = result["response"]
    
    return state