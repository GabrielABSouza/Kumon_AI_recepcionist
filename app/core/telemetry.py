"""
Structured Telemetry System for Kumon Assistant
Implements telemetry with fields mínimos, PII protection, and sampling.
"""

import json
import time
import uuid
import hashlib
import traceback
import random
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Required telemetry fields
REQUIRED_FIELDS = {
    "trace_id", "ts", "node_id", "stage", "step", "channel", "duration_ms"
}

@dataclass
class TelemetryEvent:
    """Structured telemetry event with required fields"""
    trace_id: str
    ts: str
    node_id: str
    stage: str
    step: str
    channel: Literal["web", "app", "whatsapp"]
    duration_ms: float
    
    # Optional fields
    intent_id: Optional[str] = None
    policy_action: Optional[str] = None
    winning_rule: Optional[str] = None
    err_type: Optional[str] = None
    stack_hash: Optional[str] = None
    top2_margin: Optional[float] = None


def generate_trace_id() -> str:
    """Generate UUID v4 trace identifier"""
    return str(uuid.uuid4())


def now_utc_iso() -> str:
    """Generate UTC ISO 8601 timestamp"""
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


def sha1_hash(text: str) -> str:
    """Generate SHA1 hash of text"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def stack_hash() -> str:
    """Generate SHA1 hash of current stack trace"""
    tb = traceback.format_exc(limit=10)
    return sha1_hash(tb)


def should_sample(event_type: Literal["success", "error"] = "success") -> bool:
    """Determine if event should be sampled (1% success / 100% error)"""
    if event_type == "error":
        return True  # Always sample errors
    return random.random() < 0.01  # 1% sampling for success


def emit_telemetry_event(event: Dict[str, Any]) -> None:
    """
    Emit telemetry event with validation and PII protection
    
    Args:
        event: Telemetry event dict with required fields
        
    Raises:
        ValueError: If required fields are missing
    """
    # Validate required fields
    missing_fields = REQUIRED_FIELDS - set(event.keys())
    if missing_fields:
        raise ValueError(f"Telemetry missing required fields: {missing_fields}")
    
    # PII protection - mask sensitive data
    event = _mask_pii(event)
    
    # Sample based on event type
    event_type = "error" if event.get("err_type") else "success"
    if not should_sample(event_type):
        return
    
    # Output to structured logging (JSON Lines format)
    try:
        json_event = json.dumps(event, ensure_ascii=False)
        # In production, this would go to a structured log aggregator
        logger.info(f"TELEMETRY: {json_event}")
    except Exception as e:
        logger.error(f"Failed to emit telemetry: {e}")


def _mask_pii(event: Dict[str, Any]) -> Dict[str, Any]:
    """Mask PII from telemetry event"""
    # Create copy to avoid modifying original
    masked = event.copy()
    
    # Remove/mask sensitive fields that shouldn't be in telemetry
    sensitive_keys = ["phone_number", "parent_name", "child_name", "email", "message_text"]
    for key in sensitive_keys:
        if key in masked:
            del masked[key]
    
    # Hash user identifiers
    if "user_hash" in masked:
        masked["user_hash"] = sha1_hash(str(masked["user_hash"]))[:16]  # First 16 chars
    
    return masked


# Context manager for tracing operations
class TelemetryTracer:
    """Context manager for automatic telemetry emission"""
    
    def __init__(
        self, 
        node_id: str, 
        stage: str, 
        step: str, 
        channel: str,
        trace_id: Optional[str] = None
    ):
        self.node_id = node_id
        self.stage = stage
        self.step = step
        self.channel = channel
        self.trace_id = trace_id or generate_trace_id()
        self.start_time = time.time()
        self.event_data = {}
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        
        event = {
            "trace_id": self.trace_id,
            "ts": now_utc_iso(),
            "node_id": self.node_id,
            "stage": self.stage,
            "step": self.step,
            "channel": self.channel,
            "duration_ms": duration_ms,
            **self.event_data
        }
        
        # Add error information if exception occurred
        if exc_type:
            event.update({
                "err_type": exc_type.__name__,
                "stack_hash": stack_hash()
            })
        
        emit_telemetry_event(event)
    
    def add_data(self, **kwargs):
        """Add additional data to telemetry event"""
        self.event_data.update(kwargs)


# Convenience functions for common telemetry scenarios
def emit_intent_classification_event(
    trace_id: str,
    node_id: str,
    stage: str,
    step: str,
    channel: str,
    duration_ms: float,
    intent_id: str,
    confidence: float,
    winning_rule: Optional[str] = None,
    top2_margin: Optional[float] = None
):
    """Emit intent classification telemetry"""
    event = {
        "trace_id": trace_id,
        "ts": now_utc_iso(),
        "node_id": node_id,
        "stage": stage,
        "step": step,
        "channel": channel,
        "duration_ms": duration_ms,
        "intent_id": intent_id,
        "winning_rule": winning_rule,
        "top2_margin": top2_margin,
        "confidence": confidence
    }
    emit_telemetry_event(event)


def emit_delivery_event(
    trace_id: str,
    node_id: str,
    stage: str,
    step: str,
    channel: str,
    duration_ms: float,
    success: bool,
    message_id: Optional[str] = None,
    err_type: Optional[str] = None
):
    """Emit message delivery telemetry"""
    event = {
        "trace_id": trace_id,
        "ts": now_utc_iso(),
        "node_id": node_id,
        "stage": stage,
        "step": step,
        "channel": channel,
        "duration_ms": duration_ms,
        "delivery_success": success,
        "message_id": message_id
    }
    
    if not success and err_type:
        event["err_type"] = err_type
    
    emit_telemetry_event(event)


def emit_stage_transition_event(
    trace_id: str,
    from_stage: str,
    to_stage: str,
    from_step: str,
    to_step: str,
    channel: str,
    duration_ms: float,
    trigger: str
):
    """Emit stage transition telemetry"""
    event = {
        "trace_id": trace_id,
        "ts": now_utc_iso(),
        "node_id": f"transition_{from_stage}_to_{to_stage}",
        "stage": to_stage,
        "step": to_step,
        "channel": channel,
        "duration_ms": duration_ms,
        "from_stage": from_stage,
        "from_step": from_step,
        "transition_trigger": trigger
    }
    emit_telemetry_event(event)