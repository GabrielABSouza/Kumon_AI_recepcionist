"""
DedupStore - Idempotency tracking using Redis

Sistema simples de deduplicação baseado em idempotency_key para garantir
que cada OutboxItem seja enviado apenas 1 vez, mesmo em caso de retry.

Arquitetura: TurnController → Planner → Delivery
- Delivery verifica seen_idem() antes de enviar
- Delivery chama mark_idem() após envio bem-sucedido  
- Fallback também usa idempotência por turn_id
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# TTL padrão para chaves de deduplicação (24 horas)
DEFAULT_DEDUP_TTL = 86400


def _dedup_key(conversation_id: str, idempotency_key: str) -> str:
    """
    Chave Redis para deduplicação de mensagens
    
    Args:
        conversation_id: ID da conversa
        idempotency_key: Chave de idempotência única
        
    Returns:
        str: Chave Redis formatada
    """
    return f"idem:{conversation_id}:{idempotency_key}"


def seen_idem(cache, conversation_id: str, idempotency_key: str) -> bool:
    """
    Verifica se idempotency_key já foi processado
    
    Args:
        cache: Cliente Redis/cache
        conversation_id: ID da conversa
        idempotency_key: Chave de idempotência
        
    Returns:
        bool: True se já foi processado, False caso contrário
    """
    if not idempotency_key:
        logger.warning(f"DEDUP|empty_idem_key|conv={conversation_id}")
        return False
    
    key = _dedup_key(conversation_id, idempotency_key)
    
    try:
        exists = bool(cache.get(key))
        
        if exists:
            logger.info(
                f"DEDUP|hit|conv={conversation_id}|idem={idempotency_key}|"
                f"ttl={cache.ttl(key)}s"
            )
        else:
            logger.debug(f"DEDUP|miss|conv={conversation_id}|idem={idempotency_key}")
        
        return exists
        
    except Exception as e:
        logger.error(f"DEDUP|seen_error|conv={conversation_id}|idem={idempotency_key}|error={e}")
        # Em caso de erro no Redis, assume não visto para não bloquear entrega
        return False


def mark_idem(cache, conversation_id: str, idempotency_key: str, ttl: int = DEFAULT_DEDUP_TTL) -> bool:
    """
    Marca idempotency_key como processado
    
    Args:
        cache: Cliente Redis/cache
        conversation_id: ID da conversa
        idempotency_key: Chave de idempotência
        ttl: TTL em segundos (padrão: 24h)
        
    Returns:
        bool: True se marcou com sucesso
    """
    if not idempotency_key:
        logger.warning(f"DEDUP|mark_empty_key|conv={conversation_id}")
        return False
    
    key = _dedup_key(conversation_id, idempotency_key)
    
    try:
        # Marca como processado com TTL
        cache.setex(key, ttl, "1")
        
        logger.info(
            f"DEDUP|marked|conv={conversation_id}|idem={idempotency_key}|ttl={ttl}s"
        )
        return True
        
    except Exception as e:
        logger.error(f"DEDUP|mark_error|conv={conversation_id}|idem={idempotency_key}|error={e}")
        return False


def ensure_fallback_key(phone_number: str, turn_id: str) -> str:
    """
    Gera idempotency_key determinístico para fallback messages
    
    Garante que fallbacks também sejam idempotentes por turno.
    
    Args:
        phone_number: Número do telefone
        turn_id: ID do turno do TurnController
        
    Returns:
        str: idempotency_key para fallback
    """
    import hashlib
    
    raw = f"{phone_number}:{turn_id}:fallback"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def clear_conversation_dedup(cache, conversation_id: str) -> int:
    """
    Remove todas as chaves de deduplicação de uma conversa
    
    Útil para testes ou reset de conversa.
    
    Args:
        cache: Cliente Redis/cache
        conversation_id: ID da conversa
        
    Returns:
        int: Número de chaves removidas
    """
    try:
        # Busca todas as chaves da conversa
        pattern = f"idem:{conversation_id}:*"
        keys = cache.keys(pattern)
        
        if not keys:
            logger.debug(f"DEDUP|clear_no_keys|conv={conversation_id}")
            return 0
        
        # Remove as chaves
        deleted = cache.delete(*keys)
        
        logger.info(f"DEDUP|cleared|conv={conversation_id}|count={deleted}")
        return deleted
        
    except Exception as e:
        logger.error(f"DEDUP|clear_error|conv={conversation_id}|error={e}")
        return 0


def get_dedup_stats(cache, conversation_id: str) -> dict:
    """
    Estatísticas de deduplicação para debugging
    
    Args:
        cache: Cliente Redis/cache  
        conversation_id: ID da conversa
        
    Returns:
        dict: Estatísticas das chaves de deduplicação
    """
    try:
        pattern = f"idem:{conversation_id}:*"
        keys = cache.keys(pattern)
        
        if not keys:
            return {
                "conversation_id": conversation_id,
                "total_keys": 0,
                "keys": []
            }
        
        # Coleta informações de cada chave
        key_info = []
        for key in keys:
            try:
                ttl = cache.ttl(key)
                # Extrai idempotency_key da chave
                idem_key = key.split(":")[-1] if ":" in key else key
                key_info.append({
                    "idempotency_key": idem_key,
                    "ttl_seconds": ttl,
                    "redis_key": key
                })
            except Exception:
                continue
        
        return {
            "conversation_id": conversation_id,
            "total_keys": len(key_info),
            "keys": key_info
        }
        
    except Exception as e:
        logger.error(f"DEDUP|stats_error|conv={conversation_id}|error={e}")
        return {"error": str(e)}