"""
Outbox Repository Redis - Fonte da verdade para handoff Planner → Delivery

Resolve o problema crítico de outbox perdido entre nós do LangGraph workflow.
Redis como repositório primário garante que o Delivery sempre encontre as mensagens
planejadas pelo Planner, mesmo com diferentes instâncias de estado.

Arquitetura:
- Planner: outbox_push() para persistir mensagens
- Delivery: outbox_pop_all() para consumir mensagens  
- TTL automático evita vazamento de memória
"""

import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Configuração
OUTBOX_KEY_PREFIX = "outbox"
OUTBOX_TTL_SEC = 3600  # 1 hora
DEDUPE_TTL_SEC = 30    # 30 segundos


def _get_redis_client():
    """Get Redis client - import locally to avoid circular dependencies"""
    try:
        from ..cache.redis_manager import redis_cache
        return redis_cache.client
    except ImportError:
        logger.error("REDIS_OUTBOX|redis_unavailable|falling_back_to_memory")
        return None


def _outbox_key(conv_id: str) -> str:
    """Generate Redis key for outbox"""
    return f"{OUTBOX_KEY_PREFIX}:{conv_id}"


def outbox_push(conv_id: str, messages: List[Dict[str, Any]]) -> int:
    """
    Persist outbox messages to Redis (atomic handoff Planner → Delivery)
    
    Args:
        conv_id: Conversation/session identifier
        messages: List of message dicts to persist
        
    Returns:
        int: Number of messages persisted
    """
    if not messages:
        logger.debug(f"REDIS_OUTBOX|push_empty|conv={conv_id}")
        return 0
        
    redis = _get_redis_client()
    if not redis:
        logger.error(f"REDIS_OUTBOX|push_no_redis|conv={conv_id}|count={len(messages)}")
        return 0
    
    try:
        key = _outbox_key(conv_id)
        
        # Pipeline for atomic operation
        pipe = redis.pipeline()
        
        # Clear any existing messages first
        pipe.delete(key)
        
        # Push all messages
        for msg in messages:
            serialized = json.dumps(msg, ensure_ascii=False)
            pipe.rpush(key, serialized)
        
        # Set TTL to prevent memory leaks
        pipe.expire(key, OUTBOX_TTL_SEC)
        
        # Execute pipeline
        results = pipe.execute()
        
        logger.info(f"REDIS_OUTBOX|push_success|conv={conv_id}|count={len(messages)}|ttl={OUTBOX_TTL_SEC}s")
        return len(messages)
        
    except Exception as e:
        logger.error(f"REDIS_OUTBOX|push_failed|conv={conv_id}|count={len(messages)}|error={e}")
        return 0


def outbox_peek_all(conv_id: str) -> List[Dict[str, Any]]:
    """
    Peek at all outbox messages without consuming them
    
    Args:
        conv_id: Conversation/session identifier
        
    Returns:
        List of message dicts
    """
    redis = _get_redis_client()
    if not redis:
        logger.debug(f"REDIS_OUTBOX|peek_no_redis|conv={conv_id}")
        return []
    
    try:
        key = _outbox_key(conv_id)
        raw_messages = redis.lrange(key, 0, -1)
        
        if not raw_messages:
            logger.debug(f"REDIS_OUTBOX|peek_empty|conv={conv_id}")
            return []
        
        # Deserialize messages
        messages = []
        for raw_msg in raw_messages:
            try:
                msg = json.loads(raw_msg)
                messages.append(msg)
            except json.JSONDecodeError as e:
                logger.warning(f"REDIS_OUTBOX|peek_invalid_json|conv={conv_id}|error={e}")
                continue
        
        logger.debug(f"REDIS_OUTBOX|peek_success|conv={conv_id}|count={len(messages)}")
        return messages
        
    except Exception as e:
        logger.error(f"REDIS_OUTBOX|peek_failed|conv={conv_id}|error={e}")
        return []


