"""
Turn Lock - Prevent concurrent processing per conversation

Implementa trava de turno usando Redis para garantir que apenas um
processo execute o workflow por conversação, evitando múltiplas respostas
para a mesma mensagem ou rajada de mensagens.

Arquitetura:
- Lock Redis com TTL automático para safety
- Context manager para uso fácil
- Identifica conversas por session_id/phone
"""

import logging
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# Configuração
LOCK_TTL_SEC = 15  # TTL de segurança para evitar locks órfãos
LOCK_PREFIX = "turnlock"


def _get_redis_client():
    """Get Redis client - import locally to avoid circular dependencies"""
    try:
        from ..cache.redis_manager import redis_cache
        return redis_cache.client
    except ImportError:
        logger.error("TURN_LOCK|redis_unavailable|no_turn_protection")
        return None


def _lock_key(conv_id: str) -> str:
    """Generate Redis key for turn lock"""
    return f"{LOCK_PREFIX}:{conv_id}"


@contextmanager
def turn_lock(conv_id: str, ttl_sec: int = LOCK_TTL_SEC):
    """
    Turn lock context manager for conversation processing
    
    Garante que apenas um processo execute o workflow por conversação.
    Se já existe um lock ativo, yields False e aborda graciosamente.
    
    Args:
        conv_id: Conversation/session identifier  
        ttl_sec: TTL in seconds for safety (default: 15s)
        
    Yields:
        bool: True if lock acquired, False if already locked
        
    Usage:
        with turn_lock(conversation_id) as acquired:
            if not acquired:
                logger.info("Turn already in progress, skipping")
                return
            # Process workflow normally
    """
    redis = _get_redis_client()
    if not redis:
        # No Redis = no lock protection, but allow processing
        logger.warning(f"TURN_LOCK|no_redis|conv={conv_id}|allowing_processing")
        yield True
        return
    
    key = _lock_key(conv_id)
    
    try:
        # Try to acquire lock with SETNX + TTL
        acquired = redis.set(key, "1", nx=True, ex=ttl_sec)
        
        if not acquired:
            # Lock already exists - another process is working
            logger.info(f"TURN_LOCK|already_locked|conv={conv_id}|skipping_turn")
            yield False
            return
        
        # Successfully acquired lock
        logger.info(f"TURN_LOCK|acquired|conv={conv_id}|ttl={ttl_sec}s")
        
        try:
            yield True
        finally:
            # Release lock on completion
            try:
                deleted = redis.delete(key)
                logger.info(f"TURN_LOCK|released|conv={conv_id}|deleted={deleted}")
            except Exception as e:
                logger.warning(f"TURN_LOCK|release_failed|conv={conv_id}|error={e}")
                # TTL will eventually clean up the lock
                
    except Exception as e:
        logger.error(f"TURN_LOCK|lock_failed|conv={conv_id}|error={e}")
        # On error, allow processing to continue
        yield True


def is_turn_locked(conv_id: str) -> bool:
    """
    Check if conversation has an active turn lock
    
    Args:
        conv_id: Conversation/session identifier
        
    Returns:
        bool: True if locked, False if available
    """
    redis = _get_redis_client()
    if not redis:
        return False
    
    try:
        key = _lock_key(conv_id)
        exists = redis.exists(key)
        
        logger.debug(f"TURN_LOCK|check|conv={conv_id}|locked={bool(exists)}")
        return bool(exists)
        
    except Exception as e:
        logger.error(f"TURN_LOCK|check_failed|conv={conv_id}|error={e}")
        return False


def force_unlock(conv_id: str) -> bool:
    """
    Force unlock a conversation (for debugging/emergency)
    
    Args:
        conv_id: Conversation/session identifier
        
    Returns:
        bool: True if unlocked successfully
    """
    redis = _get_redis_client()
    if not redis:
        return False
    
    try:
        key = _lock_key(conv_id)
        deleted = redis.delete(key)
        
        logger.warning(f"TURN_LOCK|force_unlocked|conv={conv_id}|deleted={deleted}")
        return deleted > 0
        
    except Exception as e:
        logger.error(f"TURN_LOCK|force_unlock_failed|conv={conv_id}|error={e}")
        return False


def get_lock_stats(conv_id: str) -> dict:
    """
    Get lock statistics for debugging
    
    Args:
        conv_id: Conversation/session identifier
        
    Returns:
        Dict with lock statistics
    """
    redis = _get_redis_client()
    if not redis:
        return {"error": "redis_unavailable"}
    
    try:
        key = _lock_key(conv_id)
        
        # Get existence and TTL
        pipe = redis.pipeline()
        pipe.exists(key)
        pipe.ttl(key)
        results = pipe.execute()
        
        exists = bool(results[0]) if results else False
        ttl = results[1] if len(results) > 1 else -1
        
        return {
            "conversation_id": conv_id,
            "is_locked": exists,
            "ttl_seconds": ttl,
            "redis_key": key
        }
        
    except Exception as e:
        logger.error(f"TURN_LOCK|stats_failed|conv={conv_id}|error={e}")
        return {"error": str(e)}