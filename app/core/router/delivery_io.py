# app/core/router/delivery_io.py
"""
Delivery IO-Only Node - Atomic Message Delivery

Responsibilities:
- Drain state["outbox"] 
- Emit messages via existing channels (Evolution API)
- Update last_bot_response atomically
- Idempotent operations with deduplication
- NO business logic or decision making
"""

from collections import deque
import hashlib
import logging
from typing import Dict, Any
from ...api.evolution import send_message
from ...workflows.contracts import MessageEnvelope

logger = logging.getLogger(__name__)


def _msg_id(msg: Dict[str, Any]) -> str:
    """Generate unique message ID for deduplication"""
    text = msg.get("text", "")
    channel = msg.get("channel", "")
    meta_str = str(msg.get("meta", {}))
    base = f'{text}|{channel}|{meta_str}'
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def emit_to_channel(msg: Dict[str, Any]) -> bool:
    """
    Emit message to appropriate channel
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        channel = msg.get("channel", "whatsapp")
        text = msg.get("text", "")
        
        if not text:
            logger.warning("Empty message text, skipping emission")
            return False
            
        if channel == "whatsapp":
            # Use existing Evolution API integration
            # This is a simplified version - adapt to existing send_message signature
            result = send_message(
                phone_number="default",  # Will be resolved by existing logic
                message=text,
                instance_name="default"
            )
            return bool(result)
            
        elif channel in ["web", "app"]:
            # Placeholder for web/app delivery logic
            # In production, integrate with existing WebSocket/HTTP endpoints
            logger.info(f"[{channel.upper()}] Message emitted: {text[:50]}...")
            return True
            
        else:
            logger.warning(f"Unsupported channel: {channel}")
            return False
            
    except Exception as e:
        logger.error(f"Channel emission failed: {e}")
        return False


def delivery_node(state: dict, *, max_batch: int = 10) -> dict:
    """
    Delivery Node - IO-only operations with idempotency
    
    Responsibilities:
    1. Drain state["outbox"] with batch limit
    2. Emit messages via channels 
    3. Update last_bot_response atomically
    4. Handle failures gracefully
    5. Maintain idempotency with deduplication
    
    Args:
        state: Conversation state
        max_batch: Maximum messages per batch (prevent runaway)
        
    Returns:
        dict: Updated state with drained outbox
    """
    
    # Initialize outbox and tracking
    q = deque(state.get("outbox", []))
    state["outbox"] = []
    
    emitted = []
    seen = set(state.get("_emitted_ids", []))
    
    try:
        processed = 0
        while q and processed < max_batch:
            msg = q.popleft()
            
            # Deduplication check
            mid = _msg_id(msg)
            if mid in seen:
                logger.debug(f"Message already emitted, skipping: {mid}")
                processed += 1
                continue
            
            # Attempt emission
            success = emit_to_channel(msg)
            
            if success:
                seen.add(mid)
                emitted.append(msg)
                logger.info(f"Message delivered successfully: {mid}")
            else:
                # Re-queue failed message for retry
                state["outbox"].append(msg)
                logger.warning(f"Message delivery failed, re-queued: {mid}")
            
            processed += 1
            
    except Exception as e:
        logger.error(f"Delivery batch processing failed: {e}")
        
        # Re-queue all remaining messages
        state["outbox"] = list(q) + state["outbox"]
        
        # Set degraded status
        state["_delivery_status"] = {
            "status": "degraded",
            "error_type": type(e).__name__,
            "error_message": str(e)
        }
        
        return state
    
    # Update state atomically
    if emitted:
        # Set last_bot_response to most recent message
        state["last_bot_response"] = emitted[-1]["text"]
        
        # Store successful emission stats
        state["_delivery_status"] = {
            "status": "ok",
            "messages_emitted": len(emitted),
            "batch_size": processed
        }
    
    # Persist emitted message IDs for deduplication
    state["_emitted_ids"] = list(seen)
    
    logger.info(f"Delivery completed: {len(emitted)} messages sent, {len(state['outbox'])} queued")
    
    return state


def smart_router_node(state: dict) -> dict:
    """
    SmartRouter Node - Decision-only operations
    
    Responsibilities:
    - Analyze state and user input
    - Write routing_decision ONLY
    - NO message generation or outbox manipulation
    """
    
    from .smart_router_adapter import smart_router_adapter
    
    try:
        # Use existing SmartRouter infrastructure 
        decision = smart_router_adapter.make_decision(state)
        
        # Store decision in state
        state["routing_decision"] = {
            "target_node": decision.target_node,
            "threshold_action": decision.threshold_action,
            "final_confidence": decision.confidence,
            "intent_confidence": decision.intent_confidence,
            "pattern_confidence": decision.pattern_confidence,
            "rule_applied": decision.rule_applied,
            "reasoning": decision.reasoning,
            "mandatory_data_override": decision.mandatory_data_override
        }
        
        logger.info(f"SmartRouter decision: {decision.target_node} ({decision.threshold_action})")
        
        return state
        
    except Exception as e:
        logger.error(f"SmartRouter failed: {e}")
        
        # Fallback decision
        state["routing_decision"] = {
            "target_node": "fallback",
            "threshold_action": "fallback_level2", 
            "final_confidence": 0.3,
            "rule_applied": "error_fallback",
            "reasoning": f"SmartRouter error: {str(e)}"
        }
        
        return state