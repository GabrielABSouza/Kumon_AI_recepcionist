"""
Availability checking service with Google Calendar integration
"""
from datetime import datetime, timedelta
from typing import List, Optional
import pytz

from ..models.booking_request import AvailabilitySlot
from ..core.config import settings
from ..core.logger import app_logger
from ..clients.google_calendar import GoogleCalendarClient


class AvailabilityService:
    """Service to check calendar availability and suggest time slots"""
    
    def __init__(self):
        self.calendar_client = GoogleCalendarClient()
        self.timezone = pytz.timezone(settings.TIMEZONE)
        
        # Business configuration
        self.business_hours = {
            'start': settings.BUSINESS_HOURS_START,
            'end': settings.BUSINESS_HOURS_END
        }
        self.business_days = settings.BUSINESS_DAYS
        self.appointment_duration = settings.APPOINTMENT_DURATION_MINUTES
        self.buffer_time = settings.BUFFER_TIME_MINUTES
    
    async def get_available_slots(
        self, 
        days_ahead: int = 14,
        preferred_date: Optional[str] = None,
        appointment_type: str = "consultation"
    ) -> List[AvailabilitySlot]:
        """Get available time slots for appointments"""
        
        try:
            if preferred_date:
                # Check specific date
                target_date = datetime.strptime(preferred_date, "%Y-%m-%d").date()
                return await self._get_slots_for_date(target_date, appointment_type)
            else:
                # Get slots for the next N days
                return await self._get_slots_for_period(days_ahead, appointment_type)
                
        except Exception as e:
            app_logger.error(f"Error getting available slots: {str(e)}")
            return []
    
    async def _get_slots_for_period(
        self, 
        days_ahead: int, 
        appointment_type: str
    ) -> List[AvailabilitySlot]:
        """Get available slots for a period of days"""
        
        all_slots = []
        start_date = datetime.now(self.timezone).date() + timedelta(days=1)  # Start tomorrow
        
        for i in range(days_ahead):
            check_date = start_date + timedelta(days=i)
            
            # Skip non-business days
            if check_date.weekday() not in self.business_days:
                continue
            
            day_slots = await self._get_slots_for_date(check_date, appointment_type)
            all_slots.extend(day_slots)
            
            # Limit total slots returned
            if len(all_slots) >= 10:
                break
        
        return all_slots[:10]  # Return max 10 slots
    
    async def _get_slots_for_date(
        self, 
        date: datetime.date, 
        appointment_type: str
    ) -> List[AvailabilitySlot]:
        """Get available slots for a specific date"""
        
        # Skip weekends if not in business days
        if date.weekday() not in self.business_days:
            return []
        
        # Generate potential time slots
        potential_slots = self._generate_time_slots(date)
        
        # Check each slot against calendar
        available_slots = []
        
        for slot_time in potential_slots:
            if await self._is_slot_available(date, slot_time):
                slot = AvailabilitySlot(
                    date=date.strftime("%Y-%m-%d"),
                    time=slot_time,
                    duration_minutes=self.appointment_duration,
                    slot_type=appointment_type
                )
                available_slots.append(slot)
        
        return available_slots
    
    def _generate_time_slots(self, date: datetime.date) -> List[str]:
        """Generate potential time slots for a given date"""
        
        slots = []
        current_time = self.business_hours['start']
        
        while current_time + (self.appointment_duration / 60) <= self.business_hours['end']:
            slots.append(f"{current_time:02d}:00")
            current_time += 1  # 1-hour slots
        
        return slots
    
    async def _is_slot_available(self, date: datetime.date, time: str) -> bool:
        """Check if a specific time slot is available"""
        
        try:
            # Create datetime for the slot
            slot_datetime = datetime.combine(date, datetime.strptime(time, "%H:%M").time())
            slot_datetime = self.timezone.localize(slot_datetime)
            
            # Add buffer time for checking conflicts
            start_check = slot_datetime - timedelta(minutes=self.buffer_time)
            end_check = slot_datetime + timedelta(minutes=self.appointment_duration + self.buffer_time)
            
            # Check for conflicts in Google Calendar
            conflicts = await self.calendar_client.check_conflicts(start_check, end_check)
            
            return len(conflicts) == 0
            
        except Exception as e:
            app_logger.error(f"Error checking slot availability: {str(e)}")
            return False
    
    async def check_specific_time_availability(
        self, 
        date: str, 
        time: str
    ) -> bool:
        """Check if a specific date/time is available"""
        
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
            return await self._is_slot_available(target_date, time)
            
        except Exception as e:
            app_logger.error(f"Error checking specific time availability: {str(e)}")
            return False
    
    def format_availability_message(self, slots: List[AvailabilitySlot]) -> str:
        """Format available slots into a user-friendly message"""
        
        if not slots:
            return "No momento não temos horários disponíveis. Por favor, entre em contato diretamente."
        
        message = "📅 Horários disponíveis:\n\n"
        
        for i, slot in enumerate(slots[:5], 1):  # Show max 5 slots
            # Format date in Portuguese
            date_obj = datetime.strptime(slot.date, "%Y-%m-%d")
            day_name = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][date_obj.weekday()]
            formatted_date = f"{day_name}, {date_obj.day:02d}/{date_obj.month:02d}"
            
            message += f"{i}. {formatted_date} às {slot.time}\n"
        
        message += "\nDigite o número da opção desejada ou me informe outro horário de sua preferência."
        
        return message 