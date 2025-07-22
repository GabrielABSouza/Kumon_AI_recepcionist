"""
Message processing service
"""
from typing import Dict, Any, Optional
import asyncio

from ..models.message import WhatsAppMessage, MessageResponse, MessageType
from ..services.intent_classifier import IntentClassifier
from ..services.availability_service import AvailabilityService
from ..services.booking_service import BookingService
from ..services.rag_engine import RAGEngine
from ..services.conversation_flow import conversation_flow_manager
from ..core.logger import app_logger
from ..core.config import settings


class MessageProcessor:
    """Main message processing orchestrator"""
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.availability_service = AvailabilityService()
        self.booking_service = BookingService()
        self.rag_engine = RAGEngine()
        self.conversation_flow = conversation_flow_manager
        
        app_logger.info("MessageProcessor initialized")
    
    async def process_message(self, message: WhatsAppMessage) -> MessageResponse:
        """Process incoming WhatsApp message and generate response"""
        
        try:
            # Extract unit context if available
            unit_context = self._extract_unit_context(message)
            
            app_logger.info("Processing message", extra={
                "message_id": message.message_id,
                "from_number": message.from_number,
                "content_length": len(message.content),
                "user_id": unit_context.get("user_id") if unit_context else None
            })
            
            # Check if user is in an active conversation flow
            conversation_state = self.conversation_flow.get_conversation_state(message.from_number)
            
            app_logger.info("Conversation state", extra={
                "phone_number": message.from_number,
                "stage": conversation_state.stage.value,
                "step": conversation_state.step.value
            })
            
            # Process message through conversation flow
            flow_response = await self.conversation_flow.advance_conversation(
                message.from_number, 
                message.content
            )
            
            # Check if human handoff was triggered
            if flow_response.get("human_handoff", False):
                app_logger.info(f"Human handoff triggered for {message.from_number}, reason: {flow_response.get('handoff_reason')}")
                
                return MessageResponse(
                    content=flow_response["message"],
                    message_type=MessageType.TEXT,
                    metadata={
                        "human_handoff": True,
                        "handoff_reason": flow_response.get("handoff_reason"),
                        "conversation_ended": True
                    }
            )
            
            # Check if conversation ended or we should fall back to RAG
            elif flow_response.get("end_conversation", False):
                # Reset conversation state for future interactions
                if message.from_number in self.conversation_flow.conversation_states:
                    del self.conversation_flow.conversation_states[message.from_number]
                
                return MessageResponse(
                    content=flow_response["message"],
                    message_type=MessageType.TEXT,
                    metadata={"conversation_ended": True}
                )
            
            # Check if user asked a specific question that should be handled by RAG
            elif self._should_use_rag(message.content):
                # Use RAG for specific questions while preserving conversation state
                rag_answer = await self.rag_engine.answer_question(
                    message.content, 
                    context=unit_context
                )
                
                # Add context about continuing the conversation
                if rag_answer:
                    rag_answer += f"\n\n---\n\nPara continuar nossa conversa sobre matricular seu filho(a) no Kumon, responda minha pergunta anterior ou diga 'continuar'. 😊"
                
                return MessageResponse(
                    content=rag_answer or "Desculpe, não encontrei uma resposta específica. Vamos continuar nossa conversa?",
                    message_type=MessageType.TEXT,
                    metadata={"rag_answer": True, "conversation_preserved": True}
                )
            
            # Continue with structured conversation flow
            else:
                return MessageResponse(
                    content=flow_response["message"],
                    message_type=MessageType.TEXT,
                    metadata={
                        "conversation_stage": conversation_state.stage.value,
                        "conversation_step": conversation_state.step.value,
                        "conversation_advanced": flow_response.get("advance", False)
                    }
                )
            
        except Exception as e:
            app_logger.error(f"Error processing message: {str(e)}", extra={
                "message_id": message.message_id,
                "from_number": message.from_number
            })
            
            # Send error response
            error_response = MessageResponse(
                content="Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente em alguns minutos.",
                message_type=MessageType.TEXT,
                metadata={"error": True}
            )
            
            return error_response
    
    def _should_use_rag(self, message_content: str) -> bool:
        """Determine if message should be handled by RAG instead of conversation flow"""
        
        # Keywords that indicate specific questions
        rag_keywords = [
            "como funciona", "o que é", "qual", "quanto custa", "preço", "valor",
            "horário", "endereço", "onde fica", "telefone", "email",
            "método kumon", "disciplinas", "matemática", "português", "inglês",
            "kumon connect", "material", "aula", "professor", "orientador"
        ]
        
        message_lower = message_content.lower()
        
        # Check for question words
        if any(word in message_lower for word in ["?", "como", "o que", "qual", "onde", "quando", "quanto", "por que"]):
            return True
        
        # Check for specific keywords
        if any(keyword in message_lower for keyword in rag_keywords):
            return True
        
        return False
    
    def _extract_unit_context(self, message: WhatsAppMessage) -> Optional[Dict[str, Any]]:
        """Extract unit context from message metadata"""
        if not message.metadata:
            return None
        
        unit_context = message.metadata.get("unit_context")
        if unit_context:
            return {
                "user_id": message.metadata.get("user_id"),
                **unit_context
            }
        
        return None
    
    def _get_business_info(self, unit_context: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Get business information with optional unit context"""
        return {
            "name": unit_context.get("username", settings.BUSINESS_NAME),
            "email": unit_context.get("email", settings.BUSINESS_EMAIL),
            "hours": unit_context.get("operating_hours", settings.BUSINESS_HOURS),
            "phone": unit_context.get("phone", ""),
            "address": unit_context.get("address", ""),
            "timezone": unit_context.get("timezone", settings.TIMEZONE)
        }

    async def get_conversation_status(self, phone_number: str) -> Dict[str, Any]:
        """Get conversation status for a phone number"""
        return self.conversation_flow.get_conversation_progress(phone_number)
    
    async def reset_conversation(self, phone_number: str) -> bool:
        """Reset conversation state for a phone number"""
        if phone_number in self.conversation_flow.conversation_states:
            del self.conversation_flow.conversation_states[phone_number]
            app_logger.info(f"Reset conversation for {phone_number}")
            return True
        return False 