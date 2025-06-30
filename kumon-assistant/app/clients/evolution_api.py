"""
Evolution API client for WhatsApp integration
"""
import httpx
import asyncio
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
import json
import base64
from pathlib import Path

from ..core.config import settings
from ..core.logger import app_logger


@dataclass
class WhatsAppMessage:
    """Represents a WhatsApp message"""
    message_id: str
    phone: str
    message: str
    message_type: str
    timestamp: int
    instance: str
    sender_name: Optional[str] = None
    quoted_message: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None


@dataclass
class InstanceInfo:
    """Represents a WhatsApp instance"""
    instance_name: str
    status: str
    qr_code: Optional[str] = None
    phone_number: Optional[str] = None
    profile_name: Optional[str] = None


class EvolutionAPIClient:
    """Client for Evolution API WhatsApp integration"""
    
    def __init__(self):
        self.base_url = settings.EVOLUTION_API_URL
        self.api_key = settings.EVOLUTION_API_KEY
        self.global_api_key = settings.EVOLUTION_GLOBAL_API_KEY
        self.auth_key = settings.AUTHENTICATION_API_KEY
        
        # HTTP client with default headers
        self.headers = {
            "Content-Type": "application/json",
            "apikey": self.global_api_key if self.global_api_key else self.api_key
        }
        
        app_logger.info(f"Evolution API client initialized with base URL: {self.base_url}")
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        instance_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Evolution API"""
        url = f"{self.base_url}/{endpoint}"
        
        headers = self.headers.copy()
        if instance_name and self.auth_key:
            headers["Authorization"] = f"Bearer {self.auth_key}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=data)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=headers, json=data)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                
                # Handle different response types
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                else:
                    return {"content": response.text, "status_code": response.status_code}
                
        except httpx.HTTPStatusError as e:
            app_logger.error(f"HTTP error in Evolution API request: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            app_logger.error(f"Request error in Evolution API: {str(e)}")
            raise
        except Exception as e:
            app_logger.error(f"Unexpected error in Evolution API request: {str(e)}")
            raise
    
    async def create_instance(self, instance_name: str, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """Create a new WhatsApp instance"""
        data = {
            "instanceName": instance_name,
            "token": self.api_key,
            "qrcode": True,
            "markMessagesRead": True,
            "delayMessage": 1000,
            "webhook": {
                "url": webhook_url or settings.WEBHOOK_GLOBAL_URL,
                "by_events": True,
                "base64": False,
                "events": [
                    "APPLICATION_STARTUP",
                    "QRCODE_UPDATED",
                    "MESSAGES_UPSERT",
                    "MESSAGES_UPDATE", 
                    "MESSAGES_DELETE",
                    "SEND_MESSAGE",
                    "CONTACTS_UPDATE",
                    "CONTACTS_UPSERT",
                    "PRESENCE_UPDATE",
                    "CHATS_UPDATE",
                    "CHATS_UPSERT",
                    "CHATS_DELETE",
                    "GROUPS_UPSERT",
                    "GROUP_UPDATE",
                    "GROUP_PARTICIPANTS_UPDATE",
                    "CONNECTION_UPDATE"
                ]
            },
            "websocket": {
                "enabled": False,
                "events": []
            },
            "rabbitmq": {
                "enabled": False
            },
            "chatwoot": {
                "enabled": False
            },
            "openai": {
                "enabled": False
            }
        }
        
        app_logger.info(f"Creating WhatsApp instance: {instance_name}")
        result = await self._make_request("POST", "instance/create", data)
        app_logger.info(f"Instance created successfully: {instance_name}")
        return result
    
    async def get_instance_info(self, instance_name: str) -> InstanceInfo:
        """Get information about a WhatsApp instance"""
        try:
            result = await self._make_request("GET", f"instance/connect/{instance_name}")
            
            return InstanceInfo(
                instance_name=instance_name,
                status=result.get("instance", {}).get("state", "unknown"),
                qr_code=result.get("base64", ""),
                phone_number=result.get("instance", {}).get("wuid", ""),
                profile_name=result.get("instance", {}).get("profileName", "")
            )
        except Exception as e:
            app_logger.error(f"Error getting instance info for {instance_name}: {str(e)}")
            return InstanceInfo(instance_name=instance_name, status="error")
    
    async def list_instances(self) -> List[InstanceInfo]:
        """List all WhatsApp instances"""
        try:
            result = await self._make_request("GET", "instance/fetchInstances")
            instances = []
            
            for instance_data in result:
                instance = InstanceInfo(
                    instance_name=instance_data.get("instance", {}).get("instanceName", ""),
                    status=instance_data.get("instance", {}).get("state", "unknown"),
                    phone_number=instance_data.get("instance", {}).get("wuid", ""),
                    profile_name=instance_data.get("instance", {}).get("profileName", "")
                )
                instances.append(instance)
            
            return instances
        except Exception as e:
            app_logger.error(f"Error listing instances: {str(e)}")
            return []
    
    async def send_text_message(self, instance_name: str, phone: str, message: str) -> Dict[str, Any]:
        """Send a text message via WhatsApp"""
        # Clean phone number (remove special characters, ensure country code)
        clean_phone = self._clean_phone_number(phone)
        
        data = {
            "number": clean_phone,
            "options": {
                "delay": 1200,
                "presence": "composing",
                "linkPreview": False
            },
            "textMessage": {
                "text": message
            }
        }
        
        app_logger.info(f"Sending text message to {clean_phone} via instance {instance_name}")
        result = await self._make_request("POST", f"message/sendText/{instance_name}", data, instance_name)
        app_logger.info(f"Message sent successfully to {clean_phone}")
        return result
    
    async def send_media_message(
        self, 
        instance_name: str, 
        phone: str, 
        media_url: str, 
        caption: Optional[str] = None,
        media_type: str = "image"
    ) -> Dict[str, Any]:
        """Send a media message via WhatsApp"""
        clean_phone = self._clean_phone_number(phone)
        
        data = {
            "number": clean_phone,
            "options": {
                "delay": 1200,
                "presence": "composing"
            },
            "mediaMessage": {
                "mediatype": media_type,
                "media": media_url,
                "caption": caption or ""
            }
        }
        
        app_logger.info(f"Sending {media_type} message to {clean_phone} via instance {instance_name}")
        result = await self._make_request("POST", f"message/sendMedia/{instance_name}", data, instance_name)
        return result
    
    async def send_button_message(
        self, 
        instance_name: str, 
        phone: str, 
        text: str, 
        buttons: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Send a message with buttons via WhatsApp"""
        clean_phone = self._clean_phone_number(phone)
        
        # Format buttons for Evolution API
        formatted_buttons = []
        for i, button in enumerate(buttons):
            formatted_buttons.append({
                "buttonId": f"btn_{i}",
                "buttonText": {
                    "displayText": button.get("text", f"Option {i+1}")
                },
                "type": 1
            })
        
        data = {
            "number": clean_phone,
            "options": {
                "delay": 1200,
                "presence": "composing"
            },
            "buttonMessage": {
                "text": text,
                "buttons": formatted_buttons,
                "headerType": 1
            }
        }
        
        app_logger.info(f"Sending button message to {clean_phone} via instance {instance_name}")
        result = await self._make_request("POST", f"message/sendButtons/{instance_name}", data, instance_name)
        return result
    
    async def get_qr_code(self, instance_name: str) -> Optional[str]:
        """Get QR code for WhatsApp instance"""
        try:
            result = await self._make_request("GET", f"instance/connect/{instance_name}")
            return result.get("base64", "")
        except Exception as e:
            app_logger.error(f"Error getting QR code for {instance_name}: {str(e)}")
            return None
    
    async def delete_instance(self, instance_name: str) -> bool:
        """Delete a WhatsApp instance"""
        try:
            await self._make_request("DELETE", f"instance/delete/{instance_name}")
            app_logger.info(f"Instance deleted successfully: {instance_name}")
            return True
        except Exception as e:
            app_logger.error(f"Error deleting instance {instance_name}: {str(e)}")
            return False
    
    async def restart_instance(self, instance_name: str) -> bool:
        """Restart a WhatsApp instance"""
        try:
            await self._make_request("PUT", f"instance/restart/{instance_name}")
            app_logger.info(f"Instance restarted successfully: {instance_name}")
            return True
        except Exception as e:
            app_logger.error(f"Error restarting instance {instance_name}: {str(e)}")
            return False
    
    def _clean_phone_number(self, phone: str) -> str:
        """Clean and format phone number for WhatsApp"""
        # Remove all non-numeric characters
        clean = ''.join(filter(str.isdigit, phone))
        
        # Add country code if not present (assuming Brazil +55)
        if len(clean) == 11 and clean.startswith('11'):  # São Paulo mobile
            clean = f"55{clean}"
        elif len(clean) == 10 and clean.startswith('11'):  # São Paulo landline
            clean = f"55{clean}"
        elif len(clean) == 11 and not clean.startswith('55'):  # Mobile without country code
            clean = f"55{clean}"
        elif len(clean) == 10 and not clean.startswith('55'):  # Landline without country code
            clean = f"55{clean}"
        
        return clean
    
    def parse_webhook_message(self, webhook_data: Dict[str, Any]) -> Optional[WhatsAppMessage]:
        """Parse webhook data into WhatsAppMessage object"""
        try:
            event = webhook_data.get("event", "")
            data = webhook_data.get("data", {})
            
            if event != "messages.upsert":
                return None
            
            message_info = data.get("messages", [{}])[0]
            
            # Skip messages sent by the bot itself
            if message_info.get("key", {}).get("fromMe", False):
                return None
            
            message_id = message_info.get("key", {}).get("id", "")
            phone = message_info.get("key", {}).get("remoteJid", "").replace("@s.whatsapp.net", "")
            timestamp = message_info.get("messageTimestamp", 0)
            instance = webhook_data.get("instance", "")
            
            # Extract message content
            message_content = message_info.get("message", {})
            message_text = ""
            message_type = "text"
            media_url = None
            media_type = None
            
            if "conversation" in message_content:
                message_text = message_content["conversation"]
            elif "extendedTextMessage" in message_content:
                message_text = message_content["extendedTextMessage"].get("text", "")
            elif "imageMessage" in message_content:
                message_type = "image"
                message_text = message_content["imageMessage"].get("caption", "")
                media_type = "image"
            elif "videoMessage" in message_content:
                message_type = "video"
                message_text = message_content["videoMessage"].get("caption", "")
                media_type = "video"
            elif "audioMessage" in message_content:
                message_type = "audio"
                media_type = "audio"
            elif "documentMessage" in message_content:
                message_type = "document"
                message_text = message_content["documentMessage"].get("caption", "")
                media_type = "document"
            
            # Get sender name
            sender_name = message_info.get("pushName", "")
            
            return WhatsAppMessage(
                message_id=message_id,
                phone=phone,
                message=message_text,
                message_type=message_type,
                timestamp=int(timestamp),
                instance=instance,
                sender_name=sender_name,
                media_url=media_url,
                media_type=media_type
            )
            
        except Exception as e:
            app_logger.error(f"Error parsing webhook message: {str(e)}")
            return None
    
    async def get_instance_status(self, instance_name: str) -> str:
        """Get the connection status of an instance"""
        try:
            result = await self._make_request("GET", f"instance/connectionState/{instance_name}")
            return result.get("instance", {}).get("state", "unknown")
        except Exception as e:
            app_logger.error(f"Error getting instance status for {instance_name}: {str(e)}")
            return "error"


# Global instance
evolution_api_client = EvolutionAPIClient() 