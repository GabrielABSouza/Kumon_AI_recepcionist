"""
Intent classification models
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum

class IntentType(str, Enum):
    """Possible intent types"""
    GREETING = "greeting"
    SCHEDULE_APPOINTMENT = "schedule_appointment"
    QUESTION = "question"
    BUSINESS_INFO = "business_info"
    COMPLAINT = "complaint"
    GENERAL_INQUIRY = "general_inquiry"
    PROVIDE_INFO = "provide_info"

class Intent(BaseModel):
    """Intent classification result"""
    intent_type: IntentType
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    entities: Optional[Dict[str, Any]] = None
    raw_message: str
    classification_method: str = "keyword"  # "keyword" or "openai"
    
    class Config:
        use_enum_values = True 