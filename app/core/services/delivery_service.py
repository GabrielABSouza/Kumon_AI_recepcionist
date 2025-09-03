"""
DeliveryService - Centralized Message Delivery with Atomic State Updates

Handles the final step of the conversation pipeline:
1. Send planned_response to user via Evolution API
2. Update current_stage/current_step only after successful delivery
3. Apply fallback if delivery fails
4. Persist state atomically
"""

from typing import Dict, Any, Optional
import time
from datetime import datetime, timezone
import logging

from ...core.state.models import CeciliaState
from ...core.state.managers import StateManager
from ...api.evolution import send_message
from ...workflows.contracts import IntentResult, DeliveryResult, RoutingDecision, normalize_routing_decision, normalize_intent_result, safe_get_payload, safe_get_delivery_field
from ..telemetry import emit_delivery_event, generate_trace_id

logger = logging.getLogger(__name__)


def _safe_get(obj, key: str, default=None):
    """Safely get value from dict or dataclass object"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    else:
        return getattr(obj, key, default)


class DeliveryService:
    """
    Centralized message delivery service with atomic state management
    
    Responsibilities:
    - Send planned_response to user
    - Update conversation stage/step only after successful delivery
    - Apply fallback strategies on delivery failure
    - Maintain state atomicity and consistency
    """
    
    def __init__(self):
        self.delivery_stats = {
            "total_deliveries": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "fallback_activations": 0
        }
    
    async def deliver_response(
        self,
        state: CeciliaState,
        phone_number: str,
        intent_result: IntentResult,
        routing_decision: Dict[str, Any] | RoutingDecision
    ) -> DeliveryResult:
        """
        Deliver response using IntentResult with validated payload
        
        Args:
            state: Current conversation state
            phone_number: Target phone number
            intent_result: IntentResult with delivery_payload
            routing_decision: SmartRouter decision with target_node
            
        Returns:
            DeliveryResult with delivery outcome and details
        """
        start_time = time.time()
        delivery_id = f"delivery_{int(time.time() * 1000)}"
        trace_id = generate_trace_id()
        
        logger.info(
            f"🚀 Starting delivery {delivery_id} for {phone_number[-4:]} (trace: {trace_id[:8]})"
        )
        
        # DEBUG: Log what we received
        logger.info(f"🔍 DEBUG received routing_decision: {routing_decision}")
        logger.info(f"🔍 DEBUG routing_decision type: {type(routing_decision)}")
        if isinstance(routing_decision, dict):
            logger.info(f"🔍 DEBUG routing_decision keys: {routing_decision.keys()}")
        else:
            logger.info(f"🔍 DEBUG routing_decision attrs: {[attr for attr in dir(routing_decision) if not attr.startswith('_')]}")
        
        try:
            # Normalize inputs to dataclasses
            intent_result = normalize_intent_result(intent_result)
            routing_decision = normalize_routing_decision(routing_decision)
            
            # Extract delivery payload safely
            delivery_payload = safe_get_payload(intent_result)
            if not delivery_payload:
                return DeliveryResult(
                    success=False,
                    channel=getattr(routing_decision, "channel", "unknown"),
                    status="failed",
                    reason="missing_delivery_payload"
                )
            
            # Extract channel from payload (now guaranteed to be dict)
            channel = delivery_payload.get("channel", "whatsapp")
            
            # Pre-delivery validation
            validation_result = self._validate_delivery(state, delivery_payload, routing_decision)
            if not validation_result["valid"]:
                # Emit validation failure telemetry
                delivery_time_ms = (time.time() - start_time) * 1000
                emit_delivery_event(
                    trace_id=trace_id,
                    node_id="delivery_service",
                    stage=str(state.get("current_stage", "unknown")),
                    step=str(state.get("current_step", "unknown")),
                    channel=channel,
                    duration_ms=delivery_time_ms,
                    success=False,
                    err_type=f"validation_failed_{validation_result['reason']}"
                )
                
                return await self._handle_validation_failure(
                    state, phone_number, validation_result, delivery_id, channel, trace_id
                )
            
            # Attempt message delivery
            delivery_result = await self._send_message_safe(
                phone_number, delivery_payload, delivery_id, channel
            )
            
            if delivery_result["success"]:
                # SUCCESS: Update state atomically after successful delivery
                updated_state = await self._apply_successful_delivery_updates(
                    state, routing_decision, delivery_result, delivery_id
                )
                
                # Update delivery stats
                self.delivery_stats["successful_deliveries"] += 1
                self.delivery_stats["total_deliveries"] += 1
                
                delivery_time_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"✅ Delivery {delivery_id} successful ({delivery_time_ms:.0f}ms)"
                )
                
                # Emit successful delivery telemetry
                emit_delivery_event(
                    trace_id=trace_id,
                    node_id="delivery_service",
                    stage=str(state.get("current_stage", "unknown")),
                    step=str(state.get("current_step", "unknown")),
                    channel=channel,
                    duration_ms=delivery_time_ms,
                    success=True,
                    message_id=safe_get_delivery_field(delivery_result, "message_id")
                )
                
                return DeliveryResult(
                    success=True,
                    channel=channel,
                    message_id=safe_get_delivery_field(delivery_result, "message_id"),
                    status="ok",
                    reason=None
                )
            
            else:
                # FAILURE: Apply fallback strategy
                delivery_time_ms = (time.time() - start_time) * 1000
                
                # Emit failure delivery telemetry
                emit_delivery_event(
                    trace_id=trace_id,
                    node_id="delivery_service",
                    stage=str(state.get("current_stage", "unknown")),
                    step=str(state.get("current_step", "unknown")),
                    channel=channel,
                    duration_ms=delivery_time_ms,
                    success=False,
                    err_type=safe_get_delivery_field(delivery_result, "reason", "delivery_failed")
                )
                
                return await self._handle_delivery_failure(
                    state, phone_number, delivery_result, routing_decision, delivery_id, trace_id
                )
        
        except Exception as e:
            logger.error(f"🚨 Critical delivery error {delivery_id}: {e}", exc_info=True)
            
            # Emit critical failure telemetry
            delivery_time_ms = (time.time() - start_time) * 1000
            emit_delivery_event(
                trace_id=trace_id,
                node_id="delivery_service",
                stage=str(state.get("current_stage", "unknown")),
                step=str(state.get("current_step", "unknown")),
                channel=getattr(routing_decision, "channel", "unknown"),
                duration_ms=delivery_time_ms,
                success=False,
                err_type="critical_delivery_exception"
            )
            
            return await self._handle_critical_failure(
                state, phone_number, str(e), routing_decision, delivery_id, trace_id
            )
    
    def _validate_delivery(
        self,
        state: CeciliaState,
        payload: Dict[str, Any],
        routing_decision: RoutingDecision
    ) -> Dict[str, Any]:
        """Pre-delivery validation with guardrails and sanitization"""
        
        # Basic content validation - payload is now guaranteed to be dict
        content = payload.get("content", {})
        text = content.get("text", "") if content else ""
            
        if not text.strip():
            return {
                "valid": False,
                "reason": "empty_content",
                "details": "Delivery payload content is empty"
            }
        
        # PHASE 2.3: Sanitize template for user-facing content only
        sanitized_text = self._sanitize_template_content(text)
        
        # Update payload with sanitized text
        if not payload.get("content"):
            payload["content"] = {}
        payload["content"]["text"] = sanitized_text
        
        # Length validation (after sanitization)
        if len(sanitized_text) > 4000:  # WhatsApp limit
            return {
                "valid": False,
                "reason": "response_too_long",
                "details": f"Response length: {len(sanitized_text)} > 4000"
            }
        
        # Placeholder validation
        if "{{" in sanitized_text or "}}" in sanitized_text:
            return {
                "valid": False,
                "reason": "unresolved_placeholders",
                "details": "Response contains unresolved template variables"
            }
        
        # Routing decision validation
        logger.info(f"🔍 DEBUG _validate_delivery routing_decision: {routing_decision}")
        logger.info(f"🔍 DEBUG routing_decision target_node: {routing_decision.target_node}")
        
        if not routing_decision.target_node:
            return {
                "valid": False,
                "reason": "invalid_routing",
                "details": "No target_node in routing decision"
            }
        
        return {"valid": True}
    
    def _sanitize_template_content(self, template_content: str) -> str:
        """
        Sanitize template content to remove internal directives and keep only user-facing content.
        
        PHASE 2.3: Remove lines that contain system directives, leaving only the content
        that should be sent to the user.
        
        Args:
            template_content: Raw template content with possible internal directives
            
        Returns:
            Sanitized content safe for user delivery
        """
        lines = template_content.split('\n')
        sanitized_lines = []
        
        # Patterns to identify internal directives (not user content)
        internal_patterns = [
            # System directives
            r'^(Você é|You are) (Cecília|the assistant)',
            r'^DIRETRIZES',
            r'^INSTRUÇÕES',
            r'^INFORMAÇÕES DE PREÇOS',
            r'^POLÍTICA',
            r'^EXEMPLOS',
            r'^## (DIRETRIZES|INSTRUÇÕES|INFORMAÇÕES|POLÍTICA|EXEMPLOS)',
            r'^Contexto da conversa:',
            r'^Mensagem do responsável:',
            r'^Responda como',
            r'^\d+\.',  # Numbered instructions
            # Variable placeholders at start of line
            r'^{context}',
            r'^{user_message}',
            # Comments and meta information
            r'^#',
            r'^\*\*Exemplo \d+:',
            # Empty example responses in templates
            r'^Responsável:',
            r'^Cecília:',
        ]
        
        skip_next = False
        in_examples_section = False
        
        for line in lines:
            line_stripped = line.strip()
            
            # Skip empty lines at start
            if not line_stripped and not sanitized_lines:
                continue
                
            # Check if we're entering examples section
            if any([
                'EXEMPLOS' in line_stripped.upper(),
                '**Exemplo' in line,
                'Responsável:' in line,
                'Cecília:' in line and not sanitized_lines  # Only if at start
            ]):
                in_examples_section = True
                continue
                
            # Skip content if in examples section
            if in_examples_section:
                continue
                
            # Check against internal patterns
            is_internal = False
            for pattern in internal_patterns:
                import re
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    is_internal = True
                    break
            
            # Skip internal directives
            if is_internal:
                continue
                
            # If we have a line that looks like actual response content, keep it
            if line_stripped and not is_internal:
                sanitized_lines.append(line)
        
        # Join and clean up
        sanitized_content = '\n'.join(sanitized_lines)
        
        # Remove excessive whitespace
        import re
        sanitized_content = re.sub(r'\n\s*\n\s*\n', '\n\n', sanitized_content)
        sanitized_content = sanitized_content.strip()
        
        # Log sanitization if significant content was removed
        original_length = len(template_content)
        sanitized_length = len(sanitized_content)
        if original_length - sanitized_length > 100:
            logger.info(f"🧹 Template sanitized: {original_length} → {sanitized_length} chars")
            
        return sanitized_content
    
    async def _send_to_channel(self, channel: str, phone_number: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send message to web/app channels with proper error handling"""
        
        content = payload.get("content", {})
        message_text = content.get("text", "") if content else ""
        attachments = payload.get("attachments", [])
        meta = payload.get("meta", {})
        
        try:
            if channel == "web":
                return await self._send_web_message(phone_number, message_text, attachments, meta)
            elif channel == "app":
                return await self._send_app_message(phone_number, message_text, attachments, meta)
            else:
                return {
                    "status": "error",
                    "error": "unsupported_channel",
                    "details": f"Channel {channel} not supported"
                }
                
        except Exception as e:
            logger.error(f"Channel {channel} delivery failed: {e}")
            return {
                "status": "error", 
                "error": f"{channel}_delivery_exception",
                "details": str(e)
            }
    
    async def _send_web_message(
        self, 
        phone_number: str, 
        message_text: str, 
        attachments: list, 
        meta: dict
    ) -> Dict[str, Any]:
        """Send message to web channel (WebSocket, HTTP API, etc.)"""
        
        # Simulate web delivery - in real implementation this would:
        # 1. Send via WebSocket to active web sessions
        # 2. Send via HTTP POST to webhook endpoints
        # 3. Store in web message queue for pickup
        
        # For P1.D implementation: Create realistic failure scenarios for testing
        import random
        
        # Simulate network issues, server downtime, etc.
        if random.random() < 0.1:  # 10% failure rate for testing
            return {
                "status": "error",
                "error": "web_api_timeout", 
                "details": "Web API connection timeout"
            }
        
        # Simulate successful delivery
        message_id = f"web_{phone_number}_{int(time.time() * 1000)}"
        
        logger.info(f"📧 Web message sent: {message_id} to {phone_number[-4:]}")
        
        return {
            "status": "success",
            "message_id": message_id,
            "delivery_method": "web_api",
            "channel_info": {
                "endpoint": "web_messaging_api", 
                "delivery_time": time.time()
            }
        }
    
    async def _send_app_message(
        self, 
        phone_number: str, 
        message_text: str, 
        attachments: list, 
        meta: dict
    ) -> Dict[str, Any]:
        """Send message to app channel (push notifications, in-app messaging, etc.)"""
        
        # Simulate app delivery - in real implementation this would:
        # 1. Send push notification via Firebase/APNs
        # 2. Store in in-app message inbox
        # 3. Send via app-specific messaging API
        
        # For P1.D implementation: Create realistic failure scenarios for testing
        import random
        
        # Simulate push notification service issues, app not installed, etc.
        if random.random() < 0.15:  # 15% failure rate for testing (higher than web)
            return {
                "status": "error",
                "error": "push_service_failed",
                "details": "Push notification service unavailable"
            }
        
        # Simulate successful delivery
        message_id = f"app_{phone_number}_{int(time.time() * 1000)}"
        
        logger.info(f"📱 App message sent: {message_id} to {phone_number[-4:]}")
        
        return {
            "status": "success", 
            "message_id": message_id,
            "delivery_method": "app_push",
            "channel_info": {
                "service": "firebase_fcm",
                "delivery_time": time.time()
            }
        }
    
    async def _send_message_safe(
        self,
        phone_number: str,
        payload: Dict[str, Any],
        delivery_id: str,
        channel: str
    ) -> Dict[str, Any]:
        """Send message with error handling and retries"""
        
        try:
            # Extract message text from payload
            content = payload.get("content", {})
            message_text = content.get("text", "") if content else ""
            
            # Channel-specific delivery logic
            if channel == "whatsapp":
                # Attempt delivery via Evolution API
                send_result = await send_message(phone_number, message_text)
            elif channel in ["web", "app"]:
                # Placeholder for web/app delivery (P1.D will implement fallback)
                send_result = await self._send_to_channel(channel, phone_number, payload)
            else:
                return {
                    "success": False,
                    "reason": "unsupported_channel",
                    "details": f"Channel {channel} not supported"
                }
            
            if send_result and send_result.get("status") == "success":
                return {
                    "success": True,
                    "delivery_method": "evolution_api",
                    "message_id": send_result.get("message_id"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": "evolution_api_failure",
                    "details": send_result,
                    "retry_possible": True
                }
        
        except Exception as e:
            logger.error(f"Evolution API send failed for {delivery_id}: {e}")
            return {
                "success": False,
                "error": "evolution_api_exception",
                "details": str(e),
                "retry_possible": False
            }
    
    async def _apply_successful_delivery_updates(
        self,
        state: CeciliaState,
        routing_decision: RoutingDecision,
        delivery_result: Dict[str, Any],
        delivery_id: str
    ) -> CeciliaState:
        """Apply state updates after successful delivery using canonical stage mapping"""
        
        # PHASE 2.3: Use corrected target from routing_info (set by edges after validation)
        routing_info = state.get("routing_info", {})
        target_node = routing_info.get("target_node", routing_decision.target_node or "fallback")
        current_stage = state.get("current_stage")
        
        # Log which target we're using
        original_target = routing_info.get("original_target", routing_decision.target_node)
        if target_node != original_target:
            logger.info(f"🔧 Using corrected target: {original_target} → {target_node}")
        else:
            logger.info(f"🎯 Using validated target: {target_node}")
        
        # PHASE 2.3: Use canonical stage mapping utility
        from ...core.state.stage_mapping import map_target_to_stage_step
        
        # Don't update stage if target_node is "fallback"
        if target_node == "fallback":
            logger.info(f"⚠️ Target is fallback - keeping current stage: {current_stage}")
            stage_updates = {
                "current_stage": current_stage,
                "current_step": state.get("current_step")
            }
        else:
            # Use canonical mapping for stage progression
            new_stage, new_step = map_target_to_stage_step(target_node, current_stage)
            stage_updates = {
                "current_stage": new_stage,
                "current_step": new_step
            }
            
            # Log stage progression
            old_stage = self._get_stage_value(current_stage)
            new_stage_str = self._get_stage_value(new_stage)
            logger.info(f"📊 Stage progression: {old_stage} → {new_stage_str} (target: {target_node})")
        
        # Add delivery metadata
        delivery_updates = {
            **stage_updates,
            "last_delivery": {
                "delivery_id": delivery_id,
                "timestamp": delivery_result["timestamp"],
                "method": delivery_result["delivery_method"],
                "message_id": safe_get_delivery_field(delivery_result, "message_id"),
                "target_node": target_node
            },
            "last_activity": datetime.now(timezone.utc),
            "delivery_success": True
        }
        
        # Apply updates atomically
        updated_state = StateManager.update_state(state, delivery_updates)
        
        return updated_state
    
    def _get_stage_value(self, stage):
        """Safely extract stage value for logging (handle both Enum and string)"""
        if hasattr(stage, 'value'):
            return stage.value
        return str(stage) if stage else "unknown"
    
    async def _handle_delivery_failure(
        self,
        state: CeciliaState,
        phone_number: str,
        delivery_result: Dict[str, Any],
        routing_decision: RoutingDecision,
        delivery_id: str,
        trace_id: str
    ) -> DeliveryResult:
        """Handle delivery failure with fallback strategies"""
        
        logger.warning(f"⚠️ Delivery {delivery_id} failed: {safe_get_delivery_field(delivery_result, 'reason')}")
        
        # Update failure stats
        self.delivery_stats["failed_deliveries"] += 1
        self.delivery_stats["total_deliveries"] += 1
        
        # Apply fallback strategy with channel-aware fallback
        # Check if retry is possible based on delivery status
        if safe_get_delivery_field(delivery_result, "status") != "failed":
            # Get original channel from the payload that failed
            original_channel = state.get("delivery_payload", {}).get("channel", "whatsapp")
            fallback_channel, fallback_message = self._get_fallback_channel_and_message(
                state, routing_decision, delivery_result, original_channel
            )
            
            # Create fallback payload from simple message
            from ...workflows.contracts import DeliveryPayload
            fallback_payload = DeliveryPayload(
                channel=fallback_channel,
                content={"text": fallback_message},
                attachments=[],
                meta={}
            )
            
            retry_result = await self._send_message_safe(
                phone_number, fallback_payload, f"{delivery_id}_retry", fallback_channel
            )
            
            if retry_result["success"]:
                logger.info(f"✅ Fallback delivery successful for {delivery_id}")
                self.delivery_stats["fallback_activations"] += 1
                
                # Apply updates with fallback flag
                updated_state = await self._apply_successful_delivery_updates(
                    state, routing_decision, retry_result, delivery_id
                )
                updated_state["delivery_fallback_used"] = True
                
                return DeliveryResult(
                    success=True,
                    channel=fallback_channel,
                    message_id=retry_result.get("message_id"),
                    status="ok",
                    reason=None
                )
        
        # Critical failure - do not update stage
        logger.error(f"🚨 Critical delivery failure {delivery_id} - stage NOT updated")
        
        failure_updates = {
            "delivery_failed": True,
            "last_delivery_error": {
                "delivery_id": delivery_id,
                "error": safe_get_delivery_field(delivery_result, "reason"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "target_node": routing_decision.target_node
            }
        }
        
        updated_state = StateManager.update_state(state, failure_updates)
        
        return DeliveryResult(
            success=False,
            channel=getattr(routing_decision, "channel", "unknown"),
            message_id=None,
            status="failed",
            reason=safe_get_delivery_field(delivery_result, "reason", "delivery_failed")
        )
    
    async def _handle_validation_failure(
        self,
        state: CeciliaState,
        phone_number: str,
        validation_result: Dict[str, Any],
        delivery_id: str,
        channel: str,
        trace_id: str
    ) -> DeliveryResult:
        """Handle pre-delivery validation failure"""
        
        logger.warning(f"⚠️ Validation failed {delivery_id}: {validation_result['reason']}")
        
        # Try to send emergency fallback
        emergency_response = "Desculpe, houve um problema técnico. Nossa equipe entrará em contato em breve."
        
        # Create emergency payload
        from ...workflows.contracts import DeliveryPayload
        emergency_payload = DeliveryPayload(
            channel=channel,
            content={"text": emergency_response},
            attachments=[],
            meta={}
        )
        
        emergency_result = await self._send_message_safe(
            phone_number, emergency_payload, f"{delivery_id}_emergency", channel
        )
        
        validation_updates = {
            "validation_failed": True,
            "validation_error": validation_result["reason"],
            "emergency_response_sent": emergency_result["success"]
        }
        
        updated_state = StateManager.update_state(state, validation_updates)
        
        return DeliveryResult(
            success=False,
            channel=channel,
            message_id=emergency_result.get("message_id") if emergency_result["success"] else None,
            status="failed",
            reason=f"validation_failed_{validation_result['reason']}"
        )
    
    async def _handle_critical_failure(
        self,
        state: CeciliaState,
        phone_number: str,
        error: str,
        routing_decision: RoutingDecision,
        delivery_id: str,
        trace_id: str
    ) -> DeliveryResult:
        """Handle critical system failures"""
        
        logger.error(f"🚨 CRITICAL FAILURE {delivery_id}: {error}")
        
        critical_updates = {
            "critical_delivery_failure": True,
            "critical_error": error,
            "requires_manual_intervention": True
        }
        
        updated_state = StateManager.update_state(state, critical_updates)
        
        return DeliveryResult(
            success=False,
            channel=getattr(routing_decision, "channel", "unknown"),
            message_id=None,
            status="failed",
            reason=f"critical_failure_{error}"
        )
    
    def _get_fallback_message(
        self,
        state: CeciliaState,
        routing_decision: RoutingDecision
    ) -> str:
        """Generate simple fallback message"""
        
        target_node = routing_decision.target_node
        
        fallback_messages = {
            "greeting": "Olá! Sou Cecília do Kumon Vila A. Como posso ajudá-lo hoje? 😊",
            "qualification": "Vamos conhecer melhor o estudante para oferecer o melhor programa!",
            "information": "Tenho informações completas sobre nossos programas. O que gostaria de saber?",
            "scheduling": "Vamos agendar sua visita! Quando seria melhor para você?",
            "confirmation": "Perfeito! Confirmo seu agendamento. Até breve!",
            "handoff": "Vou transferir você para nossa equipe especializada. Aguarde um momento."
        }
        
        return fallback_messages.get(
            target_node,
            "Obrigada pelo seu contato! Nossa equipe retornará em breve."
        )
    
    def _get_fallback_channel_and_message(
        self,
        state: CeciliaState,
        routing_decision: RoutingDecision,
        delivery_result: Dict[str, Any],
        original_channel: str
    ) -> tuple[str, str]:
        """Get fallback channel and message based on original channel and failure reason"""
        failure_reason = safe_get_delivery_field(delivery_result, "reason", "unknown")
        
        # Channel fallback strategy
        fallback_channel_map = {
            "web": "whatsapp",      # Web fallback to WhatsApp (most reliable)
            "app": "whatsapp",      # App fallback to WhatsApp (most reliable)
            "whatsapp": "whatsapp"  # WhatsApp fallback to itself (retry)
        }
        
        fallback_channel = fallback_channel_map.get(original_channel, "whatsapp")
        
        # Get base fallback message
        base_message = self._get_fallback_message(state, routing_decision)
        
        # Add channel-specific context if needed
        if original_channel != fallback_channel:
            if original_channel in ["web", "app"]:
                # Inform user about channel switch
                channel_message = (
                    f"⚠️ Houve um problema na comunicação via {original_channel}. "
                    f"Continuando via WhatsApp.\n\n{base_message}"
                )
                logger.info(f"📱 Fallback: {original_channel} → {fallback_channel}")
                return fallback_channel, channel_message
        
        # Same channel retry - just use base message
        logger.info(f"🔄 Retry on same channel: {fallback_channel}")
        return fallback_channel, base_message
    
    def get_stats(self) -> Dict[str, Any]:
        """Get delivery statistics"""
        total = self.delivery_stats["total_deliveries"]
        
        if total == 0:
            return {**self.delivery_stats, "success_rate": 0.0, "failure_rate": 0.0}
        
        return {
            **self.delivery_stats,
            "success_rate": self.delivery_stats["successful_deliveries"] / total,
            "failure_rate": self.delivery_stats["failed_deliveries"] / total,
            "fallback_rate": self.delivery_stats["fallback_activations"] / total
        }


# Global service instance
delivery_service = DeliveryService()