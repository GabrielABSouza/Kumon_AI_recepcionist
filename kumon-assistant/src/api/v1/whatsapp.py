"""
WhatsApp webhook routes
"""
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from fastapi.responses import PlainTextResponse
import hmac
import hashlib
from typing import Dict, Any

from app.models.webhook import WhatsAppWebhook, WebhookResponse
from app.models.message import WhatsAppMessage, MessageType, MessageResponse
from app.services.message_processor import MessageProcessor
from app.core.config import settings
from app.core.logger import app_logger

router = APIRouter()

# Initialize message processor
message_processor = MessageProcessor()


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"), 
    hub_verify_token: str = Query(..., alias="hub.verify_token")
):
    """
    Verify WhatsApp webhook
    This endpoint is called by WhatsApp to verify the webhook URL
    """
    app_logger.info("Webhook verification requested", extra={
        "hub_mode": hub_mode,
        "hub_verify_token": hub_verify_token
    })
    
    # Verify the token matches our configured token
    if hub_verify_token != settings.WHATSAPP_VERIFY_TOKEN:
        app_logger.error("Invalid verification token")
        raise HTTPException(status_code=403, detail="Invalid verification token")
    
    if hub_mode != "subscribe":
        app_logger.error(f"Invalid hub mode: {hub_mode}")
        raise HTTPException(status_code=400, detail="Invalid hub mode")
    
    app_logger.info("Webhook verification successful")
    # Return the challenge to verify the webhook
    return PlainTextResponse(content=hub_challenge)


@router.post("/webhook")
async def handle_webhook(webhook_data: WhatsAppWebhook):
    """
    Handle incoming WhatsApp webhook
    This endpoint receives messages from WhatsApp
    """
    app_logger.info("Webhook received", extra={
        "object": webhook_data.object,
        "entries_count": len(webhook_data.entry)
    })
    
    try:
        # Process each entry in the webhook
        for entry in webhook_data.entry:
            for change in entry.changes:
                # Check if this is a message change
                if change.get("field") == "messages":
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    
                    # Process each message
                    for message_data in messages:
                        await process_incoming_message(message_data, value)
        
        return WebhookResponse(status="success")
        
    except Exception as e:
        app_logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing webhook")


async def process_incoming_message(message_data: Dict[str, Any], value: Dict[str, Any]):
    """Process a single incoming WhatsApp message"""
    
    try:
        # Extract message information
        message_id = message_data.get("id")
        from_number = message_data.get("from")
        message_type = message_data.get("type", "text")
        timestamp = message_data.get("timestamp")
        
        # Get phone number from metadata
        metadata = value.get("metadata", {})
        to_number = metadata.get("phone_number_id")
        
        # Extract message content based on type
        content = ""
        if message_type == "text" and "text" in message_data:
            content = message_data["text"]["body"]
        else:
            content = f"[{message_type} message]"
        
        app_logger.info("Processing message", extra={
            "message_id": message_id,
            "from_number": from_number,
            "message_type": message_type
        })
        
        # Create WhatsApp message object
        whatsapp_message = WhatsAppMessage(
            message_id=message_id,
            from_number=from_number,
            to_number=to_number,
            message_type=MessageType.TEXT if message_type == "text" else MessageType.TEXT,
            content=content,
            metadata=message_data
        )
        
        # Process the message through our AI system
        response = await message_processor.process_message(whatsapp_message)
        
        # Send response back to WhatsApp (this will be implemented in WhatsApp client)
        app_logger.info("Message processed successfully", extra={
            "message_id": message_id,
            "response_length": len(response.content)
        })
        
    except Exception as e:
        app_logger.error(f"Error processing message: {str(e)}", extra={
            "message_id": message_data.get("id"),
            "from_number": message_data.get("from")
        })
        raise


@router.get("/status")
async def webhook_status():
    """Get webhook status and configuration"""
    return {
        "status": "active",
        "webhook_url": settings.WHATSAPP_WEBHOOK_URL,
        "verify_token_configured": bool(settings.WHATSAPP_VERIFY_TOKEN),
        "message_processor": "initialized"
    } 