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

logger = logging.getLogger(__name__)


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
        planned_response: str,
        routing_decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deliver response to user with atomic state updates
        
        Args:
            state: Current conversation state
            phone_number: Target phone number
            planned_response: Response to send
            routing_decision: SmartRouter decision with target_node
            
        Returns:
            Dict with delivery result and updated state
        """
        start_time = time.time()
        delivery_id = f"delivery_{int(time.time() * 1000)}"
        
        logger.info(
            f"🚀 Starting delivery {delivery_id} for {phone_number[-4:]}"
        )
        
        try:
            # Pre-delivery validation
            validation_result = self._validate_delivery(state, planned_response, routing_decision)
            if not validation_result["valid"]:
                return await self._handle_validation_failure(
                    state, phone_number, validation_result, delivery_id
                )
            
            # Attempt message delivery
            delivery_result = await self._send_message_safe(
                phone_number, planned_response, delivery_id
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
                
                return {
                    "success": True,
                    "delivery_id": delivery_id,
                    "delivery_time_ms": delivery_time_ms,
                    "updated_state": updated_state,
                    "stage_updated": True,
                    "message_sent": True
                }
            
            else:
                # FAILURE: Apply fallback strategy
                return await self._handle_delivery_failure(
                    state, phone_number, delivery_result, routing_decision, delivery_id
                )
        
        except Exception as e:
            logger.error(f"🚨 Critical delivery error {delivery_id}: {e}", exc_info=True)
            return await self._handle_critical_failure(
                state, phone_number, str(e), routing_decision, delivery_id
            )
    
    def _validate_delivery(
        self,
        state: CeciliaState,
        planned_response: str,
        routing_decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Pre-delivery validation with guardrails"""
        
        # Basic content validation
        if not planned_response or len(planned_response.strip()) == 0:
            return {
                "valid": False,
                "reason": "empty_response",
                "details": "Planned response is empty"
            }
        
        # Length validation
        if len(planned_response) > 4000:  # WhatsApp limit
            return {
                "valid": False,
                "reason": "response_too_long",
                "details": f"Response length: {len(planned_response)} > 4000"
            }
        
        # Placeholder validation
        if "{{" in planned_response or "}}" in planned_response:
            return {
                "valid": False,
                "reason": "unresolved_placeholders",
                "details": "Response contains unresolved template variables"
            }
        
        # Routing decision validation
        if not routing_decision.get("target_node"):
            return {
                "valid": False,
                "reason": "invalid_routing",
                "details": "No target_node in routing decision"
            }
        
        return {"valid": True}
    
    async def _send_message_safe(
        self,
        phone_number: str,
        message: str,
        delivery_id: str
    ) -> Dict[str, Any]:
        """Send message with error handling and retries"""
        
        try:
            # Attempt delivery via Evolution API
            send_result = await send_message(phone_number, message)
            
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
        routing_decision: Dict[str, Any],
        delivery_result: Dict[str, Any],
        delivery_id: str
    ) -> CeciliaState:
        """Apply state updates after successful delivery"""
        
        target_node = routing_decision["target_node"]
        
        # Map target_node to stage updates
        stage_updates = self._get_stage_updates_for_target(target_node, state)
        
        # Add delivery metadata
        delivery_updates = {
            **stage_updates,
            "last_delivery": {
                "delivery_id": delivery_id,
                "timestamp": delivery_result["timestamp"],
                "method": delivery_result["delivery_method"],
                "message_id": delivery_result.get("message_id"),
                "target_node": target_node
            },
            "last_activity": datetime.now(timezone.utc),
            "delivery_success": True
        }
        
        # Apply updates atomically
        updated_state = StateManager.update_state(state, delivery_updates)
        
        logger.info(
            f"📊 Stage updated: {state.get('current_stage')} → {updated_state.get('current_stage')} "
            f"(target: {target_node})"
        )
        
        return updated_state
    
    def _get_stage_updates_for_target(
        self,
        target_node: str,
        current_state: CeciliaState
    ) -> Dict[str, Any]:
        """Map target_node to appropriate stage/step updates"""
        
        from ...core.state.models import ConversationStage, ConversationStep
        
        # Define stage mappings
        stage_mapping = {
            "greeting": {
                "current_stage": ConversationStage.GREETING,
                "current_step": ConversationStep.WELCOME
            },
            "qualification": {
                "current_stage": ConversationStage.QUALIFICATION,
                "current_step": ConversationStep.CHILD_AGE_INQUIRY
            },
            "information": {
                "current_stage": ConversationStage.INFORMATION_GATHERING,
                "current_step": ConversationStep.METHODOLOGY_EXPLANATION
            },
            "scheduling": {
                "current_stage": ConversationStage.SCHEDULING,
                "current_step": ConversationStep.DATE_PREFERENCE
            },
            "confirmation": {
                "current_stage": ConversationStage.CONFIRMATION,
                "current_step": ConversationStep.APPOINTMENT_CONFIRMED
            },
            "handoff": {
                "current_stage": ConversationStage.COMPLETED,
                "current_step": ConversationStep.CONVERSATION_ENDED
            }
        }
        
        return stage_mapping.get(target_node, {
            # Default: keep current stage
            "current_stage": current_state.get("current_stage"),
            "current_step": current_state.get("current_step")
        })
    
    async def _handle_delivery_failure(
        self,
        state: CeciliaState,
        phone_number: str,
        delivery_result: Dict[str, Any],
        routing_decision: Dict[str, Any],
        delivery_id: str
    ) -> Dict[str, Any]:
        """Handle delivery failure with fallback strategies"""
        
        logger.warning(f"⚠️ Delivery {delivery_id} failed: {delivery_result.get('error')}")
        
        # Update failure stats
        self.delivery_stats["failed_deliveries"] += 1
        self.delivery_stats["total_deliveries"] += 1
        
        # Apply fallback strategy
        if delivery_result.get("retry_possible", False):
            # Attempt simple retry with fallback message
            fallback_message = self._get_fallback_message(state, routing_decision)
            
            retry_result = await self._send_message_safe(
                phone_number, fallback_message, f"{delivery_id}_retry"
            )
            
            if retry_result["success"]:
                logger.info(f"✅ Fallback delivery successful for {delivery_id}")
                self.delivery_stats["fallback_activations"] += 1
                
                # Apply updates with fallback flag
                updated_state = await self._apply_successful_delivery_updates(
                    state, routing_decision, retry_result, delivery_id
                )
                updated_state["delivery_fallback_used"] = True
                
                return {
                    "success": True,
                    "delivery_id": delivery_id,
                    "fallback_used": True,
                    "updated_state": updated_state,
                    "stage_updated": True,
                    "message_sent": True
                }
        
        # Critical failure - do not update stage
        logger.error(f"🚨 Critical delivery failure {delivery_id} - stage NOT updated")
        
        failure_updates = {
            "delivery_failed": True,
            "last_delivery_error": {
                "delivery_id": delivery_id,
                "error": delivery_result.get("error"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "target_node": routing_decision["target_node"]
            }
        }
        
        updated_state = StateManager.update_state(state, failure_updates)
        
        return {
            "success": False,
            "delivery_id": delivery_id,
            "error": delivery_result.get("error"),
            "updated_state": updated_state,
            "stage_updated": False,  # CRITICAL: Stage not updated on failure
            "message_sent": False
        }
    
    async def _handle_validation_failure(
        self,
        state: CeciliaState,
        phone_number: str,
        validation_result: Dict[str, Any],
        delivery_id: str
    ) -> Dict[str, Any]:
        """Handle pre-delivery validation failure"""
        
        logger.warning(f"⚠️ Validation failed {delivery_id}: {validation_result['reason']}")
        
        # Try to send emergency fallback
        emergency_response = "Desculpe, houve um problema técnico. Nossa equipe entrará em contato em breve."
        
        emergency_result = await self._send_message_safe(
            phone_number, emergency_response, f"{delivery_id}_emergency"
        )
        
        validation_updates = {
            "validation_failed": True,
            "validation_error": validation_result["reason"],
            "emergency_response_sent": emergency_result["success"]
        }
        
        updated_state = StateManager.update_state(state, validation_updates)
        
        return {
            "success": False,
            "delivery_id": delivery_id,
            "error": f"validation_failed: {validation_result['reason']}",
            "updated_state": updated_state,
            "stage_updated": False,
            "message_sent": emergency_result["success"]
        }
    
    async def _handle_critical_failure(
        self,
        state: CeciliaState,
        phone_number: str,
        error: str,
        routing_decision: Dict[str, Any],
        delivery_id: str
    ) -> Dict[str, Any]:
        """Handle critical system failures"""
        
        logger.error(f"🚨 CRITICAL FAILURE {delivery_id}: {error}")
        
        critical_updates = {
            "critical_delivery_failure": True,
            "critical_error": error,
            "requires_manual_intervention": True
        }
        
        updated_state = StateManager.update_state(state, critical_updates)
        
        return {
            "success": False,
            "delivery_id": delivery_id,
            "error": f"critical_failure: {error}",
            "updated_state": updated_state,
            "stage_updated": False,
            "message_sent": False,
            "requires_intervention": True
        }
    
    def _get_fallback_message(
        self,
        state: CeciliaState,
        routing_decision: Dict[str, Any]
    ) -> str:
        """Generate simple fallback message"""
        
        target_node = routing_decision["target_node"]
        
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