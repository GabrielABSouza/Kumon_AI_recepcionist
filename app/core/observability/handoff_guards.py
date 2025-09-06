# app/core/observability/handoff_guards.py
"""
Guards Críticos - Validação do Hand-off Planner→Delivery

Guards de segurança para garantir integridade do pipeline V2:
- Outbox hand-off validation (planner_count_after ≥ 1 AND delivery_count_before = 0 = CRITICAL)
- Instance resolution validation (thread_* ou "default" = CRITICAL) 
- State reference integrity validation
"""

import logging
from typing import Dict, Any
from .structured_logging import log_outbox_guard_critical, log_instance_guard_critical, validate_instance_pattern
from ...workflows.contracts import OUTBOX_KEY

logger = logging.getLogger(__name__)


class OutboxHandoffViolation(Exception):
    """Exceção crítica para violação de hand-off do outbox"""
    pass


class InstanceResolutionViolation(Exception):
    """Exceção crítica para padrão inválido de instância"""
    pass


def guard_outbox_handoff(planner_count_after: int, delivery_count_before: int, state: Dict[str, Any]) -> None:
    """
    Guard crítico: Valida hand-off Planner → Delivery
    
    CRITICAL VIOLATION: planner_count_after ≥ 1 E delivery_count_before = 0
    Indica que mensagens foram perdidas entre planner e delivery.
    
    Args:
        planner_count_after: Contagem de mensagens após planner
        delivery_count_before: Contagem de mensagens antes de delivery
        state: Estado da conversa
        
    Raises:
        OutboxHandoffViolation: Se violação crítica detectada
    """
    
    # Condição de violação crítica
    if planner_count_after >= 1 and delivery_count_before == 0:
        # Log estruturado para auditoria
        log_outbox_guard_critical(
            guard_type='handoff_violation',
            planner_after=planner_count_after,
            delivery_before=delivery_count_before,
            state=state
        )
        
        # Log adicional para debugging
        logger.error(
            f"CRITICAL OUTBOX HANDOFF VIOLATION DETECTED:\n"
            f"  Planner produced: {planner_count_after} messages\n"  
            f"  Delivery received: {delivery_count_before} messages\n"
            f"  State outbox length: {len(state.get(OUTBOX_KEY, []))}\n"
            f"  State outbox ID: {id(state.get(OUTBOX_KEY, []))}\n"
            f"  Conversation: {state.get('conversation_id', 'unknown')}"
        )
        
        # Interromper execução imediatamente
        raise OutboxHandoffViolation(
            f"CRITICAL outbox handoff violation: "
            f"planner_after={planner_count_after}, delivery_before={delivery_count_before}"
        )
    
    # Log aprovação se passou no guard
    logger.debug(f"OUTBOX_HANDOFF_GUARD_PASS: planner_after={planner_count_after}, delivery_before={delivery_count_before}")


def guard_instance_pattern(instance: str, state: Dict[str, Any]) -> None:
    """
    Guard crítico: Valida padrão de instância WhatsApp
    
    CRITICAL VIOLATION: Padrões inválidos thread_* ou "default"
    Estes padrões nunca devem ser usados em produção.
    
    Args:
        instance: Valor da instância para validar
        state: Estado da conversa
        
    Raises:
        InstanceResolutionViolation: Se padrão inválido detectado
    """
    
    if not validate_instance_pattern(instance):
        # Log estruturado para auditoria
        log_instance_guard_critical(instance, state)
        
        # Log adicional para debugging
        logger.error(
            f"CRITICAL INSTANCE PATTERN VIOLATION DETECTED:\n"
            f"  Instance value: '{instance}'\n"
            f"  Forbidden patterns: thread_*, default\n" 
            f"  Conversation: {state.get('conversation_id', 'unknown')}"
        )
        
        # Interromper execução imediatamente
        raise InstanceResolutionViolation(
            f"CRITICAL instance pattern violation: '{instance}' matches forbidden pattern"
        )
    
    # Log aprovação se passou no guard
    logger.debug(f"INSTANCE_PATTERN_GUARD_PASS: instance='{instance}'")


def guard_state_reference_integrity(state: Dict[str, Any], operation: str = "unknown") -> None:
    """
    Guard: Valida integridade de referência do state[OUTBOX_KEY]
    
    Verifica que state[OUTBOX_KEY] é sempre uma lista e nunca None.
    
    Args:
        state: Estado da conversa
        operation: Nome da operação para contexto de log
        
    Raises:
        ValueError: Se state[OUTBOX_KEY] não existe ou não é lista
    """
    
    if OUTBOX_KEY not in state:
        logger.error(f"STATE_REFERENCE_GUARD_FAIL: {OUTBOX_KEY} missing in state during {operation}")
        raise ValueError(f"State reference integrity violation: {OUTBOX_KEY} missing during {operation}")
    
    outbox = state[OUTBOX_KEY]
    if not isinstance(outbox, list):
        logger.error(f"STATE_REFERENCE_GUARD_FAIL: {OUTBOX_KEY} is {type(outbox)}, expected list during {operation}")
        raise ValueError(f"State reference integrity violation: {OUTBOX_KEY} is {type(outbox)}, expected list")
    
    # Log aprovação com ID da referência
    outbox_id = id(outbox)
    logger.debug(f"STATE_REFERENCE_GUARD_PASS: operation={operation}, outbox_id={outbox_id}, count={len(outbox)}")


def validate_planner_delivery_pipeline(state_before_planner: Dict[str, Any], 
                                     state_after_planner: Dict[str, Any],
                                     state_before_delivery: Dict[str, Any]) -> None:
    """
    Validação completa do pipeline Planner → Delivery
    
    Executa todos os guards críticos em sequência:
    1. Reference integrity em cada estágio
    2. Outbox handoff validation
    3. Instance pattern validation (se disponível)
    
    Args:
        state_before_planner: Estado antes do planner
        state_after_planner: Estado após planner  
        state_before_delivery: Estado antes do delivery
        
    Raises:
        OutboxHandoffViolation: Se hand-off inválido
        ValueError: Se integridade de referência violada
    """
    
    # Guard 1: Reference integrity
    guard_state_reference_integrity(state_before_planner, "before_planner")
    guard_state_reference_integrity(state_after_planner, "after_planner") 
    guard_state_reference_integrity(state_before_delivery, "before_delivery")
    
    # Guard 2: Outbox handoff
    planner_count_after = len(state_after_planner[OUTBOX_KEY])
    delivery_count_before = len(state_before_delivery[OUTBOX_KEY])
    
    guard_outbox_handoff(planner_count_after, delivery_count_before, state_before_delivery)
    
    # Guard 3: Instance validation (se mensagens existem)
    if delivery_count_before > 0:
        first_msg = state_before_delivery[OUTBOX_KEY][0]
        if isinstance(first_msg, dict):
            envelope_meta = first_msg.get("meta", {})
            instance = envelope_meta.get("instance")
            
            if instance:
                guard_instance_pattern(instance, state_before_delivery)
    
    logger.info(
        f"PIPELINE_GUARDS_PASS: planner_after={planner_count_after}, "
        f"delivery_before={delivery_count_before}, all guards passed"
    )