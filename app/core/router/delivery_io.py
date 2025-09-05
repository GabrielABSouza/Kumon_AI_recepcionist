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
from .instance_resolver import resolve_instance
from ..outbox_store import load_outbox, mark_sent, mark_failed
from ..dedup_store import seen_idem, mark_idem, ensure_fallback_key

logger = logging.getLogger(__name__)


async def delivery_node_turn_based(state: dict) -> dict:
    """
    NEW FUNCTION: Turn-based delivery with DB rehydration + idempotency
    
    Arquitetura mínima: TurnController → Planner → Delivery
    - Rehydrata do DB se state.outbox vazio (fonte de verdade durável)
    - Envia exatamente 1 item por turno (idempotente)
    - Fallback também idempotente por turn_id
    - Marca como enviado no DB + Redis dedup
    
    Args:
        state: Conversation state with turn_id, phone_number, conversation_id
        
    Returns:
        dict: Updated state with delivery status
    """
    
    # Extract turn-based data
    turn_id = state.get("turn_id")
    phone_number = state.get("phone_number", "unknown")
    conversation_id = state.get("conversation_id", f"conv_{phone_number}")
    
    if not turn_id:
        logger.error(f"DELIVERY|missing_turn_id|phone={phone_number[-4:]}")
        state["turn_status"] = "error"
        return state
    
    logger.info(
        f"DELIVERY|turn_based_start|phone={phone_number[-4:]}|turn={turn_id}"
    )
    
    # Step 1: Try to get items from memory first (fast path)
    items = state.get(OUTBOX_KEY, [])
    
    # Step 2: Rehydrate from snapshot if memory is empty
    if not items:
        snapshot = state.get("_planner_snapshot_outbox", [])
        items = snapshot or []
        if items:
            logger.info(f"DELIVERY|rehydrate=snapshot|count={len(items)}|turn={turn_id}")
    
    # Step 3: **ESSENCIAL** Rehydrate from DB if still empty (durável)
    if not items:
        db_connection = state.get("db")
        if db_connection:
            items = load_outbox(db_connection, conversation_id, turn_id)
            if items:
                logger.info(f"DELIVERY|rehydrate=db|count={len(items)}|turn={turn_id}")
            else:
                logger.debug(f"DELIVERY|no_db_items|turn={turn_id}")
        else:
            logger.warning(f"DELIVERY|no_db_connection|turn={turn_id}")
    
    # Step 4: Generate fallback if still empty - BUT idempotente por turn_id
    if not items:
        logger.warning(f"DELIVERY|empty_outbox_fallback|turn={turn_id}")
        
        fallback_key = ensure_fallback_key(phone_number, turn_id)
        fallback_item = {
            "text": "Olá! Como posso ajudar?",
            "channel": "whatsapp",
            "meta": {"source": "delivery_fallback"},
            "idempotency_key": fallback_key
        }
        items = [fallback_item]
    
    # Step 5: Process exactly 1 item (primeiro da lista)
    if not items:
        logger.error(f"DELIVERY|no_items_available|turn={turn_id}")
        state["turn_status"] = "no_content"
        return state
    
    item = items[0]  # 1 resposta por turno
    item_text = item.get("text", "")
    item_channel = item.get("channel", "whatsapp") 
    idem_key = item.get("idempotency_key", "")
    
    if not item_text:
        logger.warning(f"DELIVERY|empty_text|turn={turn_id}|generating_fallback")
        item_text = "Obrigada pelo contato!"
        idem_key = ensure_fallback_key(phone_number, turn_id)
    
    if not idem_key:
        logger.warning(f"DELIVERY|missing_idem_key|turn={turn_id}|generating")
        idem_key = ensure_fallback_key(phone_number, turn_id) 
    
    # Step 6: Check idempotency (dedup)
    cache = state.get("cache")  # Redis connection
    if cache and seen_idem(cache, conversation_id, idem_key):
        logger.info(
            f"DELIVERY|dedup_hit|turn={turn_id}|idem={idem_key}|skipping"
        )
        state["turn_status"] = "already_delivered"
        state["delivery_dedup_hit"] = True
        return state
    
    # Step 7: Send message (1 vez por turn_id)
    try:
        if item_channel == "whatsapp":
            instance_name = resolve_instance(state)
            
            provider_result = await send_message(
                phone_number=phone_number,
                message=item_text,
                instance_name=instance_name
            )
            
            success = provider_result and provider_result.get("status") != "error"
            provider_id = provider_result.get("message_id") if success else None
            
            if success:
                logger.info(
                    f"DELIVERY|sent|turn={turn_id}|idem={idem_key}|"
                    f"provider_id={provider_id}|text_len={len(item_text)}"
                )
                
                # Step 8: Mark as sent in DB + Redis dedup
                db_connection = state.get("db")
                if db_connection:
                    mark_sent(db_connection, conversation_id, turn_id, 0, provider_id)
                
                if cache:
                    mark_idem(cache, conversation_id, idem_key)
                
                # Update state
                state["last_delivery_id"] = provider_id
                state["last_bot_response"] = item_text
                state["turn_status"] = "delivered"
                
                return state
                
            else:
                logger.error(
                    f"DELIVERY|send_failed|turn={turn_id}|idem={idem_key}|"
                    f"result={provider_result}"
                )
                
                # Mark as failed in DB for retry
                db_connection = state.get("db") 
                if db_connection:
                    error_reason = str(provider_result) if provider_result else "send_failed"
                    mark_failed(db_connection, conversation_id, turn_id, 0, error_reason)
                
                state["turn_status"] = "send_failed"
                return state
        
        else:
            # Other channels (web, app) - placeholder
            logger.info(f"DELIVERY|channel={item_channel}|turn={turn_id}|text_len={len(item_text)}")
            state["turn_status"] = "delivered"
            state["last_bot_response"] = item_text
            return state
            
    except Exception as e:
        logger.error(f"DELIVERY|exception|turn={turn_id}|error={e}")
        
        # Mark as failed 
        db_connection = state.get("db")
        if db_connection:
            mark_failed(db_connection, conversation_id, turn_id, 0, str(e))
        
        state["turn_status"] = "exception"
        state["delivery_error"] = str(e)
        return state


