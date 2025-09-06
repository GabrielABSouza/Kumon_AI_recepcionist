"""
Turn Deduplication - Message-level deduplication with Redis
Prevents processing duplicate webhook messages and implements turn-based debouncing
"""

import logging
import time
from typing import Optional, Dict, Any
from contextlib import contextmanager
from .cache_manager import get_redis

logger = logging.getLogger(__name__)

# Configuration
DEDUP_TTL_SEC = 60  # 1 minute TTL for message deduplication
TURN_LOCK_TTL_SEC = 10  # 10 seconds for turn lock
DEBOUNCE_WINDOW_MS = 500  # 500ms debounce window

# Redis key prefixes
DEDUP_PREFIX = "dedup:msg"
TURNLOCK_PREFIX = "turnlock"
DEBOUNCE_PREFIX = "debounce"


def generate_message_key(instance: str, phone: str, message_id: str) -> str:
    """Generate unique key for message deduplication"""
    return f"{instance}:{phone}:{message_id}"


def is_duplicate_message(instance: str, phone: str, message_id: str) -> bool:
    """
    Check if message is a duplicate (already processed)
    
    Args:
        instance: WhatsApp instance name
        phone: Phone number
        message_id: Message ID from Evolution API
        
    Returns:
        bool: True if duplicate (should skip), False if new (should process)
    """
    redis = get_redis()
    if not redis:
        logger.warning("DEDUP|redis_unavailable|allowing_processing")
        return False
    
    try:
        msg_key = generate_message_key(instance, phone, message_id)
        redis_key = f"{DEDUP_PREFIX}:{msg_key}"
        
        # Try to set with NX (only if not exists)
        is_new = redis.set(redis_key, "1", nx=True, ex=DEDUP_TTL_SEC)
        
        if is_new:
            from .structured_logging import log_dedup_event
            log_dedup_event("new_message", msg_key, phone)
            return False  # New message, should process
        else:
            from .structured_logging import log_dedup_event
            log_dedup_event("duplicate", msg_key, phone)
            return True  # Duplicate, should skip
            
    except Exception as e:
        logger.error(f"DEDUP|error|key={msg_key}|error={e}|allowing_processing")
        return False  # On error, allow processing


@contextmanager
def turn_lock(conversation_id: str, ttl_sec: int = TURN_LOCK_TTL_SEC):
    """
    Turn lock to prevent concurrent processing of same conversation
    
    Args:
        conversation_id: Unique conversation identifier
        ttl_sec: Lock TTL in seconds
        
    Yields:
        bool: True if lock acquired, False if already locked
    """
    redis = get_redis()
    if not redis:
        logger.warning(f"TURNLOCK|redis_unavailable|conv={conversation_id}|allowing_processing")
        yield True
        return
    
    lock_key = f"{TURNLOCK_PREFIX}:{conversation_id}"
    
    try:
        # Try to acquire lock with SETNX + TTL
        acquired = redis.set(lock_key, "1", nx=True, ex=ttl_sec)
        
        if not acquired:
            from .structured_logging import log_turn_event
            log_turn_event("duplicate", conversation_id, conversation_id.replace("conv_", ""))
            yield False
            return
        
        from .structured_logging import log_turn_event
        log_turn_event("acquired", conversation_id, conversation_id.replace("conv_", ""))
        
        try:
            yield True
        finally:
            # Release lock
            try:
                redis.delete(lock_key)
                logger.info(f"TURNLOCK|released|key={lock_key}")
            except Exception as e:
                logger.warning(f"TURNLOCK|release_failed|key={lock_key}|error={e}")
                
    except Exception as e:
        logger.error(f"TURNLOCK|error|key={lock_key}|error={e}|allowing_processing")
        yield True


def ensure_fallback_key(phone: str, turn_id: str) -> str:
    """Generate idempotency key for fallback messages"""
    return f"fallback:{phone}:{turn_id}"


def seen_idem(cache, conversation_id: str, idem_key: str) -> bool:
    """Check if idempotency key was already processed"""
    if not cache:
        return False
    
    try:
        redis_key = f"sent:{conversation_id}:{idem_key}"
        return bool(cache.exists(redis_key))
    except Exception as e:
        logger.error(f"SEEN_IDEM|error|conv={conversation_id}|idem={idem_key}|error={e}")
        return False


def mark_idem(cache, conversation_id: str, idem_key: str, ttl: int = 600):
    """Mark idempotency key as processed"""
    if not cache:
        return
    
    try:
        redis_key = f"sent:{conversation_id}:{idem_key}"
        cache.setex(redis_key, ttl, "1")
        logger.info(f"MARK_IDEM|success|conv={conversation_id}|idem={idem_key}")
    except Exception as e:
        logger.error(f"MARK_IDEM|error|conv={conversation_id}|idem={idem_key}|error={e}")


def now_ms() -> int:
    """Get current timestamp in milliseconds"""
    return int(time.time() * 1000)


def should_debounce(phone: str, current_ts: int, window_ms: int = DEBOUNCE_WINDOW_MS) -> bool:
    """
    Check if message should be debounced (within debounce window)
    
    Args:
        phone: Phone number
        current_ts: Current timestamp in milliseconds  
        window_ms: Debounce window in milliseconds
        
    Returns:
        bool: True if should debounce (skip), False if should process
    """
    redis = get_redis()
    if not redis:
        return False
    
    try:
        debounce_key = f"{DEBOUNCE_PREFIX}:{phone}"
        
        # Get last timestamp
        last_ts = redis.get(debounce_key)
        if last_ts:
            last_ts = int(last_ts)
            if current_ts - last_ts < window_ms:
                logger.info(f"DEBOUNCE|within_window|phone={phone}|delta_ms={current_ts - last_ts}")
                return True  # Within window, debounce
        
        # Update last timestamp  
        redis.setex(debounce_key, 5, str(current_ts))  # 5 second TTL
        return False  # Should process
        
    except Exception as e:
        logger.error(f"DEBOUNCE|error|phone={phone}|error={e}")
        return False