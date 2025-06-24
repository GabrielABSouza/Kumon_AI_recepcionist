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
            app_logger.info("Processing message", extra={
                "message_id": message.message_id,
                "from_number": message.from_number,
                "content_length": len(message.content)
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
            
            # Generate response based on intent
            response = await self._generate_response(message, intent)
            
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
    
    async def _generate_response(self, message: WhatsAppMessage, intent) -> MessageResponse:
        """Generate response based on classified intent"""
        
        try:
            # Handle different intent types
            if intent.intent_type == "greeting":
                return MessageResponse(
                    content=f"Olá! Bem-vindo ao {settings.BUSINESS_NAME}! 👋\n\n"
                           "Como posso ajudá-lo hoje? Posso:\n"
                           "📅 Agendar uma consulta\n"
                           "❓ Responder suas dúvidas\n"
                           "📍 Fornecer informações sobre nossos serviços\n\n"
                           "O que você gostaria de fazer?",
                    message_type=MessageType.TEXT,
                    metadata={"intent": intent.intent_type}
                )
            
            elif intent.intent_type == "schedule_appointment":
                # Start booking process
                booking_response = await self.booking_service.start_booking(
                    message.from_number, 
                    message.content
                )
                
                return MessageResponse(
                    content=booking_response,
                    message_type=MessageType.TEXT,
                    metadata={"intent": intent.intent_type, "booking_started": True}
                )
            
            elif intent.intent_type == "question":
                # Use RAG engine to answer questions
                answer = await self.rag_engine.answer_question(message.content)
                
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
                               f"{settings.BUSINESS_PHONE} ou email {settings.BUSINESS_EMAIL}.",
                        message_type=MessageType.TEXT,
                        metadata={"intent": intent.intent_type, "no_answer": True}
                    )
            
            elif intent.intent_type == "business_info":
                return MessageResponse(
                    content=f"📍 **{settings.BUSINESS_NAME}**\n\n"
                           f"📞 Telefone: {settings.BUSINESS_PHONE}\n"
                           f"📧 Email: {settings.BUSINESS_EMAIL}\n"
                           f"📍 Endereço: {settings.BUSINESS_ADDRESS}\n"
                           f"🕒 Horário: {settings.BUSINESS_HOURS}\n\n"
                           "Estamos aqui para ajudar você! 😊",
                    message_type=MessageType.TEXT,
                    metadata={"intent": intent.intent_type}
                )
            
            elif intent.intent_type == "complaint":
                # Collect lead and escalate
                await self.lead_collector.collect_lead(
                    phone_number=message.from_number,
                    message_content=message.content,
                    lead_type="complaint"
                )
                
                return MessageResponse(
                    content="Obrigado por entrar em contato. Sua mensagem foi registrada e nossa equipe "
                           "entrará em contato com você o mais breve possível para resolver sua questão.\n\n"
                           f"Você também pode nos contatar diretamente pelo telefone {settings.BUSINESS_PHONE}.",
                    message_type=MessageType.TEXT,
                    metadata={"intent": intent.intent_type, "escalated": True}
                )
            
            else:
                # Default response for unrecognized intents
                return MessageResponse(
                    content="Obrigado por sua mensagem! 😊\n\n"
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