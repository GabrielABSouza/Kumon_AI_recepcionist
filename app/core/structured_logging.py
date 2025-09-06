"""
Structured Logging - Standardized log format for operational monitoring
Provides consistent, parsable log entries for debugging and monitoring
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def log_pipeline_event(event: str, **fields):
    """
    Log pipeline events with structured format (generic, kwargs-only)
    
    Args:
        event: Event name (e.g., "preprocess_start", "classify_complete")
        **fields: Event data as keyword arguments only
    
    Usage:
        log_pipeline_event("preprocess_start", phone="1234", message_id="abc")
        log_pipeline_event("classify_complete", phone="1234", intent="info", confidence=0.85)
    """
    parts = [f"event={event}"]
    for k, v in fields.items():
        if v is not None:
            parts.append(f"{k}={v}")
    
    log_message = "|".join(parts)
    
    if "error" in event or "failed" in event:
        logger.error(f"PIPELINE|{log_message}")
    elif "start" in event or "complete" in event:
        logger.info(f"PIPELINE|{log_message}")
    else:
        logger.info(f"PIPELINE|{log_message}")


def log_turn_event(event_type: str, conversation_id: str, phone: str, **kwargs):
    """
    Log turn-level events with structured format (legacy compatibility)
    
    Args:
        event_type: Type of turn event (acquired, duplicate, released, etc.)
        conversation_id: Conversation identifier
        phone: Phone number (last 4 digits for privacy)
        **kwargs: Additional event data
    """
    phone_suffix = phone[-4:] if len(phone) >= 4 else phone
    
    log_data = {
        "event": "TURN",
        "type": event_type,
        "conversation_id": conversation_id,
        "phone": phone_suffix,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }
    
    # Format for structured parsing
    log_message = "|".join([f"{k}={v}" for k, v in log_data.items()])
    
    if event_type in ["duplicate", "blocked"]:
        logger.info(f"TURN|{log_message}")
    elif event_type in ["error", "failed"]:
        logger.error(f"TURN|{log_message}")
    else:
        logger.info(f"TURN|{log_message}")


def log_outbox_event(event_type: str, conversation_id: str, count: int = None, **kwargs):
    """
    Log outbox persistence and delivery events
    
    Args:
        event_type: Type of outbox event (persisted, rehydrate_hit, rehydrate_miss, etc.)
        conversation_id: Conversation identifier
        count: Number of messages involved
        **kwargs: Additional event data
    """
    log_data = {
        "event": "OUTBOX",
        "type": event_type,
        "conversation_id": conversation_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if count is not None:
        log_data["count"] = count
    
    log_data.update(kwargs)
    
    # Format for structured parsing
    log_message = "|".join([f"{k}={v}" for k, v in log_data.items()])
    
    if event_type in ["rehydrate_miss", "error"]:
        logger.warning(f"OUTBOX|{log_message}")
    else:
        logger.info(f"OUTBOX|{log_message}")


def log_delivery_event(event_type: str, conversation_id: str, idempotency_key: str, **kwargs):
    """
    Log message delivery events
    
    Args:
        event_type: Type of delivery event (sent, failed, dedup_hit, etc.)
        conversation_id: Conversation identifier  
        idempotency_key: Message idempotency key
        **kwargs: Additional event data
    """
    log_data = {
        "event": "DELIVERY",
        "type": event_type,
        "conversation_id": conversation_id,
        "idempotency_key": idempotency_key,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }
    
    # Format for structured parsing
    log_message = "|".join([f"{k}={v}" for k, v in log_data.items()])
    
    if event_type in ["failed", "error"]:
        logger.error(f"DELIVERY|{log_message}")
    elif event_type == "dedup_hit":
        logger.info(f"DELIVERY|{log_message}")
    else:
        logger.info(f"DELIVERY|{log_message}")


def log_webhook_event(event_type: str, phone: str, message_id: str, **kwargs):
    """
    Log webhook processing events
    
    Args:
        event_type: Type of webhook event (received, duplicate, echo_filtered, etc.)
        phone: Phone number (last 4 digits for privacy)
        message_id: Message ID from webhook
        **kwargs: Additional event data
    """
    phone_suffix = phone[-4:] if len(phone) >= 4 else phone
    
    log_data = {
        "event": "WEBHOOK",
        "type": event_type,
        "phone": phone_suffix,
        "message_id": message_id,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }
    
    # Format for structured parsing  
    log_message = "|".join([f"{k}={v}" for k, v in log_data.items()])
    
    if event_type in ["duplicate", "echo_filtered"]:
        logger.info(f"WEBHOOK|{log_message}")
    elif event_type == "error":
        logger.error(f"WEBHOOK|{log_message}")
    else:
        logger.info(f"WEBHOOK|{log_message}")


def log_workflow_event(event_type: str, conversation_id: str, stage: str, **kwargs):
    """
    Log workflow progression events
    
    Args:
        event_type: Type of workflow event (stage_entered, recursion_check, etc.)
        conversation_id: Conversation identifier
        stage: Current workflow stage
        **kwargs: Additional event data
    """
    log_data = {
        "event": "WORKFLOW",
        "type": event_type,
        "conversation_id": conversation_id,
        "stage": stage,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }
    
    # Format for structured parsing
    log_message = "|".join([f"{k}={v}" for k, v in log_data.items()])
    
    if event_type in ["recursion_limit_exceeded", "greeting_loop_prevented"]:
        logger.error(f"WORKFLOW|{log_message}")
    else:
        logger.info(f"WORKFLOW|{log_message}")


def log_dedup_event(event_type: str, key: str, phone: str = None, **kwargs):
    """
    Log deduplication events
    
    Args:
        event_type: Type of dedup event (new_message, duplicate, etc.)
        key: Deduplication key
        phone: Phone number (optional)
        **kwargs: Additional event data
    """
    log_data = {
        "event": "DEDUP",
        "type": event_type,
        "key": key,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }
    
    if phone:
        phone_suffix = phone[-4:] if len(phone) >= 4 else phone
        log_data["phone"] = phone_suffix
    
    # Format for structured parsing
    log_message = "|".join([f"{k}={v}" for k, v in log_data.items()])
    logger.info(f"DEDUP|{log_message}")


def log_fallback_event(event_type: str, conversation_id: str, reason: str, **kwargs):
    """
    Log fallback message events
    
    Args:
        event_type: Type of fallback event (triggered, generated, etc.)
        conversation_id: Conversation identifier
        reason: Reason for fallback
        **kwargs: Additional event data
    """
    log_data = {
        "event": "FALLBACK",
        "type": event_type,
        "conversation_id": conversation_id,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }
    
    # Format for structured parsing
    log_message = "|".join([f"{k}={v}" for k, v in log_data.items()])
    logger.warning(f"FALLBACK|{log_message}")


def create_log_summary(events: list) -> Dict[str, Any]:
    """
    Create summary of structured log events for debugging
    
    Args:
        events: List of event dictionaries
        
    Returns:
        Dict with event summary statistics
    """
    summary = {
        "total_events": len(events),
        "event_types": {},
        "conversations": set(),
        "phones": set(),
        "first_event": None,
        "last_event": None
    }
    
    for event in events:
        event_type = event.get("event")
        if event_type:
            summary["event_types"][event_type] = summary["event_types"].get(event_type, 0) + 1
        
        if event.get("conversation_id"):
            summary["conversations"].add(event["conversation_id"])
        
        if event.get("phone"):
            summary["phones"].add(event["phone"])
        
        if not summary["first_event"]:
            summary["first_event"] = event.get("timestamp")
        summary["last_event"] = event.get("timestamp")
    
    # Convert sets to counts for JSON serialization
    summary["unique_conversations"] = len(summary["conversations"])
    summary["unique_phones"] = len(summary["phones"])
    del summary["conversations"]
    del summary["phones"]
    
    return summary