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
from ..services.rag_engine import RAGEngine
from ..services.message_processor import MessageProcessor
from ..core.logger import app_logger
from ..core.config import settings

# Import conversation flow manager
from app.services.conversation_flow import conversation_flow_manager

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


# Initialize message processor and simple RAG engine
message_processor = MessageProcessor()
simple_rag_engine = RAGEngine()


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
                
                # Process message in background to avoid webhook timeout
                background_tasks.add_task(process_message_background, parsed_message)
                
                return {
                    "success": True,
                    "message": "Messages webhook received and message queued for processing"
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
                
                # Process message in background to avoid webhook timeout
                background_tasks.add_task(process_message_background, parsed_message)
                
                return {
                    "success": True,
                    "message": "Webhook received and message queued for processing"
                }
            else:
                # Handle non-message events (connection updates, QR codes, etc.)
                webhook_event_type = webhook_data.get("event", "unknown")
                
                if webhook_event_type == "qrcode.updated":
                    app_logger.info("QR Code updated event received")
                elif webhook_event_type == "connection.update":
                    connection_state = webhook_data.get("data", {}).get("state", "unknown")
                    app_logger.info(f"Connection state updated: {connection_state}")
        
        return {
            "success": True,
            "message": f"Webhook event '{event_type}' processed successfully"
        }
        
    except Exception as e:
        app_logger.error(f"Error processing webhook: {str(e)}")
        return {
            "success": False,
            "error": "Failed to process webhook"
        }


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
                "message": "Messages-update webhook received and message queued for processing"
            }
        else:
            app_logger.info("No processable message found in messages-update webhook")
            return {
                "success": True,
                "message": "Messages-update webhook received but no message to process"
            }
        
    except Exception as e:
        app_logger.error(f"Error processing messages-update webhook: {str(e)}")
        return {
            "success": False,
            "error": "Failed to process messages-update webhook"
        }


@router.post("/messages-upsert")
async def handle_messages_upsert_direct(request: Request):
    """Handle messages-upsert webhook directly"""
    try:
        webhook_data = await request.json()
        
        app_logger.info(f"📨 Received messages-upsert webhook: {webhook_data}")
        
        # Extract message information
        instance = webhook_data.get("instance")
        message_data = webhook_data.get("data", {})
        
        # Skip messages from ourselves
        if message_data.get("key", {}).get("fromMe", False):
            app_logger.info(f"🔄 Skipping message from self (fromMe=True)")
            return {"status": "ok", "message": "Message from self, skipped"}
        
        app_logger.info(f"📱 Processing message from instance: {instance}")
        
        # Process message in background
        asyncio.create_task(process_message_from_webhook(webhook_data))
        
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
        
        return {
            "success": True,
            "message": f"Presence update processed: {presence_state}"
        }
        
    except Exception as e:
        app_logger.error(f"Error processing presence-update webhook: {str(e)}")
        return {
            "success": False,
            "error": "Failed to process presence-update webhook"
        }


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
        
        return {
            "success": True,
            "message": "Chats update processed"
        }
        
    except Exception as e:
        app_logger.error(f"Error processing chats-update webhook: {str(e)}")
        return {
            "success": False,
            "error": "Failed to process chats-update webhook"
        }


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
        
        return {
            "success": True,
            "message": f"Connection update processed: {connection_state}"
        }
        
    except Exception as e:
        app_logger.error(f"Error processing connection-update webhook: {str(e)}")
        return {
            "success": False,
            "error": "Failed to process connection-update webhook"
        }


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


async def process_message_from_webhook(webhook_data: Dict[str, Any]):
    """Process message from webhook data"""
    try:
        # Parse message from the webhook
        parsed_message = evolution_api_client.parse_webhook_message(webhook_data)
        
        if parsed_message:
            app_logger.info(f"✅ Message parsed successfully: {parsed_message.phone} | '{parsed_message.message}'")
            
            # Process message in background to avoid webhook timeout
            await process_message_background(parsed_message)
        else:
            app_logger.info("ℹ️ No processable message found in webhook")
            
    except Exception as e:
        app_logger.error(f"❌ Error processing message from webhook: {str(e)}")


async def process_message_background(message: WhatsAppMessage):
    """Process incoming WhatsApp message in background"""
    try:
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
        
        app_logger.info(f"🔄 Processing message: '{message.message}' from {message.phone}")
        
        # Log conversation state before processing
        conversation_state = conversation_flow_manager.get_conversation_state(message.phone)
        app_logger.info(f"📊 Conversation state BEFORE: Stage={conversation_state.stage.value}, Step={conversation_state.step.value}, Data={list(conversation_state.data.keys())}")
        
        # ALWAYS use conversation flow manager as primary system
        flow_response = await conversation_flow_manager.advance_conversation(message.phone, message.message)
        
        # Log conversation state after processing
        conversation_state_after = conversation_flow_manager.get_conversation_state(message.phone)
        app_logger.info(f"📊 Conversation state AFTER: Stage={conversation_state_after.stage.value}, Step={conversation_state_after.step.value}, Data={list(conversation_state_after.data.keys())}")
        
        # Get the AI response from conversation flow
        if flow_response and flow_response.get("message"):
            ai_response = flow_response["message"]
            app_logger.info(f"✅ Using conversation flow response: '{ai_response[:100]}...'")
        else:
            # Fallback to a generic welcome message if conversation flow fails
            app_logger.warning(f"⚠️ Conversation flow returned empty response, using fallback")
            ai_response = (
                "Olá! Bem-vindo ao Kumon Vila A! 😊\n\n"
                "Sou a sua assistente virtual e estou aqui para ajudá-lo com informações sobre nossa metodologia de ensino.\n\n"
                "Para começar, você está buscando o Kumon para você mesmo ou para outra pessoa? 🤔"
            )
        
        # Send response back via WhatsApp
        app_logger.info(f"📤 Sending response to {message.phone}: '{ai_response[:100]}...'")
        await evolution_api_client.send_text_message(
            instance_name=message.instance,
            phone=message.phone,
            message=ai_response
        )
        
        app_logger.info(f"✅ Response sent successfully to {message.phone}")
        
    except Exception as e:
        app_logger.error(f"❌ Error processing message in background: {str(e)}")
        
        # Send error message to user
        try:
            error_response = (
                "Olá! Bem-vindo ao Kumon Vila A! 😊\n\n"
                "Desculpe, houve um pequeno problema técnico. "
                "Você está buscando o Kumon para você mesmo ou para outra pessoa?"
            )
            await evolution_api_client.send_text_message(
                instance_name=message.instance,
                phone=message.phone,
                message=error_response
            )
        except Exception as send_error:
            app_logger.error(f"❌ Failed to send error message: {str(send_error)}")


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
            "rag_engine_initialized": True  # Simple RAG engine is always initialized
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
        # Build test context
        context = {
            "phone": phone,
            "sender_name": "Test User",
            "instance": instance_name
        }
        
        # Get AI response
        ai_response = await simple_rag_engine.answer_question(
            question=message,
            context=context
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