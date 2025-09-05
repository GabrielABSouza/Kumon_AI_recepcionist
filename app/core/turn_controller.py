"""
TurnController - Debounce + Redis Lock para 1 resposta por turno

ÚNICO componente novo da arquitetura mínima:
TurnController → Planner → Delivery

Responsabilidades:
- Agrega mensagens do usuário em janela de debounce (1200ms)
- Usa Redis lock para garantir 1 chamada de Planner por turno
- Gera turn_id determinístico baseado na primeira mensagem
- Empacota múltiplas mensagens em 1 texto agregado
"""

import time
import json
import hashlib
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Configuração de debounce e TTL
DEBOUNCE_MS = 1200  # janela de empacotamento de mensagens
TURN_TTL_S = 60     # TTL do lock e buffer


def _now_ms() -> int:
    """Timestamp atual em milissegundos"""
    return int(time.time() * 1000)


def _turn_key(phone: str) -> str:
    """Chave Redis para buffer de mensagens do telefone"""
    return f"turn:{phone}:buffer"


def _lock_key(phone: str) -> str:
    """Chave Redis para lock do turno"""
    return f"turn:{phone}:lock"


def make_turn_id(phone: str, first_msg_id: str, first_ts_ms: int) -> str:
    """
    Gera turn_id determinístico baseado na primeira mensagem do turno
    
    Args:
        phone: Número do telefone
        first_msg_id: ID da primeira mensagem
        first_ts_ms: Timestamp da primeira mensagem em ms
        
    Returns:
        str: turn_id hash de 16 caracteres
    """
    # Usar timestamp em segundos para maior determinismo
    first_ts_s = first_ts_ms // 1000
    raw = f"{phone}:{first_msg_id}:{first_ts_s}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@contextmanager
def turn_lock(cache, phone: str):
    """
    Context manager para lock de turno usando Redis
    
    Garante que apenas 1 processo chame o Planner por turno.
    Outros processos podem empacotar mensagens mas não disparam workflow.
    
    Args:
        cache: Cliente Redis/cache
        phone: Número do telefone
        
    Yields:
        bool: True se este processo detém o lock, False caso contrário
    """
    key = _lock_key(phone)
    
    # Tenta adquirir o lock
    if not cache.setnx(key, "1"):
        # Já existe turno em andamento para este telefone
        # → apenas empacota mensagens, sem disparar planner
        logger.info(f"TURN_LOCK|status=waiting|phone={phone[-4:]}|reason=lock_held")
        yield False
        return
    
    # Conseguiu o lock - define TTL e processa
    cache.expire(key, TURN_TTL_S)
    logger.info(f"TURN_LOCK|status=acquired|phone={phone[-4:]}|ttl={TURN_TTL_S}s")
    
    try:
        yield True
    finally:
        # Libera o lock
        cache.delete(key)
        logger.info(f"TURN_LOCK|status=released|phone={phone[-4:]}")


def append_user_message(cache, phone: str, msg_id: str, text: str, ts_ms: int) -> None:
    """
    Adiciona mensagem do usuário ao buffer de turno
    
    Args:
        cache: Cliente Redis/cache
        phone: Número do telefone
        msg_id: ID da mensagem
        text: Texto da mensagem
        ts_ms: Timestamp em milissegundos
    """
    key = _turn_key(phone)
    
    # Carrega buffer existente
    buf_json = cache.get(key) or "[]"
    try:
        buf = json.loads(buf_json)
    except json.JSONDecodeError:
        logger.warning(f"TURN_BUFFER|corrupted_json|phone={phone[-4:]}|resetting")
        buf = []
    
    # Adiciona nova mensagem
    message = {
        "id": msg_id,
        "text": text,
        "ts": ts_ms
    }
    buf.append(message)
    
    # Salva buffer atualizado
    cache.setex(key, TURN_TTL_S, json.dumps(buf))
    
    logger.info(
        f"TURN_BUFFER|appended|phone={phone[-4:]}|msg_id={msg_id}|"
        f"buffer_size={len(buf)}|text_len={len(text)}"
    )


def flush_turn_if_quiet(cache, phone: str, now_ms: int) -> Optional[Dict[str, Any]]:
    """
    Verifica se o turno está quieto e pode ser processado
    
    Args:
        cache: Cliente Redis/cache  
        phone: Número do telefone
        now_ms: Timestamp atual em milissegundos
        
    Returns:
        Dict com turn_id, messages e text agregado se pronto para processar,
        None se ainda aguardando mensagens
    """
    key = _turn_key(phone)
    
    # Carrega buffer
    buf_json = cache.get(key) or "[]"
    try:
        buf = json.loads(buf_json)
    except json.JSONDecodeError:
        logger.warning(f"TURN_FLUSH|corrupted_json|phone={phone[-4:]}|skipping")
        return None
    
    if not buf:
        logger.debug(f"TURN_FLUSH|empty_buffer|phone={phone[-4:]}")
        return None
    
    # Verifica se última mensagem é recente (dentro da janela de debounce)
    last_msg_ts = buf[-1]["ts"]
    time_since_last = now_ms - last_msg_ts
    
    if time_since_last < DEBOUNCE_MS:
        logger.debug(
            f"TURN_FLUSH|waiting|phone={phone[-4:]}|"
            f"time_since_last={time_since_last}ms|debounce={DEBOUNCE_MS}ms"
        )
        return None
    
    # Turno está quieto - pode processar
    first_msg = buf[0]
    turn_id = make_turn_id(phone, first_msg["id"], first_msg["ts"])
    
    # Agrega texto de todas as mensagens não-vazias
    texts = [msg["text"].strip() for msg in buf if msg["text"].strip()]
    aggregated_text = "\n".join(texts)
    
    # Remove buffer do Redis (turno consumido)
    cache.delete(key)
    
    result = {
        "turn_id": turn_id,
        "messages": buf,
        "text": aggregated_text,
        "message_count": len(buf),
        "first_ts": first_msg["ts"],
        "last_ts": buf[-1]["ts"],
        "span_ms": buf[-1]["ts"] - first_msg["ts"]
    }
    
    logger.info(
        f"TURN_FLUSH|ready|phone={phone[-4:]}|turn_id={turn_id}|"
        f"msg_count={len(buf)}|text_len={len(aggregated_text)}|"
        f"span_ms={result['span_ms']}"
    )
    
    return result


def get_turn_status(cache, phone: str) -> Dict[str, Any]:
    """
    Verifica status atual do turno para debugging
    
    Args:
        cache: Cliente Redis/cache
        phone: Número do telefone
        
    Returns:
        Dict com status do lock e buffer
    """
    lock_key = _lock_key(phone)
    buffer_key = _turn_key(phone)
    
    has_lock = bool(cache.get(lock_key))
    buffer_json = cache.get(buffer_key) or "[]"
    
    try:
        buffer_msgs = json.loads(buffer_json)
    except json.JSONDecodeError:
        buffer_msgs = []
    
    return {
        "has_lock": has_lock,
        "buffer_size": len(buffer_msgs),
        "buffer_msgs": buffer_msgs,
        "lock_ttl": cache.ttl(lock_key) if has_lock else 0,
        "buffer_ttl": cache.ttl(buffer_key) if buffer_msgs else 0
    }