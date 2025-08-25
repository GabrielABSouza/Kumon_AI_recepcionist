"""
Secure Message Processor with Integrated Security (Fase 5 Complete)

Replaces the standard message processor with military-grade security:
- Real-time threat detection and mitigation
- Multi-layer input validation and sanitization  
- Comprehensive response quality assurance
- Business scope enforcement (anti-besteiras)
- Information disclosure prevention
- Advanced behavioral analysis and learning
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

from ..core.logger import app_logger
from ..core.config import settings
from ..models.message import WhatsAppMessage, MessageResponse
from ..workflows.secure_conversation_workflow import SecureConversationWorkflow, SecureWorkflowAction
from ..security.security_manager import security_manager


@dataclass
class ProcessingMetrics:
    """Message processing performance metrics"""
    total_messages: int = 0
    processed_messages: int = 0
    blocked_messages: int = 0
    escalated_messages: int = 0
    error_messages: int = 0
    avg_processing_time: float = 0.0
    security_incidents: int = 0
    validation_failures: int = 0


class SecureMessageProcessor:
    """
    Enterprise-grade secure message processor
    
    Implements complete Fase 5 security integration with:
    - Pre-processing threat assessment
    - Real-time input sanitization
    - Multi-layer conversation workflow
    - Post-processing validation
    - Comprehensive audit logging
    - Performance monitoring
    """
    
    def __init__(self):
        # Processing metrics
        self.metrics = ProcessingMetrics()
        
        # Initialize workflow instance via service factory
        self.secure_workflow = None  # Will be initialized lazily
        
        # Processing configuration
        self.config = {
            "max_processing_time": 30.0,  # seconds
            "enable_detailed_logging": True,
            "enable_performance_monitoring": True,
            "auto_escalation_enabled": True,
            "fallback_response_enabled": True,
        }
        
        # Fallback responses for various scenarios
        self.fallback_responses = {
            "security_block": "Por questões de segurança, não posso prosseguir com essa conversa.",
            "processing_error": "Desculpe, ocorreu um problema técnico. Entre em contato conosco pelo telefone (51) 99692-1999.",
            "validation_failure": "Desculpe, vou precisar de um momento para processar sua solicitação adequadamente.",
            "escalation": "Vou transferir você para um de nossos especialistas para melhor atendê-lo. Um momento, por favor!",
            "timeout": "Sua solicitação está demorando para ser processada. Entre em contato conosco pelo telefone (51) 99692-1999."
        }
        
        app_logger.info("Secure Message Processor initialized (Fase 5 Complete)")
    
    async def _get_secure_workflow(self):
        """Get secure workflow instance using unified service resolver"""
        if self.secure_workflow is None:
            from ..core.unified_service_resolver import get_secure_workflow
            self.secure_workflow = await get_secure_workflow()
        return self.secure_workflow
    
    async def process_message(self, whatsapp_message) -> MessageResponse:
        """
        Process WhatsApp message through secure workflow
        
        Args:
            whatsapp_message: Incoming WhatsApp message
            
        Returns:
            Secure, validated response ready for delivery
        """
        
        processing_start = time.time()
        self.metrics.total_messages += 1
        
        # Extract message details - Support both Evolution and Model formats
        phone_number = getattr(whatsapp_message, 'phone', None) or getattr(whatsapp_message, 'from_number', None)
        message_content = getattr(whatsapp_message, 'message', None) or getattr(whatsapp_message, 'content', None)
        message_id = whatsapp_message.message_id
        
        # Prepare processing metadata
        processing_metadata = {
            "message_id": message_id,
            "message_type": getattr(whatsapp_message, 'message_type', 'text'),
            "timestamp": datetime.now(),
            "processing_version": "fase_5_secure",
            "source_identifier": phone_number
        }
        
        try:
            app_logger.info(
                f"Processing message {message_id} from {phone_number}",
                extra=processing_metadata
            )
            
            # Phase 1: Pre-processing Security Validation
            security_pre_check = await self._pre_processing_security_validation(
                phone_number, message_content, processing_metadata
            )
            
            if not security_pre_check["allowed"]:
                self.metrics.blocked_messages += 1
                self.metrics.security_incidents += 1
                
                return self._create_secure_response(
                    whatsapp_message,
                    security_pre_check["response"],
                    processing_metadata
                )
            
            # Phase 2: Input Sanitization and Normalization
            sanitized_content = await self._sanitize_and_normalize_input(
                message_content, processing_metadata
            )
            
            # Phase 3: Secure Workflow Execution
            workflow_result = await self._execute_secure_workflow(
                phone_number, sanitized_content, processing_metadata
            )
            
            # Phase 4: Post-processing Validation and Delivery
            final_response = await self._post_processing_validation(
                workflow_result, whatsapp_message, processing_metadata
            )
            
            # Update metrics
            processing_time = time.time() - processing_start
            self.metrics.processed_messages += 1
            self.metrics.avg_processing_time = (
                (self.metrics.avg_processing_time * (self.metrics.processed_messages - 1) + processing_time) /
                self.metrics.processed_messages
            )
            
            # Log successful processing
            app_logger.info(
                f"Message processed successfully in {processing_time:.2f}s: "
                f"{workflow_result.action_taken.value}",
                extra={**processing_metadata, "processing_time": processing_time}
            )
            
            return final_response
            
        except asyncio.TimeoutError:
            self.metrics.error_messages += 1
            app_logger.error(f"Message processing timeout for {phone_number}")
            
            return self._create_secure_response(
                whatsapp_message,
                self.fallback_responses["timeout"],
                processing_metadata
            )
            
        except Exception as e:
            self.metrics.error_messages += 1
            app_logger.error(
                f"Message processing error for {phone_number}: {e}",
                extra=processing_metadata
            )
            
            return self._create_secure_response(
                whatsapp_message,
                self.fallback_responses["processing_error"],
                processing_metadata
            )
    
    async def _pre_processing_security_validation(
        self,
        phone_number: str,
        message_content: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Comprehensive pre-processing security validation"""
        
        try:
            # Initial security threat assessment
            security_action, security_context = await security_manager.evaluate_security_threat(
                phone_number, message_content, metadata
            )
            
            # DEBUG: Log security action
            app_logger.info(f"DEBUG: Security action={security_action.value}, context keys={list(security_context.keys())}")
            
            # Check for blocking conditions
            if security_action.value in ["block_permanent", "block_temporary"]:
                app_logger.info(f"DEBUG: BLOCKING due to security action: {security_action.value}")
                return {
                    "allowed": False,
                    "response": self.fallback_responses["security_block"],
                    "reason": f"Security action: {security_action.value}",
                    "security_context": security_context
                }
            
            # Check for rate limiting
            elif security_action.value == "rate_limit":
                return {
                    "allowed": False,
                    "response": "Você está enviando mensagens muito rapidamente. Aguarde um momento antes de continuar.",
                    "reason": "Rate limit exceeded",
                    "security_context": security_context
                }
            
            # Additional security checks
            security_score = security_context.get("security_score", 0.0)
            if security_score > 0.8:  # High threat score
                app_logger.warning(
                    f"High security score ({security_score}) for {phone_number}",
                    extra=metadata
                )
                
                # Could implement additional verification here
                
            return {
                "allowed": True,
                "security_context": security_context,
                "security_score": security_score
            }
            
        except Exception as e:
            app_logger.error(f"Pre-processing security validation error: {e}")
            # Fail secure - block on security validation errors
            return {
                "allowed": False,
                "response": self.fallback_responses["security_block"],
                "reason": f"Security validation failed: {str(e)}"
            }
    
    async def _sanitize_and_normalize_input(
        self,
        message_content: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Sanitize and normalize user input"""
        
        try:
            # Use security manager for comprehensive input sanitization
            sanitized_content = await security_manager.sanitize_user_input(message_content)
            
            # Additional normalization
            # Remove excessive whitespace
            sanitized_content = " ".join(sanitized_content.split())
            
            # Limit message length
            max_length = 2000  # 2KB limit
            if len(sanitized_content) > max_length:
                sanitized_content = sanitized_content[:max_length] + "...(truncated)"
                app_logger.warning(
                    f"Message truncated due to length: {len(message_content)} chars",
                    extra=metadata
                )
            
            return sanitized_content
            
        except Exception as e:
            app_logger.error(f"Input sanitization error: {e}")
            # Return original content if sanitization fails
            return message_content
    
    async def _execute_secure_workflow(
        self,
        phone_number: str,
        message_content: str,
        metadata: Dict[str, Any]
    ):
        """Execute the secure conversation workflow"""
        
        try:
            # Execute workflow with timeout
            secure_workflow_instance = await self._get_secure_workflow()
            workflow_task = secure_workflow_instance.process_secure_message(
                phone_number, message_content, metadata
            )
            
            workflow_result = await asyncio.wait_for(
                workflow_task,
                timeout=self.config["max_processing_time"]
            )
            
            return workflow_result
            
        except asyncio.TimeoutError:
            app_logger.error(f"Workflow execution timeout for {phone_number}")
            raise
        except Exception as e:
            app_logger.error(f"Workflow execution error: {e}")
            raise
    
    async def _post_processing_validation(
        self,
        workflow_result,
        original_message: WhatsAppMessage,
        metadata: Dict[str, Any]
    ) -> MessageResponse:
        """Post-processing validation and response preparation"""
        
        try:
            # Handle different workflow actions
            if workflow_result.action_taken == SecureWorkflowAction.BLOCK:
                self.metrics.blocked_messages += 1
                self.metrics.security_incidents += 1
                response_content = self.fallback_responses["security_block"]
                
            elif workflow_result.action_taken == SecureWorkflowAction.ESCALATE:
                self.metrics.escalated_messages += 1
                response_content = self.fallback_responses["escalation"]
                
            elif workflow_result.action_taken == SecureWorkflowAction.END_CONVERSATION:
                response_content = workflow_result.final_response
                
            else:
                # Normal conversation flow
                response_content = workflow_result.final_response
                
                # Validate response quality
                if workflow_result.quality_score < 0.5:
                    self.metrics.validation_failures += 1
                    app_logger.warning(
                        f"Low quality response: {workflow_result.quality_score}",
                        extra=metadata
                    )
            
            # Final security check on response
            final_security_check = await self._final_response_security_check(
                response_content, metadata
            )
            
            if not final_security_check["safe"]:
                response_content = self.fallback_responses["security_block"]
                self.metrics.security_incidents += 1
            
            return self._create_secure_response(
                original_message, response_content, metadata
            )
            
        except Exception as e:
            app_logger.error(f"Post-processing validation error: {e}")
            return self._create_secure_response(
                original_message,
                self.fallback_responses["validation_failure"],
                metadata
            )
    
    async def _final_response_security_check(
        self,
        response_content: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, bool]:
        """Final security check on generated response"""
        
        try:
            # Check for information disclosure
            info_check = await security_manager.info_protection.check_information_request(
                response_content, metadata
            )
            
            if info_check.get("is_sensitive_request", False):
                return {"safe": False, "reason": "Information disclosure detected"}
            
            # Check for scope violations in response
            scope_check = await security_manager.scope_validator.validate_scope(
                response_content, metadata
            )
            
            if not scope_check.get("is_valid_scope", True):
                return {"safe": False, "reason": "Scope violation in response"}
            
            return {"safe": True}
            
        except Exception as e:
            app_logger.error(f"Final security check error: {e}")
            # Fail secure
            return {"safe": False, "reason": f"Security check failed: {str(e)}"}
    
    def _create_secure_response(
        self,
        original_message: WhatsAppMessage,
        content: str,
        metadata: Dict[str, Any]
    ) -> MessageResponse:
        """Create secure message response"""
        
        # Generate secure response ID
        import hashlib
        response_id = hashlib.md5(
            f"{original_message.message_id}_{content}_{datetime.now()}".encode()
        ).hexdigest()[:12]
        
        # Support both Evolution and Model formats
        to_number = getattr(original_message, 'phone', None) or getattr(original_message, 'from_number', None)
        msg_type = getattr(original_message, 'message_type', 'text')
        
        return MessageResponse(
            to_number=to_number,
            content=content,
            message_type=msg_type,
            reply_to_message_id=original_message.message_id
        )
    
    def get_processing_metrics(self) -> Dict[str, Any]:
        """Get comprehensive processing metrics"""
        
        success_rate = (
            self.metrics.processed_messages / max(1, self.metrics.total_messages)
        )
        
        security_incident_rate = (
            self.metrics.security_incidents / max(1, self.metrics.total_messages)
        )
        
        return {
            "processing_metrics": {
                "total_messages": self.metrics.total_messages,
                "processed_messages": self.metrics.processed_messages,
                "blocked_messages": self.metrics.blocked_messages,
                "escalated_messages": self.metrics.escalated_messages,
                "error_messages": self.metrics.error_messages,
                "avg_processing_time": self.metrics.avg_processing_time
            },
            "security_metrics": {
                "security_incidents": self.metrics.security_incidents,
                "validation_failures": self.metrics.validation_failures,
                "security_incident_rate": security_incident_rate
            },
            "performance_metrics": {
                "success_rate": success_rate,
                "error_rate": self.metrics.error_messages / max(1, self.metrics.total_messages),
                "block_rate": self.metrics.blocked_messages / max(1, self.metrics.total_messages),
                "escalation_rate": self.metrics.escalated_messages / max(1, self.metrics.total_messages)
            },
            "configuration": self.config,
            "status": "OPERATIONAL - Military-grade security active"
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        
        try:
            # Check core components
            security_status = security_manager.get_security_metrics()
            secure_workflow_instance = await self._get_secure_workflow()
            workflow_status = secure_workflow_instance.get_security_metrics()
            
            # Test security responsiveness
            test_start = time.time()
            test_result = await security_manager.evaluate_security_threat(
                "health_check", "test message", {"test": True}
            )
            security_response_time = (time.time() - test_start) * 1000  # ms
            
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "secure_message_processor": "operational",
                    "security_manager": "operational" if security_status else "degraded",
                    "secure_workflow": "operational" if workflow_status else "degraded"
                },
                "performance": {
                    "security_response_time_ms": security_response_time,
                    "avg_processing_time": self.metrics.avg_processing_time
                },
                "security_level": "MILITARY_GRADE",
                "processing_metrics": self.get_processing_metrics()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "components": {
                    "secure_message_processor": "degraded"
                }
            }


# Global secure message processor instance
secure_message_processor = SecureMessageProcessor()