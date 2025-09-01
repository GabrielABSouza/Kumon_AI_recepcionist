"""
Twilio Provider Implementation
WhatsApp + SMS fallback provider for production resilience when Evolution API fails
"""

import asyncio
import time
import json
from typing import AsyncIterator, Optional, Dict, Any, List
import httpx
from urllib.parse import urljoin

from ...core.config import settings
from ...core.logger import app_logger
from ..llm_base import BaseLLMProvider, LLMRequest, LLMResponse, LLMMetrics


class TwilioProvider(BaseLLMProvider):
    """
    Twilio provider implementation for WhatsApp and SMS fallback
    
    Features:
    - WhatsApp Business API integration
    - SMS fallback when WhatsApp unavailable
    - Rate limiting and cost estimation
    - Circuit breaker pattern integration
    """
    
    def __init__(self, account_sid: str = None, auth_token: str = None, model: str = None, **kwargs):
        super().__init__("twilio", "whatsapp-business-api")
        
        # Twilio credentials
        self.account_sid = account_sid or getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        self.auth_token = auth_token or getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        self.whatsapp_from = getattr(settings, 'TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
        self.sms_from = getattr(settings, 'TWILIO_SMS_FROM', None)
        
        # API configuration
        self.base_url = "https://api.twilio.com/2010-04-01"
        self.timeout = 30.0
        self.max_retries = 2
        
        # Check configuration
        if not self.account_sid or not self.auth_token:
            app_logger.warning("Twilio credentials not configured - provider will be unavailable")
            self.client = None
            return
        
        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            auth=(self.account_sid, self.auth_token),
            timeout=self.timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        
        # Default configuration for Kumon business context
        self.default_config = {
            "provider": "twilio",
            "type": "whatsapp",
            "fallback_to_sms": True,
            "max_message_length": 1600,  # WhatsApp limit
            "sms_max_length": 320,  # SMS segments
            "rate_limit_per_minute": 60  # Twilio WhatsApp limits
        }
        
        # Business context message template
        self.business_template = """🏫 *Kumon Vila A - Porto Alegre*

{message}

📞 *Contato direto*: (51) 99692-1999
📍 *Endereço*: Vila A, Porto Alegre
⏰ *Horário*: Seg-Sex, 9h-12h e 14h-17h

_Mensagem automática do sistema Kumon_"""
        
        app_logger.info("Twilio provider initialized", extra={
            "account_sid": f"{self.account_sid[:8]}..." if self.account_sid else "not_configured",
            "whatsapp_configured": bool(self.whatsapp_from),
            "sms_configured": bool(self.sms_from),
            "status": "ready" if self.client else "unavailable"
        })
    
    async def stream_response(self, request: LLMRequest) -> AsyncIterator[str]:
        """
        Send message via Twilio WhatsApp/SMS (non-streaming response)
        
        Note: Twilio doesn't support streaming, so we simulate streaming
        by yielding the formatted message in chunks
        """
        if not self.client:
            app_logger.warning("Twilio service unavailable - using fallback response")
            yield "Desculpe, o sistema de mensagens está temporariamente indisponível. Entre em contato: (51) 99692-1999"
            return
        
        metrics = LLMMetrics(
            provider="twilio",
            model="whatsapp-business-api",
            start_time=time.time()
        )
        
        try:
            # Extract message content and target phone
            message_content = self._extract_message_content(request.messages)
            target_phone = request.context.get("target_phone") if request.context else None
            
            if not target_phone:
                app_logger.error("Twilio provider requires target_phone in request context")
                yield "Erro de configuração do sistema. Entre em contato: (51) 99692-1999"
                return
            
            # Format business message
            formatted_message = self.business_template.format(message=message_content)
            
            # Attempt WhatsApp delivery first
            delivery_result = await self._send_whatsapp_message(target_phone, formatted_message)
            
            if not delivery_result.get("success") and self.default_config["fallback_to_sms"]:
                app_logger.info("WhatsApp delivery failed, falling back to SMS")
                delivery_result = await self._send_sms_message(target_phone, message_content)
            
            # Track metrics
            metrics.completion_time = time.time()
            metrics.total_characters = len(formatted_message)
            
            # Estimate cost (Twilio pricing)
            estimated_cost = self._estimate_delivery_cost(
                delivery_result.get("message_type", "whatsapp"),
                len(formatted_message)
            )
            metrics.cost_estimate = estimated_cost
            
            # Simulate streaming by yielding message in chunks
            if delivery_result.get("success"):
                confirmation_msg = f"✅ Mensagem enviada via {delivery_result.get('delivery_method', 'WhatsApp')} para {target_phone}"
                
                # Yield in chunks to simulate streaming
                chunk_size = 50
                for i in range(0, len(confirmation_msg), chunk_size):
                    chunk = confirmation_msg[i:i + chunk_size]
                    metrics.total_chunks += 1
                    yield chunk
                    await asyncio.sleep(0.1)  # Simulate streaming delay
                
                app_logger.info("Twilio message delivery successful", extra={
                    "target_phone": target_phone,
                    "delivery_method": delivery_result.get("delivery_method"),
                    "cost_estimate": estimated_cost,
                    "message_length": len(formatted_message)
                })
            else:
                error_msg = "❌ Falha na entrega da mensagem. Entre em contato: (51) 99692-1999"
                yield error_msg
                
                app_logger.error("Twilio message delivery failed", extra={
                    "target_phone": target_phone,
                    "error": delivery_result.get("error", "unknown")
                })
            
            # Store metrics
            self.add_metrics(metrics)
            
        except Exception as e:
            app_logger.error("Twilio provider error", extra={
                "elapsed_ms": (time.time() - metrics.start_time) * 1000,
                "provider": "twilio",
                "error_type": type(e).__name__,
                "error_id": f"twilio_error_{int(time.time())}"
            })
            
            yield "Desculpe, houve um problema no sistema de mensagens. Para atendimento imediato, entre em contato: (51) 99692-1999"
    
    async def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Generate complete response (non-streaming)"""
        if not self.client:
            raise ValueError("Twilio service not available - credentials not configured")
        
        metrics = LLMMetrics(
            provider="twilio",
            model="whatsapp-business-api",
            start_time=time.time()
        )
        
        try:
            # Extract content and send message
            message_content = self._extract_message_content(request.messages)
            target_phone = request.context.get("target_phone") if request.context else None
            
            if not target_phone:
                raise ValueError("Twilio provider requires target_phone in request context")
            
            formatted_message = self.business_template.format(message=message_content)
            
            # Send via WhatsApp with SMS fallback
            delivery_result = await self._send_whatsapp_message(target_phone, formatted_message)
            
            if not delivery_result.get("success") and self.default_config["fallback_to_sms"]:
                delivery_result = await self._send_sms_message(target_phone, message_content)
            
            metrics.completion_time = time.time()
            metrics.total_characters = len(formatted_message)
            metrics.cost_estimate = self._estimate_delivery_cost(
                delivery_result.get("message_type", "whatsapp"),
                len(formatted_message)
            )
            
            self.add_metrics(metrics)
            
            response_content = (
                f"Mensagem enviada via {delivery_result.get('delivery_method', 'WhatsApp')}" 
                if delivery_result.get("success") 
                else "Falha na entrega da mensagem"
            )
            
            return LLMResponse(
                content=response_content,
                metrics=metrics,
                provider="twilio",
                model="whatsapp-business-api",
                finish_reason="delivered" if delivery_result.get("success") else "failed",
                usage={
                    "characters": len(formatted_message),
                    "delivery_method": delivery_result.get("delivery_method"),
                    "cost_estimate": metrics.cost_estimate
                }
            )
            
        except Exception as e:
            app_logger.error("Twilio generation error", extra={
                "provider": "twilio",
                "error_type": type(e).__name__,
                "error_id": f"twilio_gen_error_{int(time.time())}"
            })
            raise ValueError("Twilio service temporarily unavailable") from e
    
    async def _send_whatsapp_message(self, to_phone: str, message: str) -> Dict[str, Any]:
        """Send message via Twilio WhatsApp Business API"""
        try:
            # Format phone number for WhatsApp
            formatted_to = f"whatsapp:+55{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone
            
            # Prepare message data
            message_data = {
                "From": self.whatsapp_from,
                "To": formatted_to,
                "Body": message[:self.default_config["max_message_length"]]
            }
            
            # Send via Twilio Messages API
            url = f"{self.base_url}/Accounts/{self.account_sid}/Messages.json"
            
            response = await self.client.post(url, data=message_data)
            
            if response.status_code == 201:
                result = response.json()
                return {
                    "success": True,
                    "message_type": "whatsapp",
                    "delivery_method": "WhatsApp",
                    "message_sid": result.get("sid"),
                    "status": result.get("status", "queued")
                }
            else:
                error_detail = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
                return {
                    "success": False,
                    "error": f"WhatsApp API error: {response.status_code}",
                    "details": error_detail
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"WhatsApp delivery exception: {str(e)}"
            }
    
    async def _send_sms_message(self, to_phone: str, message: str) -> Dict[str, Any]:
        """Send message via Twilio SMS as fallback"""
        try:
            if not self.sms_from:
                return {
                    "success": False,
                    "error": "SMS sender number not configured"
                }
            
            # Format phone number for SMS
            formatted_to = f"+55{to_phone}" if not to_phone.startswith("+") else to_phone
            
            # Truncate message for SMS
            sms_message = message[:self.default_config["sms_max_length"]]
            if len(message) > self.default_config["sms_max_length"]:
                sms_message += "... (cont. via WhatsApp)"
            
            message_data = {
                "From": self.sms_from,
                "To": formatted_to,
                "Body": sms_message
            }
            
            url = f"{self.base_url}/Accounts/{self.account_sid}/Messages.json"
            
            response = await self.client.post(url, data=message_data)
            
            if response.status_code == 201:
                result = response.json()
                return {
                    "success": True,
                    "message_type": "sms",
                    "delivery_method": "SMS",
                    "message_sid": result.get("sid"),
                    "status": result.get("status", "queued")
                }
            else:
                error_detail = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
                return {
                    "success": False,
                    "error": f"SMS API error: {response.status_code}",
                    "details": error_detail
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"SMS delivery exception: {str(e)}"
            }
    
    def _extract_message_content(self, messages: List[Dict[str, str]]) -> str:
        """Extract message content from LLM request format"""
        if not messages:
            return "Mensagem de teste do sistema Kumon"
        
        # Get the last user or assistant message
        for message in reversed(messages):
            if message.get("role") in ["user", "assistant"] and message.get("content"):
                return message["content"]
        
        return "Mensagem automática do sistema Kumon"
    
    def _estimate_delivery_cost(self, message_type: str, message_length: int) -> float:
        """Estimate cost for Twilio message delivery"""
        # Twilio pricing (as of 2024) - in USD, converted to BRL
        usd_to_brl = 5.20
        
        if message_type == "whatsapp":
            # WhatsApp Business API pricing
            if message_length <= 1024:
                usd_cost = 0.005  # Template message
            else:
                usd_cost = 0.01  # Session message
        else:  # SMS
            # SMS pricing (per segment)
            segments = (message_length // 160) + 1
            usd_cost = segments * 0.0075  # SMS segment cost
        
        return usd_cost * usd_to_brl
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for compatibility with LLM providers"""
        # For messaging providers, estimate based on typical message length
        estimated_message_length = input_tokens * 4 + output_tokens * 4  # ~4 chars per token
        return self._estimate_delivery_cost("whatsapp", estimated_message_length)
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get Twilio rate limit information"""
        return {
            "whatsapp_per_minute": 60,
            "sms_per_minute": 100,
            "concurrent_requests": 10,
            "daily_limit": 1000  # Conservative estimate
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Twilio API connection"""
        try:
            if not self.client:
                return {
                    "success": False,
                    "provider": "twilio",
                    "error": "Credentials not configured"
                }
            
            # Test account information endpoint
            url = f"{self.base_url}/Accounts/{self.account_sid}.json"
            
            start_time = time.time()
            response = await self.client.get(url)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                account_info = response.json()
                
                return {
                    "success": True,
                    "provider": "twilio",
                    "account_sid": f"{self.account_sid[:8]}...",
                    "account_status": account_info.get("status"),
                    "whatsapp_configured": bool(self.whatsapp_from),
                    "sms_configured": bool(self.sms_from),
                    "response_time_ms": duration * 1000,
                    "test_timestamp": time.time()
                }
            else:
                return {
                    "success": False,
                    "provider": "twilio",
                    "error": f"API error: {response.status_code}",
                    "response_time_ms": duration * 1000
                }
                
        except Exception as e:
            app_logger.error("Twilio connection test failed", extra={
                "provider": "twilio",
                "error_type": type(e).__name__,
                "error_id": f"twilio_test_error_{int(time.time())}"
            })
            return {
                "success": False,
                "provider": "twilio",
                "error": "Connection test failed"
            }
    
    async def cleanup(self):
        """Cleanup HTTP client resources"""
        if self.client:
            await self.client.aclose()