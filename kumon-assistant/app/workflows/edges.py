"""
LangGraph Conditional Edges for Kumon Assistant Workflow

This module defines the conditional logic that determines workflow transitions
between different nodes based on conversation state and context.

Phase 4 Enhancement: Integrated with Smart Router for intelligent routing decisions.
"""

from typing import Literal, Dict, Any
import re
import asyncio

from ..core.logger import app_logger
from .states import ConversationState, WorkflowStage, ConversationStep
from .smart_router import smart_router


# Type aliases for edge returns
GreetingNext = Literal["information", "fallback", "greeting"]
InformationNext = Literal["scheduling", "information", "fallback", "greeting"] 
SchedulingNext = Literal["completed", "fallback", "scheduling"]
FallbackNext = Literal["greeting", "information", "scheduling", "human_handoff", "completed"]


async def smart_route_conversation(state: ConversationState) -> str:
    """
    Phase 4: Smart routing with intelligent threshold system and advanced classification
    
    This function integrates the intelligent threshold system with smart routing
    for sophisticated decision-making based on confidence thresholds and context.
    
    Args:
        state: Current conversation state
        
    Returns:
        str: Next node to route to
    """
    try:
        app_logger.info(f"Smart routing for {state['phone_number']}")
        
        # Step 1: Get intent classification with confidence scoring
        from ..core.dependencies import intent_classifier
        intent_result = await intent_classifier.classify_intent(
            state["user_message"], state
        )
        
        # Step 2: Process through intelligent threshold system
        from .intelligent_threshold_system import intelligent_threshold_system
        threshold_result = await intelligent_threshold_system.process_intent_with_thresholds(
            intent_result, state
        )
        
        app_logger.info(f"Threshold system result: action={threshold_result.action}, "
                       f"confidence={threshold_result.final_confidence:.3f}, "
                       f"target={threshold_result.target_node}")
        
        # Step 3: Handle threshold system actions
        if threshold_result.action == "proceed":
            # High confidence - proceed with intent routing
            target_node = threshold_result.target_node
            
        elif threshold_result.action == "enhance_with_llm":
            # Medium confidence - use LLM-enhanced classification
            target_node = threshold_result.target_node
            
        elif threshold_result.action in ["fallback_level1", "fallback_level2"]:
            # Low confidence - intelligent fallback
            target_node = "fallback"
            
        elif threshold_result.action == "escalate_human":
            # Very low confidence - human handoff
            target_node = "human_handoff"
            
        else:
            # Fallback to smart router for edge cases
            app_logger.warning(f"Unknown threshold action: {threshold_result.action}")
            routing_decision = await smart_router.make_routing_decision(state)
            target_node = routing_decision.target_node
        
        # Update state with routing information for debugging/analytics
        state["routing_info"] = {
            "target_node": target_node,
            "confidence": threshold_result.final_confidence,
            "original_confidence": intent_result.confidence,
            "threshold_action": threshold_result.action,
            "reasoning": threshold_result.reasoning,
            "penalty_applied": threshold_result.penalty_applied,
            "timestamp": "2024-08-11T19:55:00"  # Would be datetime.now().isoformat()
        }
        
        app_logger.info(f"Final routing decision: {target_node} "
                       f"(confidence: {threshold_result.final_confidence:.3f})")
        
        return target_node
        
    except Exception as e:
        app_logger.error(f"Error in smart routing: {e}")
        # Fallback to basic routing
        return route_from_greeting(state)


def route_from_greeting(state: ConversationState) -> GreetingNext:
    """
    Determine next node after greeting stage
    
    Args:
        state: Current conversation state
        
    Returns:
        Next node to route to based on greeting completion
    """
    try:
        user_context = state["user_context"]
        step = state["step"]
        user_message = state["user_message"].lower()
        
        # Check if user wants to skip straight to scheduling
        if any(phrase in user_message for phrase in [
            "agendar", "visita", "apresentação", "appointment", "schedule"
        ]):
            app_logger.info(f"User {state['phone_number']} requesting direct scheduling")
            return "scheduling"
        
        # Check if we have enough greeting info to proceed
        if (user_context.parent_name and 
            user_context.interest_type and 
            step == ConversationStep.IDENTIFY_INTEREST):
            app_logger.info(f"Greeting complete for {state['phone_number']}, moving to information")
            return "information"
        
        # Check for confusion or unclear responses
        if state["metrics"].consecutive_confusion >= 1:
            app_logger.warning(f"Confusion detected in greeting for {state['phone_number']}")
            return "fallback"
        
        # Stay in greeting if more info needed
        app_logger.info(f"Continuing greeting for {state['phone_number']}")
        return "greeting"
        
    except Exception as e:
        app_logger.error(f"Error in route_from_greeting: {e}")
        return "fallback"


