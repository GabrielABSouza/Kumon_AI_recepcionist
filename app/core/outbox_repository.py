"""
Persistent Outbox Repository - Solve outbox loss between Planner and Delivery

Implements persistent storage for LangGraph workflow messages to ensure
reliable delivery even when state instances are lost between nodes.

Architecture:
- Planner: persists messages via save_outbox()
- Delivery: loads pending messages via get_pending_outbox()
- Evolution API: marks sent via mark_sent()
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib

from app.database.connection import get_database_connection

logger = logging.getLogger(__name__)


def generate_idempotency_key(conversation_id: str, message_content: str, timestamp: Optional[datetime] = None) -> str:
    """
    Generate deterministic idempotency key for message deduplication
    
    Args:
        conversation_id: Session/conversation identifier
        message_content: Message text content
        timestamp: Optional timestamp (uses current time if None)
        
    Returns:
        str: Deterministic hash-based idempotency key
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    # Create deterministic string combining all factors
    timestamp_str = timestamp.isoformat()[:19]  # Remove microseconds for stability
    raw_string = f"{conversation_id}:{message_content}:{timestamp_str}"
    
    # Generate hash-based key
    hash_key = hashlib.sha256(raw_string.encode()).hexdigest()[:16]
    
    logger.debug(f"Generated idempotency key: {hash_key} for conversation {conversation_id}")
    return hash_key


def save_outbox(conversation_id: str, idempotency_key: str, payload: Dict[str, Any]) -> bool:
    """
    Persist outbox message to PostgreSQL database
    
    Args:
        conversation_id: Session/conversation identifier  
        idempotency_key: Unique key for deduplication
        payload: MessageEnvelope as dict
        
    Returns:
        bool: True if saved successfully, False otherwise
    """
    if not conversation_id or not idempotency_key or not payload:
        logger.error("OUTBOX_REPO|save_outbox|missing_required_params")
        return False
    
    try:
        with get_database_connection() as conn:
            with conn.cursor() as cursor:
                # Insert with ON CONFLICT to handle idempotency
                cursor.execute("""
                    INSERT INTO persistent_outbox (
                        conversation_id, idempotency_key, payload, status
                    ) VALUES (%s, %s, %s::jsonb, 'pending')
                    ON CONFLICT (conversation_id, idempotency_key) 
                    DO UPDATE SET 
                        payload = EXCLUDED.payload,
                        created_at = now()
                """, (
                    conversation_id,
                    idempotency_key, 
                    json.dumps(payload)
                ))
                
                conn.commit()
                
                logger.info(
                    f"OUTBOX_REPO|saved|conv={conversation_id}|idem={idempotency_key}|"
                    f"text_len={len(payload.get('text', ''))}"
                )
                return True
                
    except Exception as e:
        logger.error(f"OUTBOX_REPO|save_failed|conv={conversation_id}|idem={idempotency_key}|error={e}")
        return False