def _msg_id(msg: Dict[str, Any]) -> str:
    """Generate unique message ID for deduplication"""
    text = msg.get("text", "")
    channel = msg.get("channel", "")
    meta_str = str(msg.get("meta", {}))
    base = f'{text}|{channel}|{meta_str}'
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _resolve_whatsapp_instance(msg: Dict[str, Any], state: Dict[str, Any]) -> str:
    """
    Resolve WhatsApp instance using type-safe canonical resolver
    
    Uses instance_resolver.resolve_instance() which:
    - Validates against VALID_INSTANCES set
    - Rejects invalid patterns (thread_*, default)
    - Never returns thread_* patterns
    - Falls back to kumon_assistant
    
    Args:
        msg: Message dictionary with potential instance in meta
        state: Conversation state with potential channel config
        
    Returns:
        str: Valid instance name (never thread_* patterns)
    """
    # Use new type-safe canonical resolver - only needs state parameter now
    return resolve_instance(state)


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
    
    # PERSISTENT OUTBOX: If outbox is empty, try to rehydrate from PostgreSQL
    if delivery_outbox_count_before == 0:
        logger.info("DELIVERY|attempting_outbox_rehydrate")
        delivery_outbox_count_before = _rehydrate_outbox_from_db(state)
        logger.info(f"DELIVERY|post_rehydrate_count: {delivery_outbox_count_before}")
    
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
                
                # PERSISTENT OUTBOX: Mark as sent in database
                _mark_outbox_sent(state, envelope, success_response_id=None)
            else:
                failed.append(envelope)
                logger.warning(f"Message delivery failed: {envelope.idempotency_key}")
                
                # PERSISTENT OUTBOX: Mark as failed in database  
                _mark_outbox_failed(state, envelope, error_reason="delivery_failed")
            
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


