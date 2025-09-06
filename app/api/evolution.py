"""
Evolution API integration endpoints for WhatsApp
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import service factory for RAG service
from app.core.service_factory import get_langchain_rag_service
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from ..clients.evolution_api import InstanceInfo, WhatsAppMessage, evolution_api_client
from ..core.config import settings
from ..core.logger import app_logger

# Conversation flow is now handled by message processor

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


# Clean Architecture: Use MessagePreprocessor + direct workflow call
from ..services.message_preprocessor import message_preprocessor
from ..core.workflow import get_cecilia_workflow

app_logger.info("🔄 Evolution route using clean MessagePreprocessor + CeciliaWorkflow")


# ========== OFFICIAL TEMPLATE LOADERS ==========
def _get_official_welcome_template() -> str:
    """Load official welcome template from prompts/templates"""
    try:
        template_path = Path(__file__).parent.parent / "prompts" / "templates" / "greeting" / "welcome_initial.txt"
        if template_path.exists():
            return template_path.read_text(encoding='utf-8').strip()
        else:
            app_logger.warning("Welcome template not found, using fallback")
            return "Olá! Bem-vindo ao Kumon Vila A! 😊\n\nMeu nome é Cecília e estou aqui para ajudá-lo com informações sobre nossa metodologia de ensino.\n\nPara começar, qual é o seu nome? 😊"
    except Exception as e:
        app_logger.error(f"Error loading welcome template: {str(e)}")
        return "Olá! Bem-vindo ao Kumon Vila A! 😊\n\nMeu nome é Cecília e estou aqui para ajudá-lo com informações sobre nossa metodologia de ensino.\n\nPara começar, qual é o seu nome? 😊"


def _get_official_technical_fallback_template() -> str:
    """Load official technical fallback template from prompts/templates"""
    try:
        template_path = Path(__file__).parent.parent / "prompts" / "templates" / "fallback" / "cecilia_fallback_technical.txt"
        if template_path.exists():
            content = template_path.read_text(encoding='utf-8')
            # Extract the response part (after "RESPOSTA OBRIGATÓRIA:")
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if "RESPOSTA OBRIGATÓRIA:" in line and i + 1 < len(lines):
                    return lines[i + 1].strip()
            # If no specific response found, use the general fallback message
            return "Opa, tive um probleminha aqui! Pode repetir o que você disse? Assim consigo te ajudar da melhor maneira! 😊"
        else:
            app_logger.warning("Technical fallback template not found, using fallback")
            return "Opa, tive um probleminha aqui! Pode repetir o que você disse? Assim consigo te ajudar da melhor maneira! 😊"
    except Exception as e:
        app_logger.error(f"Error loading technical fallback template: {str(e)}")
        return "Opa, tive um probleminha aqui! Pode repetir o que você disse? Assim consigo te ajudar da melhor maneira! 😊"


@router.post("/instances")
async def create_instance(request: CreateInstanceRequest):
    """Create a new WhatsApp instance"""
    try:
        result = await evolution_api_client.create_instance(
            instance_name=request.instance_name, webhook_url=request.webhook_url
        )

        return {
            "success": True,
            "message": f"Instance '{request.instance_name}' created successfully",
            "data": result,
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
                    "profile_name": instance.profile_name,
                }
                for instance in instances
            ],
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
                "profile_name": instance.profile_name,
            },
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
                "message": "Scan this QR code with WhatsApp to connect the instance",
            }
        else:
            return {
                "success": False,
                "message": "QR code not available or instance already connected",
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
            "connected": status == "open",
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
            return {"success": True, "message": f"Instance '{instance_name}' deleted successfully"}
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
                "message": f"Instance '{instance_name}' restarted successfully",
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
            instance_name=request.instance_name, phone=request.phone, message=request.message
        )

        return {"success": True, "message": "Text message sent successfully", "data": result}

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
            media_type=request.media_type,
        )

        return {"success": True, "message": "Media message sent successfully", "data": result}

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
            buttons=request.buttons,
        )

        return {"success": True, "message": "Button message sent successfully", "data": result}

    except Exception as e:
        app_logger.error(f"Error sending button message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send button message: {str(e)}")


@router.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle webhooks from Evolution API"""
    try:
        # Get raw webhook data
        webhook_data = await request.json()

        # Extract event type from URL path if present
        url_path = str(request.url.path)
        event_type = "unknown"

        if "/webhook/" in url_path:
            # Extract event type from path like /webhook/messages-upsert
            path_parts = url_path.split("/webhook/")
            if len(path_parts) > 1:
                event_type = path_parts[1].replace("-", "_")

        app_logger.info(f"Received webhook: {event_type} from path: {url_path}")

        # Handle messages-upsert specifically (most important for our AI assistant)
        if event_type in ["messages_upsert", "messages-upsert"]:
            # Parse message from the webhook
            parsed_message = evolution_api_client.parse_webhook_message(webhook_data)

            if parsed_message:
                app_logger.info(
                    f"Processing message from {parsed_message.phone} via instance {parsed_message.instance}"
                )

                # Process message in background to avoid webhook timeout - PASS HEADERS
                background_tasks.add_task(process_message_background, parsed_message, dict(request.headers))

                return {
                    "success": True,
                    "message": "Messages webhook received and message queued for processing",
                }
            else:
                app_logger.info("No processable message found in messages webhook")

        # Handle other event types
        elif event_type in ["presence_update", "presence-update"]:
            presence_data = webhook_data.get("data", {})
            presence_state = presence_data.get("presence", "unknown")
            instance = webhook_data.get("instance", "unknown")
            app_logger.info(f"Presence update for instance {instance}: {presence_state}")

        elif event_type in ["chats_update", "chats-update"]:
            chat_data = webhook_data.get("data", {})
            instance = webhook_data.get("instance", "unknown")
            app_logger.info(f"Chats update for instance {instance}")

        elif event_type in ["connection_update", "connection-update"]:
            connection_data = webhook_data.get("data", {})
            connection_state = connection_data.get("state", "unknown")
            instance = webhook_data.get("instance", "unknown")
            app_logger.info(f"Connection update for instance {instance}: {connection_state}")

        else:
            # Fallback: try to parse as regular message webhook
            parsed_message = evolution_api_client.parse_webhook_message(webhook_data)

            if parsed_message:
                app_logger.info(
                    f"Processing message from {parsed_message.phone} via instance {parsed_message.instance}"
                )

                # Process message in background to avoid webhook timeout - PASS HEADERS
                background_tasks.add_task(process_message_background, parsed_message, dict(request.headers))

                return {
                    "success": True,
                    "message": "Webhook received and message queued for processing",
                }
            else:
                # Handle non-message events (connection updates, QR codes, etc.)
                webhook_event_type = webhook_data.get("event", "unknown")

                if webhook_event_type == "qrcode.updated":
                    app_logger.info("QR Code updated event received")
                elif webhook_event_type == "connection.update":
                    connection_state = webhook_data.get("data", {}).get("state", "unknown")
                    app_logger.info(f"Connection state updated: {connection_state}")

        return {"success": True, "message": f"Webhook event '{event_type}' processed successfully"}

    except Exception as e:
        app_logger.error(f"Error processing webhook: {str(e)}")
        return {"success": False, "error": "Failed to process webhook"}


