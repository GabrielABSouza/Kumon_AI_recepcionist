# app/core/router/delivery_io.py
"""
Delivery IO-Only Node - Atomic Message Delivery

Responsibilities:
- Drain state[OUTBOX_KEY] 
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
from ...workflows.contracts import MessageEnvelope, ensure_outbox, normalize_outbox_messages, OUTBOX_KEY
from ..contracts.outbox import OutboxItem, rehydrate_outbox_if_needed
from .instance_resolver import resolve_instance, inject_instance_to_state

logger = logging.getLogger(__name__)


def _msg_id(msg: Dict[str, Any]) -> str:
    """Generate unique message ID for deduplication"""
    text = msg.get("text", "")
    channel = msg.get("channel", "")
    meta_str = str(msg.get("meta", {}))
    base = f'{text}|{channel}|{meta_str}'
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _resolve_whatsapp_instance(msg: Dict[str, Any], state: Dict[str, Any]) -> str:
    """
    Resolve WhatsApp instance using new canonical resolver
    
    Uses instance_resolver.resolve_instance() which:
    - Validates against VALID_INSTANCES set
    - Rejects invalid patterns (thread_*, default)
    - Falls back to kumon_assistant
    
    Args:
        msg: Message dictionary with potential instance in meta
        state: Conversation state with potential channel config
        
    Returns:
        str: Valid instance name (never raises)
    """
    # Use new canonical resolver
    return resolve_instance(state, msg)


async def emit_to_channel(msg: Dict[str, Any], state: Dict[str, Any]) -> bool:
    """
    Emit message to appropriate channel with proper async/await
    
    Args:
        msg: Message dictionary to emit
        state: State containing phone_number and other context
        
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
            # Use existing Evolution API integration with proper await
            phone_number = state.get("phone_number")
            if not phone_number:
                logger.error("Missing phone_number in state for WhatsApp delivery")
                return False
            
            # Resolve instance using proper hierarchy with observability and guards
            try:
                instance_name = _resolve_whatsapp_instance(msg, state)
                
                # Critical guard: Instance pattern validation
                from ..observability.handoff_guards import guard_instance_pattern
                guard_instance_pattern(instance_name, state)
                
            except (ValueError, Exception) as e:
                logger.error(f"WhatsApp delivery failed: {e}")
                return False
            
            # Structured logging - DELIVERY_TRACE send action
            from ..observability.structured_logging import log_delivery_trace_send, log_delivery_trace_result
            log_delivery_trace_send(instance_name, phone_number, state)
            
            result = await send_message(
                phone_number=phone_number,
                message=text,
                instance_name=instance_name
            )
            
            # Check if result indicates success and log structured result
            success = bool(result and result.get("status") != "error")
            http_code = result.get("http_status") if result else None
            status = "success" if success else "failed"
            
            log_delivery_trace_result(status, http_code, instance_name, state)
            
            if success:
                logger.info(f"WhatsApp message sent successfully to {phone_number}: {text[:50]}...")
            else:
                logger.error(f"WhatsApp message failed: {result}")
            return success
            
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


