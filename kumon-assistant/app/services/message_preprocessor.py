"""
Message Preprocessor - Input sanitization, rate limiting, authentication validation, and session context preparation gateway

Implements the complete specification from TECHNICAL_ARCHITECTURE.md
"""
import asyncio
import re
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
            settings.AUTHENTICATION_API_KEY
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
            # Check for API key in headers
            api_key = headers.get('apikey') or headers.get('x-api-key') or headers.get('authorization')
            
            if not api_key:
                app_logger.warning("No API key found in request headers")
                return False
            
            # Clean API key (remove Bearer prefix if present)
            if api_key.startswith('Bearer '):
                api_key = api_key[7:]
            
            # Validate against known keys
            if api_key in self.valid_api_keys:
                app_logger.debug("API key validation successful")
                return True
            else:
                app_logger.warning(f"Invalid API key provided: {api_key[:10]}...")
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
                
                # Update with current message
                context_data.update({
                    "last_user_message": message.message,
                    "phone_number": message.phone,
                    "instance": message.instance,
                    "message_timestamp": message.timestamp
                })
                
                return CeciliaState(**context_data)
            else:
                # Create new session context
                app_logger.info(f"Creating new session context for {message.phone}")
                
                context = CeciliaState(
                    phone_number=message.phone,
                    instance=message.instance,
                    last_user_message=message.message,
                    message_timestamp=message.timestamp,
                    current_stage=ConversationStage.GREETING,
                    current_step=ConversationStep.INITIAL_GREETING,
                    conversation_history=[],
                    collected_data={},
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat()
                )
                
                # Cache the new context
                await enhanced_cache_service.set(
                    cache_key,
                    json.dumps(context, default=str),
                    CacheLayer.L2,
                    ttl=3600  # 1 hour session TTL
                )
                
                return context
                
        except Exception as e:
            app_logger.error(f"Error preparing session context: {str(e)}")
            # Return minimal context as fallback
            return CeciliaState(
                phone_number=message.phone,
                instance=message.instance,
                last_user_message=message.message,
                message_timestamp=message.timestamp,
                current_stage=ConversationStage.GREETING,
                current_step=ConversationStep.INITIAL_GREETING,
                conversation_history=[],
                collected_data={}
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
                business_hours_context["last_bot_response"] = (
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
                    prepared_context=business_hours_context,
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
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            app_logger.error(f"Error in preprocessing pipeline: {str(e)}", exc_info=True)
            return PreprocessorResponse(
                success=False,
                message=None,
                prepared_context=None,
                error_code="PROCESSING_ERROR",
                error_message=f"Internal preprocessing error: {str(e)}",
                processing_time_ms=self._get_processing_time(start_time)
            )
    
    def _get_processing_time(self, start_time: datetime) -> float:
        """Calculate processing time in milliseconds"""
        return (datetime.now() - start_time).total_seconds() * 1000


# Global instance
message_preprocessor = MessagePreprocessor()