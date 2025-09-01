"""
Enterprise-Hardened Google Calendar Client
Implements production-grade resilience patterns for Google Calendar integration
"""
import os
import json
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..core.config import settings
from ..core.logger import app_logger
from ..services.calendar_circuit_breaker import circuit_breaker, CircuitBreakerOpenError
from ..services.calendar_cache_service import calendar_cache_service
from ..services.calendar_rate_limiter import calendar_rate_limiter


class GoogleCalendarClientHardened:
    """
    Enterprise-hardened Google Calendar API client
    
    Features:
    - Circuit breaker protection against API failures
    - Multi-layer caching (memory + Redis)
    - Rate limiting and quota management
    - Graceful degradation and fallback mechanisms
    - Comprehensive error handling and recovery
    - Performance monitoring and analytics
    """
    
    def __init__(self):
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Calendar service with service account credentials"""
        try:
            credentials = None
            
            # Method 1: Try environment variable with Base64 encoded JSON
            if hasattr(settings, 'GOOGLE_SERVICE_ACCOUNT_JSON') and settings.GOOGLE_SERVICE_ACCOUNT_JSON:
                try:
                    app_logger.info("Loading Google credentials from environment variable")
                    
                    # Decode Base64 encoded JSON
                    json_str = base64.b64decode(settings.GOOGLE_SERVICE_ACCOUNT_JSON).decode('utf-8')
                    credentials_info = json.loads(json_str)
                    
                    # Create credentials from JSON info
                    credentials = service_account.Credentials.from_service_account_info(
                        credentials_info,
                        scopes=['https://www.googleapis.com/auth/calendar']
                    )
                    app_logger.info("Google credentials loaded from environment variable successfully")
                    
                except Exception as env_error:
                    app_logger.warning(f"Failed to load credentials from environment variable: {env_error}")
            
            # Method 2: Fallback to file-based credentials
            if not credentials:
                credentials_path = getattr(settings, 'GOOGLE_CREDENTIALS_PATH', '/app/google-service-account.json')
                if os.path.exists(credentials_path):
                    try:
                        app_logger.info(f"Loading Google credentials from file: {credentials_path}")
                        credentials = service_account.Credentials.from_service_account_file(
                            credentials_path,
                            scopes=['https://www.googleapis.com/auth/calendar']
                        )
                        app_logger.info("Google credentials loaded from file successfully")
                    except Exception as file_error:
                        app_logger.warning(f"Failed to load credentials from file: {file_error}")
            
            # Method 3: Try environment variable with direct JSON (fallback)
            if not credentials and os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON'):
                try:
                    app_logger.info("Trying direct JSON from environment variable")
                    json_str = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
                    
                    # Try direct JSON first, then Base64 decode if needed
                    try:
                        credentials_info = json.loads(json_str)
                    except json.JSONDecodeError:
                        # If direct JSON fails, try Base64 decoding
                        json_str = base64.b64decode(json_str).decode('utf-8')
                        credentials_info = json.loads(json_str)
                    
                    credentials = service_account.Credentials.from_service_account_info(
                        credentials_info,
                        scopes=['https://www.googleapis.com/auth/calendar']
                    )
                    app_logger.info("Google credentials loaded from direct environment JSON")
                    
                except Exception as direct_error:
                    app_logger.warning(f"Failed to load credentials from direct JSON: {direct_error}")
            
            if credentials:
                # Build the Calendar API service
                self.service = build('calendar', 'v3', credentials=credentials)
                app_logger.info("✅ Enterprise Google Calendar service initialized successfully")
            else:
                app_logger.warning("⚠️ Google Calendar service not available - no valid credentials found")
                app_logger.info("Scheduling features will operate in degraded mode")
                self.service = None
                
        except Exception as e:
            app_logger.error(f"❌ Failed to initialize Google Calendar service: {str(e)}")
            self.service = None
    
    async def check_conflicts(self, start_time: datetime, end_time: datetime, calendar_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Check for calendar conflicts with enterprise resilience patterns
        
        Features:
        - Multi-layer caching (L1: memory, L2: Redis)
        - Circuit breaker protection
        - Rate limiting compliance
        - Graceful degradation
        """
        if not self.service:
            app_logger.warning("Google Calendar service not initialized - returning empty conflicts")
            return []
        
        # Use provided calendar_id or default from settings
        calendar_id = calendar_id or settings.GOOGLE_CALENDAR_ID
        if not calendar_id:
            app_logger.error("No calendar ID specified for conflict check")
            return []
        
        # Check cache first (L1: memory, L2: Redis)
        try:
            cached_conflicts = await calendar_cache_service.get_conflicts(
                start_time, end_time, calendar_id
            )
            if cached_conflicts is not None:
                app_logger.debug(f"Cache HIT: conflicts for {start_time.date()} to {end_time.date()}")
                return cached_conflicts
        except Exception as cache_error:
            app_logger.warning(f"Cache lookup error: {cache_error}")
        
        # Execute API call with circuit breaker and rate limiting
        return await self._execute_conflict_check(start_time, end_time, calendar_id)
    
    @circuit_breaker
    async def _execute_conflict_check(self, start_time: datetime, end_time: datetime, calendar_id: str) -> List[Dict[str, Any]]:
        """Execute conflict check with circuit breaker protection"""
        # Rate limiting check
        permission = await calendar_rate_limiter.acquire_permission("standard", priority=5)
        if not permission["permitted"]:
            reason = permission["reason"]
            app_logger.warning(f"Rate limit exceeded for conflict check: {reason}")
            
            # Return cached data if available, even if stale
            try:
                stale_cache = await calendar_cache_service.get_conflicts(
                    start_time, end_time, calendar_id
                )
                if stale_cache is not None:
                    app_logger.info("Using stale cache due to rate limiting")
                    return stale_cache
            except Exception:
                pass
            
            # Graceful degradation - return empty conflicts with warning
            app_logger.warning("No cached data available - assuming no conflicts due to rate limiting")
            return []
        
        start_api_time = datetime.now()
        conflicts = []
        
        try:
            # Format times for Google Calendar API (ensure timezone info)
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=datetime.now().astimezone().tzinfo)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=datetime.now().astimezone().tzinfo)
            
            time_min = start_time.isoformat()
            time_max = end_time.isoformat()
            
            app_logger.debug(f"Querying Google Calendar conflicts: {time_min} to {time_max}")
            
            # Query Google Calendar for events in the time range
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            app_logger.debug(f"Found {len(events)} potential conflicts")
            
            # Format conflicts with enhanced filtering
            for event in events:
                # Skip all-day events and events without proper time info
                if 'dateTime' not in event['start']:
                    continue
                
                event_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                event_end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                
                # Check for overlap
                if (event_start < end_time and event_end > start_time):
                    conflicts.append({
                        'id': event.get('id'),
                        'summary': event.get('summary', 'Busy'),
                        'start': event['start']['dateTime'],
                        'end': event['end']['dateTime'],
                        'status': event.get('status', 'confirmed'),
                        'created': event.get('created'),
                        'organizer': event.get('organizer', {}).get('email', 'unknown')
                    })
            
            # Record successful API call
            duration_ms = (datetime.now() - start_api_time).total_seconds() * 1000
            await calendar_rate_limiter.record_request_completion(duration_ms, True)
            
            # Cache the results
            try:
                await calendar_cache_service.set_conflicts(
                    start_time, end_time, calendar_id, conflicts
                )
            except Exception as cache_error:
                app_logger.warning(f"Failed to cache conflicts: {cache_error}")
            
            app_logger.info(f"✅ Conflict check completed: {len(conflicts)} conflicts found in {duration_ms:.1f}ms")
            return conflicts
            
        except CircuitBreakerOpenError as cb_error:
            app_logger.warning(f"Circuit breaker open for conflict check: {cb_error}")
            # Try to return cached data
            try:
                cached_conflicts = await calendar_cache_service.get_conflicts(
                    start_time, end_time, calendar_id
                )
                if cached_conflicts is not None:
                    app_logger.info("Using cached data due to circuit breaker")
                    return cached_conflicts
            except Exception:
                pass
            
            # Graceful degradation
            app_logger.warning("Circuit breaker open - assuming no conflicts for availability check")
            return []
            
        except HttpError as http_error:
            duration_ms = (datetime.now() - start_api_time).total_seconds() * 1000
            await calendar_rate_limiter.record_request_completion(duration_ms, False)
            
            app_logger.error(f"Google Calendar API HTTP error: {http_error}")
            
            # Check for quota exhaustion
            if http_error.resp.status == 429:  # Too Many Requests
                app_logger.error("Google Calendar API quota exhausted")
                
            # Try cached data as fallback
            try:
                cached_conflicts = await calendar_cache_service.get_conflicts(
                    start_time, end_time, calendar_id
                )
                if cached_conflicts is not None:
                    app_logger.info("Using cached data due to API error")
                    return cached_conflicts
            except Exception:
                pass
            
            return []
            
        except Exception as e:
            duration_ms = (datetime.now() - start_api_time).total_seconds() * 1000
            await calendar_rate_limiter.record_request_completion(duration_ms, False)
            
            app_logger.error(f"Unexpected error checking calendar conflicts: {str(e)}")
            return []
    
    async def create_event(self, event_details: Dict[str, Any], calendar_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create calendar event with enterprise resilience
        
        Features:
        - Circuit breaker protection
        - Rate limiting compliance
        - Cache invalidation on success
        - Comprehensive error handling
        """
        if not self.service:
            app_logger.warning("Google Calendar service not initialized - cannot create event")
            return None
        
        calendar_id = calendar_id or settings.GOOGLE_CALENDAR_ID
        if not calendar_id:
            app_logger.error("No calendar ID specified for event creation")
            return None
        
        return await self._execute_event_creation(event_details, calendar_id)
    
    @circuit_breaker
    async def _execute_event_creation(self, event_details: Dict[str, Any], calendar_id: str) -> Optional[Dict[str, Any]]:
        """Execute event creation with circuit breaker protection"""
        # Rate limiting check with higher priority for creation
        permission = await calendar_rate_limiter.acquire_permission("standard", priority=8)
        if not permission["permitted"]:
            reason = permission["reason"]
            app_logger.error(f"Rate limit exceeded for event creation: {reason}")
            
            # Event creation cannot be degraded gracefully - must fail
            raise Exception(f"Cannot create event due to rate limiting: {reason}")
        
        start_api_time = datetime.now()
        
        try:
            app_logger.info(f"Creating Google Calendar event: {event_details.get('summary', 'Untitled')}")
            
            # Create the event
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_details
            ).execute()
            
            # Record successful API call
            duration_ms = (datetime.now() - start_api_time).total_seconds() * 1000
            await calendar_rate_limiter.record_request_completion(duration_ms, True)
            
            # Invalidate relevant cache entries
            try:
                event_start = datetime.fromisoformat(
                    event_details['start']['dateTime'].replace('Z', '+00:00')
                )
                date_str = event_start.date().isoformat()
                await calendar_cache_service.invalidate_date_cache(date_str, calendar_id)
                app_logger.debug(f"Invalidated cache for date: {date_str}")
            except Exception as cache_error:
                app_logger.warning(f"Failed to invalidate cache after event creation: {cache_error}")
            
            app_logger.info(f"✅ Event created successfully: {created_event.get('id')} in {duration_ms:.1f}ms")
            return created_event
            
        except CircuitBreakerOpenError as cb_error:
            app_logger.error(f"Circuit breaker open - cannot create event: {cb_error}")
            raise Exception("Calendar service temporarily unavailable - please try again later")
            
        except HttpError as http_error:
            duration_ms = (datetime.now() - start_api_time).total_seconds() * 1000
            await calendar_rate_limiter.record_request_completion(duration_ms, False)
            
            app_logger.error(f"Google Calendar API HTTP error during event creation: {http_error}")
            
            if http_error.resp.status == 429:
                raise Exception("Calendar service is busy - please try again in a few minutes")
            elif http_error.resp.status == 409:
                raise Exception("Calendar conflict detected - time slot may already be booked")
            else:
                raise Exception(f"Calendar service error: {http_error.resp.status}")
                
        except Exception as e:
            duration_ms = (datetime.now() - start_api_time).total_seconds() * 1000
            await calendar_rate_limiter.record_request_completion(duration_ms, False)
            
            app_logger.error(f"Unexpected error creating calendar event: {str(e)}")
            raise Exception("Failed to create calendar event - please try again")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of the calendar client"""
        health_status = {
            "service_initialized": self.service is not None,
            "calendar_id_configured": bool(settings.GOOGLE_CALENDAR_ID),
            "credentials_configured": bool(
                getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_JSON', '') or
                getattr(settings, 'GOOGLE_CREDENTIALS_PATH', '')
            ),
            "timestamp": datetime.now().isoformat()
        }
        
        # Get circuit breaker metrics
        try:
            from ..services.calendar_circuit_breaker import calendar_circuit_breaker
            health_status["circuit_breaker"] = calendar_circuit_breaker.get_metrics()
        except Exception as e:
            health_status["circuit_breaker_error"] = str(e)
        
        # Get rate limiter analytics
        try:
            health_status["rate_limiter"] = await calendar_rate_limiter.get_analytics()
        except Exception as e:
            health_status["rate_limiter_error"] = str(e)
        
        # Get cache statistics
        try:
            health_status["cache"] = await calendar_cache_service.get_cache_stats()
        except Exception as e:
            health_status["cache_error"] = str(e)
        
        # Overall health assessment
        circuit_healthy = health_status.get("circuit_breaker", {}).get("is_healthy", False)
        rate_healthy = health_status.get("rate_limiter", {}).get("health", {}).get("quota_healthy", False)
        cache_connected = health_status.get("cache", {}).get("redis_connected", False)
        
        health_status["overall_healthy"] = (
            health_status["service_initialized"] and
            health_status["calendar_id_configured"] and
            circuit_healthy and
            rate_healthy
        )
        
        health_status["degraded_mode"] = not health_status["overall_healthy"]
        
        return health_status


# Global hardened calendar client instance
google_calendar_client_hardened = GoogleCalendarClientHardened()