"""
Google Calendar API client
"""
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..core.config import settings
from ..core.logger import app_logger


class GoogleCalendarClient:
    """Google Calendar API client with service account authentication"""
    
    def __init__(self):
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Calendar service with service account credentials"""
        try:
            # Load service account credentials
            credentials_path = settings.GOOGLE_CREDENTIALS_PATH
            if not os.path.exists(credentials_path):
                app_logger.error(f"Google credentials file not found: {credentials_path}")
                return
            
            # Set up service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            
            # Build the Calendar API service
            self.service = build('calendar', 'v3', credentials=credentials)
            app_logger.info("Google Calendar service initialized successfully")
            
        except Exception as e:
            app_logger.error(f"Failed to initialize Google Calendar service: {str(e)}")
            self.service = None
    
    async def check_conflicts(self, start_time: datetime, end_time: datetime, calendar_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Check for calendar conflicts in the specified time range"""
        if not self.service:
            app_logger.error("Google Calendar service not initialized")
            return []
        
        try:
            # Use provided calendar_id or default from settings
            calendar_id = calendar_id or settings.GOOGLE_CALENDAR_ID
            if not calendar_id:
                app_logger.error("No calendar ID specified")
                return []
            
            # Format times for Google Calendar API (ensure timezone info)
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=datetime.now().astimezone().tzinfo)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=datetime.now().astimezone().tzinfo)
            
            time_min = start_time.isoformat()
            time_max = end_time.isoformat()
            
            # Query calendar for events in the time range
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            conflicts = []
            for event in events:
                # Skip all-day events and events without proper time info
                if 'dateTime' not in event['start']:
                    continue
                
                event_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                event_end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                
                # Check for overlap
                if (event_start < end_time and event_end > start_time):
                    conflicts.append({
                        'id': event['id'],
                        'summary': event.get('summary', 'No title'),
                        'start': event_start,
                        'end': event_end,
                        'description': event.get('description', ''),
                        'attendees': event.get('attendees', [])
                    })
            
            app_logger.info(f"Found {len(conflicts)} calendar conflicts between {start_time} and {end_time}")
            return conflicts
            
        except HttpError as e:
            app_logger.error(f"Google Calendar API error in check_conflicts: {str(e)}")
            return []
        except Exception as e:
            app_logger.error(f"Unexpected error in check_conflicts: {str(e)}")
        return []
    
    async def create_event(self, event_details: Dict[str, Any]) -> str:
        """Create a calendar event"""
        if not self.service:
            app_logger.error("Google Calendar service not initialized")
            return "error_service_not_initialized"
        
        try:
            # Use provided calendar_id or default from settings
            calendar_id = event_details.get('calendar_id') or settings.GOOGLE_CALENDAR_ID
            if not calendar_id:
                app_logger.error("No calendar ID specified for event creation")
                return "error_no_calendar_id"
            
            # Build event object for Google Calendar API
            event_body = {
                'summary': event_details.get('summary', 'Kumon Session'),
                'description': event_details.get('description', ''),
                'start': {
                    'dateTime': event_details['start_time'].isoformat(),
                    'timeZone': event_details.get('timezone', 'America/Sao_Paulo'),
                },
                'end': {
                    'dateTime': event_details['end_time'].isoformat(),
                    'timeZone': event_details.get('timezone', 'America/Sao_Paulo'),
                },
                'attendees': [],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 30},       # 30 minutes before
                    ],
                },
            }
            
            # Add attendees if provided (Note: Service accounts have limitations)
            if 'attendees' in event_details:
                app_logger.warning("Service accounts cannot invite attendees without Domain-Wide Delegation")
                app_logger.info("Attendees will be added to event description instead")
                
                # Add attendees to description instead
                attendee_emails = []
                for attendee in event_details['attendees']:
                    if isinstance(attendee, str):
                        attendee_emails.append(attendee)
                    elif isinstance(attendee, dict) and 'email' in attendee:
                        attendee_emails.append(attendee['email'])
                
                if attendee_emails:
                    if event_body['description']:
                        event_body['description'] += f"\n\nAttendees: {', '.join(attendee_emails)}"
                    else:
                        event_body['description'] = f"Attendees: {', '.join(attendee_emails)}"
            
            # Add location if provided
            if 'location' in event_details:
                event_body['location'] = event_details['location']
            
            # Create the event
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()
            
            event_id = created_event['id']
            app_logger.info(f"Created calendar event: {event_id}")
            return event_id
            
        except HttpError as e:
            app_logger.error(f"Google Calendar API error in create_event: {str(e)}")
            return f"error_api_{e.resp.status}"
        except Exception as e:
            app_logger.error(f"Unexpected error in create_event: {str(e)}")
            return "error_unexpected"
    
    async def get_event(self, event_id: str, calendar_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a specific calendar event"""
        if not self.service:
            app_logger.error("Google Calendar service not initialized")
            return None
        
        try:
            calendar_id = calendar_id or settings.GOOGLE_CALENDAR_ID
            if not calendar_id:
                app_logger.error("No calendar ID specified")
                return None
            
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            return event
            
        except HttpError as e:
            app_logger.error(f"Google Calendar API error in get_event: {str(e)}")
            return None
        except Exception as e:
            app_logger.error(f"Unexpected error in get_event: {str(e)}")
            return None
    
    async def update_event(self, event_id: str, event_updates: Dict[str, Any], calendar_id: Optional[str] = None) -> bool:
        """Update a calendar event"""
        if not self.service:
            app_logger.error("Google Calendar service not initialized")
            return False
        
        try:
            calendar_id = calendar_id or settings.GOOGLE_CALENDAR_ID
            if not calendar_id:
                app_logger.error("No calendar ID specified")
                return False
            
            # Get the existing event
            existing_event = await self.get_event(event_id, calendar_id)
            if not existing_event:
                app_logger.error(f"Event {event_id} not found")
                return False
            
            # Update the event with new details
            existing_event.update(event_updates)
            
            # Update the event
            self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=existing_event
            ).execute()
            
            app_logger.info(f"Updated calendar event: {event_id}")
            return True
            
        except HttpError as e:
            app_logger.error(f"Google Calendar API error in update_event: {str(e)}")
            return False
        except Exception as e:
            app_logger.error(f"Unexpected error in update_event: {str(e)}")
            return False
    
    async def delete_event(self, event_id: str, calendar_id: Optional[str] = None) -> bool:
        """Delete a calendar event"""
        if not self.service:
            app_logger.error("Google Calendar service not initialized")
            return False
        
        try:
            calendar_id = calendar_id or settings.GOOGLE_CALENDAR_ID
            if not calendar_id:
                app_logger.error("No calendar ID specified")
                return False
            
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            app_logger.info(f"Deleted calendar event: {event_id}")
            return True
            
        except HttpError as e:
            app_logger.error(f"Google Calendar API error in delete_event: {str(e)}")
            return False
        except Exception as e:
            app_logger.error(f"Unexpected error in delete_event: {str(e)}")
            return False 