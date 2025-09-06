"""
WhatsApp webhook models
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class WebhookVerification(BaseModel):
    """WhatsApp webhook verification request"""
    hub_mode: str = Field(..., alias="hub.mode")
    hub_challenge: str = Field(..., alias="hub.challenge") 
    hub_verify_token: str = Field(..., alias="hub.verify_token")

    class Config:
        populate_by_name = True


class WebhookContact(BaseModel):
    """Contact information"""
    profile: Optional[Dict[str, Any]] = None
    wa_id: str


class WebhookText(BaseModel):
    """Text message content"""
    body: str


class WebhookMessage(BaseModel):
    """WhatsApp message"""
    from_: str = Field(..., alias="from")
    id: str
    timestamp: str
    text: Optional[WebhookText] = None
    type: str

    class Config:
        populate_by_name = True


class WebhookValue(BaseModel):
    """Webhook value object"""
    messaging_product: str
    metadata: Dict[str, Any]
    contacts: Optional[List[WebhookContact]] = None
    messages: Optional[List[WebhookMessage]] = None


class WebhookEntry(BaseModel):
    """Webhook entry"""
    id: str
    changes: List[Dict[str, Any]]


class WhatsAppWebhook(BaseModel):
    """Complete WhatsApp webhook payload"""
    object: str
    entry: List[WebhookEntry]


class WebhookResponse(BaseModel):
    """Standard webhook response"""
    status: str
    message: Optional[str] = None 