"""
Google Calendar API client
"""

class GoogleCalendarClient:
    """Google Calendar API client"""
    
    def __init__(self):
        pass
    
    async def check_conflicts(self, start_time, end_time):
        """Check for calendar conflicts"""
        return []
    
    async def create_event(self, event_details: dict) -> str:
        """Create calendar event"""
        return "test_event_id" 