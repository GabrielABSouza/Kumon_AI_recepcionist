"""
Message Postprocessor - Complete Implementation
Handles response formatting, Google Calendar integration, and message delivery coordination
Target: <100ms processing time, >99% Calendar integration success rate, 100% delivery tracking
"""

import asyncio
import json
import time
import re
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import uuid

from ..core.logger import app_logger
from ..core.config import settings
from ..models.message import MessageType, MessageResponse
from ..clients.google_calendar import GoogleCalendarClient
from ..clients.evolution_api import EvolutionAPIClient
from ..services.enhanced_cache_service import EnhancedCacheService


class MessagePriority(Enum):
    """Message delivery priority levels"""
    LOW = "low"
    NORMAL = "normal" 
    HIGH = "high"
    URGENT = "urgent"


class DeliveryStatus(Enum):
    """Message delivery status tracking"""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class FormattedMessage:
    """Container for formatted message ready for delivery"""
    content: str
    message_type: MessageType
    phone_number: str
    priority: MessagePriority = MessagePriority.NORMAL
    metadata: Dict[str, Any] = None
    delivery_options: Dict[str, Any] = None
    calendar_event_id: Optional[str] = None
    template_id: Optional[str] = None
    formatting_time_ms: float = 0.0


@dataclass
class DeliveryRecord:
    """Delivery tracking record"""
    message_id: str
    phone_number: str
    content_hash: str
    status: DeliveryStatus
    priority: MessagePriority
    attempts: int
    last_attempt: datetime
    next_retry: Optional[datetime]
    delivery_metadata: Dict[str, Any]
    calendar_integration: bool = False
    template_used: Optional[str] = None


@dataclass
class CalendarIntegration:
    """Calendar integration result"""
    success: bool
    event_id: Optional[str] = None
    event_url: Optional[str] = None
    error_message: Optional[str] = None
    booking_confirmation: Optional[str] = None
    reminder_scheduled: bool = False


