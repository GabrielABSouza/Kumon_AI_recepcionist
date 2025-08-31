from typing import Dict, Any
import re
from ..state.models import CeciliaState, ConversationStage, ConversationStep, get_collected_field, set_collected_field
from ..state.managers import StateManager
from ..state.models import safe_update_state
from ...prompts.manager import prompt_manager
import logging

logger = logging.getLogger(__name__)

class QualificationNode:
    """
    Node de qualificação - MIGRAR lógica de _handle_qualification_stage()
    """
    
    async def __call__(self, state: CeciliaState) -> Dict[str, Any]:
        """
        Processa estágio de qualificação
        MIGRAR: conversation_flow.py linha 2250-2350 aprox
        """
        logger.info(f"Processing qualification for {state['phone_number']} - step: {state['current_step']}")
        
        user_message = state["last_user_message"]
        current_step = state["current_step"]
        
        # ========== CHILD_AGE_INQUIRY ==========
        if current_step == ConversationStep.CHILD_AGE_INQUIRY:
            # Extrair idade
            age_match = re.search(r'\b(\d{1,2})\b', user_message)
            
            child_name = get_collected_field(state, "child_name") or ""
            is_for_self = get_collected_field(state, "is_for_self")
            
            if age_match:
                age = int(age_match.group(1))
                
                # Verificar se SmartRouter permite uso de templates
                routing_info = state.get("routing_info", {})
                threshold_action = routing_info.get("threshold_action", "fallback_level1")
                
                if age < 3:
                    if threshold_action in ["proceed", "enhance_with_llm"]:
                        try:
                            response = await prompt_manager.get_prompt(
                                name="kumon:qualification:age_feedback:too_young",
                                variables={"child_name": child_name, "is_for_self": is_for_self},
                                conversation_state=state
                            )
                            logger.info(f"✅ Using PromptManager for age_too_young (threshold_action={threshold_action})")
                        except Exception as e:
                            logger.warning(f"⚠️ PromptManager failed for qualification:age_too_young, using fallback: {e}")
                            response = self._get_hardcoded_age_too_young(child_name, is_for_self)
                    else:
                        logger.info(f"⚡ Using hardcoded response (threshold_action={threshold_action})")
                        response = self._get_hardcoded_age_too_young(child_name, is_for_self)
                elif age <= 18:
                    if threshold_action in ["proceed", "enhance_with_llm"]:
                        try:
                            response = await prompt_manager.get_prompt(
                                name="kumon:qualification:age_feedback:ideal_age",
                                variables={"age": age, "child_name": child_name, "is_for_self": is_for_self},
                                conversation_state=state
                            )
                            logger.info(f"✅ Using PromptManager for age_ideal (threshold_action={threshold_action})")
                        except Exception as e:
                            logger.warning(f"⚠️ PromptManager failed for qualification:age_ideal, using fallback: {e}")
                            response = self._get_hardcoded_age_ideal(age, child_name, is_for_self)
                    else:
                        logger.info(f"⚡ Using hardcoded response (threshold_action={threshold_action})")
                        response = self._get_hardcoded_age_ideal(age, child_name, is_for_self)
                else:
                    if threshold_action in ["proceed", "enhance_with_llm"]:
                        try:
                            response = await prompt_manager.get_prompt(
                                name="kumon:qualification:age_feedback:adult_age",
                                variables={"age": age, "child_name": child_name, "is_for_self": is_for_self},
                                conversation_state=state
                            )
                            logger.info(f"✅ Using PromptManager for age_adult (threshold_action={threshold_action})")
                        except Exception as e:
                            logger.warning(f"⚠️ PromptManager failed for qualification:age_adult, using fallback: {e}")
                            response = self._get_hardcoded_age_adult(age, child_name, is_for_self)
                    else:
                        logger.info(f"⚡ Using hardcoded response (threshold_action={threshold_action})")
                        response = self._get_hardcoded_age_adult(age, child_name, is_for_self)
                
                updates = {
                    "student_age": age,
                    "current_step": ConversationStep.CURRENT_SCHOOL_GRADE
                }
                
                return self._create_response(state, response, updates)
            
            else:
                response = (
                    "Não consegui identificar a idade. Poderia me dizer quantos anos tem? "
                    "Por exemplo: 'Tenho 8 anos' ou 'Meu filho tem 10 anos'."
                )
                
                updates = {
                    "failed_attempts": 1
                }
                
                return self._create_response(state, response, updates)
        
        # ========== CURRENT_SCHOOL_GRADE ==========
        elif current_step == ConversationStep.CURRENT_SCHOOL_GRADE:
            education_level = user_message.strip()
            
            # Store education level
            set_collected_field(state, "education_level", education_level)
            
            response = (
                "Ótimo! Agora vou explicar um pouco sobre a metodologia Kumon. 📚\n\n"
                "O Kumon é um método de estudo que desenvolve a autodisciplina e o hábito de estudar. "
                "Nosso foco é fazer o aluno avançar além da série escolar, desenvolvendo:\n\n"
                "• Concentração e disciplina 🎯\n"
                "• Autonomia nos estudos 📖\n"
                "• Autoconfiança 💪\n"
                "• Raciocínio lógico 🧠\n\n"
                "Temos programas de **Matemática**, **Português** e **Inglês**. \n\n"
                "Qual área desperta mais interesse? (Pode escolher mais de uma) 😊"
            )
            
            updates = {
                "current_step": ConversationStep.SUBJECT_INTEREST
            }
            
            return self._create_response(state, response, updates)
        
        # ========== SUBJECT_INTEREST - NOVO STEP ==========
        elif current_step == ConversationStep.SUBJECT_INTEREST:
            return await self._handle_subject_interest(state, user_message)
        
        # ========== LEARNING_GOALS - NOVO STEP ==========
        elif current_step == ConversationStep.LEARNING_GOALS:
            return await self._handle_learning_goals(state, user_message)
        
        # ========== AVAILABILITY_CHECK - NOVO STEP ==========
        elif current_step == ConversationStep.AVAILABILITY_CHECK:
            return await self._handle_availability_check(state, user_message)
        
        # ========== QUALIFICATION_SUMMARY - NOVO STEP ==========
        elif current_step == ConversationStep.QUALIFICATION_SUMMARY:
            return await self._handle_qualification_summary(state, user_message)
        
        # Default
        response = "Poderia me contar mais sobre isso?"
        return self._create_response(state, response, {})
    
    async def _handle_subject_interest(self, state: CeciliaState, user_message: str) -> Dict[str, Any]:
        """Processa interesse em matérias"""
        message_lower = user_message.lower()
        
        # Detectar matérias mencionadas
        subjects = []
        if any(word in message_lower for word in ['matemática', 'matematica', 'math', 'números', 'numeros', 'cálculo', 'calculo']):
            subjects.append("Matemática")
        if any(word in message_lower for word in ['português', 'portugues', 'linguagem', 'redação', 'redacao', 'leitura', 'escrita']):
            subjects.append("Português")
        if any(word in message_lower for word in ['inglês', 'ingles', 'english', 'english']):
            subjects.append("Inglês")
        
        if not subjects:
            response = (
                "Poderia me dizer qual matéria desperta mais interesse?\n\n"
                "📊 **Matemática** - Raciocínio lógico e cálculos\n"
                "📝 **Português** - Leitura, escrita e interpretação\n"
                "🗣️ **Inglês** - Comunicação global\n\n"
                "Digite o nome da matéria ou 'todas' se houver interesse em várias 😊"
            )
            updates = {}
            return self._create_response(state, response, updates)
        
        # Store subjects interest
        set_collected_field(state, "subject_interests", subjects)
        
        subjects_text = " e ".join(subjects)
        child_name = get_collected_field(state, "child_name") or ""
        is_for_self = get_collected_field(state, "is_for_self")
        student_ref = "você" if is_for_self else f"o {child_name}"
        
        response = (
            f"Excelente escolha! {subjects_text} {'são' if len(subjects) > 1 else 'é'} fundamental para o desenvolvimento! 🎓\n\n"
            f"Agora me conte: qual é o principal objetivo com o Kumon?\n\n"
            f"**📈 Melhorar notas na escola**\n"
            f"**🚀 Avançar além da série atual**\n" 
            f"**🎯 Desenvolver disciplina e autonomia**\n"
            f"**📚 Reforçar conceitos básicos**\n"
            f"**🏆 Preparar para vestibular/concursos**\n\n"
            f"Qual dessas opções mais se adequa ao que {student_ref} precisa? 😊"
        )
        
        updates = {
            "current_step": ConversationStep.LEARNING_GOALS
        }
        
        return self._create_response(state, response, updates)
    
    async def _handle_learning_goals(self, state: CeciliaState, user_message: str) -> Dict[str, Any]:
        """Processa objetivos de aprendizado"""
        message_lower = user_message.lower()
        
        # Detectar objetivos
        goals = []
        if any(word in message_lower for word in ['notas', 'escola', 'escolar', 'melhorar']):
            goals.append("Melhorar desempenho escolar")
        if any(word in message_lower for word in ['avançar', 'além', 'adiante', 'acelerar']):
            goals.append("Acelerar aprendizado")
        if any(word in message_lower for word in ['disciplina', 'autonomia', 'independência', 'hábito']):
            goals.append("Desenvolver autonomia")
        if any(word in message_lower for word in ['reforço', 'reforçar', 'básico', 'base', 'fundamentos']):
            goals.append("Reforçar fundamentos")
        if any(word in message_lower for word in ['vestibular', 'concurso', 'enem', 'preparar']):
            goals.append("Preparação para exames")
        
        # Store learning goals
        goals_text = user_message.strip() if not goals else ", ".join(goals)
        set_collected_field(state, "learning_goals", goals_text)
        
        child_name = get_collected_field(state, "child_name") or ""
        is_for_self = get_collected_field(state, "is_for_self")
        student_ref = "você" if is_for_self else f"o {child_name}"
        
        response = (
            f"Perfeito! Entendo os objetivos para {student_ref}. 🎯\n\n"
            f"Para oferecer a melhor orientação, preciso saber sobre a disponibilidade:\n\n"
            f"**📅 Quantos dias por semana seria ideal estudar?**\n"
            f"• 2-3 dias (recomendado para iniciantes)\n"
            f"• 4-5 dias (para resultados acelerados)\n"
            f"• Todos os dias (máximo desenvolvimento)\n\n"
            f"**🕐 Qual período do dia {student_ref} tem mais concentração?**\n"
            f"• Manhã (9h às 12h)\n"
            f"• Tarde (14h às 17h)\n\n"
            f"Me conte sobre a disponibilidade ideal 😊"
        )
        
        updates = {
            "current_step": ConversationStep.AVAILABILITY_CHECK
        }
        
        return self._create_response(state, response, updates)
    
    async def _handle_availability_check(self, state: CeciliaState, user_message: str) -> Dict[str, Any]:
        """Processa disponibilidade do aluno"""
        # Store availability preferences
        set_collected_field(state, "availability_preferences", user_message.strip())
        
        # Calculate qualification score
        qualification_score = self._calculate_qualification_score(state)
        set_collected_field(state, "qualification_score", qualification_score)
        
        # Transition to summary
        updates = {
            "current_step": ConversationStep.QUALIFICATION_SUMMARY
        }
        
        return await self._handle_qualification_summary(state, user_message, updates)
    
    async def _handle_qualification_summary(self, state: CeciliaState, user_message: str, custom_updates: Dict[str, Any] = None) -> Dict[str, Any]:
        """Gera resumo da qualificação e decide próximo passo"""
        
        if custom_updates:
            # CRITICAL FIX: Use safe_update_state to preserve CeciliaState structure
            safe_update_state(state, custom_updates)
        
        # Collect all qualification data
        child_name = get_collected_field(state, "child_name") or ""
        student_age = get_collected_field(state, "student_age") or "N/A"
        education_level = get_collected_field(state, "education_level") or ""
        subjects = get_collected_field(state, "subject_interests") or []
        goals = get_collected_field(state, "learning_goals") or ""
        availability = get_collected_field(state, "availability_preferences") or ""
        qualification_score = get_collected_field(state, "qualification_score") or 0
        is_for_self = get_collected_field(state, "is_for_self")
        
        # Generate personalized response based on qualification score
        if qualification_score >= 80:
            # High qualified lead
            student_ref = "você" if is_for_self else child_name
            subjects_text = " e ".join(subjects) if subjects else "as matérias de interesse"
            
            response = (
                f"✨ **PERFIL COMPLETO!** ✨\n\n"
                f"Com base nas informações, {student_ref} tem um perfil excelente para o Kumon! 🎓\n\n"
                f"📋 **Resumo da Qualificação:**\n"
                f"👤 Aluno(a): {child_name if not is_for_self else 'Você'} ({student_age} anos)\n"
                f"📚 Escolaridade: {education_level}\n"
                f"📊 Interesse: {subjects_text}\n"
                f"🎯 Objetivo: {goals}\n\n"
                f"O Kumon será ideal para desenvolver {subjects_text} com foco em {goals.lower()}!\n\n"
                f"💰 **Investimento:**\n"
                f"• R$ 375,00 por matéria/mês\n"
                f"• R$ 100,00 taxa de matrícula (única)\n\n"
                f"Gostaria de agendar uma **apresentação gratuita** para conhecer melhor nossa metodologia? 📅"
            )
            
            # High value lead - move to scheduling
            updates = {
                "current_stage": ConversationStage.SCHEDULING,
                "current_step": ConversationStep.SCHEDULING_INTRODUCTION,
                "lead_status": "qualified",
                "qualification_score": qualification_score
            }
        else:
            # Lower qualified lead - provide more information first
            response = (
                f"Obrigada pelas informações! 😊\n\n"
                f"Com base no perfil, posso explicar melhor como o Kumon funcionaria:\n\n"
                f"🎓 **Nossa Metodologia:**\n"
                f"• Estudo individualizado e autodidata\n"
                f"• Progressão no próprio ritmo\n"
                f"• Desenvolvimento da autoconfiança\n"
                f"• Orientação educacional personalizada\n\n"
                f"💰 **Investimento mensal:**\n"
                f"• R$ 375,00 por matéria\n"
                f"• R$ 100,00 taxa de matrícula (única)\n\n"
                f"Que tal agendar uma **visita gratuita** para {child_name if not is_for_self else 'você'} conhecer nosso espaço e metodologia na prática? 📅"
            )
            
            updates = {
                "current_stage": ConversationStage.INFORMATION_GATHERING,
                "current_step": ConversationStep.METHODOLOGY_EXPLANATION,
                "lead_status": "partial_qualified", 
                "qualification_score": qualification_score
            }
        
        return self._create_response(state, response, updates)
    
    def _calculate_qualification_score(self, state: CeciliaState) -> int:
        """
        Calcula score de qualificação do lead (0-100)
        Critérios conforme PROJECT_SCOPE.md business requirements
        """
        score = 0
        
        # Age appropriateness (25 points)
        student_age = get_collected_field(state, "student_age")
        if student_age:
            if 3 <= student_age <= 18:
                score += 25
            elif student_age < 3:
                score += 5  # Too young, low score
            else:
                score += 15  # Adult education, moderate score
        
        # Subject interest defined (20 points)
        subjects = get_collected_field(state, "subject_interests")
        if subjects and len(subjects) > 0:
            score += 20
        
        # Clear learning goals (25 points)
        goals = get_collected_field(state, "learning_goals")
        if goals and len(goals.strip()) > 10:  # Meaningful response
            score += 25
        
        # Education level provided (15 points)
        education_level = get_collected_field(state, "education_level")
        if education_level and len(education_level.strip()) > 0:
            score += 15
        
        # Availability discussed (15 points)
        availability = get_collected_field(state, "availability_preferences")
        if availability and len(availability.strip()) > 5:
            score += 15
        
        return min(score, 100)  # Cap at 100
    
    def _get_hardcoded_age_too_young(self, child_name: str, is_for_self: bool) -> str:
        """Resposta hardcoded segura para idade muito baixa"""
        child_ref = "você" if is_for_self else f"o {child_name}"
        return (
            f"Entendo! Para crianças menores de 3 anos, recomendamos aguardar um pouco mais. "
            f"O Kumon é mais eficaz a partir dos 3 anos, quando {child_ref} já tem maior concentração. 🧒\n\n"
            "Gostaria de saber mais sobre quando seria o momento ideal para começar?"
        )
    
    def _get_hardcoded_age_ideal(self, age: int, child_name: str, is_for_self: bool) -> str:
        """Resposta hardcoded segura para idade ideal"""
        child_ref = "você" if is_for_self else f"o {child_name}"
        possessive = "sua" if is_for_self else f"do {child_name}"
        return (
            f"Perfeito! Com {age} anos, {child_ref} está em uma idade excelente para o Kumon! 🎓\n\n"
            f"Em que série {child_ref} está atualmente? Ou se preferir, pode me contar um pouco sobre "
            f"o nível de conhecimento atual {possessive} em matemática ou português."
        )
    
    def _get_hardcoded_age_adult(self, age: int, child_name: str, is_for_self: bool) -> str:
        """Resposta hardcoded segura para idade adulta"""
        child_ref = "você" if is_for_self else f"o {child_name}"
        possessive = "seu" if is_for_self else f"do {child_name}"
        return (
            f"Que bom saber do interesse! Com {age} anos... nunca é tarde para aprender! 💪\n\n"
            f"Qual é o objetivo principal {possessive}? Reforçar conceitos básicos, se preparar para "
            f"concursos ou desenvolver habilidades específicas?"
        )
    
    def _create_response(
        self, 
        state: CeciliaState, 
        response: str, 
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Cria resposta padronizada do node"""
        # Atualizar estado
        updated_state = StateManager.update_state(state, updates)
        
        return {
            "response": response,
            "updated_state": updated_state,
            "stage": updated_state["current_stage"],
            "step": updated_state["current_step"],
            "intent": "qualification_flow"
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