# Catch-all route for specific event paths
@router.api_route("/webhook/{path:path}", methods=["POST"])
async def handle_webhook_catch_all(path: str, request: Request, background_tasks: BackgroundTasks):
    """Catch-all route for webhook event paths like messages-upsert, presence-update, etc."""
    # Forward to main webhook handler
    return await handle_webhook(request, background_tasks)


@router.post("/messages-update")
async def handle_messages_update_direct(request: Request, background_tasks: BackgroundTasks):
    """Handle messages-update webhook from Evolution API v1.7.1"""
    try:
        # Get raw webhook data
        webhook_data = await request.json()

        app_logger.info(f"Received messages-update webhook: {webhook_data}")

        # Parse message from the webhook
        parsed_message = evolution_api_client.parse_webhook_message(webhook_data)

        if parsed_message:
            app_logger.info(
                f"Processing message from {parsed_message.phone} via instance {parsed_message.instance}"
            )

            # Process message in background to avoid webhook timeout
            background_tasks.add_task(process_message_background, parsed_message)

            return {
                "success": True,
                "message": "Messages-update webhook received and message queued for processing",
            }
        else:
            app_logger.info("No processable message found in messages-update webhook")
            return {
                "success": True,
                "message": "Messages-update webhook received but no message to process",
            }

    except Exception as e:
        app_logger.error(f"Error processing messages-update webhook: {str(e)}")
        return {"success": False, "error": "Failed to process messages-update webhook"}


