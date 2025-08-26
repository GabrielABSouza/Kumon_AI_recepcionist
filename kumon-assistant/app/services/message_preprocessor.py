"""
Message Preprocessor - Input sanitization, rate limiting, authentication validation, and session context preparation gateway

Implements the complete specification from TECHNICAL_ARCHITECTURE.md
"""
import asyncio
import re
import base64
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json
from dataclasses import dataclass
import pytz

from ..core.config import settings
from ..core.logger import app_logger
from ..core.state.models import CeciliaState, ConversationStage, ConversationStep
from ..clients.evolution_api import WhatsAppMessage
from ..services.enhanced_cache_service import enhanced_cache_service, CacheLayer


@dataclass
class PreprocessorResponse:
    """Response from preprocessor pipeline"""
    success: bool
    message: Optional[WhatsAppMessage]
    prepared_context: Optional[CeciliaState]
    preprocessed: bool = True  # Flag to mark if message has been preprocessed
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    rate_limited: bool = False
    processing_time_ms: float = 0.0


class MessageSanitizer:
    """
    Sanitize incoming WhatsApp messages for security and format compliance
    """
    
    def __init__(self):
        self.max_message_length = 1000
        self.allowed_content_types = ["text"]
        self.sanitization_patterns = [
            # Remove potential script injections
            (r'<script[^>]*>.*?</script>', ''),
            # Remove SQL injection attempts
            (r'(union\s+select|drop\s+table|delete\s+from)', ''),
            # Remove excessive whitespace
            (r'\s+', ' '),
        ]
    
    async def sanitize_message(self, raw_message: str) -> str:
        """
        Sanitize incoming message content
        
        Args:
            raw_message: Raw message text from WhatsApp
            
        Returns:
            Sanitized message safe for processing
        """
        try:
            if not raw_message:
                return ""
            
            # Length validation
            if len(raw_message) > self.max_message_length:
                app_logger.warning(f"Message exceeds max length: {len(raw_message)} > {self.max_message_length}")
                raw_message = raw_message[:self.max_message_length]
            
            # Apply sanitization patterns
            sanitized = raw_message
            for pattern, replacement in self.sanitization_patterns:
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
            
            # Normalize encoding
            sanitized = sanitized.encode('utf-8', 'ignore').decode('utf-8')
            
            # Strip and normalize whitespace
            sanitized = sanitized.strip()
            
            app_logger.debug(f"Message sanitized: {len(raw_message)} -> {len(sanitized)} chars")
            return sanitized
            
        except Exception as e:
            app_logger.error(f"Error sanitizing message: {str(e)}")
            # Return safe fallback
            return "Mensagem não pôde ser processada"


class RateLimiter:
    """
    Phone number based rate limiting with Redis backend
    """
    
    def __init__(self):
        self.messages_per_minute = 50
        self.burst_tolerance = 10
        self.window_size_seconds = 60
    
    async def check_rate_limit(self, phone_number: str) -> bool:
        """
        Check rate limit status for phone number using sliding window algorithm
        
        Args:
            phone_number: Phone number to check
            
        Returns:
            True if request is allowed, False if rate limited
        """
        try:
            cache_key = f"rate_limit:{phone_number}"
            current_time = datetime.now()
            window_start = current_time - timedelta(seconds=self.window_size_seconds)
            
            # Get current request timestamps from cache
            cached_requests = await enhanced_cache_service.get(cache_key, CacheLayer.L1)
            if cached_requests:
                request_timestamps = json.loads(cached_requests)
            else:
                request_timestamps = []
            
            # Filter out old requests (outside window)
            recent_requests = [
                ts for ts in request_timestamps 
                if datetime.fromisoformat(ts) > window_start
            ]
            
            # Check if under limit
            if len(recent_requests) < self.messages_per_minute:
                # Add current request timestamp
                recent_requests.append(current_time.isoformat())
                
                # Store updated timestamps
                await enhanced_cache_service.set(
                    cache_key,
                    json.dumps(recent_requests),
                    CacheLayer.L1,
                    ttl=self.window_size_seconds + 10  # Extra TTL buffer
                )
                
                app_logger.debug(f"Rate limit check passed for {phone_number}: {len(recent_requests)}/{self.messages_per_minute}")
                return True
            else:
                app_logger.warning(f"Rate limit exceeded for {phone_number}: {len(recent_requests)}/{self.messages_per_minute}")
                return False
                
        except Exception as e:
            app_logger.error(f"Error checking rate limit for {phone_number}: {str(e)}")
            # Fail open - allow request if rate limiting fails
            return True


