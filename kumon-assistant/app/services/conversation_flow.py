"""
Advanced conversation flow manager with state cleanup and memory management
"""
import time
import asyncio
import re
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..core.config import settings
from ..core.logger import app_logger
from ..services.rag_engine import RAGEngine
from ..services.enhanced_rag_engine import enhanced_rag_engine
from ..services.unit_manager import unit_manager
from ..clients.google_calendar import GoogleCalendarClient


class ConversationStage(Enum):
    """Conversation stages"""
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    INFORMATION_GATHERING = "information_gathering"
    SCHEDULING = "scheduling"
    CONFIRMATION = "confirmation"
    FOLLOW_UP = "follow_up"
    COMPLETED = "completed"


class ConversationStep(Enum):
    """Conversation steps within stages"""
    # Greeting stage
    WELCOME = "welcome"
    INITIAL_RESPONSE = "initial_response"
    
    # Qualification stage
    CHILD_AGE_INQUIRY = "child_age_inquiry"
    CURRENT_SCHOOL_GRADE = "current_school_grade"
    ACADEMIC_GOALS = "academic_goals"
    COMMITMENT_LEVEL = "commitment_level"
    
    # Information gathering stage
    METHODOLOGY_EXPLANATION = "methodology_explanation"
    PROGRAM_DETAILS = "program_details"
    PRICING_INFO = "pricing_info"
    
    # Scheduling stage
    AVAILABILITY_CHECK = "availability_check"
    APPOINTMENT_BOOKING = "appointment_booking"
    APPOINTMENT_SUGGESTION = "appointment_suggestion"
    DATE_PREFERENCE = "date_preference"
    TIME_SELECTION = "time_selection"
    EMAIL_COLLECTION = "email_collection"
    EVENT_CREATION = "event_creation"
    
    # Confirmation stage
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    CONTACT_INFO_COLLECTED = "contact_info_collected"
    
    # Follow-up stage
    REMINDER_SENT = "reminder_sent"
    FEEDBACK_COLLECTED = "feedback_collected"
    
    # Completed
    CONVERSATION_ENDED = "conversation_ended"


