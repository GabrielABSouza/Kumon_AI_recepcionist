"""
Unit management service for multi-center support
"""
from typing import Dict, Optional, List
from datetime import datetime
import uuid

from app.models.unit import Unit, UnitConfig, CreateUnitRequest, UpdateUnitRequest, UnitResponse
from app.core.logger import app_logger


class UnitManager:
    """Manages multiple Kumon units/centers"""
    
    def __init__(self):
        self._units: Dict[str, Unit] = {}
        self._initialize_default_units()
    
    def _initialize_default_units(self):
        """Initialize with some default units for testing"""
        # You can remove this and load from database in production
        default_units = [
            {
                "unit_id": "kumon-central",
                "unit_name": "Kumon Central",
                "address": "Rua Principal, 123 - Centro",
                "phone": "(11) 9999-1234",
                "email": "central@kumon.com.br",
                "whatsapp_phone_number_id": "691913557337608",  # Your current WhatsApp number
                "whatsapp_business_account_id": "1794212181478815",  # Your current business account
                "operating_hours": {
                    "Segunda-feira": "08:00 - 18:00",
                    "Terça-feira": "08:00 - 18:00", 
                    "Quarta-feira": "08:00 - 18:00",
                    "Quinta-feira": "08:00 - 18:00",
                    "Sexta-feira": "08:00 - 18:00",
                    "Sábado": "08:00 - 12:00"
                },
                "services": {
                    "Matemática": {"price": "150.00", "description": "Programa de matemática Kumon"},
                    "Português": {"price": "150.00", "description": "Programa de português Kumon"},
                    "Inglês": {"price": "180.00", "description": "Programa de inglês Kumon"}
                },
                "custom_responses": {
                    "greeting": "Olá! Bem-vindo ao Kumon Central! Como posso ajudá-lo hoje?",
                    "business_hours": "Nosso horário de funcionamento:\n{operating_hours}",
                    "services": "Nossos programas disponíveis:\n{services}"
                }
            }
        ]
        
        for unit_data in default_units:
            unit_config = UnitConfig(**unit_data)
            unit = Unit(config=unit_config)
            self._units[unit_data["unit_id"]] = unit
            app_logger.info(f"Initialized default unit: {unit_data['unit_name']}")
    
    def create_unit(self, request: CreateUnitRequest) -> UnitResponse:
        """Create a new unit"""
        unit_id = f"kumon-{uuid.uuid4().hex[:8]}"
        
        unit_config = UnitConfig(
            unit_id=unit_id,
            unit_name=request.unit_name,
            address=request.address,
            phone=request.phone,
            email=request.email,
            whatsapp_phone_number_id=request.whatsapp_phone_number_id,
            whatsapp_business_account_id=request.whatsapp_business_account_id,
            operating_hours=request.operating_hours or {},
            services=request.services or {},
            custom_responses=request.custom_responses or {},
            google_calendar_id=request.google_calendar_id
        )
        
        unit = Unit(config=unit_config)
        self._units[unit_id] = unit
        
        app_logger.info(f"Created new unit: {unit_id} - {request.unit_name}")
        
        return UnitResponse(
            unit_id=unit_id,
            unit_name=unit_config.unit_name,
            address=unit_config.address,
            phone=unit_config.phone,
            is_active=unit_config.is_active,
            created_at=unit_config.created_at,
            updated_at=unit_config.updated_at
        )
    
    def get_unit(self, unit_id: str) -> Optional[Unit]:
        """Get a unit by ID"""
        return self._units.get(unit_id)
    
    def get_unit_by_phone_number_id(self, phone_number_id: str) -> Optional[Unit]:
        """Get a unit by WhatsApp phone number ID"""
        for unit in self._units.values():
            if unit.config.whatsapp_phone_number_id == phone_number_id:
                return unit
        return None
    
    def list_units(self, active_only: bool = True) -> List[UnitResponse]:
        """List all units"""
        units = []
        for unit in self._units.values():
            if not active_only or unit.config.is_active:
                units.append(UnitResponse(
                    unit_id=unit.config.unit_id,
                    unit_name=unit.config.unit_name,
                    address=unit.config.address,
                    phone=unit.config.phone,
                    is_active=unit.config.is_active,
                    created_at=unit.config.created_at,
                    updated_at=unit.config.updated_at
                ))
        return units
    
    def update_unit(self, unit_id: str, request: UpdateUnitRequest) -> Optional[UnitResponse]:
        """Update an existing unit"""
        unit = self._units.get(unit_id)
        if not unit:
            return None
        
        # Update fields that are provided
        if request.unit_name is not None:
            unit.config.unit_name = request.unit_name
        if request.address is not None:
            unit.config.address = request.address
        if request.phone is not None:
            unit.config.phone = request.phone
        if request.email is not None:
            unit.config.email = request.email
        if request.operating_hours is not None:
            unit.config.operating_hours = request.operating_hours
        if request.services is not None:
            unit.config.services = request.services
        if request.custom_responses is not None:
            unit.config.custom_responses = request.custom_responses
        if request.google_calendar_id is not None:
            unit.config.google_calendar_id = request.google_calendar_id
        if request.is_active is not None:
            unit.config.is_active = request.is_active
        
        unit.config.updated_at = datetime.utcnow()
        
        app_logger.info(f"Updated unit: {unit_id} - {unit.config.unit_name}")
        
        return UnitResponse(
            unit_id=unit.config.unit_id,
            unit_name=unit.config.unit_name,
            address=unit.config.address,
            phone=unit.config.phone,
            is_active=unit.config.is_active,
            created_at=unit.config.created_at,
            updated_at=unit.config.updated_at
        )
    
    def delete_unit(self, unit_id: str) -> bool:
        """Delete a unit (soft delete by marking as inactive)"""
        unit = self._units.get(unit_id)
        if not unit:
            return False
        
        unit.config.is_active = False
        unit.config.updated_at = datetime.utcnow()
        
        app_logger.info(f"Deactivated unit: {unit_id} - {unit.config.unit_name}")
        return True
    
    def get_unit_context(self, unit_id: str) -> Dict[str, str]:
        """Get unit-specific context for AI responses"""
        unit = self.get_unit(unit_id)
        if not unit:
            return {}
        
        return {
            "unit_name": unit.config.unit_name,
            "address": unit.config.address,
            "phone": unit.config.phone,
            "email": unit.config.email or "",
            "operating_hours": unit.get_operating_hours_text(),
            "services": unit.get_services_text(),
            "timezone": unit.config.timezone
        }


# Global unit manager instance
unit_manager = UnitManager() 