class AuthValidator:
    """
    Validate webhook authentication and source verification
    """
    
    def __init__(self):
        self.valid_api_keys = [
            settings.EVOLUTION_API_KEY,
            settings.EVOLUTION_GLOBAL_API_KEY,
            settings.AUTHENTICATION_API_KEY,
            "test-development-key",  # Allow for development testing
            "webhook-key"  # Allow for webhook testing
        ]
        self.valid_api_keys = [key for key in self.valid_api_keys if key]  # Filter None values
    
    async def validate_request(self, headers: Dict[str, str], payload: Dict[str, Any]) -> bool:
        """
        Validate webhook authentication and source verification
        
        Args:
            headers: Request headers
            payload: Request payload
            
        Returns:
            True if request is authenticated, False otherwise
        """
        try:
            # Debug: Log all headers to understand what Evolution API is sending
            app_logger.info(f"Authentication validation - Headers received: {list(headers.keys())}")
            # Security-safe authentication header logging
            auth_headers_count = len([k for k in headers.keys() if any(kw in k.lower() for kw in ['api', 'auth', 'key'])])
            app_logger.debug(f"Authentication headers detected: {auth_headers_count}")
            
            # Check for API key in headers
            api_key = headers.get('apikey') or headers.get('x-api-key') or headers.get('authorization')
            
            if not api_key:
                app_logger.warning("No API key found in request headers")
                app_logger.warning(f"Available headers: {list(headers.keys())}")
                return False
            
            # Clean API key (remove Bearer prefix if present)
            if api_key.startswith('Bearer '):
                api_key = api_key[7:]
            
            # Try to decode base64 if the key looks like base64 encoding
            # Evolution API with base64=true sends encoded keys
            original_api_key = api_key
            try:
                import re
                # Base64 pattern: alphanumeric + / + = with proper length
                if len(api_key) > 8 and re.match(r'^[A-Za-z0-9+/]*={0,2}$', api_key):
                    decoded_key = base64.b64decode(api_key.encode()).decode('utf-8')
                    app_logger.debug("Base64 API key successfully decoded")
                    api_key = decoded_key
                else:
                    app_logger.debug(f"API key doesn't match base64 pattern: {api_key[:20]}...")
            except Exception as e:
                # Not base64, use original key
                app_logger.debug(f"API key is not base64 encoded: {str(e)}")
                api_key = original_api_key
            
            # Validate against known keys - security-safe logging
            app_logger.debug(f"API key validation in progress")
            app_logger.debug(f"Valid API keys configured: {len([k for k in self.valid_api_keys if k])}")
            
            if api_key in self.valid_api_keys:
                app_logger.info("✅ API key validation successful")
                return True
            else:
                app_logger.error("❌ Authentication failed - invalid API key provided")
                return False
                
        except Exception as e:
            app_logger.error(f"Error validating authentication: {str(e)}")
            return False


class SessionPreparator:
    """
    Prepare session context for LangGraph workflow integration
    """
    
    async def prepare_context(self, message: WhatsAppMessage) -> CeciliaState:
        """
        Create or retrieve session context for LangGraph workflow
        
        Args:
            message: WhatsApp message to process
            
        Returns:
            Prepared CeciliaState for LangGraph workflow
        """
        try:
            thread_id = f"thread_{message.phone}"
            
            # Check for existing session context
            cache_key = f"session:{message.phone}"
            existing_context = await enhanced_cache_service.get(cache_key, CacheLayer.L2)
            
            if existing_context:
                # Load existing context
                context_data = json.loads(existing_context)
                app_logger.debug(f"Loaded existing session context for {message.phone}")
                
                # Update with current message and convert enum strings back to enums
                context_data.update({
                    "last_user_message": message.message,
                    "phone_number": message.phone
                })
                
                # Convert string enum values back to enums
                if context_data.get("current_stage"):
                    context_data["current_stage"] = ConversationStage(context_data["current_stage"])
                if context_data.get("current_step"):
                    context_data["current_step"] = ConversationStep(context_data["current_step"])
                
                # Convert datetime string back to datetime object
                if context_data.get("conversation_metrics", {}).get("created_at"):
                    try:
                        context_data["conversation_metrics"]["created_at"] = datetime.fromisoformat(
                            context_data["conversation_metrics"]["created_at"]
                        )
                    except:
                        context_data["conversation_metrics"]["created_at"] = datetime.now()
                
                # Increment message count
                if "conversation_metrics" in context_data:
                    context_data["conversation_metrics"]["message_count"] += 1
                
                return CeciliaState(**context_data)
            else:
                # Create new session context
                app_logger.info(f"Creating new session context for {message.phone}")
                
                # Create complete CeciliaState with all required fields
                context = CeciliaState(
                    # IDENTIFICATION
                    phone_number=message.phone,
                    conversation_id=f"conv_{message.phone}_{int(datetime.now().timestamp())}",
                    
                    # FLOW CONTROL
                    current_stage=ConversationStage.GREETING,
                    current_step=ConversationStep.WELCOME,
                    messages=[],
                    last_user_message=message.message,
                    
                    # COLLECTED DATA
                    collected_data={},
                    
                    # VALIDATION SYSTEM
                    data_validation={
                        "extraction_attempts": {},
                        "pending_confirmations": [],
                        "validation_history": [],
                        "last_extraction_error": None
                    },
                    
                    # METRICS AND AUDIT
                    conversation_metrics={
                        "failed_attempts": 0,
                        "consecutive_confusion": 0,
                        "same_question_count": 0,
                        "message_count": 1,
                        "created_at": datetime.now(),
                        "last_successful_collection": None,
                        "problematic_fields": []
                    },
                    
                    decision_trail={
                        "last_decisions": [],
                        "edge_function_calls": [],
                        "validation_failures": []
                    }
                )
                
                # Cache the new context (convert to dict for JSON serialization)
                context_dict = {
                    # IDENTIFICATION
                    "phone_number": context["phone_number"],
                    "conversation_id": context["conversation_id"],
                    
                    # FLOW CONTROL
                    "current_stage": context["current_stage"].value if context["current_stage"] else None,
                    "current_step": context["current_step"].value if context["current_step"] else None,
                    "messages": context["messages"],
                    "last_user_message": context["last_user_message"],
                    
                    # COLLECTED DATA
                    "collected_data": context["collected_data"],
                    
                    # VALIDATION SYSTEM
                    "data_validation": context["data_validation"],
                    
                    # METRICS AND AUDIT
                    "conversation_metrics": {
                        **context["conversation_metrics"],
                        "created_at": context["conversation_metrics"]["created_at"].isoformat() if context["conversation_metrics"]["created_at"] else None
                    },
                    "decision_trail": context["decision_trail"]
                }
                await enhanced_cache_service.set(
                    cache_key,
                    json.dumps(context_dict),
                    CacheLayer.L2,
                    ttl=3600  # 1 hour session TTL
                )
                
                return context
                
        except Exception as e:
            app_logger.error(f"Error preparing session context: {str(e)}")
            # Return complete fallback context
            return CeciliaState(
                # IDENTIFICATION
                phone_number=message.phone,
                conversation_id=f"conv_{message.phone}_fallback_{int(datetime.now().timestamp())}",
                
                # FLOW CONTROL
                current_stage=ConversationStage.GREETING,
                current_step=ConversationStep.WELCOME,
                messages=[],
                last_user_message=message.message,
                
                # COLLECTED DATA
                collected_data={},
                
                # VALIDATION SYSTEM
                data_validation={
                    "extraction_attempts": {},
                    "pending_confirmations": [],
                    "validation_history": [],
                    "last_extraction_error": None
                },
                
                # METRICS AND AUDIT
                conversation_metrics={
                    "failed_attempts": 0,
                    "consecutive_confusion": 0,
                    "same_question_count": 0,
                    "message_count": 1,
                    "created_at": datetime.now(),
                    "last_successful_collection": None,
                    "problematic_fields": []
                },
                
                decision_trail={
                    "last_decisions": [],
                    "edge_function_calls": [],
                    "validation_failures": []
                }
            )


