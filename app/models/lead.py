"""
Lead management models
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from enum import Enum


class LeadSource(str, Enum):
    WHATSAPP = "whatsapp"
    WEBSITE = "website"
    REFERRAL = "referral"
    SOCIAL_MEDIA = "social_media"


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    SCHEDULED = "scheduled"
    CONVERTED = "converted"
    LOST = "lost"


class Lead(BaseModel):
    """Lead information model"""
    id: Optional[str] = None
    phone_number: str = Field(..., description="Contact phone number")
    source: LeadSource = LeadSource.WHATSAPP
    status: LeadStatus = LeadStatus.NEW
    
    # Parent Information
    parent_name: Optional[str] = None
    parent_email: Optional[EmailStr] = None
    
    # Student Information
    student_name: Optional[str] = None
    student_age: Optional[int] = None
    student_grade: Optional[str] = None
    current_school: Optional[str] = None
    
    # Interest Information
    subjects_interested: Optional[str] = None  # "Math, English"
    current_challenges: Optional[str] = None
    goals: Optional[str] = None
    
    # Interaction Data
    first_contact_date: datetime = Field(default_factory=datetime.utcnow)
    last_interaction_date: datetime = Field(default_factory=datetime.utcnow)
    interaction_count: int = 0
    
    # Additional Information
    notes: Optional[str] = None
    tags: Optional[str] = None  # Comma-separated tags
    referral_source: Optional[str] = None
    
    # System Fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class LeadInteraction(BaseModel):
    """Lead interaction tracking"""
    lead_id: str
    interaction_type: str  # "message", "call", "email", "booking"
    content: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict) 