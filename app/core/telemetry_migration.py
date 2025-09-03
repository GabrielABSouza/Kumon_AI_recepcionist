# app/core/telemetry_migration.py
"""
Migration Telemetry - Structured Events Without PII

Implements JSON Lines telemetry for the new perception→decision→action→delivery architecture.
All events are structured and contain zero PII data.
"""

import json
import hashlib
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def generate_text_hash(text: str) -> str:
    """Generate SHA-256 hash of text for PII-free logging"""
    if not text:
        return "sha256:empty"
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"


def generate_trace_id() -> str:
    """Generate unique trace ID for request correlation"""
    timestamp = str(int(time.time() * 1000000))  # microsecond precision
    random_suffix = hashlib.sha256(timestamp.encode()).hexdigest()[:8]
    return f"trace_{random_suffix}"


def emit_telemetry_event(event_type: str, data: Dict[str, Any]) -> None:
    """
    Emit structured telemetry event as JSON Line
    
    Args:
        event_type: Type of event (stage_entered, router_decision, etc.)
        data: Event-specific data (must be PII-free)
    """
    
    try:
        event = {
            "evt": event_type,
            "ts": datetime.now(timezone.utc).isoformat(),
            **data
        }
        
        # JSON Line format for structured logging
        logger.info(json.dumps(event, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"Telemetry emission failed: {e}")


def emit_stage_entered(trace_id: str, session_id: str, node_id: str, stage: str) -> None:
    """Emit stage_entered event"""
    emit_telemetry_event("stage_entered", {
        "trace_id": trace_id,
        "session_id": session_id,
        "node_id": node_id,
        "stage": stage
    })


def emit_router_decision(
    trace_id: str, 
    session_id: str, 
    node_id: str,
    threshold_action: str,
    confidence_scores: Dict[str, float],
    user_text: str
) -> None:
    """Emit router_decision event with confidence scores"""
    emit_telemetry_event("router_decision", {
        "trace_id": trace_id,
        "session_id": session_id,
        "node_id": node_id,
        "route_hint": threshold_action,
        "scores": confidence_scores,
        "text_hash": generate_text_hash(user_text)
    })


def emit_planner_enqueued(
    trace_id: str,
    session_id: str, 
    node_id: str,
    mode: str,
    message_count: int
) -> None:
    """Emit planner_enqueued event"""
    emit_telemetry_event("planner_enqueued", {
        "trace_id": trace_id,
        "session_id": session_id,
        "node_id": node_id,
        "mode": mode,
        "messages": message_count
    })


def emit_delivery_emitted(
    trace_id: str,
    session_id: str,
    node_id: str, 
    channel: str,
    emitted_count: int
) -> None:
    """Emit delivery_emitted event"""
    emit_telemetry_event("delivery_emitted", {
        "trace_id": trace_id,
        "session_id": session_id, 
        "node_id": node_id,
        "channel": channel,
        "count": emitted_count
    })


# ========== INSTRUMENTATION DECORATORS ==========

def instrument_stage_resolver(func):
    """Decorator to instrument StageResolver node"""
    def wrapper(state: Dict[str, Any], *args, **kwargs):
        trace_id = state.setdefault("_trace_id", generate_trace_id())
        session_id = state.get("session_id", "unknown")
        
        result = func(state, *args, **kwargs)
        
        # Emit stage_entered event
        stage = result.get("current_stage", "unknown")
        emit_stage_entered(trace_id, session_id, "STAGE_RESOLVER", stage)
        
        return result
    return wrapper


def instrument_smart_router(func):
    """Decorator to instrument SmartRouter node"""
    def wrapper(state: Dict[str, Any], *args, **kwargs):
        trace_id = state.setdefault("_trace_id", generate_trace_id())
        session_id = state.get("session_id", "unknown")
        user_text = state.get("last_user_message", "")
        
        result = func(state, *args, **kwargs)
        
        # Emit router_decision event
        routing_decision = result.get("routing_decision", {})
        threshold_action = routing_decision.get("threshold_action", "unknown")
        
        confidence_scores = {
            "intent": routing_decision.get("intent_confidence", 0.0),
            "pattern": routing_decision.get("pattern_confidence", 0.0),  
            "final": routing_decision.get("final_confidence", 0.0)
        }
        
        emit_router_decision(
            trace_id, session_id, "SMART_ROUTER",
            threshold_action, confidence_scores, user_text
        )
        
        return result
    return wrapper


def instrument_response_planner(func):
    """Decorator to instrument ResponsePlanner node"""
    def wrapper(state: Dict[str, Any], *args, **kwargs):
        trace_id = state.setdefault("_trace_id", generate_trace_id())
        session_id = state.get("session_id", "unknown")
        
        outbox_before = len(state.get("outbox", []))
        result = func(state, *args, **kwargs)
        outbox_after = len(result.get("outbox", []))
        
        messages_added = outbox_after - outbox_before
        
        # Determine mode from routing_decision
        routing_decision = state.get("routing_decision", {})
        threshold_action = routing_decision.get("threshold_action", "unknown")
        
        # Map threshold_action to planner mode
        mode_mapping = {
            "proceed": "template",
            "enhance_with_llm": "llm_rag",
            "escalate_human": "handoff", 
            "fallback_level1": "fallback_l1",
            "fallback_level2": "fallback_l2"
        }
        mode = mode_mapping.get(threshold_action, "unknown")
        
        # Emit planner_enqueued event
        emit_planner_enqueued(trace_id, session_id, "RESPONSE_PLANNER", mode, messages_added)
        
        return result
    return wrapper


def instrument_delivery(func):
    """Decorator to instrument Delivery node"""
    def wrapper(state: Dict[str, Any], *args, **kwargs):
        trace_id = state.setdefault("_trace_id", generate_trace_id())
        session_id = state.get("session_id", "unknown")
        
        result = func(state, *args, **kwargs)
        
        # Get delivery stats
        delivery_status = result.get("_delivery_status", {})
        emitted_count = delivery_status.get("messages_emitted", 0)
        
        # Determine primary channel (most common in emitted messages)
        # For simplicity, use default channel
        channel = state.get("default_channel", "whatsapp")
        
        # Emit delivery_emitted event
        if emitted_count > 0:
            emit_delivery_emitted(trace_id, session_id, "DELIVERY", channel, emitted_count)
        
        return result
    return wrapper


# ========== INSTRUMENTED NODE WRAPPERS ==========

def create_instrumented_nodes():
    """
    Create instrumented versions of workflow nodes
    
    Returns:
        dict: Mapping of node names to instrumented functions
    """
    from .nodes.stage_resolver import stage_resolver_node
    from .router.delivery_io import smart_router_node, delivery_node
    from .router.response_planner import response_planner_node
    
    return {
        "STAGE_RESOLVER": instrument_stage_resolver(stage_resolver_node),
        "SMART_ROUTER": instrument_smart_router(smart_router_node),
        "RESPONSE_PLANNER": instrument_response_planner(response_planner_node), 
        "DELIVERY": instrument_delivery(delivery_node)
    }