@dataclass
class ConversationState:
    """Represents the current state of a conversation"""
    phone_number: str
    stage: ConversationStage
    step: ConversationStep
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    last_activity: float = field(default_factory=time.time)
    
    def update(self, **kwargs):
        """Update conversation state"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()
        self.last_activity = time.time()
        self.message_count += 1


class ConversationFlowManager:
    """Manages conversation flow and roadmap with memory management"""
    
    def __init__(self):
        # In-memory storage for conversation states
        # TODO: Replace with database storage in production
        self.conversation_states: Dict[str, ConversationState] = {}
        
        # Memory management settings
        self.max_conversations = getattr(settings, 'MAX_ACTIVE_CONVERSATIONS', 1000)
        self.conversation_timeout = getattr(settings, 'CONVERSATION_TIMEOUT_HOURS', 24)
        self.cleanup_interval = getattr(settings, 'CONVERSATION_CLEANUP_INTERVAL', 3600)  # 1 hour
        self.last_cleanup_time = 0
        
        # Initialize Google Calendar client
        self.calendar_client = GoogleCalendarClient()
        
        # Define the roadmap
        self.roadmap = self._define_roadmap()
        
        app_logger.info("ConversationFlowManager initialized")
        app_logger.info(f"Memory limits: {self.max_conversations} conversations, {self.conversation_timeout}h timeout")
    
    def _define_roadmap(self) -> Dict[ConversationStage, Dict[str, Any]]:
        """Define the conversation roadmap"""
        return {
            ConversationStage.GREETING: {
                "name": "Boas-vindas",
                "description": "Recepção inicial e identificação do interesse",
                "steps": [
                    ConversationStep.WELCOME,
                    ConversationStep.INITIAL_RESPONSE
                ],
                "required_data": [],
                "next_stage": ConversationStage.QUALIFICATION
            },
            ConversationStage.QUALIFICATION: {
                "name": "Qualificação",
                "description": "Identificar perfil do estudante e relacionamento familiar",
                "steps": [
                    ConversationStep.CHILD_AGE_INQUIRY,
                    ConversationStep.CURRENT_SCHOOL_GRADE
                ],
                "required_data": ["is_for_self", "relationship", "student_age", "education_level"],
                "next_stage": ConversationStage.INFORMATION_GATHERING
            },
            ConversationStage.INFORMATION_GATHERING: {
                "name": "Coleta de Informações",
                "description": "Explicar metodologia, programas e preços",
                "steps": [
                    ConversationStep.METHODOLOGY_EXPLANATION,
                    ConversationStep.PROGRAM_DETAILS,
                    ConversationStep.PRICING_INFO
                ],
                "required_data": ["methodology_explained", "programs_of_interest", "pricing_discussed"],
                "next_stage": ConversationStage.SCHEDULING
            },
            ConversationStage.SCHEDULING: {
                "name": "Agendamento",
                "description": "Verificar disponibilidade e agendar visita",
                "steps": [
                    ConversationStep.AVAILABILITY_CHECK,
                    ConversationStep.APPOINTMENT_BOOKING,
                    ConversationStep.APPOINTMENT_SUGGESTION,
                    ConversationStep.DATE_PREFERENCE,
                    ConversationStep.TIME_SELECTION,
                    ConversationStep.EMAIL_COLLECTION,
                    ConversationStep.EVENT_CREATION
                ],
                "required_data": ["preferred_dates", "selected_time", "contact_email", "appointment_details"],
                "next_stage": ConversationStage.CONFIRMATION
            },
            ConversationStage.CONFIRMATION: {
                "name": "Confirmação",
                "description": "Confirmar agendamento e coletar informações finais",
                "steps": [
                    ConversationStep.APPOINTMENT_CONFIRMED,
                    ConversationStep.CONTACT_INFO_COLLECTED
                ],
                "required_data": ["appointment_confirmed", "full_contact_info"],
                "next_stage": ConversationStage.FOLLOW_UP
            },
            ConversationStage.FOLLOW_UP: {
                "name": "Acompanhamento",
                "description": "Lembretes e coleta de feedback",
                "steps": [
                    ConversationStep.REMINDER_SENT,
                    ConversationStep.FEEDBACK_COLLECTED
                ],
                "required_data": ["reminder_sent", "feedback_received"],
                "next_stage": ConversationStage.COMPLETED
            },
            ConversationStage.COMPLETED: {
                "name": "Finalizado",
                "description": "Conversa concluída com sucesso",
                "steps": [
                    ConversationStep.CONVERSATION_ENDED
                ],
                "required_data": [],
                "next_stage": None
            }
        }
    
    async def cleanup_old_conversations(self) -> None:
        """Clean up old and inactive conversations to prevent memory leaks"""
        current_time = time.time()
        
        # Check if cleanup is needed
        if current_time - self.last_cleanup_time < self.cleanup_interval:
            return
        
        try:
            timeout_seconds = self.conversation_timeout * 3600
            conversations_to_remove = []
            
            for phone_number, state in self.conversation_states.items():
                # Check if conversation is too old or inactive
                time_since_activity = current_time - state.last_activity
                
                if (time_since_activity > timeout_seconds or 
                    state.stage == ConversationStage.COMPLETED):
                    conversations_to_remove.append(phone_number)
            
            # Remove old conversations
            removed_count = 0
            for phone_number in conversations_to_remove:
                try:
                    del self.conversation_states[phone_number]
                    removed_count += 1
                except KeyError:
                    pass
            
            # If still too many conversations, remove oldest ones
            if len(self.conversation_states) > self.max_conversations:
                # Sort by last activity and remove oldest
                sorted_conversations = sorted(
                    self.conversation_states.items(),
                    key=lambda x: x[1].last_activity
                )
                
                excess_count = len(self.conversation_states) - self.max_conversations
                for phone_number, _ in sorted_conversations[:excess_count]:
                    try:
                        del self.conversation_states[phone_number]
                        removed_count += 1
                    except KeyError:
                        pass
            
            if removed_count > 0:
                app_logger.info(f"Cleaned up {removed_count} old conversations")
            
            self.last_cleanup_time = current_time
            
        except Exception as e:
            app_logger.error(f"Error in conversation cleanup: {str(e)}")
    
    def get_conversation_state(self, phone_number: str) -> ConversationState:
        """Get or create conversation state for a phone number"""
        # Clean up old conversations before processing new ones
        asyncio.create_task(self.cleanup_old_conversations())
        
        if phone_number not in self.conversation_states:
            self.conversation_states[phone_number] = ConversationState(
                phone_number=phone_number,
                stage=ConversationStage.GREETING,
                step=ConversationStep.WELCOME
            )
            app_logger.info(f"Created new conversation state for {phone_number}")
        
        return self.conversation_states[phone_number]
    
    def update_conversation_state(
        self, 
        phone_number: str, 
        stage: Optional[ConversationStage] = None,
        step: Optional[ConversationStep] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update conversation state"""
        state = self.get_conversation_state(phone_number)
        
        if stage:
            state.stage = stage
        if step:
            state.step = step
        if data:
            state.data.update(data)
        
        state.update()
        
        app_logger.info(f"Updated conversation state for {phone_number}: {state.stage.value} -> {state.step.value}")
    
    async def advance_conversation(self, phone_number: str, user_message: str) -> Dict[str, Any]:
        """Advance the conversation based on current state and user message"""
        state = self.get_conversation_state(phone_number)
        
        app_logger.info(f"Advancing conversation for {phone_number} in stage {state.stage.value}, step {state.step.value}")
        
        # Route based on current stage
        if state.stage == ConversationStage.GREETING:
            return self._handle_greeting_stage(state, user_message)
        elif state.stage == ConversationStage.QUALIFICATION:
            return self._handle_qualification_stage(state, user_message)
        elif state.stage == ConversationStage.INFORMATION_GATHERING:
            return await self._handle_information_gathering_stage(state, user_message)
        elif state.stage == ConversationStage.SCHEDULING:
            return await self._handle_scheduling_stage(state, user_message)
        elif state.stage == ConversationStage.CONFIRMATION:
            return self._handle_confirmation_stage(state, user_message)
        elif state.stage == ConversationStage.FOLLOW_UP:
            return self._handle_follow_up_stage(state, user_message)
        else:
            return self._handle_completed_stage(state, user_message)
    
    def _handle_greeting_stage(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Handle greeting stage logic"""
        if state.step == ConversationStep.WELCOME:
            # Initial greeting
            response = (
                "Olá! Bem-vindo ao Kumon Vila A! 😊\n\n"
                "Sou sua assistente virtual e estou aqui para ajudá-lo com informações sobre nossa metodologia de ensino.\n\n"
                "Para começar, você está buscando o Kumon para você mesmo ou para outra pessoa? 🤔"
            )
            
            self.update_conversation_state(
                state.phone_number,
                step=ConversationStep.INITIAL_RESPONSE
            )
            
            return {"message": response, "stage": state.stage.value, "step": state.step.value}
        
        elif state.step == ConversationStep.INITIAL_RESPONSE:
            # Determine if for self or someone else
            user_message_lower = user_message.lower()
            
            # Check for child first (more specific)
            if any(word in user_message_lower for word in ["filho", "filha", "criança", "filho(a)"]):
                is_for_self = False
                relationship = "responsável por filho(a)"
                response = (
                    "Que legal! É maravilhoso ver pais investindo na educação dos filhos! 👨‍👩‍👧‍👦\n\n"
                    "Qual é a idade do seu filho(a)? Isso me ajudará a explicar melhor nossos programas."
                )
            elif any(word in user_message_lower for word in ["eu", "mim", "mesmo", "minha"]):
                is_for_self = True
                relationship = "próprio interessado"
                response = (
                    "Perfeito! É ótimo ver seu interesse em aprender conosco! 🎯\n\n"
                    "Qual é a sua idade? Isso me ajudará a entender melhor suas necessidades de aprendizado."
                )
            else:
                response = (
                    "Entendi! Poderia me dizer um pouco mais sobre para quem seria o Kumon? "
                    "É para você mesmo(a) ou para outra pessoa (filho, filha, etc.)?"
                )
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
            
            # Update state and move to qualification
            self.update_conversation_state(
                state.phone_number,
                stage=ConversationStage.QUALIFICATION,
                step=ConversationStep.CHILD_AGE_INQUIRY,
                data={"is_for_self": is_for_self, "relationship": relationship}
            )
            
            return {"message": response, "stage": state.stage.value, "step": state.step.value}
        
        return {"message": "Como posso ajudá-lo hoje?", "stage": state.stage.value, "step": state.step.value}
    
    def _handle_qualification_stage(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Handle qualification stage logic"""
        if state.step == ConversationStep.CHILD_AGE_INQUIRY:
            # Extract age information
            age_match = re.search(r'\b(\d{1,2})\b', user_message)
            
            if age_match:
                age = int(age_match.group(1))
                
                if age < 3:
                    response = (
                        "Entendo! Para crianças menores de 3 anos, recomendamos aguardar um pouco mais. "
                        "O Kumon é mais eficaz a partir dos 3 anos, quando a criança já tem maior concentração. 🧒\n\n"
                        "Gostaria de saber mais sobre quando seria o momento ideal para começar?"
                    )
                elif age <= 18:
                    response = (
                        f"Perfeito! {age} anos é uma excelente idade para começar o Kumon! 🎓\n\n"
                        f"Em que série está atualmente? Ou se preferir, pode me contar um pouco sobre "
                        f"o nível de conhecimento atual em matemática ou português."
                    )
                else:
                    response = (
                        f"Que bom saber do seu interesse! {age} anos... nunca é tarde para aprender! 💪\n\n"
                        f"Qual é seu objetivo principal? Reforçar conceitos básicos, se preparar para "
                        f"concursos ou desenvolver habilidades específicas?"
                    )
                
                self.update_conversation_state(
                    state.phone_number,
                    step=ConversationStep.CURRENT_SCHOOL_GRADE,
                    data={"student_age": age}
                )
                
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
            else:
                response = (
                    "Não consegui identificar a idade. Poderia me dizer quantos anos tem? "
                    "Por exemplo: 'Tenho 8 anos' ou 'Meu filho tem 10 anos'."
                )
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
        
        elif state.step == ConversationStep.CURRENT_SCHOOL_GRADE:
            # Capture education level and move to information gathering
            education_level = user_message.strip()
            
            response = (
                "Ótimo! Agora vou explicar um pouco sobre a metodologia Kumon. 📚\n\n"
                "O Kumon é um método de estudo que desenvolve a autodisciplina e o hábito de estudar. "
                "Nosso foco é fazer o aluno avançar além da série escolar, desenvolvendo:\n\n"
                "• Concentração e disciplina 🎯\n"
                "• Autonomia nos estudos 📖\n"
                "• Autoconfiança 💪\n"
                "• Raciocínio lógico 🧠\n\n"
                "Temos programas de Matemática, Português e Inglês. Qual área desperta mais interesse?"
            )
            
            self.update_conversation_state(
                state.phone_number,
                stage=ConversationStage.INFORMATION_GATHERING,
                step=ConversationStep.METHODOLOGY_EXPLANATION,
                data={"education_level": education_level}
            )
            
            return {"message": response, "stage": state.stage.value, "step": state.step.value}
        
        return {"message": "Poderia me contar mais sobre isso?", "stage": state.stage.value, "step": state.step.value}
    
    async def _handle_information_gathering_stage(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Handle information gathering stage"""
        # Use enhanced RAG for detailed information
        try:
            # Create context with conversation data
            context = {
                "conversation_stage": state.stage.value,
                "conversation_step": state.step.value,
                "user_data": state.data,
                "phone_number": state.phone_number
            }
            
            # Get enhanced response using await instead of loop.run_until_complete
            try:
                rag_response = await enhanced_rag_engine.answer_question(
                    question=user_message,
                    context=context,
                    similarity_threshold=0.6
                )
            except Exception as e:
                app_logger.error(f"Error with enhanced RAG: {str(e)}")
                # Fallback to basic response
                rag_response = (
                    "Obrigado pelo interesse! Nossa equipe está aqui para esclarecer todas as suas dúvidas. "
                    "Que tal agendarmos uma conversa para explicar melhor nossos programas? 📅"
                )
            
            # Check if user wants to schedule or if we should suggest scheduling
            schedule_keywords = ["agendar", "visita", "horario", "quando", "disponibilidade", "encontrar"]
            should_suggest_booking = any(word in user_message.lower() for word in schedule_keywords)
            
            # Count how many exchanges we've had in this stage
            if not hasattr(state, 'info_gathering_count'):
                state.data['info_gathering_count'] = 0
            state.data['info_gathering_count'] += 1
            
            if should_suggest_booking or state.data['info_gathering_count'] >= 3:
                # Transition to scheduling
                self.update_conversation_state(
                    state.phone_number,
                    stage=ConversationStage.SCHEDULING,
                    step=ConversationStep.APPOINTMENT_SUGGESTION
                )
                
                if should_suggest_booking:
                    response = (
                        "Perfeito! Vamos agendar uma apresentação para você conhecer melhor o Kumon! 🎯\n\n"
                        "Na nossa apresentação, você poderá:\n"
                        "• Conhecer nossa metodologia na prática 📚\n"
                        "• Fazer uma avaliação diagnóstica 📝\n"
                        "• Conversar com nossa equipe pedagógica 👨‍🏫\n"
                        "• Tirar todas as suas dúvidas 💭\n\n"
                        "Qual período você prefere: manhã ou tarde? 🕐"
                    )
                else:
                    response = (
                        rag_response + "\n\n"
                        "---\n\n"
                        "Que tal agendarmos uma apresentação para você conhecer melhor o Kumon? 📅\n\n"
                        "Durante a apresentação, você poderá ver nossa metodologia na prática e fazer "
                        "uma avaliação diagnóstica gratuita!\n\n"
                        "Qual período você prefere: manhã ou tarde? 🕐"
                    )
                
                return {"message": response, "stage": ConversationStage.SCHEDULING.value, "step": ConversationStep.APPOINTMENT_SUGGESTION.value}
            
            return {"message": rag_response, "stage": state.stage.value, "step": state.step.value}
            
        except Exception as e:
            app_logger.error(f"Error in information gathering: {str(e)}")
            return {
                "message": "Desculpe, houve um problema. Pode repetir sua pergunta?",
                "stage": state.stage.value,
                "step": state.step.value
            }
    
    async def _handle_scheduling_stage(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Handle scheduling stage with comprehensive appointment booking"""
        
        if state.step == ConversationStep.APPOINTMENT_SUGGESTION:
            # User is responding to appointment suggestion
            user_response = user_message.lower()
            
            if any(word in user_response for word in ["não", "nao", "depois", "mais tarde", "não quero"]):
                # User declined appointment
                response = (
                    "Entendo! Sem problemas. 😊\n\n"
                    "Quando quiser agendar uma visita, é só me chamar! "
                    "Estarei aqui para ajudá-lo a qualquer momento.\n\n"
                    "Tem mais alguma dúvida sobre o Kumon que posso esclarecer?"
                )
                
                # Go back to information gathering
                self.update_conversation_state(
                    state.phone_number,
                    stage=ConversationStage.INFORMATION_GATHERING,
                    step=ConversationStep.METHODOLOGY_EXPLANATION
                )
                
                return {"message": response, "stage": ConversationStage.INFORMATION_GATHERING.value, "step": ConversationStep.METHODOLOGY_EXPLANATION.value}
            
            # User wants to schedule, move to date preference
            self.update_conversation_state(
                state.phone_number,
                step=ConversationStep.DATE_PREFERENCE
            )
            
            response = (
                "Ótimo! Vamos encontrar o melhor horário para você! 📅\n\n"
                "Qual dia da semana seria melhor? Por exemplo:\n"
                "• Segunda a sexta-feira\n"
                "• Qualquer dia útil\n\n"
                "E qual período prefere: manhã ou tarde?"
            )
            
            return {"message": response, "stage": state.stage.value, "step": state.step.value}
            
        elif state.step == ConversationStep.DATE_PREFERENCE:
            # Extract date and time preferences
            preferences = self._extract_date_time_preferences(user_message)
            
            if preferences.get("saturday_requested"):
                response = (
                    "Desculpe, mas a unidade do Kumon Vila A está fechada nos sábados. 😊\n\n"
                    "Por favor, escolha um dia útil (segunda a sexta-feira) para agendar sua visita."
                )
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
            
            if preferences.get("sunday_requested"):
                response = (
                    "Desculpe, mas a unidade do Kumon Vila A está fechada nos domingos. 😊\n\n"
                    "Por favor, escolha um dia útil (segunda a sexta-feira) para agendar sua visita."
                )
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
            
            if preferences.get("evening_requested"):
                response = (
                    "Desculpe, mas a unidade do Kumon Vila A funciona até às 18h. 😊\n\n"
                    f"Nosso horário de funcionamento é: {settings.BUSINESS_HOURS}\n\n"
                    "Por favor, escolha um horário de manhã (8h às 12h) ou tarde (12h às 18h)."
                )
                return {"message": response, "stage": state.stage.value, "step": state.step.value}

            if not preferences:
                response = (
                    "Não consegui entender sua preferência de horário. 😅\n\n"
                    "Poderia me dizer de forma mais clara? Por exemplo:\n"
                    "• 'Prefiro segunda-feira de manhã'\n"
                    "• 'Sábado à tarde'\n"
                    "• 'Qualquer dia da semana no período da tarde'"
                )
                
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
            
            # Store preferences and search for availability
            state.data['date_preferences'] = preferences
            
            # Search for available time slots
            try:
                available_slots = await self._find_available_slots(preferences)
                
                if not available_slots:
                    response = (
                        "Ops! Não encontrei horários disponíveis para suas preferências. 😔\n\n"
                        "Que tal tentarmos outros dias ou horários? "
                        "Posso verificar outras opções para você!"
                    )
                    
                    return {"message": response, "stage": state.stage.value, "step": state.step.value}
                
                # Present available slots
                slots_text = self._format_available_slots(available_slots)
                state.data['available_slots'] = available_slots
                
                response = (
                    "Perfeito! Encontrei alguns horários disponíveis: 🎯\n\n"
                    + slots_text + "\n\n"
                    "Qual horário é melhor para você? "
                    "Pode responder com o número da opção (1, 2 ou 3)."
                )
                
                self.update_conversation_state(
                    state.phone_number,
                    step=ConversationStep.TIME_SELECTION
                )
                
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
                
            except Exception as e:
                app_logger.error(f"Error finding available slots: {str(e)}")
                response = (
                    "Desculpe, houve um problema ao verificar a disponibilidade. 😔\n\n"
                    "Que tal tentarmos novamente? Qual seria seu dia e horário preferido?"
                )
                
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
        
        elif state.step == ConversationStep.TIME_SELECTION:
            # User selected a time slot
            selection = self._extract_time_selection(user_message)
            available_slots = state.data.get('available_slots', [])
            
            if selection is None or selection < 1 or selection > len(available_slots):
                response = (
                    "Não consegui entender sua escolha. 😅\n\n"
                    "Poderia me dizer o número da opção (1, 2 ou 3)? "
                    "Ou se preferir, me diga qual horário você escolheu."
                )
                
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
            
            # Store selected slot
            selected_slot = available_slots[selection - 1]
            state.data['selected_slot'] = selected_slot
            
            # Ask for email
            response = (
                f"Excelente escolha! 🎉\n\n"
                f"Agendamento para: {selected_slot['formatted_time']}\n\n"
                f"Para confirmar seu agendamento, preciso do seu email. "
                f"Poderia me informar seu endereço de email?"
            )
            
            self.update_conversation_state(
                state.phone_number,
                step=ConversationStep.EMAIL_COLLECTION
            )
            
            return {"message": response, "stage": state.stage.value, "step": state.step.value}
        
        elif state.step == ConversationStep.EMAIL_COLLECTION:
            # Validate and collect email
            email = self._extract_email(user_message)
            
            if not email:
                response = (
                    "Não consegui identificar um email válido. 😅\n\n"
                    "Poderia me informar seu email? Por exemplo: seuemail@gmail.com"
                )
                
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
            
            # Store email and create event
            state.data['contact_email'] = email
            
            try:
                event_result = await self._create_calendar_event(state)
                
                if event_result.get('success'):
                    response = (
                        "🎉 Agendamento confirmado com sucesso!\n\n"
                        f"📅 Data: {state.data['selected_slot']['formatted_time']}\n"
                        f"📧 Email: {email}\n"
                        f"🆔 Código do agendamento: {event_result['event_id'][:8]}\n\n"
                        "Você receberá um lembrete por email! "
                        "Aguardamos você na nossa unidade! 😊"
                    )
                    
                    self.update_conversation_state(
                        state.phone_number,
                        stage=ConversationStage.CONFIRMATION,
                        step=ConversationStep.APPOINTMENT_CONFIRMED
                    )
                    
                    return {"message": response, "stage": ConversationStage.CONFIRMATION.value, "step": ConversationStep.APPOINTMENT_CONFIRMED.value}
                else:
                    response = (
                        "Houve um problema ao confirmar seu agendamento. 😔\n\n"
                        "Mas não se preocupe! Anotei seus dados:\n"
                        f"📅 Horário: {state.data['selected_slot']['formatted_time']}\n"
                        f"📧 Email: {email}\n\n"
                        "Nossa equipe entrará em contato para confirmar! "
                        "Ou você pode ligar para nossa unidade."
                    )
                    
                    return {"message": response, "stage": state.stage.value, "step": state.step.value}
                    
            except Exception as e:
                app_logger.error(f"Error creating calendar event: {str(e)}")
                response = (
                    "Houve um problema técnico, mas anotei seus dados! 📝\n\n"
                    f"📅 Horário: {state.data['selected_slot']['formatted_time']}\n"
                    f"📧 Email: {email}\n\n"
                    "Nossa equipe entrará em contato para confirmar seu agendamento!"
                )
                
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
        
        # Default response
        response = (
            "Como posso ajudá-lo com o agendamento? 😊\n\n"
            "Podemos encontrar um horário que funcione para você!"
        )
        
        return {"message": response, "stage": state.stage.value, "step": state.step.value}
    
    def _extract_date_time_preferences(self, user_message: str) -> Dict[str, Any]:
        """Extract date and time preferences from user message."""
        user_message_lower = user_message.lower()
        preferences = {}
        
        # Check for Saturday first and handle it specially
        if "sábado" in user_message_lower or "sab" in user_message_lower:
            preferences["saturday_requested"] = True
            return preferences
        
        # Check for Sunday 
        if "domingo" in user_message_lower or "dom" in user_message_lower:
            preferences["sunday_requested"] = True
            return preferences
        
        # Check for evening/night requests
        if "noite" in user_message_lower or "noit" in user_message_lower:
            preferences["evening_requested"] = True
            return preferences
        
        # Day of the week
        if "segunda" in user_message_lower or "seg" in user_message_lower:
            preferences["day_of_week"] = "Segunda-feira"
        elif "terça" in user_message_lower or "ter" in user_message_lower:
            preferences["day_of_week"] = "Terça-feira"
        elif "quarta" in user_message_lower or "qua" in user_message_lower:
            preferences["day_of_week"] = "Quarta-feira"
        elif "quinta" in user_message_lower or "qui" in user_message_lower:
            preferences["day_of_week"] = "Quinta-feira"
        elif "sexta" in user_message_lower or "sex" in user_message_lower:
            preferences["day_of_week"] = "Sexta-feira"
        elif "qualquer" in user_message_lower or "qual" in user_message_lower:
            preferences["day_of_week"] = "Qualquer dia útil"
            
        # Time period
        if "manhã" in user_message_lower or "manha" in user_message_lower:
            preferences["time_period"] = "manhã"
        elif "tarde" in user_message_lower or "tard" in user_message_lower:
            preferences["time_period"] = "tarde"
        elif "qualquer" in user_message_lower or "qual" in user_message_lower:
            preferences["time_period"] = "qualquer"
            
        return preferences
    
    async def _find_available_slots(self, preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find available time slots based on preferences using Google Calendar."""
        try:
            # Define business hours using configuration settings
            start_hour = settings.BUSINESS_HOURS_START  # 8 AM
            end_hour = settings.BUSINESS_HOURS_END      # 6 PM
            business_days = settings.BUSINESS_DAYS      # [0, 1, 2, 3, 4] Monday-Friday
            
            # Map business days to day names
            day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            
            business_hours = {}
            for i, day_name in enumerate(day_names):
                if i in business_days:
                    business_hours[day_name] = [(start_hour, 0), (end_hour, 0)]
                else:
                    business_hours[day_name] = []  # CLOSED
            
            available_slots = []
            
            # Get the next 7 days
            today = datetime.now()
            
            for day_offset in range(7):
                check_date = today + timedelta(days=day_offset)
                day_name = check_date.strftime("%A").lower()
                
                # Skip if no business hours for this day
                if day_name not in business_hours or not business_hours[day_name]:
                    continue
                
                # Filter by day preference
                day_of_week = preferences.get("day_of_week", "").lower()
                if day_of_week and day_of_week not in ["qualquer dia útil", "qualquer"]:
                    portuguese_days = {
                        "segunda": "monday",
                        "terça": "tuesday", 
                        "quarta": "wednesday",
                        "quinta": "thursday",
                        "sexta": "friday"
                    }
                    
                    preferred_day = None
                    for pt_day, en_day in portuguese_days.items():
                        if pt_day in day_of_week:
                            preferred_day = en_day
                            break
                    
                    if preferred_day and preferred_day != day_name:
                        continue
                
                # Get business hours for this day
                hours = business_hours[day_name]
                start_hour, start_minute = hours[0]
                end_hour, end_minute = hours[1]
                
                # Filter by time period preference
                time_period = preferences.get("time_period", "").lower()
                if time_period and time_period != "qualquer":
                    if time_period == "manhã":
                        end_hour = min(end_hour, 12)
                    elif time_period == "tarde":
                        start_hour = max(start_hour, 12)
                        end_hour = min(end_hour, settings.BUSINESS_HOURS_END)
                    elif time_period == "noite":
                        start_hour = max(start_hour, settings.BUSINESS_HOURS_END)
                        # If evening start time is >= business end time, no slots available
                        if start_hour >= settings.BUSINESS_HOURS_END:
                            continue  # Skip this day - no evening slots available
                
                # Generate time slots (1-hour intervals)
                current_hour = start_hour
                while current_hour < end_hour:
                    slot_start = check_date.replace(hour=current_hour, minute=0, second=0, microsecond=0)
                    slot_end = slot_start + timedelta(hours=1)
                    
                    # Check for conflicts in Google Calendar
                    conflicts = await self.calendar_client.check_conflicts(slot_start, slot_end)
                    
                    if not conflicts:  # No conflicts, slot is available
                        available_slots.append({
                            "date": slot_start.strftime("%Y-%m-%d"),
                            "time": slot_start.strftime("%H:%M"),
                            "formatted_time": slot_start.strftime("%d/%m/%Y às %H:%M"),
                            "datetime": slot_start,
                            "is_available": True
                        })
                    
                    current_hour += 1
                
                # Limit to 3 slots maximum
                if len(available_slots) >= 3:
                    break
            
            return available_slots[:3]  # Return maximum 3 slots
            
        except Exception as e:
            app_logger.error(f"Error finding available slots: {str(e)}")
            return []
    
    def _format_available_slots(self, slots: List[Dict[str, Any]]) -> str:
        """Format available slots for display."""
        if not slots:
            return "Nenhum horário disponível no momento."
        
        formatted_slots = []
        for i, slot in enumerate(slots, 1):
            # Format: "1. Segunda-feira, 25/07/2023 às 14:00"
            slot_datetime = slot['datetime']
            day_name = slot_datetime.strftime('%A')
            
            # Translate day names to Portuguese
            portuguese_days = {
                'Monday': 'Segunda-feira',
                'Tuesday': 'Terça-feira', 
                'Wednesday': 'Quarta-feira',
                'Thursday': 'Quinta-feira',
                'Friday': 'Sexta-feira',
                'Saturday': 'Sábado',
                'Sunday': 'Domingo'
            }
            
            pt_day = portuguese_days.get(day_name, day_name)
            formatted_slots.append(f"{i}. {pt_day}, {slot['formatted_time']}")
        
        return "\n".join(formatted_slots)
    
    def _extract_time_selection(self, user_message: str) -> Optional[int]:
        """Extract the selected time slot number from user message."""
        user_message_lower = user_message.lower()
        match = re.search(r'\b(\d)\b', user_message_lower)
        if match:
            return int(match.group(1))
        return None
    
    def _extract_email(self, user_message: str) -> Optional[str]:
        """Extract email from user message."""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, user_message)
        if match:
            return match.group(0)
        return None
    
    async def _create_calendar_event(self, state: ConversationState) -> Dict[str, Any]:
        """Create a calendar event in Google Calendar with proper naming and conversation summary."""
        selected_slot = state.data.get('selected_slot')
        contact_email = state.data.get('contact_email')
        
        if not selected_slot or not contact_email:
            return {"success": False, "message": "Missing selected slot or contact email."}
        
        try:
            # Determine if it's for self or someone else
            is_for_self = state.data.get('is_for_self', False)
            relationship = state.data.get('relationship', 'unknown')
            student_age = state.data.get('student_age', 'unknown')
            
            # Create event title based on naming convention
            if is_for_self:
                # When person is the student
                event_title = f"Apresentação Kumon {state.phone_number}"
                responsible_name = "Próprio interessado"
                student_name = "Próprio interessado"
            else:
                # When person is parent/guardian
                event_title = f"Apresentação Kumon {state.phone_number}"
                responsible_name = "Responsável"
                student_name = "Filho(a)"
            
            # Create conversation summary
            conversation_summary = self._create_conversation_summary(state)
            
            # Create event description
            event_description = f"""
📋 APRESENTAÇÃO KUMON - RESUMO DA CONVERSA

👥 Participantes:
• Responsável: {responsible_name}
• Estudante: {student_name}
• Idade: {student_age} anos
• Relacionamento: {relationship}

📧 Contato:
• WhatsApp: {state.phone_number}
• Email: {contact_email}

📝 Resumo da Conversa:
{conversation_summary}

🎯 Objetivos da Apresentação:
• Explicar metodologia Kumon
• Realizar avaliação diagnóstica
• Esclarecer dúvidas sobre programas
• Apresentar investimento e formas de pagamento
• Definir próximos passos

⏰ Agendamento confirmado via WhatsApp
            """.strip()
            
            # Parse datetime from selected slot
            slot_datetime = selected_slot['datetime']
            event_start = slot_datetime
            event_end = event_start + timedelta(hours=1)  # 1 hour duration
            
            # Create event details for Google Calendar
            event_details = {
                'summary': event_title,
                'description': event_description,
                'start_time': event_start,
                'end_time': event_end,
                'location': 'Kumon Vila A - Unidade',
                'attendees': [contact_email] if contact_email else []
            }
            
            # Create the event using Google Calendar client
            event_id = await self.calendar_client.create_event(event_details)
            
            if event_id and not event_id.startswith('error_'):
                app_logger.info(f"Calendar event created successfully: {event_id}")
                return {"success": True, "event_id": event_id}
            else:
                app_logger.error(f"Failed to create calendar event: {event_id}")
                return {"success": False, "message": f"Calendar API error: {event_id}"}
                
        except Exception as e:
            app_logger.error(f"Error creating calendar event: {str(e)}")
            return {"success": False, "message": f"Failed to create calendar event: {str(e)}"}
    
    def _create_conversation_summary(self, state: ConversationState) -> str:
        """Create a summary of the conversation for the calendar event."""
        summary_parts = []
        
        # Basic information
        if state.data.get('is_for_self'):
            summary_parts.append("• Interesse próprio no método Kumon")
        else:
            summary_parts.append("• Interesse para filho(a)")
        
        if state.data.get('student_age'):
            summary_parts.append(f"• Idade do estudante: {state.data['student_age']} anos")
        
        # Preferences mentioned
        if state.data.get('date_preferences'):
            prefs = state.data['date_preferences']
            if prefs.get('day_of_week'):
                summary_parts.append(f"• Preferência de dia: {prefs['day_of_week']}")
            if prefs.get('time_period'):
                summary_parts.append(f"• Preferência de horário: {prefs['time_period']}")
        
        # Additional context
        summary_parts.append("• Demonstrou interesse em conhecer a metodologia")
        summary_parts.append("• Solicitou apresentação presencial")
        summary_parts.append("• Confirmou disponibilidade para o horário agendado")
        
        return "\n".join(summary_parts)
    
    def _handle_confirmation_stage(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Handle confirmation stage"""
        response = (
            "Muito obrigado pelo seu interesse no Kumon Vila A! 🙏\n\n"
            "Resumindo nossos próximos passos:\n"
            "✅ Entre em contato para agendar uma visita\n"
            "✅ Conhecer nossa unidade e metodologia\n"
            "✅ Fazer uma avaliação gratuita\n"
            "✅ Definir o melhor programa para você\n\n"
            "Estamos na **Rua Amoreira, 571, Salas 6 e 7 - Jardim das Laranjeiras**\n\n"
            "Alguma dúvida específica que posso esclarecer?"
        )
        
        self.update_conversation_state(
            state.phone_number,
            stage=ConversationStage.COMPLETED,
            step=ConversationStep.CONVERSATION_ENDED
        )
        
        return {"message": response, "stage": state.stage.value, "step": state.step.value}
    
    def _handle_follow_up_stage(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Handle follow-up stage"""
        response = (
            "Muito obrigado! Esperamos vê-lo em breve no Kumon Vila A! 😊\n\n"
            "Lembre-se: estamos sempre aqui para ajudar em sua jornada educacional! 🎓"
        )
        
        return {"message": response, "stage": state.stage.value, "step": state.step.value}
    
    def _handle_completed_stage(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Handle completed conversation"""
        response = (
            "Olá novamente! Como posso ajudá-lo hoje? 😊\n\n"
            "Se precisar de mais informações sobre o Kumon ou quiser agendar uma visita, "
            "estou aqui para ajudar!"
        )
        
        # Reset conversation to greeting for new interaction
        self.update_conversation_state(
            state.phone_number,
            stage=ConversationStage.GREETING,
            step=ConversationStep.WELCOME
        )
        
        return {"message": response, "stage": state.stage.value, "step": state.step.value}
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics"""
        total_conversations = len(self.conversation_states)
        stages_count = {}
        
        for state in self.conversation_states.values():
            stage = state.stage.value
            stages_count[stage] = stages_count.get(stage, 0) + 1
        
        return {
            "total_active_conversations": total_conversations,
            "max_conversations": self.max_conversations,
            "timeout_hours": self.conversation_timeout,
            "stages_distribution": stages_count,
            "memory_usage": {
                "states_count": total_conversations,
                "cleanup_interval": self.cleanup_interval
            }
        }
    
    def force_cleanup(self) -> Dict[str, Any]:
        """Force cleanup of old conversations"""
        initial_count = len(self.conversation_states)
        
        # Reset cleanup time to force cleanup
        self.last_cleanup_time = 0
        
        # Run cleanup
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.cleanup_old_conversations())
        
        final_count = len(self.conversation_states)
        removed = initial_count - final_count
        
        return {
            "initial_conversations": initial_count,
            "final_conversations": final_count,
            "removed_conversations": removed
        }


# Global instance
conversation_flow_manager = ConversationFlowManager() 