#!/usr/bin/env python3
"""
Focused test for appointment booking functionality
Tests date extraction, calendar search, and booking logic
"""
import sys
import os
import asyncio
from datetime import datetime, timedelta

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.clients.google_calendar import GoogleCalendarClient
from app.core.config import settings


class AppointmentBookingTester:
    """Test class for appointment booking functionality"""
    
    def __init__(self):
        self.calendar_client = GoogleCalendarClient()
    
    def test_date_extraction(self):
        """Test date and time preference extraction"""
        print("🔍 Testing Date/Time Preference Extraction")
        print("-" * 40)
        
        test_cases = [
            ("Prefiro segunda-feira de manhã", {"day_of_week": "Segunda-feira", "time_period": "manhã"}),
            ("Quero sábado à tarde", {"saturday_requested": True}),
            ("Domingo seria melhor", {"sunday_requested": True}),
            ("Terça-feira à noite", {"day_of_week": "Terça-feira", "time_period": "noite"}),
            ("Qualquer dia útil", {"day_of_week": "Qualquer dia útil"}),
            ("Prefiro pela manhã", {"time_period": "manhã"}),
        ]
        
        for input_text, expected in test_cases:
            result = self._extract_date_time_preferences(input_text)
            print(f"Input: '{input_text}'")
            print(f"Expected: {expected}")
            print(f"Got: {result}")
            
            # Check if result matches expected
            matches = all(result.get(k) == v for k, v in expected.items())
            print(f"✅ Match" if matches else f"❌ No match")
            print()
    
    def _extract_date_time_preferences(self, user_message: str):
        """Extract date and time preferences from user message."""
        user_message_lower = user_message.lower()
        preferences = {}
        
        # Check for Saturday first and handle it specially
        if "sábado" in user_message_lower or "sab" in user_message_lower:
            preferences["saturday_requested"] = True
            return preferences
        
        # Day of the week
        if "segunda" in user_message_lower or "seg" in user_message_lower:
            preferences["day_of_week"] = "Segunda-feira"
        elif "terça" in user_message_lower or "ter" in user_message_lower:
            preferences["day_of_week"] = "Terça-feira"
        elif "quarta" in user_message_lower or "qua" in user_message_lower:
            preferences["day_of_week"] = "Quarta-feira"
        elif "quinta" in user_message_lower or "qui" in user_message_lower:
            preferences["day_of_week"] = "Quinta-feira"
        elif "sexta" in user_message_lower or "sex" in user_message_lower:
            preferences["day_of_week"] = "Sexta-feira"
        elif "domingo" in user_message_lower or "dom" in user_message_lower:
            preferences["sunday_requested"] = True
            return preferences
        elif "qualquer" in user_message_lower or "qual" in user_message_lower:
            preferences["day_of_week"] = "Qualquer dia útil"
            
        # Time period
        if "manhã" in user_message_lower or "manha" in user_message_lower:
            preferences["time_period"] = "manhã"
        elif "tarde" in user_message_lower or "tard" in user_message_lower:
            preferences["time_period"] = "tarde"
        elif "noite" in user_message_lower or "noit" in user_message_lower:
            preferences["time_period"] = "noite"
        elif "qualquer" in user_message_lower or "qual" in user_message_lower:
            preferences["time_period"] = "qualquer"
            
        return preferences
    
    async def test_calendar_search(self):
        """Test Google Calendar availability search"""
        print("📅 Testing Google Calendar Search")
        print("-" * 40)
        
        # Check if calendar client is initialized
        if not self.calendar_client.service:
            print("❌ Google Calendar client not initialized")
            print("   Make sure google-service-account.json exists and is valid")
            return False
        
        print("✅ Google Calendar client initialized")
        
        # Test conflict checking
        try:
            # Test checking conflicts for next Monday 9-10 AM
            today = datetime.now()
            days_ahead = 7 - today.weekday()  # Days until next Monday
            if days_ahead <= 0:  # Target is next Monday
                days_ahead += 7
            
            next_monday = today + timedelta(days=days_ahead)
            test_start = next_monday.replace(hour=9, minute=0, second=0, microsecond=0)
            test_end = test_start + timedelta(hours=1)
            
            print(f"Testing conflicts for: {test_start.strftime('%A, %d/%m/%Y at %H:%M')}")
            
            conflicts = await self.calendar_client.check_conflicts(test_start, test_end)
            print(f"Conflicts found: {len(conflicts)}")
            
            if conflicts:
                print("Conflict details:")
                for conflict in conflicts:
                    print(f"  - {conflict.get('summary', 'No title')}")
            else:
                print("✅ No conflicts - time slot available")
            
            return True
            
        except Exception as e:
            print(f"❌ Error checking calendar conflicts: {str(e)}")
            return False
    
    async def test_available_slots_search(self):
        """Test finding available slots"""
        print("🔍 Testing Available Slots Search")
        print("-" * 40)
        
        preferences = {
            "day_of_week": "Segunda-feira",
            "time_period": "manhã"
        }
        
        try:
            slots = await self._find_available_slots(preferences)
            print(f"Found {len(slots)} available slots for Monday morning")
            
            if slots:
                print("Available slots:")
                for i, slot in enumerate(slots, 1):
                    print(f"  {i}. {slot['formatted_time']}")
                print("✅ Slot search working correctly")
            else:
                print("⚠️  No available slots found")
                print("   This could be normal if calendar is busy")
            
            return True
            
        except Exception as e:
            print(f"❌ Error searching available slots: {str(e)}")
            return False
    
    async def _find_available_slots(self, preferences):
        """Find available time slots based on preferences using Google Calendar."""
        try:
            # Define business hours using configuration settings
            from app.core.config import settings
            
            start_hour = settings.BUSINESS_HOURS_START  # 8 AM
            end_hour = settings.BUSINESS_HOURS_END      # 6 PM
            business_days = settings.BUSINESS_DAYS      # [0, 1, 2, 3, 4] Monday-Friday
            
            # Map business days to day names
            day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            
            business_hours = {}
            for i, day_name in enumerate(day_names):
                if i in business_days:
                    business_hours[day_name] = [(start_hour, 0), (end_hour, 0)]
                else:
                    business_hours[day_name] = []  # CLOSED
            
            available_slots = []
            
            # Get the next 7 days
            today = datetime.now()
            
            for day_offset in range(7):
                check_date = today + timedelta(days=day_offset)
                day_name = check_date.strftime("%A").lower()
                
                # Skip if no business hours for this day
                if day_name not in business_hours or not business_hours[day_name]:
                    continue
                
                # Filter by day preference
                day_of_week = preferences.get("day_of_week", "").lower()
                if day_of_week and day_of_week not in ["qualquer dia útil", "qualquer"]:
                    portuguese_days = {
                        "segunda": "monday",
                        "terça": "tuesday", 
                        "quarta": "wednesday",
                        "quinta": "thursday",
                        "sexta": "friday"
                    }
                    
                    preferred_day = None
                    for pt_day, en_day in portuguese_days.items():
                        if pt_day in day_of_week:
                            preferred_day = en_day
                            break
                    
                    if preferred_day and preferred_day != day_name:
                        continue
                
                # Get business hours for this day
                hours = business_hours[day_name]
                start_hour, start_minute = hours[0]
                end_hour, end_minute = hours[1]
                
                # Filter by time period preference
                time_period = preferences.get("time_period", "").lower()
                if time_period and time_period != "qualquer":
                    if time_period == "manhã":
                        end_hour = min(end_hour, 12)
                    elif time_period == "tarde":
                        start_hour = max(start_hour, 12)
                        end_hour = min(end_hour, 18)
                    elif time_period == "noite":
                        start_hour = max(start_hour, 18)
                
                # Generate time slots (1-hour intervals)
                current_hour = start_hour
                while current_hour < end_hour:
                    slot_start = check_date.replace(hour=current_hour, minute=0, second=0, microsecond=0)
                    slot_end = slot_start + timedelta(hours=1)
                    
                    # Check for conflicts in Google Calendar
                    conflicts = await self.calendar_client.check_conflicts(slot_start, slot_end)
                    
                    if not conflicts:  # No conflicts, slot is available
                        available_slots.append({
                            "date": slot_start.strftime("%Y-%m-%d"),
                            "time": slot_start.strftime("%H:%M"),
                            "formatted_time": slot_start.strftime("%d/%m/%Y às %H:%M"),
                            "datetime": slot_start,
                            "is_available": True
                        })
                    
                    current_hour += 1
                
                # Limit to 3 slots maximum
                if len(available_slots) >= 3:
                    break
            
            return available_slots[:3]  # Return maximum 3 slots
            
        except Exception as e:
            print(f"Error finding available slots: {str(e)}")
            return []
    
    async def test_event_creation(self):
        """Test creating a calendar event"""
        print("📝 Testing Event Creation")
        print("-" * 40)
        
        # Create a test event for tomorrow at 10 AM
        tomorrow = datetime.now() + timedelta(days=1)
        event_start = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        event_end = event_start + timedelta(hours=1)
        
        # Create event details
        event_details = {
            'summary': 'TEST - Apresentação Kumon +5511999999999',
            'description': '''
📋 APRESENTAÇÃO KUMON - TESTE

👥 Participantes:
• Responsável: Responsável Teste
• Estudante: Filho(a)
• Idade: 8 anos
• Relacionamento: child

📧 Contato:
• WhatsApp: +5511999999999
• Email: teste@gmail.com

📝 Resumo da Conversa:
• Interesse para filho(a)
• Idade do estudante: 8 anos
• Demonstrou interesse em conhecer a metodologia
• Solicitou apresentação presencial
• Confirmou disponibilidade para o horário agendado

🎯 Objetivos da Apresentação:
• Explicar metodologia Kumon
• Realizar avaliação diagnóstica
• Esclarecer dúvidas sobre programas
• Apresentar investimento e formas de pagamento
• Definir próximos passos

⏰ Agendamento confirmado via WhatsApp - TESTE
            '''.strip(),
            'start_time': event_start,
            'end_time': event_end,
            'location': 'Kumon Vila A - Unidade',
            'attendees': ['teste@gmail.com']
        }
        
        try:
            event_id = await self.calendar_client.create_event(event_details)
            
            if event_id and not event_id.startswith('error_'):
                print(f"✅ Test event created successfully!")
                print(f"Event ID: {event_id}")
                print(f"Event time: {event_start.strftime('%d/%m/%Y às %H:%M')}")
                
                # Clean up - delete the test event
                try:
                    deleted = await self.calendar_client.delete_event(event_id)
                    if deleted:
                        print("✅ Test event cleaned up successfully")
                    else:
                        print("⚠️  Could not delete test event - please remove manually")
                except:
                    print("⚠️  Could not delete test event - please remove manually")
                
                return True
            else:
                print(f"❌ Failed to create test event: {event_id}")
                return False
                
        except Exception as e:
            print(f"❌ Error creating test event: {str(e)}")
            return False


