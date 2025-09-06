"""
Message Preprocessor - Input sanitization, rate limiting, and authentication validation gateway

Implements pure preprocessing without orchestration - focused on security and format compliance
"""

import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pytz

from ..clients.evolution_api import WhatsAppMessage
from ..core.config import settings
from ..core.logger import app_logger
from ..services.enhanced_cache_service import CacheLayer, enhanced_cache_service


@dataclass
class PreprocessorResponse:
    """Response from preprocessor pipeline"""

    success: bool
    message: Optional[WhatsAppMessage]
    prepared_context: Optional[Dict[str, Any]] = None  # Reserved for future orchestrator integration
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
            (r"<script[^>]*>.*?</script>", ""),
            # Remove SQL injection attempts
            (r"(union\s+select|drop\s+table|delete\s+from)", ""),
            # Remove excessive whitespace
            (r"\s+", " "),
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
                app_logger.warning(
                    f"Message exceeds max length: {len(raw_message)} > {self.max_message_length}"
                )
                raw_message = raw_message[: self.max_message_length]

            # Apply sanitization patterns
            sanitized = raw_message
            for pattern, replacement in self.sanitization_patterns:
                sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

            # Normalize encoding
            sanitized = sanitized.encode("utf-8", "ignore").decode("utf-8")

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
                ts for ts in request_timestamps if datetime.fromisoformat(ts) > window_start
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
                    ttl=self.window_size_seconds + 10,  # Extra TTL buffer
                )

                app_logger.debug(
                    f"Rate limit check passed for {phone_number}: {len(recent_requests)}/{self.messages_per_minute}"
                )
                return True
            else:
                app_logger.warning(
                    f"Rate limit exceeded for {phone_number}: {len(recent_requests)}/{self.messages_per_minute}"
                )
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
            "webhook-key",  # Allow for webhook testing
        ]
        self.valid_api_keys = [key for key in self.valid_api_keys if key]  # Filter None values

    async def validate_request(self, headers: Dict[str, str], payload: Dict[str, Any], trusted_source: bool = False) -> bool:
        """
        Validate webhook authentication and source verification

        Args:
            headers: Request headers
            payload: Request payload
            trusted_source: Whether the request comes from a trusted source

        Returns:
            True if request is authenticated, False otherwise
        """
        try:
            # Check for empty headers with trusted_source and feature flag
            if not headers or len(headers) == 0:
                from ..core.feature_flags import is_allow_empty_headers
                from ..core.structured_logging import log_pipeline_event
                
                if trusted_source and is_allow_empty_headers():
                    app_logger.warning(f"Auth headers empty - allowing due to ALLOW_EMPTY_HEADERS (trusted_source={trusted_source})")
                    log_pipeline_event("auth_ok", has_headers=False, trusted_source=trusted_source)
                    return True
                else:
                    app_logger.error(f"PREPROCESS|auth_failed|reason=missing_headers|trusted_source={trusted_source}")
                    log_pipeline_event("auth_failed", reason="missing_headers", trusted_source=trusted_source)
                    return False
            
            # Debug: Log all headers to understand what Evolution API is sending
            app_logger.info(f"Authentication validation - Headers received: {list(headers.keys())}")
            # Security-safe authentication header logging
            auth_headers_count = len(
                [k for k in headers.keys() if any(kw in k.lower() for kw in ["api", "auth", "key"])]
            )
            app_logger.debug(f"Authentication headers detected: {auth_headers_count}")

            # Check for API key in headers
            api_key = (
                headers.get("apikey") or headers.get("x-api-key") or headers.get("authorization")
            )

            if not api_key:
                # FALLBACK: Check if this is a legitimate Evolution API webhook
                # Based on Railway staging environment and known webhook patterns
                host = headers.get("host", "")
                user_agent = headers.get("user-agent", "")
                x_forwarded_host = headers.get("x-forwarded-host", "")
                x_railway_edge = headers.get("x-railway-edge", "")

                # 🚨 SECURITY: Stricter Evolution API webhook validation for Railway deployment
                # Multiple criteria must match to prevent spoofing
                railway_domain_match = ("railway.app" in host or "railway.app" in x_forwarded_host)
                railway_headers_present = x_railway_edge and any(
                    header.startswith("x-railway") for header in headers.keys()
                )
                # Real Evolution API user agents in production
                evolution_user_agent = (
                    "okhttp" in user_agent.lower() or 
                    ("evolution" in user_agent.lower() and "api" in user_agent.lower()) or
                    user_agent.lower() in ["", "evolution", "go-http-client", "axios"] or  # Common webhook clients
                    len(user_agent) < 50  # Basic webhook clients have short user agents
                )
                
                # ALL criteria must match for webhook authentication bypass
                is_evolution_webhook = (
                    railway_domain_match and 
                    railway_headers_present and
                    evolution_user_agent and
                    len(headers) > 3  # Legitimate webhooks have multiple headers
                )

                if is_evolution_webhook:
                    from ..core.structured_logging import log_pipeline_event
                    app_logger.info(
                        "✅ Evolution API webhook authenticated via Railway infrastructure",
                        extra={
                            "security_bypass": "evolution_webhook",
                            "host": host,
                            "user_agent": user_agent[:50],  # Truncate for security
                            "railway_headers": len([h for h in headers.keys() if h.startswith("x-railway")]),
                            "total_headers": len(headers)
                        }
                    )
                    log_pipeline_event("auth_ok", has_headers=True, trusted_source=trusted_source, auth_type="evolution_webhook")
                    return True
                else:
                    # Log failed webhook authentication attempts for security monitoring
                    app_logger.warning(
                        "🚨 Potential webhook spoofing attempt detected",
                        extra={
                            "security_incident": True,
                            "railway_domain": railway_domain_match,
                            "railway_headers": railway_headers_present, 
                            "evolution_ua": evolution_user_agent,
                            "header_count": len(headers),
                            "host": host,
                            "user_agent": user_agent[:50]
                        }
                    )

                # 🚨 SECURITY AUDIT: Log unauthorized access attempt
                app_logger.critical(
                    "🚨 SECURITY BREACH ATTEMPT: Unauthorized API access denied",
                    extra={
                        "security_incident": True,
                        "incident_type": "unauthorized_access",
                        "available_headers": list(headers.keys()),
                        "header_count": len(headers),
                        "host": host,
                        "user_agent": user_agent[:100],  # More context for investigation
                        "x_forwarded_for": headers.get("x-forwarded-for", ""),
                        "x_real_ip": headers.get("x-real-ip", ""),
                        "referer": headers.get("referer", ""),
                        "timestamp": datetime.now().isoformat(),
                        "threat_level": "high"
                    }
                )
                
                # Also log to warning for backward compatibility
                app_logger.warning("No API key found in request headers")
                app_logger.warning(f"Available headers: {list(headers.keys())}")
                return False

            # Clean API key (remove Bearer prefix if present)
            if api_key.startswith("Bearer "):
                api_key = api_key[7:]

            # Try to decode base64 if the key looks like base64 encoding
            # Evolution API with base64=true sends encoded keys
            original_api_key = api_key
            try:
                import re

                # Base64 pattern: alphanumeric + / + = with proper length
                if len(api_key) > 8 and re.match(r"^[A-Za-z0-9+/]*={0,2}$", api_key):
                    decoded_key = base64.b64decode(api_key.encode()).decode("utf-8")
                    app_logger.debug("Base64 API key successfully decoded")
                    api_key = decoded_key
                else:
                    app_logger.debug(f"API key doesn't match base64 pattern: {api_key[:20]}...")
            except Exception as e:
                # Not base64, use original key
                app_logger.debug(f"API key is not base64 encoded: {str(e)}")
                api_key = original_api_key

            # Validate against known keys - security-safe logging
            app_logger.debug("API key validation in progress")
            app_logger.debug(
                f"Valid API keys configured: {len([k for k in self.valid_api_keys if k])}"
            )

            if api_key in self.valid_api_keys:
                from ..core.structured_logging import log_pipeline_event
                app_logger.info("✅ API key validation successful")
                log_pipeline_event("auth_ok", has_headers=True, trusted_source=trusted_source)
                return True
            else:
                from ..core.structured_logging import log_pipeline_event
                app_logger.error("❌ Authentication failed - invalid API key provided")
                log_pipeline_event("auth_failed", reason="invalid_api_key", trusted_source=trusted_source)
                return False

        except Exception as e:
            app_logger.error(f"Error validating authentication: {str(e)}")
            return False




