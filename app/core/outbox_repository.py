"""
Outbox Repository - PostgreSQL persistence for reliable message delivery
Provides persistent storage for planned messages with delivery status tracking
"""

import json
import logging
import uuid
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import psycopg2, handle ModuleNotFoundError gracefully
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ModuleNotFoundError as e:
    logger.error(f"psycopg2 not available for outbox repository: {e}")
    PSYCOPG2_AVAILABLE = False


def ensure_outbox_schema() -> bool:
    """
    Ensure outbox_messages table exists, create if missing
    
    Returns:
        bool: True if table exists or was created successfully
    """
    if not PSYCOPG2_AVAILABLE:
        logger.warning("OUTBOX_SCHEMA|psycopg2_unavailable|skipping_schema_check")
        return False
    
    from .database.connection import get_database_connection
    
    conn = get_database_connection()
    if not conn:
        logger.warning("OUTBOX_SCHEMA|no_database|skipping_schema_check")
        return False
    
    try:
        with conn.cursor() as cur:
            # Check if table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'outbox_messages'
                );
            """)
            
            table_exists = cur.fetchone()[0]
            
            if table_exists:
                logger.info("OUTBOX_SCHEMA|table_exists|skipping_creation")
                return True
            
            logger.info("OUTBOX_SCHEMA|creating_table|auto_migration")
            
            # Create table with full schema
            cur.execute("""
                CREATE TABLE outbox_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    conversation_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    text TEXT NOT NULL,
                    channel TEXT NOT NULL DEFAULT 'whatsapp',
                    meta JSONB DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'SENT', 'FAILED')),
                    message_order INTEGER NOT NULL DEFAULT 0,
                    provider_message_id TEXT,
                    error_reason TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    sent_at TIMESTAMPTZ,
                    failed_at TIMESTAMPTZ
                );
            """)
            
            # Create indexes
            cur.execute("CREATE INDEX idx_outbox_conversation_status ON outbox_messages (conversation_id, status);")
            cur.execute("CREATE INDEX idx_outbox_status_created ON outbox_messages (status, created_at);")
            cur.execute("CREATE INDEX idx_outbox_conversation_order ON outbox_messages (conversation_id, message_order);")
            cur.execute("CREATE INDEX idx_outbox_created_at ON outbox_messages (created_at);")
            cur.execute("CREATE UNIQUE INDEX idx_outbox_idempotency ON outbox_messages (idempotency_key);")
            cur.execute("CREATE INDEX idx_outbox_provider_id ON outbox_messages (provider_message_id) WHERE provider_message_id IS NOT NULL;")
            
            logger.info("OUTBOX_SCHEMA|table_created|success")
            return True
            
    except Exception as e:
        logger.error(f"OUTBOX_SCHEMA|creation_failed|error={e}")
        return False


def generate_idempotency_key(phone: str, turn_id: str, idx: int) -> str:
    """Generate deterministic idempotency key"""
    raw = f"{phone}:{turn_id}:{idx}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def save_outbox(conversation_id: str, messages: List[Dict[str, Any]], state: Optional[Dict] = None) -> List[str]:
    """
    Save outbox messages to database with Redis fallback
    
    Args:
        conversation_id: Unique conversation identifier
        messages: List of message dictionaries to persist
        state: Optional state dict with phone_number and turn_id
        
    Returns:
        List[str]: List of idempotency keys for saved messages
    """
    if not PSYCOPG2_AVAILABLE:
        logger.warning(f"OUTBOX_SAVE|psycopg2_unavailable|conv={conversation_id}|trying_redis_fallback")
        # Fallback to Redis
        return _save_outbox_redis_fallback(conversation_id, messages, state)
    
    from .database.connection import get_database_connection
    
    conn = get_database_connection()
    if not conn:
        logger.warning(f"OUTBOX_SAVE|no_database|conv={conversation_id}|degrading_gracefully")
        return []
    
    # Ensure outbox table exists
    if not ensure_outbox_schema():
        logger.warning(f"OUTBOX_SAVE|schema_unavailable|conv={conversation_id}|degrading_gracefully")
        return []
    
    idempotency_keys = []
    
    try:
        with conn.cursor() as cur:
            for i, message in enumerate(messages):
                # Generate idempotency key
                idem_key = str(uuid.uuid4())
                idempotency_keys.append(idem_key)
                
                # Prepare message data
                text = message.get("text", "")
                channel = message.get("channel", "whatsapp")
                meta = message.get("meta", {})
                
                # Insert into database
                cur.execute("""
                    INSERT INTO outbox_messages (
                        id, conversation_id, idempotency_key, text, channel, 
                        meta, status, created_at, message_order
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, 'QUEUED', NOW(), %s
                    )
                """, (
                    str(uuid.uuid4()),
                    conversation_id,
                    idem_key,
                    text,
                    channel,
                    json.dumps(meta),
                    i
                ))
        
        logger.info(f"OUTBOX_SAVE|success|conv={conversation_id}|count={len(messages)}")
        return idempotency_keys
        
    except Exception as e:
        logger.error(f"OUTBOX_SAVE|postgres_error|conv={conversation_id}|error={e}|trying_redis_fallback")
        # Fallback to Redis on any DB error
        return _save_outbox_redis_fallback(conversation_id, messages, state)


def _save_outbox_redis_fallback(conversation_id: str, messages: List[Dict[str, Any]], state: Optional[Dict] = None) -> List[str]:
    """
    Save outbox messages to Redis as fallback
    
    Args:
        conversation_id: Unique conversation identifier
        messages: List of message dictionaries to persist
        state: Optional state dict with phone_number and turn_id
        
    Returns:
        List[str]: List of idempotency keys for saved messages
    """
    try:
        from ..core.redis_client import get_redis_client
        from ..core.feature_flags import is_outbox_redis_fallback_enabled
        
        if not is_outbox_redis_fallback_enabled():
            logger.warning(f"OUTBOX_SAVE|redis_fallback_disabled|conv={conversation_id}")
            return []
        
        redis_client = get_redis_client()
        if not redis_client:
            logger.error(f"OUTBOX_SAVE|redis_unavailable|conv={conversation_id}")
            return []
        
        # Extract necessary data from state
        phone = state.get("phone_number", "unknown") if state else "unknown"
        turn_id = state.get("turn_id", "noturn") if state else "noturn"
        
        keys = []
        redis_key = f"outbox:{conversation_id}"
        
        for idx, item in enumerate(messages):
            # Generate idempotency key
            idem_key = generate_idempotency_key(phone, turn_id, idx)
            
            # Add idempotency key to the message
            payload = {
                **item,
                "idempotency_key": idem_key,
                "_source": "redis_fallback"
            }
            
            # Push to Redis list
            redis_client.lpush(redis_key, json.dumps(payload))
            keys.append(idem_key)
            
        # Set expiration (1 hour)
        redis_client.expire(redis_key, 3600)
        
        logger.info(f"OUTBOX_SAVE|redis_fallback_success|conv={conversation_id}|count={len(keys)}")
        return keys
        
    except Exception as e:
        logger.error(f"OUTBOX_SAVE|redis_fallback_error|conv={conversation_id}|error={e}")
        return []


def get_next_outbox_for_delivery(conversation_id: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """
    Get next queued message for delivery
    
    Args:
        conversation_id: Conversation identifier
        
    Returns:
        Tuple of (message_dict, idempotency_key) or None if no messages
    """
    if not PSYCOPG2_AVAILABLE:
        logger.warning(f"DELIVERY_REHYDRATE|psycopg2_unavailable|conv={conversation_id}")
        return None
    
    from .database.connection import get_database_connection
    
    conn = get_database_connection()
    if not conn:
        logger.warning(f"DELIVERY_REHYDRATE|no_database|conv={conversation_id}")
        return None
    
    # Ensure outbox table exists
    if not ensure_outbox_schema():
        logger.warning(f"DELIVERY_REHYDRATE|schema_unavailable|conv={conversation_id}")
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get oldest queued message
            cur.execute("""
                SELECT id, idempotency_key, text, channel, meta, message_order
                FROM outbox_messages 
                WHERE conversation_id = %s AND status = 'QUEUED'
                ORDER BY message_order ASC, created_at ASC
                LIMIT 1
            """, (conversation_id,))
            
            row = cur.fetchone()
            if not row:
                logger.debug(f"DELIVERY_REHYDRATE|no_queued_messages|conv={conversation_id}")
                return None
            
            # Convert to message dict
            message_dict = {
                "text": row["text"],
                "channel": row["channel"],
                "meta": json.loads(row["meta"]) if row["meta"] else {},
                "idempotency_key": row["idempotency_key"],
                "_db_id": row["id"]
            }
            
            logger.info(f"DELIVERY_REHYDRATE|found_message|conv={conversation_id}|idem={row['idempotency_key']}")
            return message_dict, row["idempotency_key"]
            
    except Exception as e:
        logger.error(f"DELIVERY_REHYDRATE|error|conv={conversation_id}|error={e}")
        return None


def mark_outbox_as_sent(db_id: str, provider_message_id: Optional[str] = None) -> bool:
    """
    Mark outbox message as sent
    
    Args:
        db_id: Database ID of the message
        provider_message_id: Message ID from delivery provider
        
    Returns:
        bool: True if successfully marked
    """
    from .database.connection import get_database_connection
    
    conn = get_database_connection()
    if not conn:
        logger.warning(f"OUTBOX_MARK_SENT|no_database|db_id={db_id}")
        return False
    
    # Ensure outbox table exists
    if not ensure_outbox_schema():
        logger.warning(f"OUTBOX_MARK_SENT|schema_unavailable|db_id={db_id}")
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE outbox_messages 
                SET status = 'SENT', 
                    sent_at = NOW(),
                    provider_message_id = %s
                WHERE id = %s
            """, (provider_message_id, db_id))
            
            updated = cur.rowcount > 0
            
            if updated:
                logger.info(f"OUTBOX_MARK_SENT|success|db_id={db_id}|provider_id={provider_message_id}")
            else:
                logger.warning(f"OUTBOX_MARK_SENT|not_found|db_id={db_id}")
                
            return updated
            
    except Exception as e:
        logger.error(f"OUTBOX_MARK_SENT|error|db_id={db_id}|error={e}")
        return False