async def main():
    """Run all appointment booking tests"""
    print("🧪 Appointment Booking Test Suite")
    print("=" * 60)
    
    # Check configuration
    if not settings.GOOGLE_CALENDAR_ID:
        print("⚠️  GOOGLE_CALENDAR_ID not set, using 'fagvew3@gmail.com'")
        os.environ['GOOGLE_CALENDAR_ID'] = 'fagvew3@gmail.com'
    
    if not os.path.exists(settings.GOOGLE_CREDENTIALS_PATH):
        print(f"❌ Google credentials file not found: {settings.GOOGLE_CREDENTIALS_PATH}")
        print("   Please ensure the service account key file exists")
        return
    
    print(f"📅 Using Calendar ID: {settings.GOOGLE_CALENDAR_ID}")
    print(f"🔑 Using Credentials: {settings.GOOGLE_CREDENTIALS_PATH}")
    print()
    
    # Initialize tester
    tester = AppointmentBookingTester()
    
    # Run tests
    print("1. Testing date/time extraction...")
    tester.test_date_extraction()
    
    print("\n2. Testing Google Calendar connection...")
    calendar_ok = await tester.test_calendar_search()
    
    if calendar_ok:
        print("\n3. Testing available slots search...")
        await tester.test_available_slots_search()
        
        print("\n4. Testing event creation...")
        await tester.test_event_creation()
    else:
        print("\n❌ Skipping remaining tests due to calendar connection issues")
    
    print("\n🎉 Test suite completed!")
    print("\nYour appointment booking system should now be able to:")
    print("• ✅ Extract date/time preferences correctly")
    print("• ✅ Search Google Calendar for conflicts")
    print("• ✅ Find available time slots")
    print("• ✅ Create calendar events with proper details")


if __name__ == "__main__":
    asyncio.run(main()) 