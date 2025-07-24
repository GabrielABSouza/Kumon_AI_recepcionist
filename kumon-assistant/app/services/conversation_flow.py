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
    PARENT_NAME_COLLECTION = "parent_name_collection"
    CHILD_NAME_COLLECTION = "child_name_collection"
    
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
    
    # Failure tracking fields
    failed_attempts: int = 0
    consecutive_confusion: int = 0
    same_question_count: int = 0
    last_user_message: str = ""
    dissatisfaction_indicators: List[str] = field(default_factory=list)
    low_quality_responses: int = 0
    
    # NEW: Track clarification attempts
    clarification_attempts: int = 0
    
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
                "description": "Recepção inicial, identificação do interesse e coleta de nomes",
                "steps": [
                    ConversationStep.WELCOME,
                    ConversationStep.INITIAL_RESPONSE,
                    ConversationStep.PARENT_NAME_COLLECTION,
                    ConversationStep.CHILD_NAME_COLLECTION
                ],
                "required_data": ["parent_name", "child_name"],
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
        
        # NEW: Update failure tracking first to detect repetition
        self._update_failure_tracking(state, user_message)
        
        # NEW: Handle repetition with progressive clarification strategy
        if state.same_question_count > 0:
            clarification_response = self._handle_repetition_with_clarification(state, user_message)
            if clarification_response:
                return clarification_response
        
        # CRITICAL CHECK: Detect conversation failure and user dissatisfaction FIRST
        if self._detect_conversation_failure(state, user_message):
            app_logger.warning(f"Conversation failure detected for {phone_number}, redirecting to human support")
            return self._handle_human_handoff(state, user_message)
        
        # GLOBAL CHECK: Always check for booking intent first, regardless of stage
        if self._detect_booking_intent(user_message):
            app_logger.info(f"Booking intent detected for {phone_number}, moving to scheduling")
            return await self._handle_booking_intent(state, user_message)
        
        # GLOBAL CHECK: Handle "no questions" or "no doubts" responses
        if self._detect_skip_questions_intent(user_message):
            app_logger.info(f"Skip questions intent detected for {phone_number}, suggesting appointment")
            return await self._handle_skip_to_booking(state, user_message)
        
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
    
    def _handle_repetition_with_clarification(self, state: ConversationState, user_message: str) -> Optional[Dict[str, Any]]:
        """Handle repetition with progressive clarification strategy"""
        
        # Progressive clarification based on clarification attempts
        if state.same_question_count >= 2:  # Any repetition detected
            if state.clarification_attempts == 0:
                # First repetition: Ask for clarification
                clarification_messages = [
                    "Desculpe, não entendi completamente. Pode explicar de outra forma? 🤔",
                    "Não ficou claro para mim. Pode reformular sua pergunta? 📝",
                    "Acho que não compreendi bem. Pode tentar explicar de forma diferente? 💭"
                ]
                
                response = {
                    "response": clarification_messages[state.message_count % len(clarification_messages)],
                    "stage": state.stage.value,
                    "step": state.step.value,
                    "clarification_requested": True
                }
                
                app_logger.info(f"Clarification requested for {state.phone_number} (attempt {state.clarification_attempts + 1})")
                # Increment clarification attempts and reset counter
                state.clarification_attempts += 1
                state.same_question_count = 0
                return response
                
            elif state.clarification_attempts == 1:
                # Second repetition: Try different approach
                alternative_messages = [
                    "Vou tentar uma abordagem diferente. Pode me dizer especificamente o que você gostaria de saber? 🎯",
                    "Deixe-me tentar de outra forma. Qual é exatamente sua dúvida? ❓",
                    "Vou simplificar. O que você precisa saber sobre o Kumon? 📚"
                ]
                
                response = {
                    "response": alternative_messages[state.message_count % len(alternative_messages)],
                    "stage": state.stage.value,
                    "step": state.step.value,
                    "alternative_approach": True
                }
                
                app_logger.info(f"Alternative approach for {state.phone_number} (attempt {state.clarification_attempts + 1})")
                # Increment clarification attempts and reset counter
                state.clarification_attempts += 1
                state.same_question_count = 0
                return response
                
            elif state.clarification_attempts >= 2:
                # Third repetition: Let failure detection handle handoff
                app_logger.info(f"Third repetition detected for {state.phone_number} (attempt {state.clarification_attempts + 1}), letting failure detection handle")
                # Increment counter so failure detection triggers
                state.clarification_attempts += 1
                return None
        
        # If we reach here, it means same_question_count >= 3, so let failure detection handle it
        return None

    def _detect_conversation_failure(self, state: ConversationState, user_message: str) -> bool:
        """Detect if conversation has failed and needs human intervention"""
        
        # Check for explicit human help requests
        if self._detect_human_help_request(user_message):
            return True
        
        # Check for dissatisfaction patterns
        if self._detect_dissatisfaction(user_message):
            state.dissatisfaction_indicators.append(user_message[:50])
            
        # Failure conditions (any of these triggers human handoff)
        failure_conditions = [
            # Too many consecutive failed attempts (reduced from 3 to 2 for faster response)
            state.failed_attempts >= 2,
            
            # User expressing confusion repeatedly (reduced from 3 to 2)
            state.consecutive_confusion >= 2,
            
            # Same question asked multiple times (increased to 3 for progressive clarification)
            state.same_question_count >= 3 or state.clarification_attempts >= 3,
            
            # Multiple dissatisfaction indicators (reduced from 3 to 2)
            len(state.dissatisfaction_indicators) >= 2,
            
            # Too many low-quality responses (reduced from 3 to 2)
            state.low_quality_responses >= 2,
            
            # Conversation stuck too long in same stage (reduced from 15 to 10 messages)
            state.message_count > 10 and state.stage in [ConversationStage.GREETING, ConversationStage.QUALIFICATION],
            
            # NEW: Stuck in information gathering for too long
            state.message_count > 8 and state.stage == ConversationStage.INFORMATION_GATHERING,
            
            # NEW: Multiple failed attempts in scheduling stage
            state.failed_attempts >= 1 and state.stage == ConversationStage.SCHEDULING
        ]
        
        return any(failure_conditions)
    
    def _detect_human_help_request(self, user_message: str) -> bool:
        """Detect explicit requests for human help"""
        message_lower = user_message.lower()
        
        human_help_patterns = [
            # Direct requests
            "falar com", "atendente", "pessoa", "humano", "representante",
            "funcionário", "funcionaria", "alguém", "operador",
            
            # Indirect requests  
            "não está ajudando", "não entendo", "muito confuso",
            "não serve", "quero ajuda", "preciso de ajuda",
            
            # Frustration expressions
            "desisto", "cansei", "chato", "complicado demais",
            "não funciona", "não resolve", "péssimo"
        ]
        
        return any(pattern in message_lower for pattern in human_help_patterns)
    
    def _detect_dissatisfaction(self, user_message: str) -> bool:
        """Detect user dissatisfaction patterns"""
        message_lower = user_message.lower()
        
        dissatisfaction_patterns = [
            # Confusion indicators
            "não entendi", "não entendo", "confuso", "não ficou claro",
            "não sei", "como assim", "o que", "hein", "que",
            
            # Negative feedback
            "não ajudou", "não serve", "não é isso", "não quero isso",
            "ruim", "péssimo", "horrível", "não gostei",
            
            # Repetition indicators
            "já falei", "já disse", "repetindo", "de novo",
            "outra vez", "sempre a mesma",
            
            # Frustration
            "irritante", "chato", "cansativo", "demora",
            "não funciona", "não adianta", "inútil"
        ]
        
        return any(pattern in message_lower for pattern in dissatisfaction_patterns)
    
    def _update_failure_tracking(self, state: ConversationState, user_message: str) -> None:
        """Update failure tracking metrics"""
        
        # CRITICAL FIX: Check for exact message repetition FIRST (highest priority)
        if state.last_user_message and state.last_user_message.strip().lower() == user_message.strip().lower():
            state.same_question_count += 2  # Penalize exact repetition more heavily
            app_logger.info(f"Exact message repetition detected for {state.phone_number}: '{user_message}'")
        # Then check for similar messages
        elif state.last_user_message:
            similarity = self._calculate_message_similarity(state.last_user_message, user_message)
            if similarity > 0.7:  # 70% similarity threshold
                state.same_question_count += 1
                app_logger.info(f"Similar message detected for {state.phone_number}: similarity={similarity:.2f}")
                    else:
                # Reset counter for different messages
                state.same_question_count = 0
                app_logger.info(f"Counter reset for {state.phone_number}: different message detected")
                        else:
            # First message, no repetition possible
            state.same_question_count = 0
        
        # Check for confusion indicators
        if self._detect_confusion(user_message):
            state.consecutive_confusion += 1
                    else:
            state.consecutive_confusion = 0
        
        # Track very short messages as potential confusion
        if len(user_message.strip()) < 5:
            state.consecutive_confusion += 1
            
        # Update last message
        state.last_user_message = user_message
        
        # Log tracking metrics for debugging
        app_logger.debug(f"Failure tracking for {state.phone_number}: same_question={state.same_question_count}, confusion={state.consecutive_confusion}, failed_attempts={state.failed_attempts}")
    
    def _detect_confusion(self, user_message: str) -> bool:
        """Detect if user is confused by the response"""
        message_lower = user_message.lower()
        
        confusion_indicators = [
            "não entendi", "não entendo", "confuso", "como assim",
            "que", "o que", "hein", "não sei", "não ficou claro",
            "explica melhor", "não compreendi"
        ]
        
        # Check for confusion indicators
        if any(indicator in message_lower for indicator in confusion_indicators):
            return True
        
        # NEW: Detect very short or incomprehensible messages
        if len(user_message.strip()) < 3:
            return True
        
        # NEW: Detect messages that are just punctuation or symbols
        if user_message.strip() in ["?", "!", ".", "...", "??", "!!", "???"]:
            return True
        
        # NEW: Detect messages that are just numbers without context
        if user_message.strip().isdigit() and len(user_message.strip()) < 3:
            return True
        
        return False
    
    def _calculate_message_similarity(self, msg1: str, msg2: str) -> float:
        """Calculate similarity between two messages (simple word overlap)"""
        words1 = set(msg1.lower().split())
        words2 = set(msg2.lower().split())
        
        if not words1 or not words2:
            return 0.0
            
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _handle_human_handoff(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Handle transition to human support"""
        
        # Determine the reason for handoff
        reason = self._get_handoff_reason(state, user_message)
        
        # Log the handoff for analytics
        app_logger.info(f"Human handoff triggered for {state.phone_number}", extra={
            "reason": reason,
            "failed_attempts": state.failed_attempts,
            "message_count": state.message_count,
            "dissatisfaction_count": len(state.dissatisfaction_indicators)
        })
        
        # Personalized handoff message based on reason
        if self._detect_human_help_request(user_message):
            response = (
                "Entendo que você gostaria de falar com uma pessoa! 👥\n\n"
                "Vou conectá-lo com nossa equipe para um atendimento mais personalizado.\n\n"
                "📞 **Entre em contato:**\n"
                "• WhatsApp: **(51) 99692-1999**\n"
                "• Horário: Segunda a Sexta, 8h às 18h\n\n"
                "Nossa equipe terá todo prazer em ajudá-lo! 😊"
            )
        elif reason == "repeated_confusion":
            response = (
                "Percebo que minhas explicações não estão sendo claras o suficiente. 😔\n\n"
                "Para que você tenha todas as informações detalhadas que precisa, "
                "recomendo falar diretamente com nossa equipe especializada!\n\n"
                "📞 **Contato direto:**\n"
                "• WhatsApp: **(51) 99692-1999**\n"
                "• Horário: Segunda a Sexta, 8h às 18h\n\n"
                "Eles poderão esclarecer todas suas dúvidas com muito mais detalhes! ✨"
            )
        elif reason == "conversation_stuck":
            response = (
                "Vejo que nossa conversa está se alongando mais do que deveria! ⏰\n\n"
                "Para agilizar seu atendimento e garantir que você tenha todas as informações "
                "necessárias, que tal falar diretamente com nossa equipe?\n\n"
                "📞 **Atendimento especializado:**\n"
                "• WhatsApp: **(51) 99692-1999**\n"
                "• Horário: Segunda a Sexta, 8h às 18h\n\n"
                "Será muito mais rápido e eficiente! 🚀"
            )
                    else:
            response = (
                "Para garantir que você receba o melhor atendimento possível, "
                "vou direcioná-lo para nossa equipe especializada! 🎯\n\n"
                "📞 **Fale conosco:**\n"
                "• WhatsApp: **(51) 99692-1999**\n"
                "• Horário: Segunda a Sexta, 8h às 18h\n\n"
                "Nossa equipe terá todo prazer em ajudá-lo pessoalmente! 😊"
            )
        
        # Mark conversation as completed to prevent further automated responses
        self.update_conversation_state(
            state.phone_number,
            stage=ConversationStage.COMPLETED,
            step=ConversationStep.CONVERSATION_ENDED,
            data={"handoff_reason": reason, "handoff_timestamp": datetime.now().isoformat()}
        )
                        
                        return {
            "message": response,
            "stage": state.stage.value,
            "step": state.step.value,
            "human_handoff": True,
            "handoff_reason": reason
        }
    
    def _get_handoff_reason(self, state: ConversationState, user_message: str) -> str:
        """Determine the reason for human handoff"""
        
        if self._detect_human_help_request(user_message):
            return "explicit_request"
        elif state.same_question_count >= 3:
            return "repeated_question"
        elif state.consecutive_confusion >= 3:
            return "repeated_confusion"
        elif len(state.dissatisfaction_indicators) >= 3:
            return "user_dissatisfaction"
        elif state.message_count > 15:
            return "conversation_stuck"
        elif state.low_quality_responses >= 3:
            return "poor_response_quality"
            else:
            return "general_failure"
    
    def _detect_booking_intent(self, user_message: str) -> bool:
        """Detect if user wants to book an appointment (global detection)"""
        message_lower = user_message.lower()
        
        # Comprehensive booking keywords - including common variations
        booking_patterns = [
            # Direct booking requests
            "agendar", "marcar", "visita", "horario", "horário", "encontro",
            "agendamento", "marcação", "compromisso", "reunião", "apresentação",
            
            # Intent phrases
            "quero agendar", "quero marcar", "vou agendar", "gostaria de agendar",
            "quero um horário", "quero uma visita", "preciso agendar", "posso agendar",
            "quero marcar um horário", "quero marcar uma visita", "quero conhecer",
            
            # Availability queries
            "quando", "disponibilidade", "livre", "vago", "tem vaga", "tem horário",
            "que horas", "posso ir", "posso visitar", "posso comparecer",
            
            # Immediate intent (handling negation + booking)
            "não, quero agendar", "não quero perguntas", "não tenho dúvidas, quero",
            "só quero agendar", "apenas agendar", "direto ao agendamento"
        ]
        
        # Check for booking patterns
        for pattern in booking_patterns:
            if pattern in message_lower:
                return True
        
        # Pattern matching for complex phrases
        if re.search(r'\b(não|nao).*(agendar|marcar|visita|horário|horario)\b', message_lower):
            return True
        
        if re.search(r'\b(quero|gostaria|preciso|posso).*(agendar|marcar|visita|horário|horario)\b', message_lower):
            return True
        
        return False
    
    def _detect_skip_questions_intent(self, user_message: str) -> bool:
        """Detect if user wants to skip questions and go straight to booking"""
        message_lower = user_message.lower()
        
        skip_patterns = [
            "não tenho dúvidas", "não tenho duvidas", "não tenho perguntas", "não tenho nenhuma pergunta",
            "sem dúvidas", "sem duvidas", "sem perguntas", "sem questões",
            "já conheço", "já sei", "conheço o kumon", "sei como funciona",
            "não quero perguntas", "pula as perguntas", "direto ao ponto",
            "só quero agendar", "apenas agendar", "vamos direto", "não tenho dúvida",
            "não tenho duvida", "não tenho pergunta", "sem dúvida", "sem duvida"
        ]
        
        for pattern in skip_patterns:
            if pattern in message_lower:
                return True
        
        # Pattern for "no" + "want to book"
        if re.search(r'\b(não|nao).*(quero|vou|preciso).*(agendar|marcar)\b', message_lower):
            return True
            
        return False
    
    async def _handle_booking_intent(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Handle direct booking intent from any stage"""
        # Move directly to scheduling stage
        self.update_conversation_state(
            state.phone_number,
            stage=ConversationStage.SCHEDULING,
            step=ConversationStep.APPOINTMENT_SUGGESTION
        )
        
        response = (
            "Perfeito! Vamos agendar uma apresentação para você conhecer melhor o Kumon! 🎯\n\n"
            "Na nossa apresentação, você poderá:\n"
            "• Conhecer nossa metodologia na prática 📚\n"
            "• Fazer uma avaliação diagnóstica gratuita 📝\n"
            "• Conversar com nossa equipe pedagógica 👨‍🏫\n"
            "• Tirar todas as suas dúvidas 💭\n\n"
            "Para que dia você gostaria de agendar? Qual período você prefere: **manhã** ou **tarde**? 🕐"
        )
        
                    return {
            "message": response, 
            "stage": ConversationStage.SCHEDULING.value, 
            "step": ConversationStep.DATE_PREFERENCE.value
        }
    
    async def _handle_skip_to_booking(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Handle when user wants to skip questions and go to booking"""
        # Move directly to scheduling stage
        self.update_conversation_state(
            state.phone_number,
            stage=ConversationStage.SCHEDULING,
            step=ConversationStep.APPOINTMENT_SUGGESTION
        )
        
        response = (
            "Entendo perfeitamente! Vamos direto ao agendamento então! 😊\n\n"
            "Que tal marcarmos uma apresentação da nossa metodologia? "
            "É a melhor forma de conhecer o Kumon na prática!\n\n"
            "Durante a visita você poderá:\n"
            "• Ver nossos materiais didáticos 📚\n"
            "• Fazer uma avaliação diagnóstica gratuita 📝\n"
            "• Conhecer nossa equipe 👨‍🏫\n\n"
            "Qual período é melhor para você: **manhã** ou **tarde**? 🕐"
        )
                    
                    return {
            "message": response, 
            "stage": ConversationStage.SCHEDULING.value, 
            "step": ConversationStep.DATE_PREFERENCE.value
        }
    
    def _handle_greeting_stage(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Handle greeting stage logic with name collection"""
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
                    "Para que eu possa atendê-lo melhor, qual é o seu nome? 😊"
                )
            elif any(word in user_message_lower for word in ["eu", "mim", "mesmo", "minha"]):
                is_for_self = True
                relationship = "próprio interessado"
                response = (
                    "Perfeito! É ótimo ver seu interesse em aprender conosco! 🎯\n\n"
                    "Para que eu possa atendê-lo melhor, qual é o seu nome? 😊"
                )
            else:
                response = (
                    "Entendi! Poderia me dizer um pouco mais sobre para quem seria o Kumon? "
                    "É para você mesmo(a) ou para outra pessoa (filho, filha, etc.)?"
                )
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
            
            # Update state and move to parent name collection
            self.update_conversation_state(
                state.phone_number,
                step=ConversationStep.PARENT_NAME_COLLECTION,
                data={"is_for_self": is_for_self, "relationship": relationship}
            )
            
            return {"message": response, "stage": state.stage.value, "step": state.step.value}
        
        elif state.step == ConversationStep.PARENT_NAME_COLLECTION:
            # Collect parent/responsible person name
            parent_name = user_message.strip()
            
            # Update state with parent name
            self.update_conversation_state(
                state.phone_number,
                data={"parent_name": parent_name}
            )
            
            # Check if we need to collect child name or move to qualification
            is_for_self = state.data.get("is_for_self", False)
            
                if is_for_self:
                # Skip child name collection for self-students
                response = (
                    f"Prazer em conhecê-lo, {parent_name}! 😊\n\n"
                    "Agora me conte: qual é a sua idade? Isso me ajudará a entender melhor suas necessidades de aprendizado."
                )
                
                self.update_conversation_state(
                    state.phone_number,
                    stage=ConversationStage.QUALIFICATION,
                    step=ConversationStep.CHILD_AGE_INQUIRY,
                    data={"child_name": parent_name}  # For self-students, use parent name as student name
                )
            else:
                # Ask for child name
                response = (
                    f"Muito prazer, {parent_name}! 😊\n\n"
                    "Agora me conte: qual é o nome do seu filho(a) que faria o Kumon?"
                )
                
                self.update_conversation_state(
                    state.phone_number,
                    step=ConversationStep.CHILD_NAME_COLLECTION
                )
            
            return {"message": response, "stage": state.stage.value, "step": state.step.value}
        
        elif state.step == ConversationStep.CHILD_NAME_COLLECTION:
            # Collect child name
            child_name = user_message.strip()
            parent_name = state.data.get("parent_name", "")
            
            response = (
                f"Perfeito! É um prazer conhecer você, {parent_name}, e saber sobre o {child_name}! 😊\n\n"
                f"Agora me conte: quantos anos tem o {child_name}? Isso me ajudará a explicar melhor nossos programas."
            )
            
            # Update state and move to qualification
            self.update_conversation_state(
                state.phone_number,
                stage=ConversationStage.QUALIFICATION,
                step=ConversationStep.CHILD_AGE_INQUIRY,
                data={"child_name": child_name}
            )
            
            return {"message": response, "stage": state.stage.value, "step": state.step.value}
        
        return {"message": "Como posso ajudá-lo hoje?", "stage": state.stage.value, "step": state.step.value}
    
    def _handle_qualification_stage(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Handle qualification stage logic"""
        if state.step == ConversationStep.CHILD_AGE_INQUIRY:
            # Extract age information
            age_match = re.search(r'\b(\d{1,2})\b', user_message)
            
            # Get collected names
            child_name = state.data.get("child_name", "")
            is_for_self = state.data.get("is_for_self", False)
            
            if age_match:
                age = int(age_match.group(1))
                
                if age < 3:
                    child_ref = "você" if is_for_self else f"o {child_name}"
                    response = (
                        f"Entendo! Para crianças menores de 3 anos, recomendamos aguardar um pouco mais. "
                        f"O Kumon é mais eficaz a partir dos 3 anos, quando {child_ref} já tem maior concentração. 🧒\n\n"
                        "Gostaria de saber mais sobre quando seria o momento ideal para começar?"
                    )
                elif age <= 18:
                    child_ref = "você" if is_for_self else f"o {child_name}"
                    possessive = "sua" if is_for_self else f"do {child_name}"
                    response = (
                        f"Perfeito! Com {age} anos, {child_ref} está em uma idade excelente para o Kumon! 🎓\n\n"
                        f"Em que série {child_ref} está atualmente? Ou se preferir, pode me contar um pouco sobre "
                        f"o nível de conhecimento atual {possessive} em matemática ou português."
                    )
                else:
                    child_ref = "você" if is_for_self else f"o {child_name}"
                    possessive = "seu" if is_for_self else f"do {child_name}"
                    response = (
                        f"Que bom saber do interesse! Com {age} anos... nunca é tarde para aprender! 💪\n\n"
                        f"Qual é o objetivo principal {possessive}? Reforçar conceitos básicos, se preparar para "
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
        """Handle information gathering stage - answer questions and naturally advance"""
        
        # Initialize tracking if needed
        if 'questions_answered' not in state.data:
            state.data['questions_answered'] = []
        if 'info_gathering_count' not in state.data:
            state.data['info_gathering_count'] = 0
            
        state.data['info_gathering_count'] += 1
        
        # CRITICAL FIX: Check for skip questions intent FIRST
        if self._detect_skip_questions_intent(user_message):
            app_logger.info(f"Skip questions intent detected in information gathering for {state.phone_number}")
            return await self._handle_skip_to_booking(state, user_message)
        
        # Get specific answer based on the question
        answer = self._get_specific_answer(user_message)
        question_category = self._categorize_question(user_message)
        
        if answer and question_category:
            # Mark this category as answered
            if question_category not in state.data['questions_answered']:
                state.data['questions_answered'].append(question_category)
            
            # Check if we should suggest scheduling after this answer
            should_suggest_appointment = (
                len(state.data['questions_answered']) >= 2 or  # After 2 different topics
                state.data['info_gathering_count'] >= 3 or    # After 3 exchanges
                self._is_engagement_question(user_message)    # If they're asking about engagement
            )
            
            if should_suggest_appointment:
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
                
                self.update_conversation_state(
                    state.phone_number,
                    stage=ConversationStage.SCHEDULING,
                    step=ConversationStep.DATE_PREFERENCE
                )
            
            return {
                    "message": response, 
                    "stage": ConversationStage.SCHEDULING.value, 
                    "step": ConversationStep.DATE_PREFERENCE.value
                }
            else:
                # Continue with information gathering
                follow_up = self._get_natural_follow_up(question_category, state.data['questions_answered'])
                response = f"{answer}\n\n{follow_up}"
                
                return {"message": response, "stage": state.stage.value, "step": state.step.value}
                
            else:
            # If we can't categorize the question, try RAG as fallback
            try:
                context = {
                    "conversation_stage": state.stage.value,
                    "user_data": state.data,
                    "phone_number": state.phone_number
                }
                
                rag_response = await enhanced_rag_engine.answer_question(
                    question=user_message,
                    context=context,
                    similarity_threshold=0.6
                )
                
                if rag_response and len(rag_response) > 50:  # If we got a meaningful response
                    return {"message": rag_response, "stage": state.stage.value, "step": state.step.value}
                else:
                    # Track low-quality RAG response
                    state.low_quality_responses += 1
                    app_logger.warning(f"Low quality RAG response for {state.phone_number}, count: {state.low_quality_responses}")
                
            except Exception as e:
                app_logger.error(f"Error with enhanced RAG: {str(e)}")
                state.failed_attempts += 1
                
            # Track that we're falling back to generic response
            state.failed_attempts += 1
            
            # IMPROVED FALLBACK: More intelligent and varied responses
            if state.failed_attempts >= 2:
                # After 2 failed attempts, suggest human contact
                response = (
                    "Percebo que minhas respostas não estão sendo suficientes para suas dúvidas! 🤔\n\n"
                    "Para que você tenha todas as informações detalhadas que precisa, "
                    "recomendo falar diretamente com nossa equipe especializada:\n\n"
                    "📞 **WhatsApp**: (51) 99692-1999\n"
                    "🕐 **Horário**: Segunda a Sexta, 8h às 18h\n\n"
                    "Eles poderão esclarecer tudo com muito mais detalhes! ✨"
                )
            elif state.failed_attempts == 1:
                # First failed attempt - try to redirect to appointment
                response = (
                    "Entendo sua pergunta! 😊\n\n"
                    "Para dar uma resposta mais completa e personalizada, que tal agendar uma conversa? "
                    "Nossa equipe poderá esclarecer todas as suas dúvidas com detalhes específicos para seu caso!\n\n"
                    "Gostaria de agendar uma apresentação? É rápido e sem compromisso! 📅"
                )
            else:
                # Very first attempt - try to clarify
                response = (
                    "Desculpe, não consegui entender exatamente sua pergunta. 😅\n\n"
                    "Poderia reformular de uma forma diferente? Por exemplo:\n"
                    "• 'Como funciona o material?'\n"
                    "• 'Quanto tempo demora para ver resultados?'\n"
                    "• 'Como é o acompanhamento dos professores?'\n\n"
                    "Ou se preferir, posso ajudar a agendar uma visita para esclarecer tudo pessoalmente! 😊"
                )
            
            return {"message": response, "stage": state.stage.value, "step": state.step.value}
    
    def _get_specific_answer(self, user_message: str) -> Optional[str]:
        """Provide specific answers to common questions"""
        message_lower = user_message.lower()
        
        # Material didático
        if any(word in message_lower for word in ["material", "didático", "didatico", "apostila", "livro"]):
            return (
                "📚 **Material Didático Kumon:**\n\n"
                "O material Kumon é único e autoinstrutivo! Cada folha de estudo:\n\n"
                "• **Graduação progressiva**: Aumenta gradualmente a dificuldade\n"
                "• **Autoinstrutivo**: O aluno aprende sozinho, desenvolvendo independência\n"  
                "• **Exemplos claros**: Cada conceito novo vem com exemplos práticos\n"
                "• **Repetição inteligente**: Consolida o aprendizado sem ser monótono\n\n"
                "O material é desenvolvido no Japão e usado mundialmente há mais de 65 anos!"
            )
        
        # Tempo para resultados
        elif any(word in message_lower for word in ["tempo", "resultado", "demora", "quanto tempo", "prazo"]):
            return (
                "⏰ **Tempo para Resultados:**\n\n"
                "Cada criança tem seu próprio ritmo, mas geralmente:\n\n"
                "• **Primeiros 3 meses**: Desenvolvimento do hábito de estudo e concentração\n"
                "• **6 meses**: Melhoras significativas na disciplina e autoconfiança\n"
                "• **1 ano**: Avanços claros no conteúdo acadêmico\n\n"
                "O mais importante não é a velocidade, mas a solidez do aprendizado! 🎯"
            )
        
        # Acompanhamento dos instrutores
        elif any(word in message_lower for word in ["instrutor", "professor", "acompanhamento", "orientador"]):
            return (
                "👨‍🏫 **Acompanhamento dos Orientadores:**\n\n"
                "Nossos orientadores são treinados na metodologia Kumon e:\n\n"
                "• **Observam** o desempenho individual de cada aluno\n"
                "• **Orientam** quando necessário, sem dar respostas prontas\n"
                "• **Ajustam** o ritmo conforme a necessidade de cada criança\n"
                "• **Motivam** e celebram cada conquista do aluno\n\n"
                "O objetivo é desenvolver a independência, não a dependência! 💪"
            )
        
        # Avaliação do progresso
        elif any(word in message_lower for word in ["avaliação", "progresso", "acompanhar", "evolução"]):
            return (
                "📊 **Avaliação do Progresso:**\n\n"
                "Acompanhamos o desenvolvimento através de:\n\n"
                "• **Testes diagnósticos** regulares\n"
                "• **Relatórios de progresso** mensais para os pais\n"
                "• **Observação diária** do desempenho nas atividades\n"
                "• **Reuniões** periódicas com os responsáveis\n\n"
                "Você sempre saberá como seu filho está evoluindo! 📈"
            )
        
        # Método Kumon
        elif any(word in message_lower for word in ["método", "metodologia", "como funciona", "sistema"]):
            return (
                "🎯 **Método Kumon:**\n\n"
                "O Kumon desenvolve ao máximo o potencial de cada aluno através de:\n\n"
                "• **Ensino individualizado**: Cada aluno avança no seu ritmo\n"
                "• **Autodidatismo**: Desenvolve a capacidade de aprender sozinho\n"
                "• **Hábito de estudo**: Cria disciplina e concentração\n"
                "• **Base sólida**: Garante domínio completo antes de avançar\n\n"
                "O objetivo é formar pessoas capazes, confiantes e autodisciplinadas! 🌟"
            )
        
        # Preços
        elif any(word in message_lower for word in ["preço", "valor", "custa", "mensalidade", "investimento"]):
            return (
                "💰 **Investimento Kumon:**\n\n"
                "• **Matemática ou Português**: R$ 150,00/mês por disciplina\n"
                "• **Inglês**: R$ 180,00/mês\n"
                "• **Taxa de matrícula**: R$ 50,00 (única vez)\n\n"
                "**Incluso:**\n"
                "• Material didático\n"
                "• Acompanhamento pedagógico\n"
                "• Relatórios de progresso\n"
                "• 2 aulas por semana na unidade\n\n"
                "É um investimento no futuro! 🎓"
            )
        
        return None
    
    def _categorize_question(self, user_message: str) -> Optional[str]:
        """Categorize the type of question"""
        message_lower = user_message.lower()
        
        if any(word in message_lower for word in ["material", "didático", "apostila", "livro"]):
            return "material"
        elif any(word in message_lower for word in ["tempo", "resultado", "demora", "prazo"]):
            return "tempo"
        elif any(word in message_lower for word in ["instrutor", "professor", "acompanhamento"]):
            return "instrutor"
        elif any(word in message_lower for word in ["avaliação", "progresso", "evolução"]):
            return "avaliacao"
        elif any(word in message_lower for word in ["método", "metodologia", "como funciona"]):
            return "metodologia"
        elif any(word in message_lower for word in ["preço", "valor", "custa", "mensalidade"]):
            return "preco"
        
        return None
    
    def _is_engagement_question(self, user_message: str) -> bool:
        """Check if the question indicates high engagement"""
        message_lower = user_message.lower()
        
        engagement_indicators = [
            "quando", "como começar", "matrícula", "inscrição", "interesse",
            "quero saber mais", "gostaria de", "preciso de", "como funciona na prática"
        ]
        
        return any(indicator in message_lower for indicator in engagement_indicators)
    
    def _get_natural_follow_up(self, answered_category: str, previous_answers: List[str]) -> str:
        """Get natural follow-up questions/responses"""
        
        # If they asked about material, suggest methodology or results
        if answered_category == "material" and "metodologia" not in previous_answers:
            return "Gostaria de saber mais sobre nossa metodologia de ensino? 🤔"
        elif answered_category == "material" and "tempo" not in previous_answers:
            return "Quer saber quanto tempo demora para ver os primeiros resultados? ⏰"
            
        # If they asked about time/results, suggest instructor support or evaluation
        elif answered_category == "tempo" and "instrutor" not in previous_answers:
            return "Que tal saber como nossos orientadores acompanham o desenvolvimento? 👨‍🏫"
        elif answered_category == "tempo" and "avaliacao" not in previous_answers:
            return "Quer entender como avaliamos o progresso do aluno? 📊"
            
        # If they asked about methodology, suggest pricing or material
        elif answered_category == "metodologia" and "preco" not in previous_answers:
            return "Gostaria de conhecer nossos valores de investimento? 💰"
        elif answered_category == "metodologia" and "material" not in previous_answers:
            return "Quer saber mais sobre nosso material didático exclusivo? 📚"
            
        # Generic follow-ups
                else:
            return "Tem mais alguma dúvida específica? Ou gostaria de agendar uma visita para ver tudo na prática? 😊"
    
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
            # Get collected information
            is_for_self = state.data.get('is_for_self', False)
            relationship = state.data.get('relationship', 'unknown')
            student_age = state.data.get('student_age', 'unknown')
            parent_name = state.data.get('parent_name', 'Não informado')
            child_name = state.data.get('child_name', 'Não informado')
            
            # Create event title based on naming convention
                    if is_for_self:
                # When person is the student
                event_title = f"Apresentação Kumon - {parent_name}"
                responsible_name = parent_name
                student_name = parent_name
                    else:
                # When person is parent/guardian
                event_title = f"Apresentação Kumon - {parent_name} e {child_name}"
                responsible_name = parent_name
                student_name = child_name
            
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