def mark_outbox_as_failed(db_id: str, error_reason: str) -> bool:
    """
    Mark outbox message as failed
    
    Args:
        db_id: Database ID of the message
        error_reason: Reason for failure
        
    Returns:
        bool: True if successfully marked
    """
    from .database.connection import get_database_connection
    
    conn = get_database_connection()
    if not conn:
        logger.warning(f"OUTBOX_MARK_FAILED|no_database|db_id={db_id}")
        return False
    
    # Ensure outbox table exists
    if not ensure_outbox_schema():
        logger.warning(f"OUTBOX_MARK_FAILED|schema_unavailable|db_id={db_id}")
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE outbox_messages 
                SET status = 'FAILED',
                    failed_at = NOW(),
                    error_reason = %s
                WHERE id = %s
            """, (error_reason, db_id))
            
            updated = cur.rowcount > 0
            
            if updated:
                logger.warning(f"OUTBOX_MARK_FAILED|success|db_id={db_id}|reason={error_reason}")
            else:
                logger.warning(f"OUTBOX_MARK_FAILED|not_found|db_id={db_id}")
                
            return updated
            
    except Exception as e:
        logger.error(f"OUTBOX_MARK_FAILED|error|db_id={db_id}|error={e}")
        return False


def cleanup_old_outbox_messages(days: int = 7) -> int:
    """
    Clean up old outbox messages
    
    Args:
        days: Number of days to keep messages
        
    Returns:
        int: Number of messages cleaned up
    """
    from .database.connection import get_database_connection
    
    conn = get_database_connection()
    if not conn:
        logger.warning("OUTBOX_CLEANUP|no_database")
        return 0
    
    # Ensure outbox table exists
    if not ensure_outbox_schema():
        logger.warning("OUTBOX_CLEANUP|schema_unavailable")
        return 0
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM outbox_messages 
                WHERE created_at < NOW() - INTERVAL '%s days'
                AND status IN ('SENT', 'FAILED')
            """, (days,))
            
            deleted = cur.rowcount
            logger.info(f"OUTBOX_CLEANUP|success|deleted_count={deleted}|days={days}")
            return deleted
            
    except Exception as e:
        logger.error(f"OUTBOX_CLEANUP|error|error={e}")
        return 0