async def delivery_node(state: dict, *, max_batch: int = 10) -> dict:
    """
    Delivery Node - IO-only operations with idempotency
    
    Responsibilities:
    1. Drain state[OUTBOX_KEY] with batch limit
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
    
    # Ensure outbox exists and add structured PRE-DELIVERY telemetry
    ensure_outbox(state)
    
    # CRITICAL: Rehydrate outbox if needed (fixes planner→delivery bridge issue)
    rehydrate_outbox_if_needed(state)
    
    # Structured logging - OUTBOX_TRACE delivery phase  
    from ..observability.structured_logging import log_outbox_trace
    from ..observability.handoff_guards import guard_state_reference_integrity
    
    log_outbox_trace("delivery", state)
    
    # Critical guard: State reference integrity
    guard_state_reference_integrity(state, "pre_delivery")
    
    delivery_outbox_count_before = len(state[OUTBOX_KEY])
    
    logger.info(f"PRE-DELIVERY – Outbox contains {delivery_outbox_count_before} message(s)")
    logger.info(f"delivery_outbox_count_before: {delivery_outbox_count_before}")
    
    if delivery_outbox_count_before > 0:
        first_item = state[OUTBOX_KEY][0]
        logger.info(f"delivery_first_item_type: {type(first_item).__name__}")
        if isinstance(first_item, dict):
            logger.info(f"delivery_first_item_keys: {list(first_item.keys())}")
    else:
        # Track emergency fallback count (1x per session limit)
        emergency_count = state.get("_emergency_fallback_count", 0)
        if emergency_count < 1:
            logger.warning("PRE-DELIVERY – EMPTY OUTBOX detected, adding emergency fallback")
            # Emergency fallback
            envelope = MessageEnvelope(
                text="Olá! Como posso ajudar?",
                channel="whatsapp",
                meta={"source": "delivery_emergency_fallback"}
            )
            state[OUTBOX_KEY].append(envelope.to_dict())
            state["_emergency_fallback_count"] = emergency_count + 1
            delivery_outbox_count_before = 1
            logger.info(f"delivery_emergency_fallback_added: 1 (count: {emergency_count + 1})")
        else:
            logger.error("PRE-DELIVERY – EMPTY OUTBOX detected but emergency fallback limit reached")
            # Force termination to prevent infinite loops
            state["should_end"] = True  
            state["stop_reason"] = "empty_outbox_fallback_limit_exceeded"
            return state
    
    # Convert outbox to MessageEnvelope objects using unified normalization
    try:
        envelopes = normalize_outbox_messages(state[OUTBOX_KEY])
    except Exception as e:
        logger.error(f"Outbox normalization failed: {e}")
        envelopes = []
    
    # Clear outbox (will be repopulated with failed messages)
    state[OUTBOX_KEY] = []
    
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
                state[OUTBOX_KEY].extend([env.to_dict() for env in remaining_envelopes])
                break
            
            # Idempotency check
            if envelope.idempotency_key in seen:
                logger.debug(f"Message already emitted, skipping: {envelope.idempotency_key}")
                idempotency_dedup_hits += 1
                processed += 1
                continue
            
            # Attempt emission with proper await
            msg_dict = envelope.to_dict()
            success = await emit_to_channel(msg_dict, state)
            
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
        state[OUTBOX_KEY].extend([env.to_dict() for env in remaining_envelopes])
        
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
    state[OUTBOX_KEY].extend([env.to_dict() for env in failed])
    
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
    
    # Final telemetry with guard-rails integration
    delivery_sent_count = len(emitted)
    delivery_queued_count = len(state[OUTBOX_KEY])
    
    logger.info(f"delivery_sent_count: {delivery_sent_count}")
    logger.info(f"delivery_queued_count: {delivery_queued_count}")
    logger.info(f"idempotency_dedup_hits: {idempotency_dedup_hits}")
    
    logger.info(f"Delivery completed: {delivery_sent_count} messages sent, {delivery_queued_count} queued")
    
    # Guard-rails integration - track delivery metrics
    from ..observability.metrics_guard_rails import log_outbox_handoff
    
    log_outbox_handoff(
        planner_count_before=0,  # Will be provided by planner
        planner_count_after=delivery_outbox_count_before,
        delivery_count_before=delivery_outbox_count_before,
        delivery_sent=delivery_sent_count,
        delivery_failed=len(failed),
        phone_number=state.get("phone_number", "unknown"),
        instance=state.get("instance", "unknown")
    )
    
    # Enhanced anti-loop fail-safe with emergency session tracking
    emergency_fallbacks = state.get("_emergency_fallback_count", 0)
    max_emergency_fallbacks = 1  # 1x per session as per specification
    
    # Stop condition 1: No messages delivered and outbox empty
    if delivery_sent_count == 0 and delivery_queued_count == 0:
        logger.warning("No messages delivered and outbox empty - marking conversation for termination to prevent loops")
        state["should_end"] = True
        state["stop_reason"] = "no_delivery_content"
    
    # Stop condition 2: Emergency fallback limit exceeded  
    elif emergency_fallbacks >= max_emergency_fallbacks and delivery_sent_count == 0:
        logger.warning(f"Emergency fallback limit exceeded ({emergency_fallbacks}/{max_emergency_fallbacks}) - terminating session")
        state["should_end"] = True
        state["stop_reason"] = "emergency_fallback_limit_exceeded"
    
    # Stop condition 3: Conversation marked as completed or handoff
    elif state.get("current_stage") in ["completed", "handoff"]:
        logger.info(f"Conversation stage '{state.get('current_stage')}' reached - natural termination")
        state["should_end"] = True
        state["stop_reason"] = f"stage_{state.get('current_stage')}_reached"
    
    return state


# REMOVED: smart_router_node moved to dedicated routing_and_planning.py
# This file is now IO-ONLY as per V2 architecture