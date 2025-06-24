"""
WhatsApp Business API client
"""
import httpx
import json
from typing import Dict, Any, Optional, List
import asyncio
from urllib.parse import urljoin

from ..core.config import settings
from ..core.logger import app_logger
from ..models.message import MessageResponse, MessageType


class WhatsAppAPIError(Exception):
    """WhatsApp API specific error"""
    def __init__(self, message: str, status_code: int = None, response_data: Dict = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


class WhatsAppClient:
    """WhatsApp Business API client"""
    
    def __init__(self):
        self.base_url = "https://graph.facebook.com/v18.0"
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = settings.WHATSAPP_TOKEN
        
        # HTTP client with timeout and retry configuration
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        
        app_logger.info("WhatsApp client initialized", extra={
            "phone_number_id": self.phone_number_id[:8] + "..." if self.phone_number_id else None
        })
    
    async def send_message(self, to_number: str, message: str, message_type: MessageType = MessageType.TEXT) -> Dict[str, Any]:
        """Send message via WhatsApp Business API"""
        
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Prepare message payload
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": message_type.value
        }
        
        # Add message content based on type
        if message_type == MessageType.TEXT:
            payload["text"] = {"body": message}
        else:
            # For now, convert everything to text
            payload["text"] = {"body": message}
            payload["type"] = "text"
        
        try:
            app_logger.info("Sending WhatsApp message", extra={
                "to_number": to_number,
                "message_length": len(message),
                "message_type": message_type.value
            })
            
            response = await self.client.post(url, headers=headers, json=payload)
            response_data = response.json()
            
            if response.status_code == 200:
                app_logger.info("Message sent successfully", extra={
                    "to_number": to_number,
                    "message_id": response_data.get("messages", [{}])[0].get("id")
                })
                return response_data
            else:
                error_message = response_data.get("error", {}).get("message", "Unknown error")
                app_logger.error("Failed to send message", extra={
                    "to_number": to_number,
                    "status_code": response.status_code,
                    "error": error_message
                })
                raise WhatsAppAPIError(
                    f"Failed to send message: {error_message}",
                    status_code=response.status_code,
                    response_data=response_data
                )
        
        except httpx.TimeoutException:
            app_logger.error("WhatsApp API timeout", extra={"to_number": to_number})
            raise WhatsAppAPIError("WhatsApp API request timed out")
        
        except httpx.RequestError as e:
            app_logger.error(f"WhatsApp API request error: {str(e)}", extra={"to_number": to_number})
            raise WhatsAppAPIError(f"WhatsApp API request failed: {str(e)}")
    
    async def send_template_message(self, to_number: str, template_name: str, language_code: str = "pt_BR", components: List[Dict] = None) -> Dict[str, Any]:
        """Send template message via WhatsApp Business API"""
        
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code}
            }
        }
        
        if components:
            payload["template"]["components"] = components
        
        try:
            app_logger.info("Sending WhatsApp template message", extra={
                "to_number": to_number,
                "template_name": template_name,
                "language_code": language_code
            })
            
            response = await self.client.post(url, headers=headers, json=payload)
            response_data = response.json()
            
            if response.status_code == 200:
                app_logger.info("Template message sent successfully", extra={
                    "to_number": to_number,
                    "template_name": template_name
                })
                return response_data
            else:
                error_message = response_data.get("error", {}).get("message", "Unknown error")
                raise WhatsAppAPIError(
                    f"Failed to send template message: {error_message}",
                    status_code=response.status_code,
                    response_data=response_data
                )
        
        except Exception as e:
            app_logger.error(f"Template message error: {str(e)}")
            raise
    
    async def mark_message_as_read(self, message_id: str) -> bool:
        """Mark message as read"""
        
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        
        try:
            response = await self.client.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                app_logger.info("Message marked as read", extra={"message_id": message_id})
                return True
            else:
                app_logger.warning("Failed to mark message as read", extra={
                    "message_id": message_id,
                    "status_code": response.status_code
                })
                return False
        
        except Exception as e:
            app_logger.error(f"Error marking message as read: {str(e)}")
            return False
    
    async def get_media(self, media_id: str) -> Optional[Dict[str, Any]]:
        """Get media information from WhatsApp"""
        
        url = f"{self.base_url}/{media_id}"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            response = await self.client.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                app_logger.error("Failed to get media info", extra={
                    "media_id": media_id,
                    "status_code": response.status_code
                })
                return None
        
        except Exception as e:
            app_logger.error(f"Error getting media: {str(e)}")
            return None
    
    async def verify_webhook(self, token: str) -> bool:
        """Verify webhook token"""
        return token == settings.WHATSAPP_VERIFY_TOKEN
    
    async def get_business_profile(self) -> Optional[Dict[str, Any]]:
        """Get WhatsApp Business profile information"""
        
        url = f"{self.base_url}/{self.phone_number_id}/whatsapp_business_profile"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            response = await self.client.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                app_logger.error("Failed to get business profile", extra={
                    "status_code": response.status_code
                })
                return None
        
        except Exception as e:
            app_logger.error(f"Error getting business profile: {str(e)}")
            return None
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        try:
            asyncio.create_task(self.close())
        except Exception:
            pass


# Global WhatsApp client instance
whatsapp_client = WhatsAppClient() 