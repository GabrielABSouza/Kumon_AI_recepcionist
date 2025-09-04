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
from ...workflows.contracts import MessageEnvelope, ensure_outbox, normalize_outbox_messages

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
    
    # Ensure outbox exists and add PRE-DELIVERY telemetry
    ensure_outbox(state)
    delivery_outbox_count_before = len(state["outbox"])
    
    logger.info(f"PRE-DELIVERY – Outbox contains {delivery_outbox_count_before} message(s)")
    logger.info(f"delivery_outbox_count_before: {delivery_outbox_count_before}")
    
    if delivery_outbox_count_before > 0:
        first_item = state["outbox"][0]
        logger.info(f"delivery_first_item_type: {type(first_item).__name__}")
        if isinstance(first_item, dict):
            logger.info(f"delivery_first_item_keys: {list(first_item.keys())}")
    else:
        logger.warning("PRE-DELIVERY – EMPTY OUTBOX detected")
        # Emergency fallback
        envelope = MessageEnvelope(
            text="Olá! Como posso ajudar?",
            channel="whatsapp",
            meta={"source": "delivery_emergency_fallback"}
        )
        state["outbox"].append(envelope.to_dict())
        delivery_outbox_count_before = 1
        logger.info(f"delivery_emergency_fallback_added: 1")
    
    # Convert outbox to MessageEnvelope objects using unified normalization
    try:
        envelopes = normalize_outbox_messages(state["outbox"])
    except Exception as e:
        logger.error(f"Outbox normalization failed: {e}")
        envelopes = []
    
    # Clear outbox (will be repopulated with failed messages)
    state["outbox"] = []
    
    # Initialize tracking
    emitted = []
    failed = []
    seen = set(state.get("_emitted_ids", []))
    idempotency_dedup_hits = 0
    
    try:
        processed = 0
        for envelope in envelopes:
            if processed >= max_batch:
                # Re-queue unprocessed messages
                remaining_envelopes = envelopes[processed:]
                state["outbox"].extend([env.to_dict() for env in remaining_envelopes])
                break
            
            # Idempotency check
            if envelope.idempotency_key in seen:
                logger.debug(f"Message already emitted, skipping: {envelope.idempotency_key}")
                idempotency_dedup_hits += 1
                processed += 1
                continue
            
            # Attempt emission
            msg_dict = envelope.to_dict()
            success = emit_to_channel(msg_dict)
            
            if success:
                seen.add(envelope.idempotency_key)
                emitted.append(envelope)
                logger.info(f"Message delivered successfully: {envelope.idempotency_key}")
            else:
                failed.append(envelope)
                logger.warning(f"Message delivery failed: {envelope.idempotency_key}")
            
            processed += 1
            
    except Exception as e:
        logger.error(f"Delivery batch processing failed: {e}")
        
        # Re-queue all unprocessed messages
        remaining_envelopes = envelopes[processed:]
        state["outbox"].extend([env.to_dict() for env in remaining_envelopes])
        
        # Set degraded status
        state["_delivery_status"] = {
            "status": "degraded",
            "error_type": type(e).__name__,
            "error_message": str(e)
        }
        
        logger.info(f"delivery_sent_count: 0")
        logger.info(f"delivery_failed_count: {len(remaining_envelopes)}")
        logger.info(f"idempotency_dedup_hits: {idempotency_dedup_hits}")
        
        return state
    
    # Re-queue failed messages
    state["outbox"].extend([env.to_dict() for env in failed])
    
    # Update state atomically
    if emitted:
        # Set last_bot_response to most recent message
        state["last_bot_response"] = emitted[-1].text
        
        # Store successful emission stats
        state["_delivery_status"] = {
            "status": "ok",
            "messages_emitted": len(emitted),
            "messages_failed": len(failed),
            "batch_size": processed,
            "deduplication_hits": idempotency_dedup_hits
        }
    else:
        state["_delivery_status"] = {
            "status": "no_messages",
            "messages_failed": len(failed),
            "deduplication_hits": idempotency_dedup_hits
        }
    
    # Persist emitted message IDs for deduplication
    state["_emitted_ids"] = list(seen)
    
    # Final telemetry
    delivery_sent_count = len(emitted)
    delivery_queued_count = len(state["outbox"])
    
    logger.info(f"delivery_sent_count: {delivery_sent_count}")
    logger.info(f"delivery_queued_count: {delivery_queued_count}")
    logger.info(f"idempotency_dedup_hits: {idempotency_dedup_hits}")
    
    logger.info(f"Delivery completed: {delivery_sent_count} messages sent, {delivery_queued_count} queued")
    
    # Anti-loop fail-safe: If no messages were sent and outbox is empty, mark for termination
    if delivery_sent_count == 0 and delivery_queued_count == 0:
        logger.warning("No messages delivered and outbox empty - marking conversation for termination to prevent loops")
        state["should_end"] = True
        state["stop_reason"] = "no_delivery_content"
    
    return state


# REMOVED: smart_router_node moved to dedicated routing_and_planning.py
# This file is now IO-ONLY as per V2 architecture