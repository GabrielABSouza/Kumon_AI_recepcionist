"""
Booking request models for state management
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class BookingStatus(str, Enum):
    INITIATED = "initiated"
    COLLECTING_INFO = "collecting_info" 
    CHECKING_AVAILABILITY = "checking_availability"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class BookingRequest(BaseModel):
    """Booking request tracking model"""
    id: Optional[str] = None
    phone_number: str = Field(..., description="User phone number")
    status: BookingStatus = BookingStatus.INITIATED
    
    # Student Information
    student_name: Optional[str] = None
    student_age: Optional[int] = None
    student_grade: Optional[str] = None
    
    # Parent Information  
    parent_name: Optional[str] = None
    parent_email: Optional[str] = None
    
    # Appointment Details
    requested_date: Optional[str] = None  # "2024-01-15"
    requested_time: Optional[str] = None  # "14:00"
    appointment_type: Optional[str] = "consultation"  # consultation, assessment, etc.
    
    # Calendar Information
    calendar_event_id: Optional[str] = None
    confirmed_datetime: Optional[datetime] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class AvailabilitySlot(BaseModel):
    """Available time slot model"""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    time: str = Field(..., description="Time in HH:MM format")
    duration_minutes: int = Field(default=60)
    is_available: bool = True
    slot_type: str = "consultation"  # consultation, assessment, etc.
    
    @property
    def datetime_str(self) -> str:
        return f"{self.date} {self.time}"


class BookingConfirmation(BaseModel):
    """Booking confirmation details"""
    booking_id: str
    calendar_event_id: str
    student_name: str
    parent_name: str
    appointment_datetime: datetime
    appointment_type: str
    confirmation_message: str 