"""
OutboxStore - Persistent storage for planned responses

Fonte de verdade durável para OutboxItems planejados pelo Planner.
Resolve o problema de "outbox sumiu no caminho" entre Planner e Delivery.

Arquitetura: TurnController → Planner → Delivery
- Planner: persiste 1 OutboxItem por turn_id
- Delivery: rehydrata do DB se state.outbox estiver vazio
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def persist_outbox(db, conversation_id: str, turn_id: str, items: List[Dict[str, Any]]) -> bool:
    """
    Persiste OutboxItems no banco de dados de forma durável
    
    Args:
        db: Conexão de banco (assume interface execute/executemany)
        conversation_id: ID da conversa
        turn_id: ID do turno (determinístico do TurnController)
        items: Lista de OutboxItems serializados como dict
        
    Returns:
        bool: True se persistiu com sucesso
    """
    if not items:
        logger.warning(f"OUTBOX_STORE|empty_items|conv={conversation_id}|turn={turn_id}")
        return True
    
    try:
        # Insere cada item com índice sequencial
        for idx, item in enumerate(items):
            # Valida campos obrigatórios
            if not item.get("idempotency_key"):
                logger.error(f"OUTBOX_STORE|missing_idem_key|conv={conversation_id}|turn={turn_id}|idx={idx}")
                continue
            
            # Insert with ON CONFLICT DO NOTHING para idempotência
            db.execute("""
                INSERT INTO outbox_messages (
                    conversation_id, turn_id, item_index, payload, status, idempotency_key
                ) VALUES (%s, %s, %s, %s::jsonb, 'queued', %s)
                ON CONFLICT (conversation_id, turn_id, item_index) DO NOTHING
            """, (
                conversation_id,
                turn_id, 
                idx,
                json.dumps(item),
                item["idempotency_key"]
            ))
        
        logger.info(
            f"OUTBOX_STORE|persisted|conv={conversation_id}|turn={turn_id}|count={len(items)}"
        )
        return True
        
    except Exception as e:
        logger.error(f"OUTBOX_STORE|persist_failed|conv={conversation_id}|turn={turn_id}|error={e}")
        return False


def load_outbox(db, conversation_id: str, turn_id: str) -> List[Dict[str, Any]]:
    """
    Carrega OutboxItems persistidos para rehydrate
    
    Args:
        db: Conexão de banco (assume interface fetch/fetchall)
        conversation_id: ID da conversa
        turn_id: ID do turno
        
    Returns:
        Lista de OutboxItems como dict, ordenada por item_index
    """
    try:
        # Busca itens pendentes (queued ou failed) ordenados por índice
        rows = db.fetch("""
            SELECT item_index, payload
            FROM outbox_messages 
            WHERE conversation_id = %s 
              AND turn_id = %s 
              AND status IN ('queued', 'failed')
            ORDER BY item_index ASC
        """, (conversation_id, turn_id))
        
        if not rows:
            logger.debug(f"OUTBOX_STORE|no_items|conv={conversation_id}|turn={turn_id}")
            return []
        
        # Deserializa payloads JSON
        items = []
        for row in rows:
            try:
                payload = row["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                items.append(payload)
            except json.JSONDecodeError as e:
                logger.error(f"OUTBOX_STORE|json_decode_error|conv={conversation_id}|turn={turn_id}|error={e}")
                continue
        
        logger.info(
            f"OUTBOX_STORE|rehydrated|conv={conversation_id}|turn={turn_id}|count={len(items)}"
        )
        return items
        
    except Exception as e:
        logger.error(f"OUTBOX_STORE|load_failed|conv={conversation_id}|turn={turn_id}|error={e}")
        return []


def mark_sent(db, conversation_id: str, turn_id: str, item_index: int, provider_id: str) -> bool:
    """
    Marca OutboxItem como enviado com ID do provedor
    
    Args:
        db: Conexão de banco
        conversation_id: ID da conversa  
        turn_id: ID do turno
        item_index: Índice do item (geralmente 0 para 1 resposta por turno)
        provider_id: ID retornado pelo provedor (WhatsApp/SMS)
        
    Returns:
        bool: True se marcou com sucesso
    """
    try:
        result = db.execute("""
            UPDATE outbox_messages 
            SET status = 'sent', 
                sent_provider_id = %s, 
                sent_at = now()
            WHERE conversation_id = %s 
              AND turn_id = %s 
              AND item_index = %s
        """, (provider_id, conversation_id, turn_id, item_index))
        
        # Verifica se atualizou alguma linha
        updated = getattr(result, 'rowcount', 1) > 0
        
        if updated:
            logger.info(
                f"OUTBOX_STORE|marked_sent|conv={conversation_id}|turn={turn_id}|"
                f"idx={item_index}|provider_id={provider_id}"
            )
        else:
            logger.warning(
                f"OUTBOX_STORE|mark_sent_no_rows|conv={conversation_id}|turn={turn_id}|idx={item_index}"
            )
        
        return updated
        
    except Exception as e:
        logger.error(
            f"OUTBOX_STORE|mark_sent_failed|conv={conversation_id}|turn={turn_id}|"
            f"idx={item_index}|error={e}"
        )
        return False


def mark_failed(db, conversation_id: str, turn_id: str, item_index: int, error_reason: str) -> bool:
    """
    Marca OutboxItem como falhou para retry posterior
    
    Args:
        db: Conexão de banco
        conversation_id: ID da conversa
        turn_id: ID do turno  
        item_index: Índice do item
        error_reason: Motivo da falha
        
    Returns:
        bool: True se marcou com sucesso
    """
    try:
        result = db.execute("""
            UPDATE outbox_messages 
            SET status = 'failed'
            WHERE conversation_id = %s 
              AND turn_id = %s 
              AND item_index = %s
        """, (conversation_id, turn_id, item_index))
        
        updated = getattr(result, 'rowcount', 1) > 0
        
        if updated:
            logger.warning(
                f"OUTBOX_STORE|marked_failed|conv={conversation_id}|turn={turn_id}|"
                f"idx={item_index}|reason={error_reason}"
            )
        
        return updated
        
    except Exception as e:
        logger.error(
            f"OUTBOX_STORE|mark_failed_error|conv={conversation_id}|turn={turn_id}|"
            f"idx={item_index}|error={e}"
        )
        return False


def get_outbox_stats(db, conversation_id: str, turn_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Estatísticas do outbox para debugging
    
    Args:
        db: Conexão de banco
        conversation_id: ID da conversa
        turn_id: ID do turno (opcional, se None mostra toda a conversa)
        
    Returns:
        Dict com estatísticas por status
    """
    try:
        where_clause = "WHERE conversation_id = %s"
        params = [conversation_id]
        
        if turn_id:
            where_clause += " AND turn_id = %s"
            params.append(turn_id)
        
        rows = db.fetch(f"""
            SELECT status, COUNT(*) as count
            FROM outbox_messages 
            {where_clause}
            GROUP BY status
            ORDER BY status
        """, params)
        
        stats = {row["status"]: row["count"] for row in rows}
        
        # Adiciona estatísticas zeradas para status ausentes
        for status in ["queued", "sent", "failed", "discarded"]:
            if status not in stats:
                stats[status] = 0
        
        return {
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "stats": stats,
            "total": sum(stats.values())
        }
        
    except Exception as e:
        logger.error(f"OUTBOX_STORE|stats_failed|conv={conversation_id}|turn={turn_id}|error={e}")
        return {"error": str(e)}