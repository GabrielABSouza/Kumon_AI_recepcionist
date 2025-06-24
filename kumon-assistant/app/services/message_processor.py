"""
Main message processor - orchestrates all WhatsApp message handling
"""
from typing import Optional
from datetime import datetime

from ..models.message import WhatsAppMessage, MessageResponse, ConversationState
from ..models.booking_request import BookingRequest
from ..core.logger import app_logger
from .intent_classifier import IntentClassifier
from .availability_service import AvailabilityService
from .booking_service import BookingService
from .rag_engine import RAGEngine
from .lead_collector import LeadCollector


class MessageProcessor:
    """Main orchestrator for processing WhatsApp messages"""
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.availability_service = AvailabilityService()
        self.booking_service = BookingService()
        self.rag_engine = RAGEngine()
        self.lead_collector = LeadCollector()
        
        # In-memory conversation state (in production, use Redis or database)
        self.conversation_states = {}
    
    async def process_message(self, message: WhatsAppMessage) -> MessageResponse:
        """Process incoming WhatsApp message and return appropriate response"""
        
        app_logger.info(
            "Processing message",
            extra={
                "user_id": message.from_number,
                "message_id": message.message_id,
                "action": "process_message"
            }
        )
        
        try:
            # Get or create conversation state
            conversation_state = self._get_conversation_state(message.from_number)
            
            # Update last interaction time
            conversation_state.last_message_time = datetime.utcnow()
            
            # Check if we're in the middle of a booking process
            if conversation_state.booking_in_progress:
                return await self._handle_booking_flow(message, conversation_state)
            
            # Classify intent for new messages
            intent = await self.intent_classifier.classify_intent(message.content)
            conversation_state.current_intent = intent
            
            # Route to appropriate handler based on intent
            if intent == "schedule_appointment":
                return await self._handle_scheduling_request(message, conversation_state)
            elif intent == "ask_question":
                return await self._handle_question(message, conversation_state)
            elif intent == "provide_info":
                return await self._handle_lead_collection(message, conversation_state)
            else:
                return await self._handle_general_inquiry(message, conversation_state)
                
        except Exception as e:
            app_logger.error(
                f"Error processing message: {str(e)}",
                extra={
                    "user_id": message.from_number,
                    "message_id": message.message_id,
                    "action": "process_message_error"
                }
            )
            return MessageResponse(
                to_number=message.from_number,
                content="Desculpe, ocorreu um erro. Por favor, tente novamente em alguns minutos."
            )
    
    def _get_conversation_state(self, phone_number: str) -> ConversationState:
        """Get or create conversation state for user"""
        if phone_number not in self.conversation_states:
            self.conversation_states[phone_number] = ConversationState(
                phone_number=phone_number
            )
        return self.conversation_states[phone_number]
    
    async def _handle_scheduling_request(
        self, 
        message: WhatsAppMessage, 
        state: ConversationState
    ) -> MessageResponse:
        """Handle appointment scheduling requests"""
        
        state.booking_in_progress = True
        
        # Start the booking process
        booking_request = await self.booking_service.initiate_booking(message.from_number)
        
        # Get available slots for suggestion
        available_slots = await self.availability_service.get_available_slots(days_ahead=7)
        
        if not available_slots:
            return MessageResponse(
                to_number=message.from_number,
                content="No momento não temos horários disponíveis. Por favor, entre em contato diretamente conosco."
            )
        
        # Suggest some time slots
        suggestion_text = "Ótimo! Vou ajudar você a agendar uma consulta. Temos os seguintes horários disponíveis:\n\n"
        for i, slot in enumerate(available_slots[:3], 1):
            suggestion_text += f"{i}. {slot.date} às {slot.time}\n"
        
        suggestion_text += "\nPor favor, me informe:\n1. Qual horário prefere?\n2. Nome do aluno(a)\n3. Nome do responsável"
        
        return MessageResponse(
            to_number=message.from_number,
            content=suggestion_text
        )
    
    async def _handle_booking_flow(
        self, 
        message: WhatsAppMessage, 
        state: ConversationState
    ) -> MessageResponse:
        """Handle ongoing booking conversation"""
        
        # Continue booking process with user's response
        result = await self.booking_service.process_booking_response(
            message.from_number,
            message.content
        )
        
        if result.get("completed"):
            state.booking_in_progress = False
            # Collect lead information
            await self.lead_collector.update_lead_from_booking(
                message.from_number,
                result.get("booking_request")
            )
        
        return MessageResponse(
            to_number=message.from_number,
            content=result.get("response", "Entendi. Continue...")
        )
    
    async def _handle_question(
        self, 
        message: WhatsAppMessage, 
        state: ConversationState
    ) -> MessageResponse:
        """Handle questions using RAG"""
        
        answer = await self.rag_engine.get_answer(message.content)
        
        # Add scheduling suggestion at the end
        answer += "\n\n💡 Gostaria de agendar uma consulta? É só me avisar!"
        
        return MessageResponse(
            to_number=message.from_number,
            content=answer
        )
    
    async def _handle_lead_collection(
        self, 
        message: WhatsAppMessage, 
        state: ConversationState
    ) -> MessageResponse:
        """Handle lead information collection"""
        
        await self.lead_collector.collect_lead_info(message.from_number, message.content)
        
        return MessageResponse(
            to_number=message.from_number,
            content="Obrigado pelas informações! Nosso time entrará em contato em breve. \n\nEnquanto isso, posso responder alguma dúvida sobre o Kumon ou agendar uma consulta?"
        )
    
    async def _handle_general_inquiry(
        self, 
        message: WhatsAppMessage, 
        state: ConversationState
    ) -> MessageResponse:
        """Handle general inquiries and provide helpful response"""
        
        response = """Olá! Sou a assistente virtual do Kumon. 

Posso te ajudar com:
📚 Informações sobre nossos programas
📅 Agendamento de consultas
❓ Dúvidas sobre metodologia

Como posso te ajudar hoje?"""
        
        return MessageResponse(
            to_number=message.from_number,
            content=response
        ) 