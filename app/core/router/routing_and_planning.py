# app/core/router/routing_and_planning.py
"""
Routing and Planning Node - Decision + Action Planning

This node sits between StageResolver and Delivery in the V2 architecture:
StageResolver → routing_and_planning → delivery_io

Responsibilities:
1. Make routing decisions via SmartRouterAdapter
2. Generate response plans via ResponsePlanner  
3. Enqueue messages to state.outbox
4. NO IO operations (that's delivery_io's job)
"""

import logging
from typing import Dict, Any
from .outbox_helpers import enqueue_message, enqueue_fallback_message, log_outbox_sanity_check
from ...workflows.contracts import OUTBOX_KEY

logger = logging.getLogger(__name__)


def routing_and_planning_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Combined routing decision + response planning node
    
    Flow:
    1. SmartRouter analyzes state → routing_decision
    2. ResponsePlanner generates response → intent_result + outbox
    3. Pass to delivery_io for actual message sending
    
    Args:
        state: Conversation state with user input
        
    Returns:
        dict: State with routing_decision, intent_result, and populated outbox
    """
    
    try:
        # Step 1: Make routing decision
        routing_decision = _make_routing_decision(state)
        state["routing_decision"] = routing_decision
        
        logger.info(f"[DECISION] SmartRouter decision: {routing_decision.get('target_node')} "
                   f"({routing_decision.get('threshold_action')})")
        
        # Step 2: Generate response plan
        intent_result = _generate_response_plan(state, routing_decision)
        state["intent_result"] = intent_result
        
        # Step 3: Enqueue messages for delivery
        messages_enqueued = _enqueue_messages(state, intent_result)
        
        logger.info(f"[ACTION] ResponsePlanner enqueued {messages_enqueued} message(s) to outbox")
        
        # Detailed sanity logging
        logger.info(f"[SANITY] routing_decision.target_node: {routing_decision.get('target_node')}")
        logger.info(f"[SANITY] routing_decision.threshold_action: {routing_decision.get('threshold_action')}")
        
        # POST-PLANNING telemetry
        outbox_count = len(state.get(OUTBOX_KEY, []))
        logger.info(f"POST-PLANNING – Outbox contains {outbox_count} message(s)")
        
        # Bridge telemetry for graph handoff tracking
        logger.info(f"graph_bridge_outbox_count: {outbox_count}")
        
        if outbox_count == 0:
            logger.error("[SANITY] CRITICAL: Outbox is empty after planning - this will cause loops!")
            # Emergency fallback using unified helpers
            from ...workflows.contracts import MessageEnvelope
            envelope = MessageEnvelope(
                text="Olá! Como posso ajudar?",
                channel="whatsapp",
                meta={"source": "routing_planning_emergency"}
            )
            state[OUTBOX_KEY] = [envelope.to_dict()]
            logger.info(f"graph_bridge_outbox_count: 1 (emergency)")
        else:
            first_msg = state[OUTBOX_KEY][0]
            logger.info(f"[SANITY] First message type: {type(first_msg)}, keys: {list(first_msg.keys()) if isinstance(first_msg, dict) else 'N/A'}")
        
        return state
        
    except Exception as e:
        logger.error(f"Routing and planning failed: {e}")
        
        # Emergency fallback: create minimal response
        state["routing_decision"] = {
            "target_node": "fallback",
            "threshold_action": "fallback_level2",
            "final_confidence": 0.3,
            "rule_applied": "emergency_fallback",
            "reasoning": f"Routing/planning error: {str(e)}"
        }
        
        # Enqueue fallback message using helper
        enqueue_fallback_message(state, f"routing_planning_error: {str(e)}")
        
        # Mark for termination to prevent loops
        state["stop_reason"] = "planner_error"
        
        logger.warning("Emergency fallback activated - 1 message enqueued")
        
        return state


def _make_routing_decision(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use SmartRouterAdapter to make routing decision
    
    Returns:
        dict: routing_decision with target_node, confidence, etc.
    """
    
    from .smart_router_adapter import smart_router_adapter
    
    try:
        # Use existing decide_route method from SmartRouterAdapter
        decision = smart_router_adapter.decide_route(state)
        
        return {
            "target_node": decision.target_node,
            "threshold_action": decision.threshold_action,
            "final_confidence": decision.confidence,
            "intent_confidence": decision.intent_confidence,
            "pattern_confidence": decision.pattern_confidence,
            "rule_applied": decision.rule_applied,
            "reasoning": decision.reasoning,
            "mandatory_data_override": decision.mandatory_data_override
        }
    except Exception as e:
        logger.error(f"SmartRouter decision failed: {e}")
        raise


def _generate_response_plan(state: Dict[str, Any], routing_decision: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use ResponsePlanner to generate response based on routing decision
    
    Returns:
        dict: intent_result with delivery_payload
    """
    
    from ..router.response_planner import plan_response
    
    try:
        # Generate response plan using canonical API
        intent_result = plan_response(
            state=state,
            routing_decision=routing_decision
        )
        
        logger.info(f"[PLANNER] strategy={intent_result.get('routing_mode', 'unknown')} → intent_result persisted")
        
        return intent_result
        
    except Exception as e:
        logger.error(f"ResponsePlanner failed: {e}")
        
        # Create minimal fallback intent_result
        return {
            "delivery_payload": {
                "messages": [{
                    "text": "Desculpe, houve um erro no planejamento da resposta. Como posso ajudar?",
                    "type": "text"
                }]
            },
            "error": str(e),
            "fallback": True
        }


def _enqueue_messages(state: Dict[str, Any], intent_result: Dict[str, Any]) -> int:
    """
    Extract messages from intent_result and enqueue to state.outbox using helpers
    
    Returns:
        int: Number of messages enqueued
    """
    
    messages_added = 0
    
    try:
        # Extract messages from delivery_payload
        delivery_payload = intent_result.get("delivery_payload", {})
        messages = delivery_payload.get("messages", [])
        
        for msg in messages:
            # Use unified helper for enqueueing
            success = enqueue_message(
                state=state,
                text=msg.get("text", ""),
                channel=msg.get("channel", "whatsapp"),
                meta={
                    "type": msg.get("type", "text"),
                    "routing_decision": state.get("routing_decision", {}).get("target_node", "unknown")
                },
                source="response_planner"
            )
            
            if success:
                messages_added += 1
        
        return messages_added
        
    except Exception as e:
        logger.error(f"Message enqueuing failed: {e}")
        return 0


def _convert_decision_format(decision) -> Dict[str, Any]:
    """
    Convert various decision formats to standardized format
    
    Args:
        decision: Decision object from SmartRouter
        
    Returns:
        dict: Standardized routing_decision format
    """
    
    # Handle different decision object formats
    if hasattr(decision, '__dict__'):
        decision_dict = decision.__dict__
    else:
        decision_dict = decision
    
    return {
        "target_node": decision_dict.get("target_node", "fallback"),
        "threshold_action": decision_dict.get("threshold_action", "fallback_level1"),
        "final_confidence": decision_dict.get("confidence", 0.5),
        "intent_confidence": decision_dict.get("intent_confidence", 0.0),
        "pattern_confidence": decision_dict.get("pattern_confidence", 0.0),
        "rule_applied": decision_dict.get("rule_applied", "unknown"),
        "reasoning": decision_dict.get("reasoning", "No reasoning provided"),
        "mandatory_data_override": decision_dict.get("mandatory_data_override", False)
    }