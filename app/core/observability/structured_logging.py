# app/core/observability/structured_logging.py
"""
Observabilidade Estruturada - Logs estruturados para auditoria grep/jq

Padrões exatos conforme especificação:
- OUTBOX_TRACE|phase={planner|delivery}|conv={id}|idem={key}|state_id={id}|outbox_id={id}|count={n}
- INSTANCE_TRACE|source={meta|channel|state|error}|instance={value}|conv={id}|idem={key}
- DELIVERY_TRACE|action={send|result}|status={success|failed}|http={code}|instance={instance}|conv={id}|idem={key}
- OUTBOX_GUARD|level=CRITICAL|type=handoff_violation|planner_after={N}|delivery_before={M}|conv={id}|idem={key}
- INSTANCE_GUARD|level=CRITICAL|type=invalid_pattern|value={instance}|conv={id}|idem={key}
"""

import logging
import re
from typing import Dict, Any, Optional
from ...workflows.contracts import OUTBOX_KEY

logger = logging.getLogger(__name__)

# Regex patterns for instance validation
INVALID_INSTANCE_PATTERNS = [
    r'^thread_\d+$',    # thread_123
    r'^default$'        # default
]

def get_trace_context(state: Dict[str, Any]) -> Dict[str, str]:
    """Extract common trace context from state"""
    return {
        'conv': state.get('conversation_id', state.get('session_id', 'unknown')),
        'idem': state.get('idempotency_key', 'unknown'),
        'state_id': str(id(state)),
        'outbox_id': str(id(state.get(OUTBOX_KEY))) if OUTBOX_KEY in state else 'MISSING'
    }

def log_outbox_trace(phase: str, state: Dict[str, Any]) -> None:
    """
    Log OUTBOX_TRACE para auditoria de hand-off
    
    Args:
        phase: 'planner' ou 'delivery'
        state: Estado da conversa
    """
    ctx = get_trace_context(state)
    count = len(state.get(OUTBOX_KEY, []))
    
    logger.info(
        f"OUTBOX_TRACE|phase={phase}|conv={ctx['conv']}|idem={ctx['idem']}|"
        f"state_id={ctx['state_id']}|outbox_id={ctx['outbox_id']}|count={count}"
    )

def log_instance_trace(source: str, instance: str, state: Dict[str, Any], error: Optional[str] = None) -> None:
    """
    Log INSTANCE_TRACE para resolução de instância WhatsApp
    
    Args:
        source: 'meta', 'channel', 'state', ou 'error'
        instance: Valor da instância ou mensagem de erro
        state: Estado da conversa
        error: Mensagem de erro opcional
    """
    ctx = get_trace_context(state)
    instance_value = error if error else instance
    
    logger.info(
        f"INSTANCE_TRACE|source={source}|instance={instance_value}|"
        f"conv={ctx['conv']}|idem={ctx['idem']}"
    )

def log_delivery_trace_send(instance: str, phone: str, state: Dict[str, Any]) -> None:
    """
    Log DELIVERY_TRACE para tentativa de envio
    
    Args:
        instance: Instância WhatsApp usada
        phone: Número de telefone
        state: Estado da conversa
    """
    ctx = get_trace_context(state)
    
    logger.info(
        f"DELIVERY_TRACE|action=send|instance={instance}|phone={phone}|"
        f"conv={ctx['conv']}|idem={ctx['idem']}"
    )

def log_delivery_trace_result(status: str, http_code: Optional[int], instance: str, state: Dict[str, Any]) -> None:
    """
    Log DELIVERY_TRACE para resultado de envio
    
    Args:
        status: 'success' ou 'failed'
        http_code: Código HTTP da resposta
        instance: Instância WhatsApp usada
        state: Estado da conversa
    """
    ctx = get_trace_context(state)
    http_str = str(http_code) if http_code is not None else 'unknown'
    
    logger.info(
        f"DELIVERY_TRACE|action=result|status={status}|http={http_str}|"
        f"instance={instance}|conv={ctx['conv']}|idem={ctx['idem']}"
    )

def log_outbox_guard_critical(guard_type: str, planner_after: Optional[int] = None, 
                             delivery_before: Optional[int] = None, state: Dict[str, Any] = None) -> None:
    """
    Log OUTBOX_GUARD para violações críticas
    
    Args:
        guard_type: Tipo de violação ('handoff_violation')
        planner_after: Contagem após planner (para handoff_violation)
        delivery_before: Contagem antes delivery (para handoff_violation)  
        state: Estado da conversa
    """
    ctx = get_trace_context(state) if state else {'conv': 'unknown', 'idem': 'unknown'}
    
    if guard_type == 'handoff_violation':
        logger.error(
            f"OUTBOX_GUARD|level=CRITICAL|type=handoff_violation|"
            f"planner_after={planner_after}|delivery_before={delivery_before}|"
            f"conv={ctx['conv']}|idem={ctx['idem']}"
        )
    else:
        logger.error(
            f"OUTBOX_GUARD|level=CRITICAL|type={guard_type}|"
            f"conv={ctx['conv']}|idem={ctx['idem']}"
        )

