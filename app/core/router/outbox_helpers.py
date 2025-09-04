# app/core/router/outbox_helpers.py
"""
Outbox Helpers - Unified Message Enqueueing for V2 Architecture

Provides consistent interface between routing_and_planning and delivery_io:
- Single message envelope format
- Validation and normalization 
- Deduplication support
- Sanity logging
"""

import logging
from typing import Dict, Any, List
from ...workflows.contracts import MessageEnvelope, ensure_outbox

logger = logging.getLogger(__name__)


def enqueue_message(state: Dict[str, Any], text: str, channel: str = "whatsapp", meta: Dict[str, Any] = None, source: str = "unknown") -> bool:
    """
    Unified message enqueueing with validation and deduplication
    
    Args:
        state: Conversation state
        text: Message text content
        channel: Delivery channel (whatsapp, web, app)
        meta: Additional metadata
        source: Source component (for debugging)
        
    Returns:
        bool: True if message was enqueued, False if skipped/invalid
    """
    
    if not text or not text.strip():
        logger.warning("Attempted to enqueue empty message, skipping")
        return False
    
    # Ensure outbox exists using unified helper
    ensure_outbox(state)
    
    # Create message envelope with source tracking
    envelope_meta = meta or {}
    envelope_meta["source"] = source
    
    try:
        envelope = MessageEnvelope(
            text=text.strip(),
            channel=channel,
            meta=envelope_meta
        )
        
        # Convert to dict for consistent storage format
        envelope_dict = envelope.to_dict()
        
        # Deduplication check (optional - can be disabled for performance)
        existing_texts = [msg.get("text", "") for msg in state["outbox"]]
        if text.strip() in existing_texts:
            logger.debug(f"Message already in outbox, skipping: {text[:50]}...")
            return False
        
        # Enqueue message
        state["outbox"].append(envelope_dict)
        
        logger.debug(f"Message enqueued to outbox: {text[:50]}... (channel: {channel}, source: {source})")
        return True
        
    except ValueError as e:
        logger.warning(f"Invalid message envelope, skipping: {e}")
        return False


def enqueue_fallback_message(state: Dict[str, Any], reason: str = "unknown_error") -> bool:
    """
    Enqueue emergency fallback message to prevent empty outbox loops
    
    Args:
        state: Conversation state
        reason: Reason for fallback (for debugging)
        
    Returns:
        bool: True if fallback was enqueued
    """
    
    fallback_text = "Desculpe, tivemos um problema técnico. Como posso ajudar?"
    
    success = enqueue_message(
        state=state,
        text=fallback_text,
        channel="whatsapp",
        meta={
            "fallback": True,
            "reason": reason,
            "source": "emergency_fallback"
        }
    )
    
    if success:
        logger.warning(f"Emergency fallback message enqueued: {reason}")
    
    return success


def log_outbox_sanity_check(state: Dict[str, Any], operation: str = "pre-delivery") -> None:
    """
    Log outbox state for debugging and sanity checking
    
    Args:
        state: Conversation state
        operation: Which operation is calling this (pre-delivery, post-planning, etc.)
    """
    
    outbox = state.get("outbox", [])
    
    logger.info(f"[SANITY] {operation.upper()} - Outbox contains {len(outbox)} message(s)")
    
    if len(outbox) == 0:
        logger.warning(f"[SANITY] {operation.upper()} - EMPTY OUTBOX detected")
        return
    
    # Log details of first few messages
    for i, msg in enumerate(outbox[:3]):  # Show first 3 messages max
        msg_text = msg.get("text", "NO_TEXT")
        msg_channel = msg.get("channel", "NO_CHANNEL")
        msg_meta = msg.get("meta", {})
        
        logger.info(f"[SANITY] {operation.upper()} - Message {i+1}: "
                   f"text='{msg_text[:30]}...', channel={msg_channel}, "
                   f"meta_keys={list(msg_meta.keys())}")
    
    if len(outbox) > 3:
        logger.info(f"[SANITY] {operation.upper()} - ... and {len(outbox) - 3} more messages")


def normalize_outbox_format(state: Dict[str, Any]) -> int:
    """
    Normalize outbox messages to consistent dict format
    
    Handles mixed formats from different sources:
    - MessageEnvelope objects → dict
    - Already dict → validate fields
    - Invalid entries → remove
    
    Args:
        state: Conversation state
        
    Returns:
        int: Number of messages normalized/removed
    """
    
    if "outbox" not in state:
        state["outbox"] = []
        return 0
    
    original_count = len(state["outbox"])
    normalized_outbox = []
    
    for msg in state["outbox"]:
        try:
            # If it's already a dict, validate required fields
            if isinstance(msg, dict):
                if "text" in msg and msg["text"]:
                    # Ensure standard fields exist with idempotency_key
                    normalized_msg = {
                        "text": str(msg["text"]).strip(),
                        "channel": msg.get("channel", "whatsapp"),
                        "meta": msg.get("meta", {}),
                        "idempotency_key": msg.get("idempotency_key", "")
                    }
                    # Generate idempotency_key if missing
                    if not normalized_msg["idempotency_key"]:
                        import hashlib
                        base = f'{normalized_msg["text"]}|{normalized_msg["channel"]}|{str(normalized_msg["meta"])}'
                        normalized_msg["idempotency_key"] = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
                    
                    normalized_outbox.append(normalized_msg)
                else:
                    logger.warning("Removing invalid message from outbox: missing text")
            
            # If it's a MessageEnvelope object, convert to dict
            elif hasattr(msg, 'text'):
                try:
                    if hasattr(msg, 'to_dict'):
                        normalized_msg = msg.to_dict()
                    else:
                        # Fallback for older MessageEnvelope objects
                        from dataclasses import asdict
                        normalized_msg = asdict(msg)
                    
                    if normalized_msg["text"]:
                        normalized_outbox.append(normalized_msg)
                    else:
                        logger.warning("Removing empty MessageEnvelope from outbox")
                except Exception as e:
                    logger.warning(f"Error converting MessageEnvelope to dict: {e}")
            
            else:
                logger.warning(f"Removing unknown message type from outbox: {type(msg)}")
                
        except Exception as e:
            logger.warning(f"Error normalizing outbox message, removing: {e}")
    
    state["outbox"] = normalized_outbox
    removed_count = original_count - len(normalized_outbox)
    
    if removed_count > 0:
        logger.info(f"Normalized outbox: {original_count} → {len(normalized_outbox)} messages "
                   f"({removed_count} removed)")
    
    return removed_count