def _rehydrate_outbox_from_db(state: dict) -> int:
    """
    Rehydrate outbox from PostgreSQL when memory state is lost
    
    Args:
        state: LangGraph state to populate with messages
        
    Returns:
        int: Number of messages loaded from database
    """
    from ..outbox_repository import get_pending_outbox
    
    # Get conversation ID
    conversation_id = state.get("session_id") or state.get("conversation_id")
    if not conversation_id:
        logger.warning("DELIVERY_REHYDRATE|no_conversation_id|skipping_rehydrate")
        return 0
    
    try:
        # Load pending messages from database
        pending_messages = get_pending_outbox(conversation_id)
        
        if not pending_messages:
            logger.debug(f"DELIVERY_REHYDRATE|no_pending|conv={conversation_id}")
            return 0
        
        # Convert database messages to outbox format
        rehydrated_count = 0
        for msg_data in pending_messages:
            try:
                payload = msg_data['payload']
                
                # Ensure message has required fields
                if 'text' not in payload:
                    logger.warning(f"DELIVERY_REHYDRATE|missing_text|conv={conversation_id}|id={msg_data['id']}")
                    continue
                
                # Add database metadata for tracking
                payload['_db_id'] = msg_data['id']
                payload['_rehydrated'] = True
                
                # Add to outbox
                state[OUTBOX_KEY].append(payload)
                rehydrated_count += 1
                
                logger.debug(f"DELIVERY_REHYDRATE|loaded|conv={conversation_id}|id={msg_data['id']}")
                
            except Exception as e:
                logger.error(f"DELIVERY_REHYDRATE|message_error|conv={conversation_id}|id={msg_data.get('id')}|error={e}")
                continue
        
        logger.info(f"DELIVERY_REHYDRATE|success|conv={conversation_id}|count={rehydrated_count}")
        return rehydrated_count
        
    except Exception as e:
        logger.error(f"DELIVERY_REHYDRATE|failed|conv={conversation_id}|error={e}")
        return 0


def _mark_outbox_sent(state: dict, envelope, success_response_id: str = None) -> None:
    """
    Mark outbox message as sent in PostgreSQL database
    
    Args:
        state: LangGraph state
        envelope: MessageEnvelope that was sent
        success_response_id: Response ID from Evolution API
    """
    from ..outbox_repository import mark_sent
    
    # Get database ID from envelope if it was rehydrated
    envelope_dict = envelope.to_dict() if hasattr(envelope, 'to_dict') else envelope
    db_id = envelope_dict.get('_db_id')
    
    if not db_id:
        logger.debug(f"DELIVERY_MARK_SENT|no_db_id|idem={envelope.idempotency_key}|skipping")
        return
    
    try:
        success = mark_sent(db_id, success_response_id)
        if success:
            logger.info(f"DELIVERY_MARK_SENT|success|db_id={db_id}|idem={envelope.idempotency_key}")
        else:
            logger.warning(f"DELIVERY_MARK_SENT|failed|db_id={db_id}|idem={envelope.idempotency_key}")
            
    except Exception as e:
        logger.error(f"DELIVERY_MARK_SENT|error|db_id={db_id}|idem={envelope.idempotency_key}|error={e}")


def _mark_outbox_failed(state: dict, envelope, error_reason: str) -> None:
    """
    Mark outbox message as failed in PostgreSQL database
    
    Args:
        state: LangGraph state
        envelope: MessageEnvelope that failed
        error_reason: Reason for failure
    """
    from ..outbox_repository import mark_failed
    
    # Get database ID from envelope if it was rehydrated
    envelope_dict = envelope.to_dict() if hasattr(envelope, 'to_dict') else envelope
    db_id = envelope_dict.get('_db_id')
    
    if not db_id:
        logger.debug(f"DELIVERY_MARK_FAILED|no_db_id|idem={envelope.idempotency_key}|skipping")
        return
    
    try:
        success = mark_failed(db_id, error_reason)
        if success:
            logger.warning(f"DELIVERY_MARK_FAILED|success|db_id={db_id}|idem={envelope.idempotency_key}|reason={error_reason}")
        else:
            logger.error(f"DELIVERY_MARK_FAILED|failed|db_id={db_id}|idem={envelope.idempotency_key}")
            
    except Exception as e:
        logger.error(f"DELIVERY_MARK_FAILED|error|db_id={db_id}|idem={envelope.idempotency_key}|error={e}")