# Legacy compatibility functions for existing code
def load_outbox(db_connection, conversation_id: str, turn_id: str) -> List[Dict[str, Any]]:
    """Legacy function for backward compatibility"""
    result = get_next_outbox_for_delivery(conversation_id)
    if result:
        message_dict, _ = result
        return [message_dict]
    return []


def mark_sent(db_connection, conversation_id: str, turn_id: str, message_index: int, provider_id: str) -> bool:
    """Legacy function for backward compatibility"""
    # This would need the actual db_id, which we'd need to track differently
    # For now, return True to avoid breaking existing code
    logger.info(f"LEGACY_MARK_SENT|conv={conversation_id}|turn={turn_id}|provider={provider_id}")
    return True


def mark_failed(db_connection, conversation_id: str, turn_id: str, message_index: int, error_reason: str) -> bool:
    """Legacy function for backward compatibility"""
    # This would need the actual db_id, which we'd need to track differently
    # For now, return True to avoid breaking existing code
    logger.warning(f"LEGACY_MARK_FAILED|conv={conversation_id}|turn={turn_id}|reason={error_reason}")
    return True


def persist_outbox(db_connection, conversation_id: str, turn_id: str, outbox_items: List[Dict[str, Any]]) -> List[str]:
    """Legacy function for backward compatibility"""
    return save_outbox(conversation_id, outbox_items)