def outbox_pop_all(conv_id: str) -> List[Dict[str, Any]]:
    """
    Pop (consume) all outbox messages atomically
    
    Args:
        conv_id: Conversation/session identifier
        
    Returns:
        List of message dicts (removes them from Redis)
    """
    redis = _get_redis_client()
    if not redis:
        logger.debug(f"REDIS_OUTBOX|pop_no_redis|conv={conv_id}")
        return []
    
    try:
        key = _outbox_key(conv_id)
        
        # Atomic operation: get all + delete
        pipe = redis.pipeline()
        pipe.lrange(key, 0, -1)  # Get all
        pipe.delete(key)         # Remove
        results = pipe.execute()
        
        raw_messages = results[0] if results else []
        
        if not raw_messages:
            logger.debug(f"REDIS_OUTBOX|pop_empty|conv={conv_id}")
            return []
        
        # Deserialize messages
        messages = []
        for raw_msg in raw_messages:
            try:
                msg = json.loads(raw_msg)
                messages.append(msg)
            except json.JSONDecodeError as e:
                logger.warning(f"REDIS_OUTBOX|pop_invalid_json|conv={conv_id}|error={e}")
                continue
        
        logger.info(f"REDIS_OUTBOX|pop_success|conv={conv_id}|count={len(messages)}")
        return messages
        
    except Exception as e:
        logger.error(f"REDIS_OUTBOX|pop_failed|conv={conv_id}|error={e}")
        return []


def is_recent_duplicate(message_id: str) -> bool:
    """
    Check if message_id was processed recently (dedupe with TTL)
    
    Args:
        message_id: Unique message identifier
        
    Returns:
        bool: True if it's a recent duplicate, False if new
    """
    if not message_id:
        return False
        
    redis = _get_redis_client()
    if not redis:
        logger.debug(f"REDIS_OUTBOX|dedupe_no_redis|msg_id={message_id}")
        return False  # Without Redis, can't dedupe - allow processing
    
    try:
        key = f"dedupe:{message_id}"
        
        # SETNX with TTL: set only if not exists
        was_set = redis.set(key, "1", nx=True, ex=DEDUPE_TTL_SEC)
        
        is_duplicate = was_set is None  # None means key already existed
        
        if is_duplicate:
            logger.info(f"REDIS_OUTBOX|duplicate_detected|msg_id={message_id}")
        else:
            logger.debug(f"REDIS_OUTBOX|new_message|msg_id={message_id}")
            
        return is_duplicate
        
    except Exception as e:
        logger.error(f"REDIS_OUTBOX|dedupe_failed|msg_id={message_id}|error={e}")
        return False  # On error, allow processing to be safe


def get_outbox_stats(conv_id: str) -> Dict[str, Any]:
    """
    Get outbox statistics for debugging
    
    Args:
        conv_id: Conversation/session identifier
        
    Returns:
        Dict with statistics
    """
    redis = _get_redis_client()
    if not redis:
        return {"error": "redis_unavailable"}
    
    try:
        key = _outbox_key(conv_id)
        
        # Get list length and TTL
        pipe = redis.pipeline()
        pipe.llen(key)
        pipe.ttl(key)
        results = pipe.execute()
        
        count = results[0] if results else 0
        ttl = results[1] if len(results) > 1 else -1
        
        return {
            "conversation_id": conv_id,
            "outbox_count": count,
            "ttl_seconds": ttl,
            "redis_key": key
        }
        
    except Exception as e:
        logger.error(f"REDIS_OUTBOX|stats_failed|conv={conv_id}|error={e}")
        return {"error": str(e)}


def clear_conversation_outbox(conv_id: str) -> bool:
    """
    Clear all outbox messages for a conversation (for debugging/testing)
    
    Args:
        conv_id: Conversation/session identifier
        
    Returns:
        bool: True if cleared successfully
    """
    redis = _get_redis_client()
    if not redis:
        return False
    
    try:
        key = _outbox_key(conv_id)
        deleted = redis.delete(key)
        
        logger.info(f"REDIS_OUTBOX|cleared|conv={conv_id}|deleted={deleted}")
        return deleted > 0
        
    except Exception as e:
        logger.error(f"REDIS_OUTBOX|clear_failed|conv={conv_id}|error={e}")
        return False