def get_pending_outbox(conversation_id: str) -> List[Dict[str, Any]]:
    """
    Load pending outbox messages from PostgreSQL database
    
    Args:
        conversation_id: Session/conversation identifier
        
    Returns:
        List[Dict]: List of pending messages with metadata
    """
    if not conversation_id:
        logger.error("OUTBOX_REPO|get_pending_outbox|missing_conversation_id")
        return []
    
    try:
        with get_database_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, idempotency_key, payload, created_at
                    FROM persistent_outbox 
                    WHERE conversation_id = %s 
                      AND status = 'pending'
                    ORDER BY created_at ASC
                """, (conversation_id,))
                
                rows = cursor.fetchall()
                
                if not rows:
                    logger.debug(f"OUTBOX_REPO|no_pending|conv={conversation_id}")
                    return []
                
                # Convert rows to list of dicts
                messages = []
                for row in rows:
                    try:
                        payload = row[2]  # payload column (JSONB)
                        if isinstance(payload, str):
                            payload = json.loads(payload)
                        
                        message = {
                            'id': row[0],
                            'idempotency_key': row[1], 
                            'payload': payload,
                            'created_at': row[3]
                        }
                        messages.append(message)
                    except json.JSONDecodeError as e:
                        logger.error(f"OUTBOX_REPO|invalid_json|conv={conversation_id}|id={row[0]}|error={e}")
                        continue
                
                logger.info(f"OUTBOX_REPO|loaded|conv={conversation_id}|count={len(messages)}")
                return messages
                
    except Exception as e:
        logger.error(f"OUTBOX_REPO|load_failed|conv={conversation_id}|error={e}")
        return []


def mark_sent(outbox_id: int, evolution_message_id: Optional[str] = None) -> bool:
    """
    Mark outbox message as successfully sent
    
    Args:
        outbox_id: Database ID of the outbox message
        evolution_message_id: Message ID from Evolution API response
        
    Returns:
        bool: True if marked successfully, False otherwise
    """
    if not outbox_id:
        logger.error("OUTBOX_REPO|mark_sent|missing_outbox_id")
        return False
    
    try:
        with get_database_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE persistent_outbox 
                    SET status = 'sent', 
                        sent_at = now(),
                        evolution_message_id = %s
                    WHERE id = %s AND status = 'pending'
                """, (evolution_message_id, outbox_id))
                
                updated_rows = cursor.rowcount
                conn.commit()
                
                if updated_rows > 0:
                    logger.info(f"OUTBOX_REPO|marked_sent|id={outbox_id}|evolution_id={evolution_message_id}")
                    return True
                else:
                    logger.warning(f"OUTBOX_REPO|mark_sent_no_update|id={outbox_id}")
                    return False
                    
    except Exception as e:
        logger.error(f"OUTBOX_REPO|mark_sent_failed|id={outbox_id}|error={e}")
        return False


def mark_failed(outbox_id: int, error_reason: str) -> bool:
    """
    Mark outbox message as failed to send
    
    Args:
        outbox_id: Database ID of the outbox message
        error_reason: Reason for delivery failure
        
    Returns:
        bool: True if marked successfully, False otherwise
    """
    if not outbox_id:
        logger.error("OUTBOX_REPO|mark_failed|missing_outbox_id") 
        return False
    
    try:
        with get_database_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE persistent_outbox 
                    SET status = 'failed'
                    WHERE id = %s
                """, (outbox_id,))
                
                updated_rows = cursor.rowcount
                conn.commit()
                
                if updated_rows > 0:
                    logger.warning(f"OUTBOX_REPO|marked_failed|id={outbox_id}|reason={error_reason}")
                    return True
                else:
                    logger.error(f"OUTBOX_REPO|mark_failed_no_update|id={outbox_id}")
                    return False
                    
    except Exception as e:
        logger.error(f"OUTBOX_REPO|mark_failed_error|id={outbox_id}|error={e}")
        return False


def get_outbox_stats(conversation_id: str) -> Dict[str, Any]:
    """
    Get outbox statistics for debugging and monitoring
    
    Args:
        conversation_id: Session/conversation identifier
        
    Returns:
        Dict with statistics by status
    """
    if not conversation_id:
        return {"error": "missing_conversation_id"}
    
    try:
        with get_database_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT status, COUNT(*) as count
                    FROM persistent_outbox 
                    WHERE conversation_id = %s
                    GROUP BY status
                    ORDER BY status
                """, (conversation_id,))
                
                rows = cursor.fetchall()
                
                # Build stats dict
                stats = {}
                total = 0
                for row in rows:
                    status = row[0]
                    count = row[1]
                    stats[status] = count
                    total += count
                
                # Add zeros for missing statuses
                for status in ['pending', 'sent', 'failed']:
                    if status not in stats:
                        stats[status] = 0
                
                return {
                    "conversation_id": conversation_id,
                    "stats": stats,
                    "total": total
                }
                
    except Exception as e:
        logger.error(f"OUTBOX_REPO|stats_failed|conv={conversation_id}|error={e}")
        return {"error": str(e)}


def cleanup_old_messages(days_old: int = 30) -> int:
    """
    Clean up old outbox messages to prevent database bloat
    
    Args:
        days_old: Remove messages older than this many days
        
    Returns:
        int: Number of messages cleaned up
    """
    try:
        with get_database_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM persistent_outbox 
                    WHERE created_at < now() - interval '%s days'
                      AND status IN ('sent', 'failed')
                """, (days_old,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"OUTBOX_REPO|cleanup|deleted={deleted_count}|days_old={days_old}")
                return deleted_count
                
    except Exception as e:
        logger.error(f"OUTBOX_REPO|cleanup_failed|days_old={days_old}|error={e}")
        return 0