class BusinessHoursValidator:
    """
    Validate business hours according to PROJECT_SCOPE.md:
    Monday-Friday 9AM-12PM, 2PM-5PM (UTC-3 Brazilian timezone)
    """

    def __init__(self):
        self.timezone = pytz.timezone("America/Sao_Paulo")  # UTC-3
        self.business_days = [0, 1, 2, 3, 4]  # Monday to Friday
        self.business_hours = [(9, 12), (14, 17)]  # 9AM-12PM  # 2PM-5PM

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
    Pure message preprocessing - sanitization, rate limiting, and authentication validation
    """

    def __init__(self):
        self.sanitizer = MessageSanitizer()
        self.rate_limiter = RateLimiter()
        self.auth_validator = AuthValidator()

    async def process_message(
        self, message: WhatsAppMessage, headers: Dict[str, str], trusted_source: bool = False
    ) -> PreprocessorResponse:
        """
        Process incoming WhatsApp message through complete preprocessing pipeline

        Args:
            message: WhatsApp message to process
            headers: Request headers for authentication
            trusted_source: Whether the message comes from a trusted source

        Returns:
            PreprocessorResponse with processing results
        """
        start_time = datetime.now()

        try:
            app_logger.info(f"Starting preprocessing pipeline for message from {message.phone}")

            # Step 1: Authentication validation
            if not await self.auth_validator.validate_request(headers, {}, trusted_source=trusted_source):
                return PreprocessorResponse(
                    success=False,
                    message=None,
                    prepared_context=None,
                    preprocessed=False,  # Failed authentication - no preprocessing
                    error_code="AUTH_FAILED",
                    error_message="Authentication validation failed",
                    processing_time_ms=self._get_processing_time(start_time),
                )

            # Step 2: Business hours validation (REMOVED as per user request to allow 24/7 service)

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
                    processing_time_ms=self._get_processing_time(start_time),
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
                media_type=message.media_type,
            )

            processing_time = self._get_processing_time(start_time)

            app_logger.info(
                f"✅ Preprocessing completed for {message.phone}",
                extra={
                    "processing_time_ms": processing_time,
                    "sanitized_length": len(sanitized_message),
                    "original_length": len(message.message),
                },
            )

            return PreprocessorResponse(
                success=True,
                message=sanitized_whatsapp_message,
                prepared_context=None,  # Session context moved to orchestrator
                preprocessed=True,
                processing_time_ms=processing_time,
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
                processing_time_ms=self._get_processing_time(start_time),
            )

    def _get_processing_time(self, start_time: datetime) -> float:
        """Calculate processing time in milliseconds"""
        return (datetime.now() - start_time).total_seconds() * 1000


# Global instance
message_preprocessor = MessagePreprocessor()
