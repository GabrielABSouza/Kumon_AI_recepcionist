"""
Evolution API integration endpoints for WhatsApp
"""
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import asyncio
import json

from ..clients.evolution_api import evolution_api_client, WhatsAppMessage, InstanceInfo
from ..services.enhanced_rag_engine import enhanced_rag_engine
from ..services.message_processor import MessageProcessor
from ..core.logger import app_logger
from ..core.config import settings

router = APIRouter(prefix="/api/v1/evolution", tags=["evolution"])


class CreateInstanceRequest(BaseModel):
    """Request model for creating WhatsApp instance"""
    instance_name: str = Field(..., description="Name for the WhatsApp instance")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for this instance")


class SendMessageRequest(BaseModel):
    """Request model for sending messages"""
    instance_name: str = Field(..., description="WhatsApp instance name")
    phone: str = Field(..., description="Phone number to send message to")
    message: str = Field(..., description="Message text to send")


class SendMediaRequest(BaseModel):
    """Request model for sending media messages"""
    instance_name: str = Field(..., description="WhatsApp instance name")
    phone: str = Field(..., description="Phone number to send message to")
    media_url: str = Field(..., description="URL of the media to send")
    caption: Optional[str] = Field(None, description="Caption for the media")
    media_type: str = Field("image", description="Type of media (image, video, audio, document)")


class SendButtonRequest(BaseModel):
    """Request model for sending button messages"""
    instance_name: str = Field(..., description="WhatsApp instance name")
    phone: str = Field(..., description="Phone number to send message to")
    text: str = Field(..., description="Message text")
    buttons: List[Dict[str, str]] = Field(..., description="List of buttons with text")


# Initialize message processor
message_processor = MessageProcessor()


@router.post("/instances")
async def create_instance(request: CreateInstanceRequest):
    """Create a new WhatsApp instance"""
    try:
        result = await evolution_api_client.create_instance(
            instance_name=request.instance_name,
            webhook_url=request.webhook_url
        )
        
        return {
            "success": True,
            "message": f"Instance '{request.instance_name}' created successfully",
            "data": result
        }
        
    except Exception as e:
        app_logger.error(f"Error creating instance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create instance: {str(e)}")


@router.get("/instances")
async def list_instances():
    """List all WhatsApp instances"""
    try:
        instances = await evolution_api_client.list_instances()
        
        return {
            "success": True,
            "instances": [
                {
                    "instance_name": instance.instance_name,
                    "status": instance.status,
                    "phone_number": instance.phone_number,
                    "profile_name": instance.profile_name
                }
                for instance in instances
            ]
        }
        
    except Exception as e:
        app_logger.error(f"Error listing instances: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list instances: {str(e)}")


@router.get("/instances/{instance_name}")
async def get_instance_info(instance_name: str):
    """Get information about a specific WhatsApp instance"""
    try:
        instance = await evolution_api_client.get_instance_info(instance_name)
        
        return {
            "success": True,
            "instance": {
                "instance_name": instance.instance_name,
                "status": instance.status,
                "qr_code": instance.qr_code,
                "phone_number": instance.phone_number,
                "profile_name": instance.profile_name
            }
        }
        
    except Exception as e:
        app_logger.error(f"Error getting instance info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get instance info: {str(e)}")


@router.get("/instances/{instance_name}/qr")
async def get_qr_code(instance_name: str):
    """Get QR code for WhatsApp instance"""
    try:
        qr_code = await evolution_api_client.get_qr_code(instance_name)
        
        if qr_code:
            return {
                "success": True,
                "qr_code": qr_code,
                "message": "Scan this QR code with WhatsApp to connect the instance"
            }
        else:
            return {
                "success": False,
                "message": "QR code not available or instance already connected"
            }
        
    except Exception as e:
        app_logger.error(f"Error getting QR code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get QR code: {str(e)}")


@router.get("/instances/{instance_name}/status")
async def get_instance_status(instance_name: str):
    """Get connection status of an instance"""
    try:
        status = await evolution_api_client.get_instance_status(instance_name)
        
        return {
            "success": True,
            "instance_name": instance_name,
            "status": status,
            "connected": status == "open"
        }
        
    except Exception as e:
        app_logger.error(f"Error getting instance status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get instance status: {str(e)}")