@router.post("/messages-upsert")
async def handle_messages_upsert_direct(request: Request, background_tasks: BackgroundTasks):
    """Handle messages-upsert webhook directly"""
    try:
        webhook_data = await request.json()

        app_logger.info(f"📨 Received messages-upsert webhook: {webhook_data}")

        # Extract message information
        instance = webhook_data.get("instance")
        message_data = webhook_data.get("data", {})

        # Skip messages from ourselves (prevent echo loops)
        if message_data.get("key", {}).get("fromMe", False):
            from ..core.structured_logging import log_webhook_event
            log_webhook_event("echo_filtered", "unknown", webhook_data.get("data", {}).get("key", {}).get("id", "unknown"))
            return {"status": "ok", "message": "Message from self, skipped"}

        app_logger.info(f"📱 Processing message from instance: {instance}")

        # Parse message from the webhook
        parsed_message = evolution_api_client.parse_webhook_message(webhook_data)
        
        if parsed_message:
            # Process message in background to avoid webhook timeout
            background_tasks.add_task(process_message_background, parsed_message, dict(request.headers))
        else:
            app_logger.info("No processable message found in messages-upsert webhook")

        return {"status": "ok", "message": "Message received and queued for processing"}

    except Exception as e:
        app_logger.error(f"❌ Error handling messages-upsert: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/presence-update")
async def handle_presence_update_direct(request: Request):
    """Handle presence-update webhook from Evolution API v1.7.1"""
    try:
        # Get raw webhook data
        webhook_data = await request.json()

        app_logger.info(f"Received presence-update webhook: {webhook_data}")

        # Extract presence information
        presence_data = webhook_data.get("data", {})
        presence_state = presence_data.get("presence", "unknown")
        instance = webhook_data.get("instance", "unknown")

        app_logger.info(f"Presence update for instance {instance}: {presence_state}")

        return {"success": True, "message": f"Presence update processed: {presence_state}"}

    except Exception as e:
        app_logger.error(f"Error processing presence-update webhook: {str(e)}")
        return {"success": False, "error": "Failed to process presence-update webhook"}


@router.post("/chats-update")
async def handle_chats_update_direct(request: Request):
    """Handle chats-update webhook from Evolution API v1.7.1"""
    try:
        # Get raw webhook data
        webhook_data = await request.json()

        app_logger.info(f"Received chats-update webhook: {webhook_data}")

        # Extract chat information
        chat_data = webhook_data.get("data", {})
        instance = webhook_data.get("instance", "unknown")

        app_logger.info(f"Chats update for instance {instance}")

        return {"success": True, "message": "Chats update processed"}

    except Exception as e:
        app_logger.error(f"Error processing chats-update webhook: {str(e)}")
        return {"success": False, "error": "Failed to process chats-update webhook"}


@router.post("/connection-update")
async def handle_connection_update_direct(request: Request):
    """Handle connection-update webhook from Evolution API v1.7.1"""
    try:
        # Get raw webhook data
        webhook_data = await request.json()

        app_logger.info(f"Received connection-update webhook: {webhook_data}")

        # Extract connection information
        connection_data = webhook_data.get("data", {})
        connection_state = connection_data.get("state", "unknown")
        instance = webhook_data.get("instance", "unknown")

        app_logger.info(f"Connection update for instance {instance}: {connection_state}")

        return {"success": True, "message": f"Connection update processed: {connection_state}"}

    except Exception as e:
        app_logger.error(f"Error processing connection-update webhook: {str(e)}")
        return {"success": False, "error": "Failed to process connection-update webhook"}


# Additional webhook endpoints for all Evolution API events
@router.post("/application-startup")
async def handle_application_startup(request: Request):
    """Handle application-startup webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received application-startup webhook: {webhook_data}")
        return {"success": True, "message": "Application startup processed"}
    except Exception as e:
        app_logger.error(f"Error processing application-startup webhook: {str(e)}")
        return {"success": False, "error": "Failed to process application-startup webhook"}


@router.post("/qrcode-updated")
async def handle_qrcode_updated(request: Request):
    """Handle qrcode-updated webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received qrcode-updated webhook: {webhook_data}")
        return {"success": True, "message": "QR code update processed"}
    except Exception as e:
        app_logger.error(f"Error processing qrcode-updated webhook: {str(e)}")
        return {"success": False, "error": "Failed to process qrcode-updated webhook"}


@router.post("/messages-set")
async def handle_messages_set(request: Request):
    """Handle messages-set webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received messages-set webhook: {webhook_data}")
        return {"success": True, "message": "Messages set processed"}
    except Exception as e:
        app_logger.error(f"Error processing messages-set webhook: {str(e)}")
        return {"success": False, "error": "Failed to process messages-set webhook"}


@router.post("/messages-delete")
async def handle_messages_delete(request: Request):
    """Handle messages-delete webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received messages-delete webhook: {webhook_data}")
        return {"success": True, "message": "Messages delete processed"}
    except Exception as e:
        app_logger.error(f"Error processing messages-delete webhook: {str(e)}")
        return {"success": False, "error": "Failed to process messages-delete webhook"}