def route_from_information(state: ConversationState) -> InformationNext:
    """
    Determine next node after information stage
    
    Args:
        state: Current conversation state
        
    Returns:
        Next node to route to based on information requests
    """
    try:
        user_message = state["user_message"].lower()
        user_context = state["user_context"]
        
        # Direct scheduling request
        if any(phrase in user_message for phrase in [
            "agendar", "visita", "apresentação", "appointment", 
            "schedule", "marcar", "quando posso", "horário"
        ]):
            app_logger.info(f"User {state['phone_number']} requesting scheduling from information")
            return "scheduling"
        
        # More greeting info needed (like name)
        if not user_context.parent_name and any(phrase in user_message for phrase in [
            "meu nome", "me chamo", "sou", "nome é"
        ]):
            app_logger.info(f"User {state['phone_number']} providing name, back to greeting")
            return "greeting"
        
        # Check for specific information requests
        if any(phrase in user_message for phrase in [
            "matemática", "português", "preço", "valor", "programa", 
            "metodologia", "como funciona", "math", "port"
        ]):
            app_logger.info(f"User {state['phone_number']} requesting more information")
            return "information"
        
        # Check for confusion indicators
        if (state["metrics"].consecutive_confusion >= 1 or
            any(phrase in user_message for phrase in [
                "não entendi", "confuso", "what", "huh", "?"
            ])):
            app_logger.warning(f"Confusion detected in information for {state['phone_number']}")
            return "fallback"
        
        # Default: continue providing information
        return "information"
        
    except Exception as e:
        app_logger.error(f"Error in route_from_information: {e}")
        return "fallback"


def route_from_scheduling(state: ConversationState) -> SchedulingNext:
    """
    Determine next node after scheduling stage
    
    Args:
        state: Current conversation state
        
    Returns:
        Next node to route to based on scheduling progress
    """
    try:
        step = state["step"]
        user_context = state["user_context"]
        
        # Check if booking is complete
        if (step == ConversationStep.CONFIRM_BOOKING and 
            user_context.booking_id):
            app_logger.info(f"Booking completed for {state['phone_number']}")
            return "completed"
        
        # Check for weekend requests (handled in scheduling_node but route back)
        user_message = state["user_message"].lower()
        if any(day in user_message for day in ["sábado", "domingo", "saturday", "sunday"]):
            app_logger.info(f"Weekend request from {state['phone_number']}, staying in scheduling")
            return "scheduling"
        
        # Check for confusion or inability to schedule
        if (state["metrics"].failed_attempts >= 2 or
            state["retry_count"] >= 3):
            app_logger.warning(f"Multiple scheduling failures for {state['phone_number']}")
            return "fallback"
        
        # Continue scheduling process
        return "scheduling"
        
    except Exception as e:
        app_logger.error(f"Error in route_from_scheduling: {e}")
        return "fallback"