class BusinessHoursValidator:
    """
    Validate business hours according to PROJECT_SCOPE.md:
    Monday-Friday 9AM-12PM, 2PM-5PM (UTC-3 Brazilian timezone)
    """
    
    def __init__(self):
        self.timezone = pytz.timezone('America/Sao_Paulo')  # UTC-3
        self.business_days = [0, 1, 2, 3, 4]  # Monday to Friday
        self.business_hours = [
            (9, 12),   # 9AM-12PM
            (14, 17)   # 2PM-5PM
        ]
    
    def is_business_hours(self, timestamp: Optional[int] = None) -> bool:
        """
        Check if current time (or provided timestamp) is within business hours
        
        Args:
            timestamp: Unix timestamp (optional, uses current time if not provided)
            
        Returns:
            True if within business hours, False otherwise
        """
        try:
            if timestamp:
                check_time = datetime.fromtimestamp(timestamp, self.timezone)
            else:
                check_time = datetime.now(self.timezone)
            
            # Check if it's a business day (Monday=0, Friday=4)
            if check_time.weekday() not in self.business_days:
                return False
            
            # Check if it's within business hours
            hour = check_time.hour
            for start_hour, end_hour in self.business_hours:
                if start_hour <= hour < end_hour:
                    return True
            
            return False
            
        except Exception as e:
            app_logger.error(f"Error checking business hours: {str(e)}")
            # Default to allowing messages if validation fails
            return True
    
    def get_next_business_time(self) -> str:
        """Get next available business time as a formatted string"""
        try:
            now = datetime.now(self.timezone)
            
            # If it's Friday after hours, next business time is Monday 9AM
            if now.weekday() == 4 and now.hour >= 17:  # Friday after 5PM
                days_ahead = 7 - now.weekday() + 0  # Days until next Monday
                next_business = now.replace(hour=9, minute=0, second=0, microsecond=0)
                next_business += timedelta(days=days_ahead)
                return next_business.strftime("segunda-feira às 9h")
            
            # If it's weekend, next business time is Monday 9AM
            elif now.weekday() >= 5:  # Weekend
                days_ahead = 7 - now.weekday()  # Days until Monday
                next_business = now.replace(hour=9, minute=0, second=0, microsecond=0)
                next_business += timedelta(days=days_ahead)
                return next_business.strftime("segunda-feira às 9h")
            
            # If it's a weekday but outside hours
            elif now.weekday() < 5:
                hour = now.hour
                
                # Before 9AM - same day at 9AM
                if hour < 9:
                    return "hoje às 9h"
                # Between 12PM-2PM - same day at 2PM  
                elif 12 <= hour < 14:
                    return "hoje às 14h"
                # After 5PM - next day at 9AM
                elif hour >= 17:
                    if now.weekday() == 4:  # Friday
                        return "segunda-feira às 9h"
                    else:
                        return "amanhã às 9h"
                
            return "no próximo horário comercial"
            
        except Exception as e:
            app_logger.error(f"Error calculating next business time: {str(e)}")
            return "no próximo horário comercial"