@router.post("/send-message")
async def handle_send_message(request: Request):
    """Handle send-message webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received send-message webhook: {webhook_data}")
        return {"success": True, "message": "Send message processed"}
    except Exception as e:
        app_logger.error(f"Error processing send-message webhook: {str(e)}")
        return {"success": False, "error": "Failed to process send-message webhook"}


@router.post("/contacts-set")
async def handle_contacts_set(request: Request):
    """Handle contacts-set webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received contacts-set webhook: {webhook_data}")
        return {"success": True, "message": "Contacts set processed"}
    except Exception as e:
        app_logger.error(f"Error processing contacts-set webhook: {str(e)}")
        return {"success": False, "error": "Failed to process contacts-set webhook"}


# ========== UTILITY FUNCTIONS FOR SERVICES ==========

async def send_message(phone_number: str, message: str, instance_name: str = None) -> Dict[str, Any]:
    """
    Central send message function used by DeliveryService
    
    Args:
        phone_number: Target phone number
        message: Message text to send
        instance_name: WhatsApp instance name (REQUIRED - no fallback to \"default\")
    
    Returns:
        Dict with status and result information
    """
    try:
        # CRITICAL: Never use "default" - require explicit instance
        if not instance_name:
            error_msg = "WhatsApp instance is required - no fallback to 'default' allowed"
            app_logger.error(f"send_message failed for {phone_number}: {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
                "phone": phone_number,
                "instance": None
            }
        
        # Send message via Evolution API client
        result = await evolution_api_client.send_text_message(
            instance_name=instance_name,
            phone=phone_number,
            message=message
        )
        
        # Standardize response format
        if result:
            return {
                "status": "success",
                "message_id": result.get("id"),
                "phone": phone_number,
                "instance": instance_name,
                "timestamp": result.get("timestamp"),
                "result": result
            }
        else:
            return {
                "status": "error", 
                "error": "No result from Evolution API",
                "phone": phone_number,
                "instance": instance_name
            }
            
    except Exception as e:
        app_logger.error(f"send_message failed for {phone_number}: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "phone": phone_number,
            "instance": instance_name
        }


@router.post("/contacts-upsert")
async def handle_contacts_upsert(request: Request):
    """Handle contacts-upsert webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received contacts-upsert webhook: {webhook_data}")
        return {"success": True, "message": "Contacts upsert processed"}
    except Exception as e:
        app_logger.error(f"Error processing contacts-upsert webhook: {str(e)}")
        return {"success": False, "error": "Failed to process contacts-upsert webhook"}


@router.post("/contacts-update")
async def handle_contacts_update(request: Request):
    """Handle contacts-update webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received contacts-update webhook: {webhook_data}")
        return {"success": True, "message": "Contacts update processed"}
    except Exception as e:
        app_logger.error(f"Error processing contacts-update webhook: {str(e)}")
        return {"success": False, "error": "Failed to process contacts-update webhook"}


@router.post("/chats-set")
async def handle_chats_set(request: Request):
    """Handle chats-set webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received chats-set webhook: {webhook_data}")
        return {"success": True, "message": "Chats set processed"}
    except Exception as e:
        app_logger.error(f"Error processing chats-set webhook: {str(e)}")
        return {"success": False, "error": "Failed to process chats-set webhook"}


@router.post("/chats-upsert")
async def handle_chats_upsert(request: Request):
    """Handle chats-upsert webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received chats-upsert webhook: {webhook_data}")
        return {"success": True, "message": "Chats upsert processed"}
    except Exception as e:
        app_logger.error(f"Error processing chats-upsert webhook: {str(e)}")
        return {"success": False, "error": "Failed to process chats-upsert webhook"}


@router.post("/chats-delete")
async def handle_chats_delete(request: Request):
    """Handle chats-delete webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received chats-delete webhook: {webhook_data}")
        return {"success": True, "message": "Chats delete processed"}
    except Exception as e:
        app_logger.error(f"Error processing chats-delete webhook: {str(e)}")
        return {"success": False, "error": "Failed to process chats-delete webhook"}


@router.post("/groups-upsert")
async def handle_groups_upsert(request: Request):
    """Handle groups-upsert webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received groups-upsert webhook: {webhook_data}")
        return {"success": True, "message": "Groups upsert processed"}
    except Exception as e:
        app_logger.error(f"Error processing groups-upsert webhook: {str(e)}")
        return {"success": False, "error": "Failed to process groups-upsert webhook"}


@router.post("/group-update")
async def handle_group_update(request: Request):
    """Handle group-update webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received group-update webhook: {webhook_data}")
        return {"success": True, "message": "Group update processed"}
    except Exception as e:
        app_logger.error(f"Error processing group-update webhook: {str(e)}")
        return {"success": False, "error": "Failed to process group-update webhook"}


@router.post("/group-participants-update")
async def handle_group_participants_update(request: Request):
    """Handle group-participants-update webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received group-participants-update webhook: {webhook_data}")
        return {"success": True, "message": "Group participants update processed"}
    except Exception as e:
        app_logger.error(f"Error processing group-participants-update webhook: {str(e)}")
        return {"success": False, "error": "Failed to process group-participants-update webhook"}