@router.delete("/instances/{instance_name}")
async def delete_instance(instance_name: str):
    """Delete a WhatsApp instance"""
    try:
        success = await evolution_api_client.delete_instance(instance_name)
        
        if success:
            return {
                "success": True,
                "message": f"Instance '{instance_name}' deleted successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete instance")
        
    except Exception as e:
        app_logger.error(f"Error deleting instance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete instance: {str(e)}")


@router.put("/instances/{instance_name}/restart")
async def restart_instance(instance_name: str):
    """Restart a WhatsApp instance"""
    try:
        success = await evolution_api_client.restart_instance(instance_name)
        
        if success:
            return {
                "success": True,
                "message": f"Instance '{instance_name}' restarted successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to restart instance")
        
    except Exception as e:
        app_logger.error(f"Error restarting instance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to restart instance: {str(e)}")


@router.post("/messages/text")
async def send_text_message(request: SendMessageRequest):
    """Send a text message via WhatsApp"""
    try:
        result = await evolution_api_client.send_text_message(
            instance_name=request.instance_name,
            phone=request.phone,
            message=request.message
        )
        
        return {
            "success": True,
            "message": "Text message sent successfully",
            "data": result
        }
        
    except Exception as e:
        app_logger.error(f"Error sending text message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@router.post("/messages/media")
async def send_media_message(request: SendMediaRequest):
    """Send a media message via WhatsApp"""
    try:
        result = await evolution_api_client.send_media_message(
            instance_name=request.instance_name,
            phone=request.phone,
            media_url=request.media_url,
            caption=request.caption,
            media_type=request.media_type
        )
        
        return {
            "success": True,
            "message": "Media message sent successfully",
            "data": result
        }
        
    except Exception as e:
        app_logger.error(f"Error sending media message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send media message: {str(e)}")


@router.post("/messages/buttons")
async def send_button_message(request: SendButtonRequest):
    """Send a message with buttons via WhatsApp"""
    try:
        result = await evolution_api_client.send_button_message(
            instance_name=request.instance_name,
            phone=request.phone,
            text=request.text,
            buttons=request.buttons
        )
        
        return {
            "success": True,
            "message": "Button message sent successfully",
            "data": result
        }
        
    except Exception as e:
        app_logger.error(f"Error sending button message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send button message: {str(e)}")


@router.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle webhooks from Evolution API"""
    try:
        # Get raw webhook data
        webhook_data = await request.json()
        
        app_logger.info(f"Received webhook: {webhook_data.get('event', 'unknown_event')}")
        
        # Parse message if it's a message event
        parsed_message = evolution_api_client.parse_webhook_message(webhook_data)
        
        if parsed_message:
            app_logger.info(
                f"Processing message from {parsed_message.phone} via instance {parsed_message.instance}"
            )
            
            # Process message in background to avoid webhook timeout
            background_tasks.add_task(process_message_background, parsed_message)
            
            return {"status": "received", "message": "Webhook processed successfully"}
        
        # Handle other webhook events
        event = webhook_data.get("event", "")
        
        if event == "qrcode.updated":
            app_logger.info(f"QR code updated for instance: {webhook_data.get('instance', 'unknown')}")
        elif event == "connection.update":
            connection_data = webhook_data.get("data", {})
            app_logger.info(
                f"Connection update for instance {webhook_data.get('instance', 'unknown')}: "
                f"{connection_data.get('state', 'unknown')}"
            )
        
        return {"status": "received"}
        
    except Exception as e:
        app_logger.error(f"Error processing webhook: {str(e)}")
        # Return 200 to avoid webhook retries
        return {"status": "error", "message": str(e)}


async def process_message_background(message: WhatsAppMessage):
    """Process incoming WhatsApp message in background"""
    try:
        # Initialize enhanced RAG engine if not already done
        if not enhanced_rag_engine._initialized:
            await enhanced_rag_engine.initialize()
        
        # Build context for the message
        context = {
            "phone": message.phone,
            "sender_name": message.sender_name,
            "message_id": message.message_id,
            "instance": message.instance,
            "timestamp": message.timestamp
        }
        
        # Skip empty messages
        if not message.message.strip():
            app_logger.info(f"Skipping empty message from {message.phone}")
            return
        
        app_logger.info(f"Processing message: '{message.message[:50]}...' from {message.phone}")
        
        # Get AI response using enhanced RAG
        ai_response = await enhanced_rag_engine.answer_question(
            question=message.message,
            context=context,
            similarity_threshold=0.7
        )
        
        # Send response back via WhatsApp
        await evolution_api_client.send_text_message(
            instance_name=message.instance,
            phone=message.phone,
            message=ai_response
        )
        
        app_logger.info(f"Response sent to {message.phone}")
        
    except Exception as e:
        app_logger.error(f"Error processing message in background: {str(e)}")
        
        # Send error message to user
        try:
            error_response = (
                "Desculpe, ocorreu um erro ao processar sua mensagem. "
                "Tente novamente ou entre em contato pelo telefone. 📞"
            )
            await evolution_api_client.send_text_message(
                instance_name=message.instance,
                phone=message.phone,
                message=error_response
            )
        except Exception as send_error:
            app_logger.error(f"Failed to send error message: {str(send_error)}")


@router.get("/health")
async def evolution_health_check():
    """Health check for Evolution API integration"""
    try:
        # Try to list instances to check if Evolution API is accessible
        instances = await evolution_api_client.list_instances()
        
        return {
            "status": "healthy",
            "evolution_api_url": settings.EVOLUTION_API_URL,
            "instances_count": len(instances),
            "rag_engine_initialized": enhanced_rag_engine._initialized
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "evolution_api_url": settings.EVOLUTION_API_URL
        }


@router.post("/test/message")
async def test_message(
    instance_name: str = "kumon_test",
    phone: str = "5511999999999",
    message: str = "Como funciona o método Kumon?"
):
    """Test endpoint to simulate a message and get AI response"""
    try:
        # Initialize enhanced RAG engine if not already done
        if not enhanced_rag_engine._initialized:
            await enhanced_rag_engine.initialize()
        
        # Build test context
        context = {
            "phone": phone,
            "sender_name": "Test User",
            "instance": instance_name
        }
        
        # Get AI response
        ai_response = await enhanced_rag_engine.answer_question(
            question=message,
            context=context,
            similarity_threshold=0.7
        )
        
        return {
            "success": True,
            "input_message": message,
            "ai_response": ai_response,
            "context": context
        }
        
    except Exception as e:
        app_logger.error(f"Error in test message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


@router.get("/setup/guide")
async def setup_guide():
    """Get setup guide for Evolution API integration"""
    return {
        "title": "Evolution API Setup Guide for Kumon Assistant",
        "steps": [
            {
                "step": 1,
                "title": "Start Evolution API",
                "description": "Run `docker-compose up -d` to start Evolution API and dependencies"
            },
            {
                "step": 2,
                "title": "Create WhatsApp Instance",
                "description": "POST to /api/v1/evolution/instances with instance_name",
                "example": {
                    "instance_name": "kumon_main",
                    "webhook_url": "http://kumon-assistant:8000/api/v1/evolution/webhook"
                }
            },
            {
                "step": 3,
                "title": "Get QR Code",
                "description": "GET /api/v1/evolution/instances/{instance_name}/qr to get QR code"
            },
            {
                "step": 4,
                "title": "Scan QR Code",
                "description": "Open WhatsApp on your phone, go to Settings > Linked Devices > Link a Device, and scan the QR code"
            },
            {
                "step": 5,
                "title": "Test Connection",
                "description": "Send a message to the connected WhatsApp number and check if the Kumon Assistant responds"
            }
        ],
        "endpoints": {
            "create_instance": "POST /api/v1/evolution/instances",
            "list_instances": "GET /api/v1/evolution/instances",
            "get_qr_code": "GET /api/v1/evolution/instances/{instance_name}/qr",
            "webhook": "POST /api/v1/evolution/webhook",
            "test_message": "POST /api/v1/evolution/test/message"
        },
        "notes": [
            "Make sure Evolution API is running before creating instances",
            "Each instance can handle one WhatsApp number",
            "Webhooks are automatically configured when creating instances",
            "The Kumon Assistant will respond to all messages sent to connected numbers"
        ]
    } 