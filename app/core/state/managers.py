"""
StateManager - Optimized State Management for CeciliaState

Migrado para usar a estrutura otimizada do state_solving.md:
- Trabalha com 12 campos core obrigatórios
- Gerencia subsistemas de forma eficiente
- Mantém funcionalidades de circuit breaker e recovery
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
import uuid
import logging

from .models import (
    CeciliaState, 
    create_initial_cecilia_state,
    ConversationStage,
    ConversationStep,
    get_collected_field,
    set_collected_field,
    increment_metric,
    add_decision_to_trail,
    add_validation_failure,
    add_error_to_recovery,
    set_error_recovery_field,
    increment_recovery_attempts
)

logger = logging.getLogger(__name__)


class StateManager:
    """
    Optimized state management system for CeciliaState
    
    Mantém funcionalidades de circuit breaker e recovery mas com
    estrutura muito mais simples e performática
    """
    
    @staticmethod
    def create_initial_state(phone_number: str, user_message: str = "") -> CeciliaState:
        """
        Create initial CeciliaState using optimized structure
        
        Args:
            phone_number: User's phone number
            user_message: Initial message from user
            
        Returns:
            CeciliaState: Fully initialized state ready for workflow
        """
        logger.info(f"Created initial CeciliaState for {phone_number}")
        return create_initial_cecilia_state(phone_number, user_message)
    
    @staticmethod
    def update_state(state: CeciliaState, updates: Dict[str, Any]) -> CeciliaState:
        """
        Update state with new data, handling subsystem routing
        
        Args:
            state: Current state
            updates: Dictionary of updates to apply
            
        Returns:
            CeciliaState: Updated state
        """
        # Update timestamp
        state["conversation_metrics"]["message_count"] += 1
        
        # Apply direct updates to core fields
        core_fields = {
            "current_stage", "current_step", "last_user_message", 
            "phone_number", "conversation_id"
        }
        
        for key, value in updates.items():
            if key in core_fields:
                state[key] = value
            
            # Route collected data updates
            elif key in ["parent_name", "child_name", "is_for_self", "student_age", 
                        "education_level", "programs_of_interest", "date_preferences",
                        "available_slots", "selected_slot", "contact_email"]:
                set_collected_field(state, key, value)
            
            # Route validation updates  
            elif key in ["extraction_attempts", "pending_confirmations", "last_extraction_error"]:
                state["data_validation"][key] = value
            
            # Route metrics updates
            elif key in ["failed_attempts", "consecutive_confusion", "same_question_count", 
                        "last_delivery", "last_activity", "delivery_success"]:
                state["conversation_metrics"][key] = value
            
            # Route error recovery updates
            elif key in ["critical_delivery_failure", "critical_error", "requires_manual_intervention",
                        "delivery_failed", "delivery_fallback_used", "last_delivery_error", 
                        "emergency_response_sent", "validation_failed", "validation_error",
                        "validation_failed_count", "recovery_attempts", "last_recovery_attempt",
                        "recovery_strategy"]:
                set_error_recovery_field(state, key, value)
                
                # Add to error history for critical errors
                if key in ["critical_delivery_failure", "critical_error", "requires_manual_intervention"] and value:
                    add_error_to_recovery(state, {
                        "type": "critical_error",
                        "key": key,
                        "value": value,
                        "stage": state.get("current_stage"),
                        "step": state.get("current_step")
                    })
            
            # Log unrecognized updates (reduced to debug level for legitimate error keys)
            else:
                logger.debug(f"Unrecognized update key (routed to error history): {key}")
                # Route unknown keys to error history instead of ignoring
                add_error_to_recovery(state, {
                    "type": "unknown_update_key",
                    "key": key,
                    "value": str(value)
                })
        
        # Add decision to trail for auditability
        if "current_stage" in updates or "current_step" in updates:
            add_decision_to_trail(state, {
                "type": "state_update",
                "updates": updates,
                "new_stage": state["current_stage"],
                "new_step": state["current_step"]
            })
        
        return state
    
    @staticmethod
    def check_circuit_breaker(state: CeciliaState) -> Dict[str, Any]:
        """
        Simplified circuit breaker logic using metrics subsystem
        
        Args:
            state: Current conversation state
            
        Returns:
            Dict with circuit breaker evaluation
        """
        metrics = state["conversation_metrics"]
        
        # Simple circuit breaker conditions
        should_activate = any([
            metrics["failed_attempts"] >= 5,
            metrics["consecutive_confusion"] >= 3,
            metrics["same_question_count"] >= 4,
            metrics["message_count"] > 15
        ])
        
        if should_activate:
            logger.warning(f"Circuit breaker activated for {state['phone_number']}")
            add_decision_to_trail(state, {
                "type": "circuit_breaker_activation",
                "reason": "failure_thresholds_exceeded",
                "metrics": metrics
            })
        
        # Determine recommended action if circuit breaker should activate
        recommended_action = None
        if should_activate:
            # Determine action based on current state and failure patterns
            if metrics["failed_attempts"] >= 5 or metrics["message_count"] > 15:
                recommended_action = "handoff"
            elif metrics["consecutive_confusion"] >= 3:
                recommended_action = "information_bypass"
            elif metrics["same_question_count"] >= 4:
                recommended_action = "emergency_scheduling"
            else:
                recommended_action = "handoff"  # Default safe action

        return {
            "should_activate": should_activate,
            "reason": "failure_thresholds_exceeded" if should_activate else "within_limits",
            "recommended_action": recommended_action,
            "metrics": metrics
        }
    
    @staticmethod
    def apply_circuit_breaker_action(state: CeciliaState, action: str) -> Dict[str, Any]:
        """
        Apply circuit breaker recovery action
        
        Args:
            state: Current state
            action: Action to apply
            
        Returns:
            Dict of updates to apply
        """
        logger.info(f"Applying circuit breaker action: {action}")
        
        # Reset failure metrics
        updates = {
            "failed_attempts": 0,
            "consecutive_confusion": 0,
            "same_question_count": 0
        }
        
        # Apply specific actions
        if action == "handoff":
            updates.update({
                "current_stage": ConversationStage.COMPLETED,
                "current_step": ConversationStep.CONVERSATION_ENDED
            })
        elif action == "emergency_scheduling":
            updates.update({
                "current_stage": ConversationStage.SCHEDULING,
                "current_step": ConversationStep.DATE_PREFERENCE
            })
        elif action == "information_bypass":
            updates.update({
                "current_stage": ConversationStage.INFORMATION_GATHERING,
                "current_step": ConversationStep.METHODOLOGY_EXPLANATION
            })
        
        add_decision_to_trail(state, {
            "type": "circuit_breaker_action",
            "action": action,
            "updates": updates
        })
        
        return updates
    
    @staticmethod
    def get_collected_data_summary(state: CeciliaState) -> Dict[str, Any]:
        """
        Get summary of collected data for debugging
        
        Args:
            state: Current state
            
        Returns:
            Dict with collected data summary
        """
        collected = state["collected_data"]
        required_fields = ["parent_name", "student_age", "contact_email"]
        
        return {
            "total_collected": len(collected),
            "required_collected": sum(1 for field in required_fields if field in collected),
            "completion_percentage": (len(collected) / 10) * 100,  # Assuming 10 total possible fields
            "collected_fields": list(collected.keys()),
            "missing_required": [field for field in required_fields if field not in collected]
        }
    
    @staticmethod
    def record_validation_attempt(state: CeciliaState, field: str, success: bool, error: str = None) -> None:
        """
        Record validation attempt in data_validation subsystem
        
        Args:
            state: Current state
            field: Field being validated
            success: Whether validation succeeded
            error: Error message if failed
        """
        validation = state["data_validation"]
        
        # Increment attempt count
        current_attempts = validation["extraction_attempts"].get(field, 0)
        validation["extraction_attempts"][field] = current_attempts + 1
        
        # Record in history
        validation["validation_history"].append({
            "field": field,
            "success": success,
            "attempt_number": current_attempts + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error
        })
        
        # Update error if failed
        if not success and error:
            validation["last_extraction_error"] = error
            add_validation_failure(state, {
                "field": field,
                "error": error,
                "attempt": current_attempts + 1
            })
        
        # Keep history manageable
        if len(validation["validation_history"]) > 20:
            validation["validation_history"] = validation["validation_history"][-20:]
    
    @staticmethod
    def is_field_collected(state: CeciliaState, field_name: str) -> bool:
        """
        Check if a field has been collected
        
        Args:
            state: Current state
            field_name: Name of field to check
            
        Returns:
            bool: True if field is collected
        """
        return field_name in state["collected_data"]
    
    @staticmethod
    def get_conversation_duration(state: CeciliaState) -> float:
        """
        Get conversation duration in seconds
        
        Args:
            state: Current state
            
        Returns:
            float: Duration in seconds
        """
        created_at = state["conversation_metrics"]["created_at"]
        now = datetime.now(timezone.utc)
        
        if isinstance(created_at, datetime):
            return (now - created_at).total_seconds()
        else:
            return 0.0
    
    @staticmethod
    def should_suggest_handoff(state: CeciliaState) -> bool:
        """
        Determine if should suggest human handoff based on metrics
        
        Args:
            state: Current state
            
        Returns:
            bool: True if should suggest handoff
        """
        metrics = state["conversation_metrics"]
        
        return any([
            metrics["failed_attempts"] >= 3,
            metrics["consecutive_confusion"] >= 2,
            len(metrics["problematic_fields"]) >= 3,
            StateManager.get_conversation_duration(state) > 600  # 10 minutes
        ])