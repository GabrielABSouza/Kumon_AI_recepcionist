"""
WhatsApp message models
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from dataclasses import dataclass


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"


class MessageStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    RESPONDED = "responded"
    FAILED = "failed"


class WhatsAppMessage(BaseModel):
    """WhatsApp message model"""
    message_id: str = Field(..., description="WhatsApp message ID")
    from_number: str = Field(..., description="Sender phone number")
    to_number: str = Field(..., description="Recipient phone number")
    message_type: MessageType = Field(..., description="Type of message")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class MessageResponse(BaseModel):
    """Response to be sent back to WhatsApp"""
    to_number: str = Field(..., description="Recipient phone number")
    message_type: MessageType = MessageType.TEXT
    content: str = Field(..., description="Response content")
    reply_to_message_id: Optional[str] = None
    
    class Config:
        use_enum_values = True


class ConversationState(BaseModel):
    """Track conversation state for context"""
    phone_number: str = Field(..., description="User phone number")
    current_intent: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    last_message_time: datetime = Field(default_factory=datetime.utcnow)
    booking_in_progress: bool = False
    
    # Booking specific context
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    student_name: Optional[str] = None
    parent_name: Optional[str] = None
    contact_info: Optional[Dict[str, str]] = None 


@dataclass
class ProcessingMetrics:
    """Message processing performance metrics"""

    total_messages: int = 0
    processed_messages: int = 0
    blocked_messages: int = 0
    escalated_messages: int = 0
    error_messages: int = 0
    avg_processing_time: float = 0.0
    security_incidents: int = 0
    validation_failures: int = 0