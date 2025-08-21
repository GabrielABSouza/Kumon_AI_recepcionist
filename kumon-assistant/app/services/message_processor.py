"""
Enhanced Message Processing Service with Security Integration
"""
from typing import Dict, Any, Optional
import asyncio

from ..models.message import WhatsAppMessage, MessageResponse, MessageType
from ..services.intent_classifier import IntentClassifier
from ..services.availability_service import AvailabilityService
from ..services.booking_service import BookingService
from ..services.langchain_rag import langchain_rag_service
# Legacy conversation flow removed - now using CeciliaWorkflow only
from ..services.secure_message_processor import secure_message_processor
from ..core.logger import app_logger
from ..core.config import settings


class MessageProcessor:
    """
    Enhanced message processing orchestrator with security integration
    
    Supports both legacy mode and secure mode (Fase 5) with feature flags.
    """
    
    def __init__(self):
        # Legacy components (for backward compatibility)
        self.intent_classifier = IntentClassifier()
        self.availability_service = AvailabilityService()
        self.booking_service = BookingService()
        # Legacy conversation flow removed - using CeciliaWorkflow instead
        
        # Security components (Fase 5)
        self.secure_processor = secure_message_processor
        
        # Feature flags for gradual rollout
        self.use_secure_processing = getattr(settings, 'USE_SECURE_PROCESSING', True)
        self.secure_rollout_percentage = getattr(settings, 'SECURE_ROLLOUT_PERCENTAGE', 100.0)
        
        app_logger.info(f"MessageProcessor initialized - Secure mode: {self.use_secure_processing}")
    
    async def process_message(self, message: WhatsAppMessage) -> MessageResponse:
        """Process incoming WhatsApp message and generate response"""
        
        try:
            app_logger.info("Processing message", extra={
                "message_id": message.message_id,
                "from_number": message.from_number,
                "content_length": len(message.content),
                "secure_mode": self.use_secure_processing
            })
            
            # Route to appropriate processor based on feature flags
            if self.use_secure_processing and self._should_use_secure_mode(message):
                # Use Fase 5 secure processing
                app_logger.info(f"Routing to secure processor: {message.from_number}")
                return await self.secure_processor.process_message(message)
            else:
                # Use legacy processing (backward compatibility)
                app_logger.info(f"Routing to legacy processor: {message.from_number}")
                return await self._process_message_legacy(message)
                
        except Exception as e:
            app_logger.error(f"Message processing failed: {e}", extra={
                "message_id": message.message_id,
                "from_number": message.from_number
            })
            
            # Fallback response
            return MessageResponse(
                content="Desculpe, ocorreu um problema técnico. Entre em contato conosco pelo telefone (51) 99692-1999.",
                message_type=MessageType.TEXT,
                metadata={"error": True, "fallback": True}
            )
    
    def _should_use_secure_mode(self, message: WhatsAppMessage) -> bool:
        """Determine if message should use secure processing"""
        
        # Always use secure mode if enabled and rollout is 100%
        if self.secure_rollout_percentage >= 100.0:
            return True
        
        # Gradual rollout based on phone number hash
        if self.secure_rollout_percentage > 0:
            import hashlib
            phone_hash = hashlib.md5(message.from_number.encode()).hexdigest()
            hash_value = int(phone_hash[:8], 16) % 100
            return hash_value < self.secure_rollout_percentage
        
        return False
    
    async def _process_message_legacy(self, message: WhatsAppMessage) -> MessageResponse:
        """Legacy message processing (backward compatibility)"""
        
        try:
            # Extract unit context if available
            unit_context = self._extract_unit_context(message)
            
            # Legacy conversation flow has been removed - this processor should not be used
            app_logger.warning("MessageProcessor.process_message_legacy called - this should use CeciliaWorkflow instead")
            
            # Return a message directing to the new system
            return MessageResponse(
                content="Sistema atualizado! Agora estou usando o novo CeciliaWorkflow. 😊",
                message_type=MessageType.TEXT,
                metadata={"system": "legacy_deprecated", "recommendation": "use_cecilia_workflow"}
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
        """Get conversation status - deprecated, use CeciliaWorkflow instead"""
        app_logger.warning("MessageProcessor.get_conversation_status called - use CeciliaWorkflow instead")
        return {"status": "deprecated", "use": "cecilia_workflow"}
    
    async def reset_conversation(self, phone_number: str) -> bool:
        """Reset conversation state - deprecated, use CeciliaWorkflow instead"""
        app_logger.warning("MessageProcessor.reset_conversation called - use CeciliaWorkflow instead")
        return False 