#!/usr/bin/env python3
"""
Test script for Google Calendar integration
"""
import sys
import os
import asyncio
from datetime import datetime, timedelta

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.clients.google_calendar import GoogleCalendarClient
from app.core.config import settings


async def test_calendar_integration():
    """Test the Google Calendar integration"""
    print("🔍 Testing Google Calendar Integration")
    print("=" * 50)
    
    # Initialize the client
    print("1. Initializing Google Calendar client...")
    calendar_client = GoogleCalendarClient()
    
    if not calendar_client.service:
        print("❌ Failed to initialize Google Calendar service")
        print("   Make sure:")
        print("   - google-service-account.json exists")
        print("   - Calendar API is enabled")
        print("   - Service account has proper permissions")
        return False
    
    print("✅ Google Calendar client initialized successfully")
    
    # Test calendar ID
    if not settings.GOOGLE_CALENDAR_ID:
        print("⚠️  No calendar ID set in configuration")
        print("   Please set GOOGLE_CALENDAR_ID in your environment or config")
        print("   You can use 'primary' for the service account's primary calendar")
        return False
    
    print(f"📅 Using calendar ID: {settings.GOOGLE_CALENDAR_ID}")
    
    # Test conflict checking
    print("\n2. Testing conflict checking...")
    try:
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)
        
        conflicts = await calendar_client.check_conflicts(start_time, end_time)
        print(f"✅ Conflict check successful - Found {len(conflicts)} conflicts")
        
        if conflicts:
            print("   Existing events:")
            for conflict in conflicts:
                print(f"     - {conflict['summary']} ({conflict['start']} - {conflict['end']})")
        
    except Exception as e:
        print(f"❌ Conflict check failed: {str(e)}")
        return False
    
    # Test event creation
    print("\n3. Testing event creation...")
    try:
        test_start = datetime.now() + timedelta(days=1)
        test_end = test_start + timedelta(hours=1)
        
        event_details = {
            'summary': 'Kumon Test Session',
            'description': 'Test event created by Kumon Assistant',
            'start_time': test_start,
            'end_time': test_end,
            'location': 'Kumon Center Test',
            'attendees': ['test@example.com']
        }
        
        event_id = await calendar_client.create_event(event_details)
        
        if event_id.startswith('error_'):
            print(f"❌ Event creation failed: {event_id}")
            return False
        
        print(f"✅ Event created successfully: {event_id}")
        
        # Test getting the event
        print("\n4. Testing event retrieval...")
        event = await calendar_client.get_event(event_id)
        if event:
            print(f"✅ Event retrieved successfully: {event['summary']}")
        else:
            print("❌ Failed to retrieve event")
            return False
        
        # Test deleting the event
        print("\n5. Testing event deletion...")
        deleted = await calendar_client.delete_event(event_id)
        if deleted:
            print("✅ Event deleted successfully")
        else:
            print("❌ Failed to delete event")
            return False
        
    except Exception as e:
        print(f"❌ Event creation/manipulation failed: {str(e)}")
        return False
    
    print("\n🎉 All tests passed! Google Calendar integration is working correctly.")
    return True


async def main():
    """Main test function"""
    print("Google Calendar Integration Test")
    print("=" * 50)
    
    # Check if credentials file exists
    if not os.path.exists(settings.GOOGLE_CREDENTIALS_PATH):
        print(f"❌ Credentials file not found: {settings.GOOGLE_CREDENTIALS_PATH}")
        print("   Please ensure the service account key file is in the correct location")
        return
    
    # Check if calendar ID is set
    if not settings.GOOGLE_CALENDAR_ID:
        print("⚠️  GOOGLE_CALENDAR_ID not set.")
        print("   Please set it in your environment or use 'primary' for testing")
        print("   Example: export GOOGLE_CALENDAR_ID='primary'")
        return
    
    print(f"📋 Service Account Email: kumon-calendar-service@kumon-ai-receptionist.iam.gserviceaccount.com")
    print(f"📅 Calendar ID: {settings.GOOGLE_CALENDAR_ID}")
    print(f"🔑 Credentials Path: {settings.GOOGLE_CREDENTIALS_PATH}")
    
    # Run the tests
    success = await test_calendar_integration()
    
    if success:
        print("\n✅ Google Calendar integration is ready!")
    else:
        print("\n❌ Google Calendar integration needs attention.")
        print("\nTroubleshooting:")
        print("1. Make sure the service account has access to the calendar")
        print("2. Share your calendar with: kumon-calendar-service@kumon-ai-receptionist.iam.gserviceaccount.com")
        print("3. Check that the Calendar API is enabled in your Google Cloud project")
        print("4. Verify the service account key file is valid")


if __name__ == "__main__":
    asyncio.run(main()) 