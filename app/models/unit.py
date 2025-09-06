"""
Unit models for multi-center support
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class UnitConfig(BaseModel):
    """Configuration for a specific Kumon unit"""
    user_id: str = Field(..., description="Unique identifier for the unit")
    username: str = Field(..., description="Display name of the unit")
    address: str = Field(..., description="Physical address of the unit")
    phone: str = Field(..., description="Contact phone number")
    email: Optional[str] = Field(None, description="Contact email")
    
    # Operating hours
    operating_hours: Dict[str, str] = Field(default_factory=dict, description="Operating hours by day")
    timezone: str = Field(default="America/Sao_Paulo", description="Timezone for the unit")
    
    # Services and pricing
    services: Dict[str, Any] = Field(default_factory=dict, description="Available services and pricing")
    
    # Custom responses
    custom_responses: Dict[str, str] = Field(default_factory=dict, description="Unit-specific response templates")
    
    # Google Calendar integration
    google_calendar_id: Optional[str] = Field(None, description="Google Calendar ID for appointments")
    
    # Status
    is_active: bool = Field(default=True, description="Whether the unit is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Unit(BaseModel):
    """Kumon unit/center representation"""
    config: UnitConfig
    
    def get_operating_hours_text(self) -> str:
        """Get formatted operating hours text"""
        if not self.config.operating_hours:
            return "Horários não configurados"
        
        hours_text = []
        for day, hours in self.config.operating_hours.items():
            hours_text.append(f"{day}: {hours}")
        
        return "\n".join(hours_text)
    
    def get_services_text(self) -> str:
        """Get formatted services text"""
        if not self.config.services:
            return "Serviços não configurados"
        
        services_text = []
        for service, details in self.config.services.items():
            if isinstance(details, dict) and "price" in details:
                services_text.append(f"• {service}: R$ {details['price']}")
            else:
                services_text.append(f"• {service}")
        
        return "\n".join(services_text)


class CreateUnitRequest(BaseModel):
    """Request model for creating a new unit"""
    username: str
    address: str
    phone: str
    email: Optional[str] = None
    operating_hours: Optional[Dict[str, str]] = None
    services: Optional[Dict[str, Any]] = None
    custom_responses: Optional[Dict[str, str]] = None
    google_calendar_id: Optional[str] = None


class UpdateUnitRequest(BaseModel):
    """Request model for updating a unit"""
    username: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    operating_hours: Optional[Dict[str, str]] = None
    services: Optional[Dict[str, Any]] = None
    custom_responses: Optional[Dict[str, str]] = None
    google_calendar_id: Optional[str] = None
    is_active: Optional[bool] = None


class UnitResponse(BaseModel):
    """Response model for unit operations"""
    user_id: str
    username: str
    address: str
    phone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime 