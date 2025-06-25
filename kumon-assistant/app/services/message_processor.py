"""
Message processing service
"""
from typing import Dict, Any, Optional
import asyncio

from ..models.message import WhatsAppMessage, MessageResponse, MessageType
from ..clients.whatsapp import whatsapp_client, WhatsAppAPIError
from ..services.intent_classifier import IntentClassifier
from ..services.availability_service import AvailabilityService
from ..services.booking_service import BookingService
from ..services.lead_collector import LeadCollector
from ..services.rag_engine import RAGEngine
from ..core.logger import app_logger
from ..core.config import settings


class MessageProcessor:
    """Main message processing orchestrator"""
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.availability_service = AvailabilityService()
        self.booking_service = BookingService()
        self.lead_collector = LeadCollector()
        self.rag_engine = RAGEngine()
        
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
                "unit_id": unit_context.get("unit_id") if unit_context else None
            })
            
            # Mark message as read
            await whatsapp_client.mark_message_as_read(message.message_id)
            
            # Classify intent
            intent = await self.intent_classifier.classify_intent(message.content)
            
            app_logger.info("Intent classified", extra={
                "message_id": message.message_id,
                "intent": intent.intent_type,
                "confidence": intent.confidence
            })
            
            # Generate response based on intent with unit context
            response = await self._generate_response(message, intent, unit_context)
            
            # Send response back to WhatsApp
            await self._send_response(message.from_number, response)
            
            return response
            
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
            
            try:
                await self._send_response(message.from_number, error_response)
            except Exception as send_error:
                app_logger.error(f"Failed to send error response: {str(send_error)}")
            
            return error_response
    
    def _extract_unit_context(self, message: WhatsAppMessage) -> Optional[Dict[str, Any]]:
        """Extract unit context from message metadata"""
        if not message.metadata:
            return None
        
        unit_context = message.metadata.get("unit_context")
        if unit_context:
            return {
                "unit_id": message.metadata.get("unit_id"),
                **unit_context
            }
        
        return None
    
    def _get_business_info(self, unit_context: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """Get business information, preferring unit-specific info over defaults"""
        if unit_context:
            return {
                "name": unit_context.get("unit_name", settings.BUSINESS_NAME),
                "phone": unit_context.get("phone", settings.BUSINESS_PHONE),
                "email": unit_context.get("email", settings.BUSINESS_EMAIL),
                "address": unit_context.get("address", settings.BUSINESS_ADDRESS),
                "hours": unit_context.get("operating_hours", settings.BUSINESS_HOURS),
                "services": unit_context.get("services", "Programas Kumon disponíveis")
            }
        else:
            return {
                "name": settings.BUSINESS_NAME,
                "phone": settings.BUSINESS_PHONE,
                "email": settings.BUSINESS_EMAIL,
                "address": settings.BUSINESS_ADDRESS,
                "hours": settings.BUSINESS_HOURS,
                "services": "Programas Kumon disponíveis"
            }
    
    async def _generate_response(self, message: WhatsAppMessage, intent, unit_context: Optional[Dict[str, Any]] = None) -> MessageResponse:
        """Generate response based on classified intent with unit context"""
        
        try:
            # Get business info (unit-specific or default)
            business_info = self._get_business_info(unit_context)
            
            # Check for custom responses if unit context exists
            custom_response = None
            if unit_context and unit_context.get("unit_id"):
                # Try to get unit-specific custom response
                # This would be implemented with unit_manager in the future
                pass
            
            # Handle different intent types
            if intent.intent_type == "greeting":
                greeting_msg = f"Olá! Bem-vindo ao {business_info['name']}! 👋\n\n"
                
                if custom_response:
                    return MessageResponse(
                        content=custom_response,
                        message_type=MessageType.TEXT,
                        metadata={"intent": intent.intent_type, "unit_specific": True}
                    )
                else:
                    return MessageResponse(
                        content=greeting_msg +
                               "Como posso ajudá-lo hoje? Posso:\n"
                               "📅 Agendar uma consulta\n"
                               "❓ Responder suas dúvidas\n"
                               "📍 Fornecer informações sobre nossos serviços\n\n"
                               "O que você gostaria de fazer?",
                        message_type=MessageType.TEXT,
                        metadata={"intent": intent.intent_type}
                    )
            
            elif intent.intent_type == "schedule_appointment":
                # Start booking process with unit context
                booking_response = await self.booking_service.start_booking(
                    message.from_number, 
                    message.content,
                    unit_context=unit_context
                )
                
                return MessageResponse(
                    content=booking_response,
                    message_type=MessageType.TEXT,
                    metadata={"intent": intent.intent_type, "booking_started": True}
                )
            
            elif intent.intent_type == "question":
                # Use RAG engine to answer questions with unit context
                answer = await self.rag_engine.answer_question(
                    message.content, 
                    context=unit_context
                )
                
                if answer:
                    return MessageResponse(
                        content=answer,
                        message_type=MessageType.TEXT,
                        metadata={"intent": intent.intent_type, "rag_answer": True}
                    )
                else:
                    return MessageResponse(
                        content="Desculpe, não encontrei uma resposta específica para sua pergunta. "
                               "Você pode entrar em contato conosco através do telefone "
                               f"{business_info['phone']} ou email {business_info['email']}.",
                        message_type=MessageType.TEXT,
                        metadata={"intent": intent.intent_type, "no_answer": True}
                    )
            
            elif intent.intent_type == "business_info":
                return MessageResponse(
                    content=f"📍 **{business_info['name']}**\n\n"
                           f"📞 Telefone: {business_info['phone']}\n"
                           f"📧 Email: {business_info['email']}\n"
                           f"📍 Endereço: {business_info['address']}\n"
                           f"🕒 Horário de funcionamento:\n{business_info['hours']}\n\n"
                           f"📚 Nossos programas:\n{business_info['services']}\n\n"
                           "Estamos aqui para ajudar você! 😊",
                    message_type=MessageType.TEXT,
                    metadata={"intent": intent.intent_type}
                )
            
            elif intent.intent_type == "complaint":
                # Collect lead and escalate with unit context
                await self.lead_collector.collect_lead(
                    phone_number=message.from_number,
                    message_content=message.content,
                    lead_type="complaint",
                    unit_context=unit_context
                )
                
                return MessageResponse(
                    content="Obrigado por entrar em contato. Sua mensagem foi registrada e nossa equipe "
                           "entrará em contato com você o mais breve possível para resolver sua questão.\n\n"
                           f"Você também pode nos contatar diretamente pelo telefone {business_info['phone']}.",
                    message_type=MessageType.TEXT,
                    metadata={"intent": intent.intent_type, "escalated": True}
                )
            
            else:
                # Default response for unrecognized intents
                return MessageResponse(
                    content=f"Obrigado por sua mensagem! 😊\n\n"
                           f"Sou o assistente virtual do {business_info['name']}.\n\n"
                           "Posso ajudá-lo com:\n"
                           "📅 Agendamento de consultas\n"
                           "❓ Dúvidas sobre nossos serviços\n"
                           "📍 Informações sobre o Kumon\n\n"
                           "Como posso ajudá-lo?",
                    message_type=MessageType.TEXT,
                    metadata={"intent": intent.intent_type}
                )
        
        except Exception as e:
            app_logger.error(f"Error generating response: {str(e)}")
            return MessageResponse(
                content="Desculpe, ocorreu um erro ao processar sua solicitação. "
                       "Tente novamente ou entre em contato conosco diretamente.",
                message_type=MessageType.TEXT,
                metadata={"error": True}
            )
    
    async def _send_response(self, to_number: str, response: MessageResponse):
        """Send response back to WhatsApp"""
        
        try:
            # Send the message
            result = await whatsapp_client.send_message(
                to_number=to_number,
                message=response.content,
                message_type=response.message_type
            )
            
            app_logger.info("Response sent successfully", extra={
                "to_number": to_number,
                "message_length": len(response.content),
                "whatsapp_message_id": result.get("messages", [{}])[0].get("id")
            })
            
        except WhatsAppAPIError as e:
            app_logger.error(f"WhatsApp API error: {e.message}", extra={
                "to_number": to_number,
                "status_code": e.status_code,
                "response_data": e.response_data
            })
            raise
        
        except Exception as e:
            app_logger.error(f"Unexpected error sending message: {str(e)}", extra={
                "to_number": to_number
            })
            raise 