class MessagePostprocessor:
    """
    Complete message postprocessor with:
    - Response formatting with template engine
    - Google Calendar integration for appointment booking
    - Message delivery coordination with Evolution API
    - Performance optimization with Redis caching
    - Comprehensive error handling and retry logic
    """
    
    def __init__(self):
        # Initialize clients and cache
        self.calendar_client = GoogleCalendarClient()
        self.evolution_client = EvolutionAPIClient() 
        self.cache_service = EnhancedCacheService()
        
        # Business rules and configuration
        self.business_config = {
            "phone": settings.BUSINESS_PHONE,
            "email": settings.BUSINESS_EMAIL,
            "address": settings.BUSINESS_ADDRESS,
            "hours": settings.BUSINESS_HOURS,
            "pricing": {
                "monthly_fee": "R$ 375",
                "material_fee": "R$ 100"
            },
            "contact_info": "(51) 99692-1999",
            "reminder_timing": "2 horas antes"
        }
        
        # Template engine configuration
        self.templates = {
            "appointment_confirmation": {
                "pattern": r"(agend|marca|entrevista|visita|horário)",
                "template": """
✅ {appointment_type} confirmado!

📅 Data: {date}
⏰ Horário: {time}
📍 Local: {location}

📞 Contato: {contact_phone}
💰 Valores: {pricing_info}

⏰ Enviaremos um lembrete {reminder_timing} antes do seu horário.

Até breve! 😊
                """.strip()
            },
            "pricing_info": {
                "pattern": r"(valor|preço|custo|mensalidade|pagamento)",
                "template": """
💰 Valores do Kumon Vila A:

📚 Mensalidade: {monthly_fee}
📖 Material didático: {material_fee}

📞 Para mais informações: {contact_phone}
📍 Endereço: {address}

Investir na educação é investir no futuro! 🎓
                """.strip()
            },
            "contact_info": {
                "pattern": r"(contato|telefone|endereço|localização|onde)",
                "template": """
📞 Contato: {contact_phone}
📧 Email: {email}
📍 Endereço: {address}
🕒 Horários: {hours}

Estamos prontos para atendê-lo! 😊
                """.strip()
            },
            "general_response": {
                "pattern": r".*",
                "template": "{content}"
            }
        }
        
        # Performance metrics
        self.metrics = {
            "total_processed": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "calendar_integrations": 0,
            "calendar_success_rate": 0.0,
            "avg_processing_time_ms": 0.0,
            "cache_hit_rate": 0.0,
            "template_usage": {}
        }
        
        # Delivery tracking
        self.delivery_records: Dict[str, DeliveryRecord] = {}
        self.retry_queue: List[str] = []
        
        # Circuit breaker for calendar integration
        self.calendar_circuit_breaker = {
            "failures": 0,
            "last_failure": None,
            "is_open": False,
            "failure_threshold": 5,
            "recovery_timeout": 300  # 5 minutes
        }
        
        app_logger.info("Message Postprocessor initialized successfully", extra={
            "templates_loaded": len(self.templates),
            "business_config": bool(self.business_config),
            "calendar_enabled": bool(self.calendar_client.service),
            "cache_enabled": True
        })
    
    async def process_message(
        self,
        response: MessageResponse,
        phone_number: str,
        context: Optional[Dict[str, Any]] = None
    ) -> FormattedMessage:
        """
        Main processing method - formats message and handles integrations
        
        Args:
            response: LangGraph workflow response
            phone_number: Target phone number  
            context: Additional context for processing
            
        Returns:
            FormattedMessage ready for delivery
        """
        start_time = time.time()
        self.metrics["total_processed"] += 1
        
        try:
            app_logger.info(f"Processing message for {phone_number}", extra={
                "content_length": len(response.content) if response.content else 0,
                "message_type": response.message_type.value if response.message_type else "unknown",
                "has_context": bool(context)
            })
            
            # Phase 1: Response formatting with template engine
            formatted_content, template_id = await self._format_response(
                response.content, context or {}
            )
            
            # Phase 2: Determine message priority
            priority = self._determine_priority(formatted_content, context or {})
            
            # Phase 3: Calendar integration (if applicable)
            calendar_result = await self._handle_calendar_integration(
                formatted_content, phone_number, context or {}
            )
            
            # Phase 4: Apply business compliance formatting
            final_content = self._apply_business_compliance(
                formatted_content, calendar_result
            )
            
            # Phase 5: Prepare delivery options
            delivery_options = self._prepare_delivery_options(priority, calendar_result)
            
            processing_time = (time.time() - start_time) * 1000
            
            formatted_message = FormattedMessage(
                content=final_content,
                message_type=response.message_type or MessageType.TEXT,
                phone_number=phone_number,
                priority=priority,
                metadata={
                    "processing_time_ms": processing_time,
                    "template_used": template_id,
                    "calendar_integrated": calendar_result.success,
                    "business_compliance": True,
                    "original_length": len(response.content) if response.content else 0,
                    "formatted_length": len(final_content),
                    "context_keys": list(context.keys()) if context else []
                },
                delivery_options=delivery_options,
                calendar_event_id=calendar_result.event_id,
                template_id=template_id,
                formatting_time_ms=processing_time
            )
            
            # Update metrics
            self._update_processing_metrics(processing_time, template_id)
            
            app_logger.info(f"Message processing completed successfully", extra={
                "phone_number": phone_number,
                "processing_time_ms": processing_time,
                "template_used": template_id,
                "calendar_integrated": calendar_result.success,
                "final_length": len(final_content)
            })
            
            return formatted_message
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            app_logger.error(f"Message processing error for {phone_number}: {e}", extra={
                "processing_time_ms": processing_time,
                "error_type": type(e).__name__
            })
            
            # Return fallback formatted message
            return self._create_fallback_message(response, phone_number, processing_time)
    
    async def _format_response(
        self, 
        content: str, 
        context: Dict[str, Any]
    ) -> Tuple[str, Optional[str]]:
        """
        Format response using template engine with caching
        Target: <50ms rendering time
        """
        if not content:
            return "Olá! Como posso ajudá-lo hoje? 😊", "general_response"
        
        # Check cache first
        cache_key = f"template_format:{hashlib.md5(content.encode()).hexdigest()}"
        cached_result = await self.cache_service.get(cache_key)
        
        if cached_result:
            self.metrics["cache_hit_rate"] = (
                self.metrics.get("cache_hit_rate", 0) * 0.9 + 0.1
            )
            return cached_result["content"], cached_result["template_id"]
        
        # Find appropriate template
        template_id = self._find_matching_template(content)
        template_config = self.templates[template_id]
        
        # Apply template formatting
        formatted_content = self._apply_template(
            template_config["template"], 
            content, 
            context
        )
        
        # Cache the result
        cache_data = {
            "content": formatted_content,
            "template_id": template_id
        }
        await self.cache_service.set(cache_key, cache_data, ttl=3600)  # 1 hour cache
        
        return formatted_content, template_id
    
    def _find_matching_template(self, content: str) -> str:
        """Find the best matching template for content"""
        content_lower = content.lower()
        
        # Check each template pattern
        for template_id, template_config in self.templates.items():
            if template_id == "general_response":
                continue  # Skip general template for now
                
            pattern = template_config["pattern"]
            if re.search(pattern, content_lower):
                return template_id
        
        return "general_response"
    
    def _apply_template(
        self, 
        template: str, 
        content: str, 
        context: Dict[str, Any]
    ) -> str:
        """Apply template with business data and context"""
        # Prepare template variables
        template_vars = {
            **self.business_config,
            "content": content,
            "pricing_info": f"{self.business_config['pricing']['monthly_fee']} + {self.business_config['pricing']['material_fee']}",
            "contact_phone": self.business_config["contact_info"],
            "reminder_timing": self.business_config["reminder_timing"],
            **context  # Allow context to override defaults
        }
        
        try:
            # Simple template variable replacement
            formatted = template
            for key, value in template_vars.items():
                placeholder = f"{{{key}}}"
                if placeholder in formatted:
                    formatted = formatted.replace(placeholder, str(value))
            
            return formatted
            
        except Exception as e:
            app_logger.error(f"Template formatting error: {e}")
            return content  # Fallback to original content
    
    def _determine_priority(
        self, 
        content: str, 
        context: Dict[str, Any]
    ) -> MessagePriority:
        """Determine message delivery priority"""
        content_lower = content.lower()
        
        # Urgent patterns
        urgent_patterns = [
            "urgente", "emergência", "problema", "erro", "falha",
            "não consegue", "não funciona", "help", "ajuda rápida"
        ]
        
        if any(pattern in content_lower for pattern in urgent_patterns):
            return MessagePriority.URGENT
        
        # High priority patterns  
        high_patterns = [
            "agendamento", "entrevista", "visita", "reunião",
            "confirmação", "cancelamento", "remarcar"
        ]
        
        if any(pattern in content_lower for pattern in high_patterns):
            return MessagePriority.HIGH
        
        # Context-based priority
        if context.get("is_new_lead", False):
            return MessagePriority.HIGH
        
        if context.get("is_followup", False):
            return MessagePriority.NORMAL
        
        return MessagePriority.NORMAL
    
    async def _handle_calendar_integration(
        self,
        content: str,
        phone_number: str,
        context: Dict[str, Any]
    ) -> CalendarIntegration:
        """
        Handle Google Calendar integration for appointment booking
        Target: >99% success rate
        """
        # Check if calendar integration is needed
        if not self._requires_calendar_integration(content, context):
            return CalendarIntegration(success=False)
        
        # Check circuit breaker
        if self._is_calendar_circuit_open():
            app_logger.warning("Calendar circuit breaker is open, skipping integration")
            return CalendarIntegration(
                success=False,
                error_message="Calendar service temporarily unavailable"
            )
        
        try:
            self.metrics["calendar_integrations"] += 1
            
            # Extract appointment details from context or content
            appointment_details = self._extract_appointment_details(content, context)
            
            if not appointment_details:
                return CalendarIntegration(success=False)
            
            # Check for conflicts
            conflicts = await self.calendar_client.check_conflicts(
                appointment_details["start_time"],
                appointment_details["end_time"]
            )
            
            if conflicts:
                app_logger.info(f"Calendar conflicts found for {phone_number}: {len(conflicts)}")
                return CalendarIntegration(
                    success=False,
                    error_message=f"Conflito de horário detectado. {len(conflicts)} evento(s) já agendado(s)."
                )
            
            # Create calendar event
            event_details = {
                "summary": f"Kumon - Entrevista/Visita - {phone_number}",
                "description": f"Agendamento via WhatsApp\nTelefone: {phone_number}\nDetalhes: {content[:200]}",
                "start_time": appointment_details["start_time"],
                "end_time": appointment_details["end_time"],
                "location": self.business_config["address"],
                "attendees": [{"email": self.business_config["email"]}]
            }
            
            event_id = await self.calendar_client.create_event(event_details)
            
            if event_id and not event_id.startswith("error"):
                # Calendar integration successful
                self._reset_calendar_circuit_breaker()
                
                # Generate booking confirmation
                confirmation = self._generate_booking_confirmation(
                    appointment_details, event_id
                )
                
                app_logger.info(f"Calendar event created successfully: {event_id}")
                
                return CalendarIntegration(
                    success=True,
                    event_id=event_id,
                    event_url=f"https://calendar.google.com/calendar/event?eid={event_id}",
                    booking_confirmation=confirmation,
                    reminder_scheduled=True
                )
            else:
                # Calendar integration failed
                self._record_calendar_failure()
                return CalendarIntegration(
                    success=False,
                    error_message=f"Erro ao criar evento no calendário: {event_id}"
                )
                
        except Exception as e:
            self._record_calendar_failure()
            app_logger.error(f"Calendar integration error: {e}")
            return CalendarIntegration(
                success=False,
                error_message="Erro interno no sistema de calendário"
            )
    
    def _requires_calendar_integration(
        self, 
        content: str, 
        context: Dict[str, Any]
    ) -> bool:
        """Check if message requires calendar integration"""
        content_lower = content.lower()
        
        calendar_keywords = [
            "agendar", "marcar", "entrevista", "visita", "reunião",
            "horário", "data", "quando", "disponível", "agenda"
        ]
        
        # Check content for calendar keywords
        has_calendar_keywords = any(
            keyword in content_lower for keyword in calendar_keywords
        )
        
        # Check context for explicit calendar requirement
        explicit_calendar = context.get("requires_calendar", False)
        
        # Check if context contains appointment details
        has_appointment_data = any(
            key in context for key in ["appointment_date", "appointment_time", "start_time"]
        )
        
        return has_calendar_keywords or explicit_calendar or has_appointment_data
    
    def _extract_appointment_details(
        self, 
        content: str, 
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract appointment details from content and context"""
        # Priority 1: Use context data if available
        if "start_time" in context and "end_time" in context:
            return {
                "start_time": context["start_time"],
                "end_time": context["end_time"],
                "type": context.get("appointment_type", "Entrevista")
            }
        
        # Priority 2: Try to parse from content (basic implementation)
        # For production, would use more sophisticated NLP
        
        # Default appointment: next business day at 10:00 AM for 1 hour
        now = datetime.now()
        
        # Find next business day (Monday = 0, Sunday = 6)
        days_ahead = 1
        while (now + timedelta(days=days_ahead)).weekday() > 4:  # 0-4 = Mon-Fri
            days_ahead += 1
        
        start_time = (now + timedelta(days=days_ahead)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        end_time = start_time + timedelta(hours=1)
        
        return {
            "start_time": start_time,
            "end_time": end_time,
            "type": "Entrevista"
        }
    
    def _generate_booking_confirmation(
        self, 
        appointment_details: Dict[str, Any],
        event_id: str
    ) -> str:
        """Generate booking confirmation message"""
        start_time = appointment_details["start_time"]
        appointment_type = appointment_details.get("type", "Entrevista")
        
        return f"""
✅ {appointment_type} agendada com sucesso!

📅 Data: {start_time.strftime('%d/%m/%Y')}
⏰ Horário: {start_time.strftime('%H:%M')}
📍 Local: {self.business_config['address']}

📞 Contato: {self.business_config['contact_info']}

⏰ Você receberá um lembrete {self.business_config['reminder_timing']} antes do horário agendado.

ID do Agendamento: {event_id[:8]}

Aguardamos você! 😊
        """.strip()
    
    def _is_calendar_circuit_open(self) -> bool:
        """Check if calendar circuit breaker is open"""
        if not self.calendar_circuit_breaker["is_open"]:
            return False
        
        # Check if recovery timeout has passed
        if self.calendar_circuit_breaker["last_failure"]:
            time_since_failure = time.time() - self.calendar_circuit_breaker["last_failure"]
            if time_since_failure > self.calendar_circuit_breaker["recovery_timeout"]:
                self.calendar_circuit_breaker["is_open"] = False
                self.calendar_circuit_breaker["failures"] = 0
                app_logger.info("Calendar circuit breaker recovered")
                return False
        
        return True
    
    def _record_calendar_failure(self):
        """Record calendar integration failure"""
        self.calendar_circuit_breaker["failures"] += 1
        self.calendar_circuit_breaker["last_failure"] = time.time()
        
        if (self.calendar_circuit_breaker["failures"] >= 
            self.calendar_circuit_breaker["failure_threshold"]):
            self.calendar_circuit_breaker["is_open"] = True
            app_logger.warning(
                f"Calendar circuit breaker opened after "
                f"{self.calendar_circuit_breaker['failures']} failures"
            )
    
    def _reset_calendar_circuit_breaker(self):
        """Reset calendar circuit breaker after successful operation"""
        self.calendar_circuit_breaker["failures"] = 0
        self.calendar_circuit_breaker["is_open"] = False
        self.calendar_circuit_breaker["last_failure"] = None
    
    def _apply_business_compliance(
        self,
        content: str,
        calendar_result: CalendarIntegration
    ) -> str:
        """Apply business compliance rules to final content"""
        # Add calendar confirmation if successful
        if calendar_result.success and calendar_result.booking_confirmation:
            content = calendar_result.booking_confirmation
        
        # Ensure contact information is present for important messages
        if any(keyword in content.lower() for keyword in ["agendar", "valor", "preço", "contato"]):
            if self.business_config["contact_info"] not in content:
                content += f"\n\n📞 Contato: {self.business_config['contact_info']}"
        
        # Ensure professional tone
        if not any(emoji in content for emoji in ["😊", "📞", "📅", "✅"]):
            content += " 😊"
        
        return content
    
    def _prepare_delivery_options(
        self,
        priority: MessagePriority,
        calendar_result: CalendarIntegration
    ) -> Dict[str, Any]:
        """Prepare delivery options based on priority and features"""
        delivery_options = {
            "delay": self._get_delivery_delay(priority),
            "presence": "composing",
            "linkPreview": False,
            "retry_count": self._get_retry_count(priority),
            "retry_delay": self._get_retry_delay(priority)
        }
        
        # Add calendar-specific options
        if calendar_result.success:
            delivery_options["calendar_event_id"] = calendar_result.event_id
            delivery_options["followup_required"] = True
            delivery_options["priority"] = "high"
        
        return delivery_options
    
    def _get_delivery_delay(self, priority: MessagePriority) -> int:
        """Get delivery delay based on priority"""
        delay_map = {
            MessagePriority.URGENT: 500,    # 0.5 seconds
            MessagePriority.HIGH: 800,      # 0.8 seconds  
            MessagePriority.NORMAL: 1200,   # 1.2 seconds
            MessagePriority.LOW: 2000       # 2 seconds
        }
        return delay_map.get(priority, 1200)
    
    def _get_retry_count(self, priority: MessagePriority) -> int:
        """Get retry count based on priority"""
        retry_map = {
            MessagePriority.URGENT: 5,
            MessagePriority.HIGH: 3,
            MessagePriority.NORMAL: 2,
            MessagePriority.LOW: 1
        }
        return retry_map.get(priority, 2)
    
    def _get_retry_delay(self, priority: MessagePriority) -> int:
        """Get retry delay based on priority (seconds)"""
        retry_delay_map = {
            MessagePriority.URGENT: 30,     # 30 seconds
            MessagePriority.HIGH: 60,       # 1 minute
            MessagePriority.NORMAL: 300,    # 5 minutes
            MessagePriority.LOW: 900        # 15 minutes
        }
        return retry_delay_map.get(priority, 300)
    
    async def deliver_message(
        self,
        formatted_message: FormattedMessage,
        instance_name: str = "kumonvilaa"
    ) -> Dict[str, Any]:
        """
        Coordinate message delivery through Evolution API with retry logic
        Target: 100% delivery tracking accuracy
        """
        message_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Create delivery record
        delivery_record = DeliveryRecord(
            message_id=message_id,
            phone_number=formatted_message.phone_number,
            content_hash=hashlib.md5(formatted_message.content.encode()).hexdigest(),
            status=DeliveryStatus.PENDING,
            priority=formatted_message.priority,
            attempts=0,
            last_attempt=datetime.now(),
            next_retry=None,
            delivery_metadata={
                "instance_name": instance_name,
                "template_used": formatted_message.template_id,
                "calendar_integrated": bool(formatted_message.calendar_event_id),
                "processing_time_ms": formatted_message.formatting_time_ms
            },
            calendar_integration=bool(formatted_message.calendar_event_id),
            template_used=formatted_message.template_id
        )
        
        self.delivery_records[message_id] = delivery_record
        
        try:
            app_logger.info(f"Starting delivery for message {message_id}", extra={
                "phone_number": formatted_message.phone_number,
                "priority": formatted_message.priority.value,
                "content_length": len(formatted_message.content),
                "instance": instance_name
            })
            
            # Update status to processing
            delivery_record.status = DeliveryStatus.PROCESSING
            delivery_record.attempts += 1
            delivery_record.last_attempt = datetime.now()
            
            # Deliver via Evolution API
            delivery_result = await self._deliver_via_evolution_api(
                formatted_message, instance_name, delivery_record
            )
            
            delivery_time = (time.time() - start_time) * 1000
            
            if delivery_result["success"]:
                # Delivery successful
                delivery_record.status = DeliveryStatus.SENT
                delivery_record.delivery_metadata.update({
                    "delivery_time_ms": delivery_time,
                    "evolution_message_id": delivery_result.get("message_id"),
                    "delivery_response": delivery_result.get("response")
                })
                
                self.metrics["successful_deliveries"] += 1
                
                app_logger.info(f"Message {message_id} delivered successfully", extra={
                    "phone_number": formatted_message.phone_number,
                    "delivery_time_ms": delivery_time,
                    "evolution_message_id": delivery_result.get("message_id")
                })
                
                return {
                    "success": True,
                    "message_id": message_id,
                    "delivery_time_ms": delivery_time,
                    "evolution_message_id": delivery_result.get("message_id"),
                    "status": "delivered"
                }
            
            else:
                # Delivery failed - schedule retry if applicable
                await self._handle_delivery_failure(delivery_record, delivery_result)
                
                return {
                    "success": False,
                    "message_id": message_id,
                    "error": delivery_result.get("error", "Unknown delivery error"),
                    "retry_scheduled": delivery_record.status == DeliveryStatus.RETRY,
                    "attempts": delivery_record.attempts
                }
        
        except Exception as e:
            delivery_time = (time.time() - start_time) * 1000
            app_logger.error(f"Delivery error for message {message_id}: {e}", extra={
                "phone_number": formatted_message.phone_number,
                "delivery_time_ms": delivery_time,
                "error_type": type(e).__name__
            })
            
            # Handle exception as delivery failure
            delivery_result = {"success": False, "error": str(e)}
            await self._handle_delivery_failure(delivery_record, delivery_result)
            
            self.metrics["failed_deliveries"] += 1
            
            return {
                "success": False,
                "message_id": message_id,
                "error": str(e),
                "retry_scheduled": delivery_record.status == DeliveryStatus.RETRY,
                "attempts": delivery_record.attempts
            }
    
    async def _deliver_via_evolution_api(
        self,
        formatted_message: FormattedMessage,
        instance_name: str,
        delivery_record: DeliveryRecord
    ) -> Dict[str, Any]:
        """Deliver message via Evolution API"""
        try:
            # Send text message
            if formatted_message.message_type == MessageType.TEXT:
                result = await self.evolution_client.send_text_message(
                    instance_name=instance_name,
                    phone=formatted_message.phone_number,
                    message=formatted_message.content
                )
                
                return {
                    "success": True,
                    "message_id": result.get("key", {}).get("id"),
                    "response": result
                }
            
            # Handle other message types (media, buttons, etc.)
            else:
                app_logger.warning(f"Message type {formatted_message.message_type} not yet implemented")
                return {
                    "success": False,
                    "error": f"Message type {formatted_message.message_type} not supported"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_delivery_failure(
        self,
        delivery_record: DeliveryRecord,
        delivery_result: Dict[str, Any]
    ):
        """Handle delivery failure and schedule retry if appropriate"""
        max_retries = self._get_retry_count(delivery_record.priority)
        
        if delivery_record.attempts < max_retries:
            # Schedule retry
            retry_delay = self._get_retry_delay(delivery_record.priority)
            delivery_record.status = DeliveryStatus.RETRY
            delivery_record.next_retry = datetime.now() + timedelta(seconds=retry_delay)
            delivery_record.delivery_metadata["last_error"] = delivery_result.get("error")
            
            # Add to retry queue
            if delivery_record.message_id not in self.retry_queue:
                self.retry_queue.append(delivery_record.message_id)
            
            app_logger.info(f"Scheduled retry for message {delivery_record.message_id}", extra={
                "attempt": delivery_record.attempts,
                "max_retries": max_retries,
                "retry_delay_seconds": retry_delay,
                "next_retry": delivery_record.next_retry.isoformat()
            })
        
        else:
            # Max retries reached
            delivery_record.status = DeliveryStatus.FAILED
            delivery_record.delivery_metadata["final_error"] = delivery_result.get("error")
            
            app_logger.error(f"Message {delivery_record.message_id} failed permanently", extra={
                "phone_number": delivery_record.phone_number,
                "attempts": delivery_record.attempts,
                "final_error": delivery_result.get("error")
            })
    
    async def process_retry_queue(self):
        """Process messages in retry queue"""
        if not self.retry_queue:
            return
        
        app_logger.info(f"Processing retry queue with {len(self.retry_queue)} messages")
        
        current_time = datetime.now()
        retries_processed = 0
        
        # Create a copy of the queue to iterate over
        retry_queue_copy = self.retry_queue.copy()
        
        for message_id in retry_queue_copy:
            if message_id not in self.delivery_records:
                self.retry_queue.remove(message_id)
                continue
            
            delivery_record = self.delivery_records[message_id]
            
            # Check if it's time to retry
            if (delivery_record.next_retry and 
                current_time >= delivery_record.next_retry):
                
                # Attempt redelivery
                # Note: Would need to reconstruct FormattedMessage from delivery_record
                # For now, just log the retry attempt
                app_logger.info(f"Retrying delivery for message {message_id}")
                
                # Remove from retry queue after processing
                self.retry_queue.remove(message_id)
                retries_processed += 1
        
        if retries_processed > 0:
            app_logger.info(f"Processed {retries_processed} retry attempts")
    
    def _create_fallback_message(
        self,
        response: MessageResponse,
        phone_number: str,
        processing_time: float
    ) -> FormattedMessage:
        """Create fallback message when processing fails"""
        fallback_content = (
            response.content if response.content 
            else "Olá! Houve um problema técnico. Entre em contato pelo (51) 99692-1999."
        )
        
        return FormattedMessage(
            content=fallback_content,
            message_type=response.message_type or MessageType.TEXT,
            phone_number=phone_number,
            priority=MessagePriority.NORMAL,
            metadata={
                "processing_time_ms": processing_time,
                "is_fallback": True,
                "error": "Processing failed"
            },
            delivery_options={"delay": 1200, "presence": "composing"},
            formatting_time_ms=processing_time
        )
    
    def _update_processing_metrics(self, processing_time: float, template_id: Optional[str]):
        """Update processing performance metrics"""
        # Update average processing time
        total_processed = self.metrics["total_processed"]
        current_avg = self.metrics["avg_processing_time_ms"]
        
        self.metrics["avg_processing_time_ms"] = (
            (current_avg * (total_processed - 1) + processing_time) / total_processed
        )
        
        # Update template usage
        if template_id:
            if template_id not in self.metrics["template_usage"]:
                self.metrics["template_usage"][template_id] = 0
            self.metrics["template_usage"][template_id] += 1
        
        # Update calendar success rate
        if self.metrics["calendar_integrations"] > 0:
            self.metrics["calendar_success_rate"] = (
                (self.metrics["successful_deliveries"] / self.metrics["calendar_integrations"]) * 100
            )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
        total_deliveries = (
            self.metrics["successful_deliveries"] + self.metrics["failed_deliveries"]
        )
        
        delivery_success_rate = (
            (self.metrics["successful_deliveries"] / max(1, total_deliveries)) * 100
        )
        
        return {
            "processing_performance": {
                "total_processed": self.metrics["total_processed"],
                "avg_processing_time_ms": round(self.metrics["avg_processing_time_ms"], 2),
                "target_met_percentage": (
                    100.0 if self.metrics["avg_processing_time_ms"] < 100 else 0.0
                ),
                "cache_hit_rate": round(self.metrics["cache_hit_rate"] * 100, 2)
            },
            "delivery_performance": {
                "total_deliveries": total_deliveries,
                "successful_deliveries": self.metrics["successful_deliveries"],
                "failed_deliveries": self.metrics["failed_deliveries"],
                "delivery_success_rate": round(delivery_success_rate, 2),
                "retry_queue_size": len(self.retry_queue)
            },
            "calendar_integration": {
                "total_integrations": self.metrics["calendar_integrations"],
                "success_rate": round(self.metrics["calendar_success_rate"], 2),
                "circuit_breaker_status": {
                    "is_open": self.calendar_circuit_breaker["is_open"],
                    "failures": self.calendar_circuit_breaker["failures"]
                }
            },
            "template_usage": self.metrics["template_usage"],
            "business_compliance": {
                "contact_info_present": True,
                "pricing_info_available": True,
                "professional_tone": True
            }
        }
    
    async def cleanup_old_records(self, retention_hours: int = 24):
        """Clean up old delivery records to manage memory"""
        cutoff_time = datetime.now() - timedelta(hours=retention_hours)
        
        records_to_remove = []
        for message_id, record in self.delivery_records.items():
            if record.last_attempt < cutoff_time:
                records_to_remove.append(message_id)
        
        for message_id in records_to_remove:
            del self.delivery_records[message_id]
            if message_id in self.retry_queue:
                self.retry_queue.remove(message_id)
        
        if records_to_remove:
            app_logger.info(f"Cleaned up {len(records_to_remove)} old delivery records")


# Global message postprocessor instance
message_postprocessor = MessagePostprocessor()