@router.post("/call")
async def handle_call(request: Request):
    """Handle call webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received call webhook: {webhook_data}")
        return {"success": True, "message": "Call processed"}
    except Exception as e:
        app_logger.error(f"Error processing call webhook: {str(e)}")
        return {"success": False, "error": "Failed to process call webhook"}


@router.post("/new-jwt-token")
async def handle_new_jwt_token(request: Request):
    """Handle new-jwt-token webhook"""
    try:
        webhook_data = await request.json()
        app_logger.info(f"Received new-jwt-token webhook: {webhook_data}")
        return {"success": True, "message": "New JWT token processed"}
    except Exception as e:
        app_logger.error(f"Error processing new-jwt-token webhook: {str(e)}")
        return {"success": False, "error": "Failed to process new-jwt-token webhook"}




async def process_message_background(message: WhatsAppMessage, headers: Optional[Dict] = None):
    """Process incoming WhatsApp message in background with turn management"""
    try:
        # Skip empty messages
        if not message.message.strip():
            app_logger.info(f"Skipping empty message from {message.phone}")
            return

        app_logger.info(f"🔄 Processing message: '{message.message}' from {message.phone}")

        # Step 1: Message-level deduplication
        from ..core.turn_dedup import is_duplicate_message, turn_lock
        
        # Check for duplicate message  
        if is_duplicate_message(message.instance, message.phone, message.message_id):
            from ..core.structured_logging import log_webhook_event
            log_webhook_event("duplicate", message.phone, message.message_id)
            return
        
        # Step 2: Conversation-level turn lock
        conversation_id = f"conv_{message.phone}"
        
        with turn_lock(conversation_id) as acquired:
            if not acquired:
                app_logger.info(f"TURNLOCK|duplicate|conv={conversation_id}")
                return
            
            app_logger.info(f"TURNLOCK|acquired|conv={conversation_id}")
            
            # Step 3: Process the message (no fallback in except)
            await _process_single_message(message, headers)

    except Exception as e:
        # CRITICAL: Do not send fallback here - just log and exit
        app_logger.error(f"TURN|error_before_planner|phone={message.phone[-4:]}|error={str(e)}", exc_info=True)
        # Let the error bubble up without sending any message


async def _process_single_message(message: WhatsAppMessage, headers: Optional[Dict] = None, turn_data: Optional[Dict] = None):
    """Process a single message (or aggregated turn) through the workflow"""
    try:
        # Clean Architecture: Preprocessor first, then workflow
        try:
            # Step 1: Preprocess message - USE ACTUAL HEADERS FROM REQUEST
            actual_headers = headers or {}
            app_logger.info(f"🔍 DEBUG: Passing headers to preprocessor: {list(actual_headers.keys())}")
            preprocessor_result = await message_preprocessor.process_message(message, actual_headers)
            
            if not preprocessor_result.success:
                app_logger.critical(
                    f"🚨 SECURITY BREACH BLOCKED: Message processing terminated due to preprocessing failure",
                    extra={
                        "security_incident": True,
                        "incident_type": "preprocessing_failure",
                        "error_code": preprocessor_result.error_code,
                        "phone_number": message.phone,
                        "message_preview": message.message[:50],
                        "threat_level": "critical"
                    }
                )
                
                # 🛡️ SECURITY: TERMINATE PROCESSING IMMEDIATELY ON AUTH_FAILED
                # No workflow execution, no response sent to potentially malicious source
                return
            else:
                # Use preprocessed message
                final_message = preprocessor_result.message
                app_logger.info("✅ Message preprocessed successfully")

            # Step 2: Process through turn-based delivery architecture
            await _process_through_turn_architecture(final_message, turn_data)

        except Exception as e:
            app_logger.error(f"TURN|processing_error|phone={message.phone[-4:]}|error={str(e)}", exc_info=True)
            # CRITICAL: Do not send any messages from evolution.py - let Delivery handle via outbox

    except Exception as e:
        app_logger.error(f"❌ Error in _process_single_message: {str(e)}")


async def _process_through_turn_architecture(message: WhatsAppMessage, turn_data: Optional[Dict] = None):
    """
    NOVA ARQUITETURA: Pipeline principal (preprocess → classify → route → plan → outbox → delivery)
    Turn Controller atua APENAS como guardrails (concurrency/dedup/single response per turn)
    """
    try:
        from ..core.feature_flags import is_main_pipeline_enabled, is_turn_guard_only
        
        # CRÍTICO: Log obrigatório - marcador exato para pipeline start
        app_logger.info(f"PIPELINE|start|phone={message.phone[-4:]}|main_enabled={is_main_pipeline_enabled()}|turn_guard_only={is_turn_guard_only()}")
        
        # STEP 1: PREPROCESSING - Sanitização, rate limiting, auth validation
        try:
            from ..services.message_preprocessor import message_preprocessor
            from ..core.structured_logging import log_turn_event
            
            # Build headers for auth validation (defensive)
            headers = turn_data.get('headers', {}) if turn_data else {}
            
            # CRÍTICO: Log obrigatório - marcador exato
            app_logger.info(f"PIPELINE|preprocess_start|phone={message.phone[-4:]}")
            log_turn_event("preprocess", message.phone, "start", {"message_id": message.message_id})
            
            preprocess_result = await message_preprocessor.process_message(message, headers)
            
            if not preprocess_result.success:
                app_logger.warning(f"PIPELINE|preprocess_failed|phone={message.phone[-4:]}|error={preprocess_result.error_code}")
                log_turn_event("preprocess", message.phone, "failed", {"error": preprocess_result.error_code})
                return  # Stop pipeline on preprocessing failure
            
            preprocessed_message = preprocess_result.message
            app_logger.info(f"PIPELINE|preprocess_complete|phone={message.phone[-4:]}|processing_time={preprocess_result.processing_time_ms:.1f}ms")
            log_turn_event("preprocess", message.phone, "complete", {"processing_time_ms": preprocess_result.processing_time_ms})
            
        except Exception as preprocess_error:
            app_logger.error(f"PIPELINE|preprocess_error|phone={message.phone[-4:]}|error={str(preprocess_error)}")
            return  # Critical pipeline failure - stop processing

        # STEP 2: INTENT CLASSIFICATION - Análise da intenção do usuário
        try:
            from ..workflows.intent_classifier import AdvancedIntentClassifier
            from ..core.dependencies import llm_service
            
            app_logger.info(f"PIPELINE|classify_start|phone={message.phone[-4:]}|message={preprocessed_message.message[:50]}")
            log_turn_event("classify", message.phone, "start", {"message_preview": preprocessed_message.message[:50]})
            
            # Build conversation state for classification
            conversation_id = f"conv_{message.phone}"
            state = {
                "phone_number": message.phone,
                "conversation_id": conversation_id,
                "last_user_message": preprocessed_message.message,
                "current_stage": "greeting",  # Default stage, will be loaded from DB if available
                "current_step": "welcome",
                "channel": "whatsapp",
                "messages": []
            }
            
            # Initialize intent classifier
            intent_classifier = AdvancedIntentClassifier(llm_service_instance=llm_service)
            intent_result = await intent_classifier.classify_intent(preprocessed_message.message, state)
            
            app_logger.info(f"PIPELINE|classify_complete|phone={message.phone[-4:]}|intent={intent_result.category}|confidence={intent_result.confidence:.2f}")
            log_turn_event("classify", message.phone, "complete", {
                "intent_category": intent_result.category,
                "confidence": intent_result.confidence,
                "subcategory": intent_result.subcategory
            })
            
        except Exception as classify_error:
            app_logger.error(f"PIPELINE|classify_error|phone={message.phone[-4:]}|error={str(classify_error)}")
            # Create fallback intent result
            from ..workflows.contracts import IntentResult
            intent_result = IntentResult(
                category="clarification",
                subcategory="technical_confusion",
                confidence=0.3,
                context_entities={"error": str(classify_error)},
                delivery_payload=None,
                slots={"error": str(classify_error)}
            )

        # STEP 3: SMART ROUTING - Decisão de roteamento inteligente
        try:
            from ..workflows.smart_router import smart_router
            
            app_logger.info(f"PIPELINE|route_start|phone={message.phone[-4:]}|intent={intent_result.category}|confidence={intent_result.confidence:.2f}")
            log_turn_event("route", message.phone, "start", {
                "intent_category": intent_result.category,
                "confidence": intent_result.confidence
            })
            
            routing_decision = await smart_router.make_routing_decision(state, intent_result)
            
            app_logger.info(f"PIPELINE|route_complete|phone={message.phone[-4:]}|target={routing_decision.target_node}|action={routing_decision.threshold_action}|final_confidence={routing_decision.final_confidence:.2f}")
            log_turn_event("route", message.phone, "complete", {
                "target_node": routing_decision.target_node,
                "threshold_action": routing_decision.threshold_action,
                "final_confidence": routing_decision.final_confidence,
                "rule_applied": routing_decision.rule_applied
            })
            
        except Exception as route_error:
            app_logger.error(f"PIPELINE|route_error|phone={message.phone[-4:]}|error={str(route_error)}")
            # Create fallback routing decision
            from ..workflows.contracts import RoutingDecision
            from datetime import datetime
            routing_decision = RoutingDecision(
                target_node="fallback",
                threshold_action="fallback_level1",
                final_confidence=0.3,
                intent_confidence=0.2,
                pattern_confidence=0.2,
                rule_applied="error_fallback",
                reasoning=f"Routing error: {str(route_error)}",
                timestamp=datetime.now()
            )

        # STEP 4: RESPONSE PLANNING - Geração da resposta
        try:
            from ..core.router.response_planner import ResponsePlanner
            
            app_logger.info(f"PIPELINE|plan_start|phone={message.phone[-4:]}|target={routing_decision.target_node}|action={routing_decision.threshold_action}")
            log_turn_event("plan", message.phone, "start", {
                "target_node": routing_decision.target_node,
                "threshold_action": routing_decision.threshold_action
            })
            
            # Initialize response planner
            response_planner = ResponsePlanner()
            
            # Plan and generate response - this will populate state with planned response and outbox items
            await response_planner.plan_and_generate(state, routing_decision)
            
            planned_outbox = state.get("_planner_snapshot_outbox", [])
            app_logger.info(f"PIPELINE|plan_complete|phone={message.phone[-4:]}|outbox_count={len(planned_outbox)}")
            log_turn_event("plan", message.phone, "complete", {
                "outbox_count": len(planned_outbox),
                "response_type": state.get("response_metadata", {}).get("type", "unknown")
            })
            
        except Exception as plan_error:
            app_logger.error(f"PIPELINE|plan_error|phone={message.phone[-4:]}|error={str(plan_error)}")
            # Create emergency fallback outbox
            turn_id = turn_data.get('turn_id') if turn_data else f"single_{message.message_id}"
            state["_planner_snapshot_outbox"] = [{
                "text": "Desculpe, tive um problema técnico. Pode repetir sua mensagem?",
                "channel": "whatsapp",
                "meta": {"source": "plan_error_fallback"},
                "idempotency_key": f"{turn_id}_plan_error"
            }]

        # STEP 5: OUTBOX PERSISTENCE - Persistir mensagens planejadas
        try:
            from ..core.outbox_repository import save_outbox
            from ..core.outbox_repo_redis import outbox_push
            from ..core.feature_flags import is_outbox_redis_fallback_enabled
            
            outbox_items = state.get("_planner_snapshot_outbox", [])
            
            app_logger.info(f"PIPELINE|outbox_start|phone={message.phone[-4:]}|count={len(outbox_items)}")
            log_turn_event("outbox", message.phone, "start", {"outbox_count": len(outbox_items)})
            
            # Try database first
            idem_keys = []
            try:
                idem_keys = save_outbox(conversation_id, outbox_items)
                if idem_keys:
                    app_logger.info(f"PIPELINE|outbox_db_success|phone={message.phone[-4:]}|count={len(outbox_items)}")
                    # Add idempotency keys to items
                    for i, key in enumerate(idem_keys):
                        if i < len(outbox_items):
                            outbox_items[i]["idempotency_key"] = key
                else:
                    raise Exception("DB outbox returned empty keys")
            except Exception as db_error:
                app_logger.warning(f"PIPELINE|outbox_db_failed|phone={message.phone[-4:]}|error={str(db_error)}")
                
                # FALLBACK: Redis outbox if enabled
                if is_outbox_redis_fallback_enabled():
                    try:
                        redis_count = outbox_push(conversation_id, outbox_items)
                        if redis_count > 0:
                            app_logger.info(f"PIPELINE|outbox_redis_success|phone={message.phone[-4:]}|count={redis_count}")
                        else:
                            raise Exception("Redis outbox failed")
                    except Exception as redis_error:
                        app_logger.error(f"PIPELINE|outbox_redis_failed|phone={message.phone[-4:]}|error={str(redis_error)}")
                        # Continue with in-memory outbox for immediate delivery
                
            app_logger.info(f"PIPELINE|outbox_complete|phone={message.phone[-4:]}|count={len(outbox_items)}")
            log_turn_event("outbox", message.phone, "complete", {"outbox_count": len(outbox_items)})
            
        except Exception as outbox_error:
            app_logger.error(f"PIPELINE|outbox_error|phone={message.phone[-4:]}|error={str(outbox_error)}")

        # STEP 6: DELIVERY - Entregar mensagens ao usuário (single-shot, idempotente)
        try:
            from ..core.router.delivery_io import delivery_node_turn_based
            
            app_logger.info(f"PIPELINE|delivery_start|phone={message.phone[-4:]}|outbox_count={len(state.get('_planner_snapshot_outbox', []))}")
            log_turn_event("delivery", message.phone, "start", {
                "outbox_count": len(state.get('_planner_snapshot_outbox', []))
            })
            
            # Delivery with idempotency and single-shot guarantee
            result_state = await delivery_node_turn_based(state)
            
            delivery_status = result_state.get('turn_status', 'unknown')
            app_logger.info(f"PIPELINE|delivery_complete|phone={message.phone[-4:]}|status={delivery_status}")
            log_turn_event("delivery", message.phone, "complete", {
                "turn_status": delivery_status,
                "messages_sent": result_state.get('messages_sent', 0)
            })
            
        except Exception as delivery_error:
            app_logger.error(f"PIPELINE|delivery_error|phone={message.phone[-4:]}|error={str(delivery_error)}")
            log_turn_event("delivery", message.phone, "error", {"error": str(delivery_error)})

        # GUARDRAILS: Turn Controller workflow guards (APENAS guardrails, não geração de conteúdo)
        if is_turn_guard_only():
            try:
                from ..core.workflow_guards import check_recursion_limit, prevent_greeting_loops
                
                app_logger.info(f"PIPELINE|guards_start|phone={message.phone[-4:]}")
                
                # Check recursion limit
                if not check_recursion_limit(conversation_id, state.get("current_stage")):
                    app_logger.error(f"PIPELINE|guards_recursion_exceeded|conv={conversation_id}")
                    return  # Stop processing to prevent infinite loops
                
                # Check greeting loops
                if not prevent_greeting_loops(message.phone, state.get("current_stage"), "greeting"):
                    app_logger.warning(f"PIPELINE|guards_greeting_loop|phone={message.phone[-4:]}")
                    return  # Stop processing to prevent greeting loops
                
                app_logger.info(f"PIPELINE|guards_complete|phone={message.phone[-4:]}")
                
            except Exception as guards_error:
                app_logger.error(f"PIPELINE|guards_error|phone={message.phone[-4:]}|error={str(guards_error)}")

        # CRÍTICO: Log obrigatório - marcador exato para pipeline complete
        app_logger.info(f"PIPELINE|complete|phone={message.phone[-4:]}|pipeline_success=true")
        log_turn_event("pipeline", message.phone, "complete", {"pipeline_success": True})

    except Exception as e:
        app_logger.error(f"TURN|architecture_error|phone={message.phone[-4:]}|error={str(e)}", exc_info=True)
        # CRITICAL: No emergency fallback from evolution.py - let proper flow handle via outbox


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
            "langchain_rag_initialized": False,  # Will be updated after service factory migration
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "evolution_api_url": settings.EVOLUTION_API_URL,
        }


@router.post("/test/message")
async def test_message(
    instance_name: str = "kumon_test",
    phone: str = "5511999999999",
    message: str = "Como funciona o método Kumon?",
):
    """Test endpoint to simulate a message and get AI response"""
    try:
        # Build test context
        context = {"phone": phone, "sender_name": "Test User", "instance": instance_name}

        # Get AI response using LangChain RAG service
        langchain_rag_service = await get_langchain_rag_service()
        rag_response = await langchain_rag_service.query(question=message, include_sources=False)
        ai_response = rag_response.answer

        return {
            "success": True,
            "input_message": message,
            "ai_response": ai_response,
            "context": context,
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
                "description": "Run `docker-compose up -d` to start Evolution API and dependencies",
            },
            {
                "step": 2,
                "title": "Create WhatsApp Instance",
                "description": "POST to /api/v1/evolution/instances with instance_name",
                "example": {
                    "instance_name": "kumon_main",
                    "webhook_url": "http://kumon-assistant:8000/api/v1/evolution/webhook",
                },
            },
            {
                "step": 3,
                "title": "Get QR Code",
                "description": "GET /api/v1/evolution/instances/{instance_name}/qr to get QR code",
            },
            {
                "step": 4,
                "title": "Scan QR Code",
                "description": "Open WhatsApp on your phone, go to Settings > Linked Devices > Link a Device, and scan the QR code",
            },
            {
                "step": 5,
                "title": "Test Connection",
                "description": "Send a message to the connected WhatsApp number and check if the Kumon Assistant responds",
            },
        ],
        "endpoints": {
            "create_instance": "POST /api/v1/evolution/instances",
            "list_instances": "GET /api/v1/evolution/instances",
            "get_qr_code": "GET /api/v1/evolution/instances/{instance_name}/qr",
            "webhook": "POST /api/v1/evolution/webhook",
            "test_message": "POST /api/v1/evolution/test/message",
        },
        "notes": [
            "Make sure Evolution API is running before creating instances",
            "Each instance can handle one WhatsApp number",
            "Webhooks are automatically configured when creating instances",
            "The Kumon Assistant will respond to all messages sent to connected numbers",
        ],
    }