def route_from_fallback(state: ConversationState) -> FallbackNext:
    """
    Determine next node after fallback handling
    
    Args:
        state: Current conversation state
        
    Returns:
        Next node to route to or completion based on fallback resolution
    """
    try:
        metrics = state["metrics"]
        user_message = state["user_message"].lower()
        
        # Check if human handoff is required
        if (state["requires_human"] or
            metrics.consecutive_confusion >= 3 or
            metrics.clarification_attempts >= 2 or
            any(phrase in user_message for phrase in [
                "falar com pessoa", "atendente", "human", "representative"
            ])):
            app_logger.warning(f"Human handoff required for {state['phone_number']}")
            return "human_handoff"
        
        # User provided clarification - route based on content
        if metrics.clarification_attempts == 1:
            # Analyze clarified message to determine intent
            if any(phrase in user_message for phrase in [
                "agendar", "visita", "horário", "schedule"
            ]):
                app_logger.info(f"Clarified scheduling intent for {state['phone_number']}")
                return "scheduling"
            elif any(phrase in user_message for phrase in [
                "informação", "programa", "preço", "matemática", "português"
            ]):
                app_logger.info(f"Clarified information intent for {state['phone_number']}")
                return "information"
            elif any(phrase in user_message for phrase in [
                "nome", "me chamo", "sou"
            ]):
                app_logger.info(f"Clarified greeting intent for {state['phone_number']}")
                return "greeting"
        
        # If we can't resolve, end conversation
        if metrics.clarification_attempts >= 2:
            app_logger.info(f"Maximum clarification attempts reached for {state['phone_number']}")
            return "completed"
        
        # Default: try one more clarification
        return "fallback"
        
    except Exception as e:
        app_logger.error(f"Error in route_from_fallback: {e}")
        return "completed"


def should_end_conversation(state: ConversationState) -> bool:
    """
    Determine if conversation should end based on state conditions
    
    Args:
        state: Current conversation state
        
    Returns:
        True if conversation should end, False otherwise
    """
    try:
        # Explicit end conditions
        if (state["conversation_ended"] or 
            state["requires_human"] or
            state["stage"] == WorkflowStage.COMPLETED):
            return True
        
        # Timeout conditions
        metrics = state["metrics"]
        if (metrics.message_count > 20 or  # Too many messages
            metrics.failed_attempts >= 3 or  # Too many failures
            metrics.consecutive_confusion >= 3):  # Too much confusion
            app_logger.warning(f"Ending conversation for {state['phone_number']} due to limits")
            return True
        
        return False
        
    except Exception as e:
        app_logger.error(f"Error in should_end_conversation: {e}")
        return True  # Safe default


def classify_user_intent(user_message: str) -> Dict[str, float]:
    """
    Classify user intent with confidence scores
    
    Args:
        user_message: User's input message
        
    Returns:
        Dictionary of intent classifications with confidence scores
    """
    user_message = user_message.lower().strip()
    intents = {
        "greeting": 0.0,
        "information": 0.0,
        "scheduling": 0.0,
        "clarification": 0.0,
        "human_request": 0.0
    }
    
    try:
        # Greeting patterns
        greeting_patterns = [
            r"\b(oi|olá|hello|hi|bom dia|boa tarde)\b",
            r"\b(meu nome|me chamo|sou)\b",
            r"\b(primeiro contato|primeira vez)\b"
        ]
        for pattern in greeting_patterns:
            if re.search(pattern, user_message):
                intents["greeting"] += 0.3
        
        # Information patterns
        info_patterns = [
            r"\b(matemática|português|programa|metodologia)\b",
            r"\b(preço|valor|custa|quanto|investimento)\b",
            r"\b(como funciona|o que é|explicar)\b"
        ]
        for pattern in info_patterns:
            if re.search(pattern, user_message):
                intents["information"] += 0.4
        
        # Scheduling patterns
        schedule_patterns = [
            r"\b(agendar|visita|horário|appointment)\b",
            r"\b(quando|disponível|livre)\b",
            r"\b(apresentação|conhecer unidade)\b"
        ]
        for pattern in schedule_patterns:
            if re.search(pattern, user_message):
                intents["scheduling"] += 0.4
        
        # Clarification patterns
        clarification_patterns = [
            r"\b(não entendi|confuso|what|huh)\b",
            r"\b(pode repetir|de novo|again)\b",
            r"\?{2,}"  # Multiple question marks
        ]
        for pattern in clarification_patterns:
            if re.search(pattern, user_message):
                intents["clarification"] += 0.5
        
        # Human request patterns
        human_patterns = [
            r"\b(pessoa|humano|atendente|representante)\b",
            r"\b(falar com|quero falar)\b"
        ]
        for pattern in human_patterns:
            if re.search(pattern, user_message):
                intents["human_request"] += 0.6
        
        return intents
        
    except Exception as e:
        app_logger.error(f"Error in classify_user_intent: {e}")
        return intents