class MessagePreprocessor:
    """
    Main preprocessor coordinator that orchestrates all preprocessing steps
    """
    
    def __init__(self):
        self.sanitizer = MessageSanitizer()
        self.rate_limiter = RateLimiter()
        self.auth_validator = AuthValidator()
        self.session_preparator = SessionPreparator()
        self.business_hours_validator = BusinessHoursValidator()
    
    async def process_message(
        self, 
        message: WhatsAppMessage, 
        headers: Dict[str, str]
    ) -> PreprocessorResponse:
        """
        Process incoming WhatsApp message through complete preprocessing pipeline
        
        Args:
            message: WhatsApp message to process
            headers: Request headers for authentication
            
        Returns:
            PreprocessorResponse with processing results
        """
        start_time = datetime.now()
        
        try:
            app_logger.info(f"Starting preprocessing pipeline for message from {message.phone}")
            
            # Step 1: Authentication validation
            if not await self.auth_validator.validate_request(headers, {}):
                return PreprocessorResponse(
                    success=False,
                    message=None,
                    prepared_context=None,
                    preprocessed=False,  # Failed authentication - no preprocessing
                    error_code="AUTH_FAILED",
                    error_message="Authentication validation failed",
                    processing_time_ms=self._get_processing_time(start_time)
                )
            
            # Step 2: Business hours validation
            if not self.business_hours_validator.is_business_hours(message.timestamp):
                next_business_time = self.business_hours_validator.get_next_business_time()
                app_logger.info(f"Message received outside business hours from {message.phone}")
                
                # Create business hours response context
                business_hours_context = await self.session_preparator.prepare_context(message)
                
                # Add business hours auto-response message
                business_hours_response = (
                    f"Olá! Sou Cecília do Kumon Vila A. 😊\n\n"
                    f"Obrigada pela sua mensagem! No momento estamos fora do horário de atendimento.\n\n"
                    f"📅 **Horário de funcionamento:**\n"
                    f"Segunda a sexta-feira\n"
                    f"• Manhã: 9h às 12h\n"
                    f"• Tarde: 14h às 17h\n\n"
                    f"🕐 Retornaremos {next_business_time}\n\n"
                    f"Para urgências, entre em contato pelo telefone (51) 99692-1999. 📞"
                )
                
                return PreprocessorResponse(
                    success=True,  # Success but with business hours message
                    message=message,
                    prepared_context={**business_hours_context, "last_bot_response": business_hours_response},
                    preprocessed=True,  # Message was preprocessed (includes session preparation)
                    error_code="OUTSIDE_BUSINESS_HOURS",
                    error_message=f"Outside business hours, next available: {next_business_time}",
                    processing_time_ms=self._get_processing_time(start_time)
                )
            
            # Step 3: Rate limiting check
            if not await self.rate_limiter.check_rate_limit(message.phone):
                return PreprocessorResponse(
                    success=False,
                    message=None,
                    prepared_context=None,
                    preprocessed=False,  # Rate limited - no preprocessing completed
                    error_code="RATE_LIMITED",
                    error_message="Rate limit exceeded",
                    rate_limited=True,
                    processing_time_ms=self._get_processing_time(start_time)
                )
            
            # Step 4: Message sanitization
            sanitized_message = await self.sanitizer.sanitize_message(message.message)
            
            # Create sanitized message object
            sanitized_whatsapp_message = WhatsAppMessage(
                message_id=message.message_id,
                phone=message.phone,
                message=sanitized_message,
                message_type=message.message_type,
                timestamp=message.timestamp,
                instance=message.instance,
                sender_name=message.sender_name,
                quoted_message=message.quoted_message,
                media_url=message.media_url,
                media_type=message.media_type
            )
            
            # Step 5: Session context preparation
            prepared_context = await self.session_preparator.prepare_context(sanitized_whatsapp_message)
            
            processing_time = self._get_processing_time(start_time)
            
            app_logger.info(
                f"Preprocessing pipeline completed successfully for {message.phone}",
                extra={
                    "processing_time_ms": processing_time,
                    "sanitized_length": len(sanitized_message),
                    "original_length": len(message.message)
                }
            )
            
            return PreprocessorResponse(
                success=True,
                message=sanitized_whatsapp_message,
                prepared_context=prepared_context,
                preprocessed=True,  # Full preprocessing pipeline completed successfully
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            app_logger.error(f"Error in preprocessing pipeline: {str(e)}", exc_info=True)
            return PreprocessorResponse(
                success=False,
                message=None,
                prepared_context=None,
                preprocessed=False,  # Processing failed - no preprocessing completed
                error_code="PROCESSING_ERROR",
                error_message=f"Internal preprocessing error: {str(e)}",
                processing_time_ms=self._get_processing_time(start_time)
            )
    
    def _get_processing_time(self, start_time: datetime) -> float:
        """Calculate processing time in milliseconds"""
        return (datetime.now() - start_time).total_seconds() * 1000


# Global instance
message_preprocessor = MessagePreprocessor()