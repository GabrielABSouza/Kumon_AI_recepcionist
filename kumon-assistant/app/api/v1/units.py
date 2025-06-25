"""
Multi-unit WhatsApp webhook routes and unit management
"""
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from fastapi.responses import PlainTextResponse
from typing import List, Dict, Any

from app.models.webhook import WhatsAppWebhook, WebhookResponse
from app.models.message import WhatsAppMessage, MessageType
from app.models.unit import CreateUnitRequest, UpdateUnitRequest, UnitResponse
from app.services.unit_manager import unit_manager
from app.services.message_processor import MessageProcessor
from app.core.config import settings
from app.core.logger import app_logger

router = APIRouter()

# Initialize message processor
message_processor = MessageProcessor()


# Unit Management Endpoints
@router.post("/units", response_model=UnitResponse)
async def create_unit(request: CreateUnitRequest):
    """Create a new Kumon unit"""
    try:
        return unit_manager.create_unit(request)
    except Exception as e:
        app_logger.error(f"Error creating unit: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creating unit")


@router.get("/units", response_model=List[UnitResponse])
async def list_units(active_only: bool = Query(True, description="Only return active units")):
    """List all Kumon units"""
    return unit_manager.list_units(active_only=active_only)


@router.get("/units/{unit_id}", response_model=UnitResponse)
async def get_unit(unit_id: str = Path(..., description="Unit ID")):
    """Get a specific unit by ID"""
    unit = unit_manager.get_unit(unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    return UnitResponse(
        unit_id=unit.config.unit_id,
        unit_name=unit.config.unit_name,
        address=unit.config.address,
        phone=unit.config.phone,
        is_active=unit.config.is_active,
        created_at=unit.config.created_at,
        updated_at=unit.config.updated_at
    )


@router.put("/units/{unit_id}", response_model=UnitResponse)
async def update_unit(
    request: UpdateUnitRequest,
    unit_id: str = Path(..., description="Unit ID")
):
    """Update a specific unit"""
    result = unit_manager.update_unit(unit_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Unit not found")
    return result


@router.delete("/units/{unit_id}")
async def delete_unit(unit_id: str = Path(..., description="Unit ID")):
    """Delete (deactivate) a specific unit"""
    if not unit_manager.delete_unit(unit_id):
        raise HTTPException(status_code=404, detail="Unit not found")
    return {"message": "Unit deactivated successfully"}


# Unit-specific WhatsApp Webhook Endpoints
@router.get("/units/{unit_id}/webhook")
async def verify_unit_webhook(
    unit_id: str = Path(..., description="Unit ID"),
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"), 
    hub_verify_token: str = Query(..., alias="hub.verify_token")
):
    """
    Verify WhatsApp webhook for a specific unit
    This endpoint is called by WhatsApp to verify the webhook URL
    """
    app_logger.info("Unit webhook verification requested", extra={
        "unit_id": unit_id,
        "hub_mode": hub_mode,
        "hub_verify_token": hub_verify_token
    })
    
    # Check if unit exists and is active
    unit = unit_manager.get_unit(unit_id)
    if not unit or not unit.config.is_active:
        app_logger.error(f"Unit not found or inactive: {unit_id}")
        raise HTTPException(status_code=404, detail="Unit not found or inactive")
    
    # Verify the token matches our configured token
    if hub_verify_token != settings.WHATSAPP_VERIFY_TOKEN:
        app_logger.error("Invalid verification token")
        raise HTTPException(status_code=403, detail="Invalid verification token")
    
    if hub_mode != "subscribe":
        app_logger.error(f"Invalid hub mode: {hub_mode}")
        raise HTTPException(status_code=400, detail="Invalid hub mode")
    
    app_logger.info(f"Unit webhook verification successful for unit: {unit_id}")
    # Return the challenge to verify the webhook
    return PlainTextResponse(content=hub_challenge)


@router.post("/units/{unit_id}/webhook")
async def handle_unit_webhook(
    unit_id: str = Path(..., description="Unit ID"),
    webhook_data: WhatsAppWebhook = None
):
    """
    Handle incoming WhatsApp webhook for a specific unit
    This endpoint receives messages from WhatsApp for a specific unit
    """
    app_logger.info("Unit webhook received", extra={
        "unit_id": unit_id,
        "object": webhook_data.object if webhook_data else None,
        "entries_count": len(webhook_data.entry) if webhook_data else 0
    })
    
    # Check if unit exists and is active
    unit = unit_manager.get_unit(unit_id)
    if not unit or not unit.config.is_active:
        app_logger.error(f"Unit not found or inactive: {unit_id}")
        raise HTTPException(status_code=404, detail="Unit not found or inactive")
    
    try:
        # Process each entry in the webhook
        for entry in webhook_data.entry:
            for change in entry.changes:
                # Check if this is a message change
                if change.get("field") == "messages":
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    
                    # Process each message with unit context
                    for message_data in messages:
                        await process_unit_message(message_data, value, unit_id)
        
        return WebhookResponse(status="success")
        
    except Exception as e:
        app_logger.error(f"Error processing unit webhook: {str(e)}", extra={"unit_id": unit_id})
        raise HTTPException(status_code=500, detail="Error processing webhook")


async def process_unit_message(message_data: Dict[str, Any], value: Dict[str, Any], unit_id: str):
    """Process a single incoming WhatsApp message for a specific unit"""
    
    try:
        # Get unit context
        unit = unit_manager.get_unit(unit_id)
        if not unit:
            raise Exception(f"Unit not found: {unit_id}")
        
        # Extract message information
        message_id = message_data.get("id")
        from_number = message_data.get("from")
        message_type = message_data.get("type", "text")
        timestamp = message_data.get("timestamp")
        
        # Get phone number from metadata
        metadata = value.get("metadata", {})
        to_number = metadata.get("phone_number_id")
        
        # Verify the message is for this unit's phone number
        if to_number != unit.config.whatsapp_phone_number_id:
            app_logger.warning(f"Message phone number mismatch for unit {unit_id}", extra={
                "expected": unit.config.whatsapp_phone_number_id,
                "received": to_number
            })
            return
        
        # Extract message content based on type
        content = ""
        if message_type == "text" and "text" in message_data:
            content = message_data["text"]["body"]
        else:
            content = f"[{message_type} message]"
        
        app_logger.info("Processing unit message", extra={
            "unit_id": unit_id,
            "message_id": message_id,
            "from_number": from_number,
            "message_type": message_type
        })
        
        # Create WhatsApp message object with unit context
        whatsapp_message = WhatsAppMessage(
            message_id=message_id,
            from_number=from_number,
            to_number=to_number,
            message_type=MessageType.TEXT if message_type == "text" else MessageType.TEXT,
            content=content,
            metadata={
                **message_data,
                "unit_id": unit_id,
                "unit_context": unit_manager.get_unit_context(unit_id)
            }
        )
        
        # Process the message through our AI system with unit context
        response = await message_processor.process_message(whatsapp_message)
        
        app_logger.info("Unit message processed successfully", extra={
            "unit_id": unit_id,
            "message_id": message_id,
            "response_length": len(response.content)
        })
        
    except Exception as e:
        app_logger.error(f"Error processing unit message: {str(e)}", extra={
            "unit_id": unit_id,
            "message_id": message_data.get("id"),
            "from_number": message_data.get("from")
        })
        raise


@router.get("/units/{unit_id}/status")
async def get_unit_webhook_status(unit_id: str = Path(..., description="Unit ID")):
    """Get webhook status and configuration for a specific unit"""
    unit = unit_manager.get_unit(unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    return {
        "unit_id": unit_id,
        "unit_name": unit.config.unit_name,
        "status": "active" if unit.config.is_active else "inactive",
        "webhook_url": f"{settings.WHATSAPP_WEBHOOK_URL}/units/{unit_id}/webhook",
        "whatsapp_phone_number_id": unit.config.whatsapp_phone_number_id,
        "whatsapp_business_account_id": unit.config.whatsapp_business_account_id,
        "verify_token_configured": bool(settings.WHATSAPP_VERIFY_TOKEN),
        "message_processor": "initialized"
    }


@router.get("/units/{unit_id}/context")
async def get_unit_context(unit_id: str = Path(..., description="Unit ID")):
    """Get unit context for AI responses"""
    unit = unit_manager.get_unit(unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    return unit_manager.get_unit_context(unit_id) 