def log_instance_guard_critical(instance_value: str, state: Dict[str, Any]) -> None:
    """
    Log INSTANCE_GUARD para padrões inválidos de instância
    
    Args:
        instance_value: Valor da instância inválida
        state: Estado da conversa
    """
    ctx = get_trace_context(state)
    
    logger.error(
        f"INSTANCE_GUARD|level=CRITICAL|type=invalid_pattern|"
        f"value={instance_value}|conv={ctx['conv']}|idem={ctx['idem']}"
    )

def validate_instance_pattern(instance: str) -> bool:
    """
    Valida se instância segue padrões válidos (NUNCA thread_* ou default)
    
    Args:
        instance: Valor da instância
        
    Returns:
        bool: True se válida, False se inválida
    """
    if not instance:
        return False
    
    for pattern in INVALID_INSTANCE_PATTERNS:
        if re.match(pattern, instance):
            return False
    
    return True

def ensure_state_reference_integrity(state: Dict[str, Any]) -> None:
    """
    Garantir que state[OUTBOX_KEY] é sempre a mesma referência
    
    Args:
        state: Estado da conversa (modificado in-place)
    """
    if OUTBOX_KEY not in state:
        state[OUTBOX_KEY] = []
    elif not isinstance(state[OUTBOX_KEY], list):
        # Force lista se for outro tipo
        state[OUTBOX_KEY] = []
    
    # Log da identidade do objeto para auditoria
    outbox_id = id(state[OUTBOX_KEY])
    logger.debug(f"STATE_REFERENCE|outbox_id={outbox_id}|type={type(state[OUTBOX_KEY]).__name__}")

def audit_outbox_handoff(planner_count_after: int, delivery_count_before: int, state: Dict[str, Any]) -> None:
    """
    Auditoria crítica do hand-off Planner → Delivery
    
    Falha crítica se:
    - planner_count_after >= 1 E delivery_count_before = 0
    
    Args:
        planner_count_after: Contagem após planner
        delivery_count_before: Contagem antes delivery
        state: Estado da conversa
    """
    # Condição de violação crítica
    if planner_count_after >= 1 and delivery_count_before == 0:
        log_outbox_guard_critical(
            guard_type='handoff_violation',
            planner_after=planner_count_after,
            delivery_before=delivery_count_before,
            state=state
        )
        
        # Lança exceção para interromper execução
        raise RuntimeError(
            f"CRITICAL outbox handoff violation detected: "
            f"planner_after={planner_count_after}, delivery_before={delivery_count_before}"
        )

def resolve_whatsapp_instance(envelope_meta: Dict[str, Any], state: Dict[str, Any]) -> str:
    """
    Resolução determinística de instância WhatsApp com hierarchy canônica e observabilidade
    
    Ordem canônica:
    1. envelope.meta["instance"]  
    2. state["channel"]["instance"]
    3. state["instance"]
    4. FAIL-SAFE (nunca default/thread_*)
    
    Args:
        envelope_meta: Metadados do envelope
        state: Estado da conversa
        
    Returns:
        str: Instância resolvida
        
    Raises:
        ValueError: Se nenhuma instância válida encontrada
    """
    
    # Priority 1: envelope.meta["instance"]
    if envelope_meta.get("instance"):
        instance = envelope_meta["instance"]
        if validate_instance_pattern(instance):
            log_instance_trace("meta", instance, state)
            return instance
        else:
            log_instance_guard_critical(instance, state)
            log_instance_trace("error", f"invalid_pattern_{instance}", state)
    
    # Priority 2: state["channel"]["instance"]
    channel_config = state.get("channel", {})
    if isinstance(channel_config, dict) and channel_config.get("instance"):
        instance = channel_config["instance"]
        if validate_instance_pattern(instance):
            log_instance_trace("channel", instance, state)
            return instance
        else:
            log_instance_guard_critical(instance, state)
            log_instance_trace("error", f"invalid_pattern_{instance}", state)
    
    # Priority 3: state["instance"]
    if state.get("instance"):
        instance = state["instance"]
        if validate_instance_pattern(instance):
            log_instance_trace("state", instance, state)
            return instance
        else:
            log_instance_guard_critical(instance, state)
            log_instance_trace("error", f"invalid_pattern_{instance}", state)
    
    # FAIL-SAFE: Nenhuma instância válida encontrada
    log_instance_trace("error", "no_valid_instance_found", state)
    raise ValueError("WhatsApp instance resolution failed: no valid instance found in canonical hierarchy")

# Função auxiliar para testes
def extract_trace_fields(log_line: str) -> Dict[str, str]:
    """
    Extrai campos de linha de log estruturada para testes
    
    Args:
        log_line: Linha de log estruturada
        
    Returns:
        dict: Campos extraídos
    """
    if '|' not in log_line:
        return {}
    
    parts = log_line.split('|')
    fields = {}
    
    for part in parts:
        if '=' in part:
            key, value = part.split('=', 1)
            fields[key] = value
    
    return fields