"""
Outbox Contract - Unified message envelope for delivery pattern

This module defines the canonical outbox item structure used across
the entire pipeline to ensure proper message delivery.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import hashlib
import json


@dataclass
class OutboxItem:
    """
    Unified outbox item for consistent message delivery
    
    This is the SINGLE source of truth for outbox messages across:
    - ResponsePlanner (enqueues messages)
    - CeciliaState (carries messages)
    - DeliveryIO (consumes messages)
    """
    text: str
    channel: str = "whatsapp"
    meta: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
    
    def __post_init__(self):
        """Generate idempotency key if not provided"""
        if not self.idempotency_key and self.text:
            # Generate idempotency key from content hash
            base = f'{self.text}|{self.channel}|{json.dumps(self.meta, sort_keys=True)}'
            self.idempotency_key = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
        
        # Validate text is not empty
        if not self.text or not self.text.strip():
            raise ValueError("OutboxItem text cannot be empty")
        
        # Normalize text to remove template placeholders if any
        if "{{" in self.text and "}}" in self.text:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"OutboxItem contains unresolved template: {self.text[:50]}...")
            # Don't raise - normalize instead
            self.text = self.text.replace("{{", "").replace("}}", "")
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for storage in CeciliaState"""
        return {
            "text": self.text,
            "channel": self.channel,
            "meta": dict(self.meta),
            "idempotency_key": self.idempotency_key
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutboxItem":
        """Deserialize from dict with validation"""
        if not data.get("text"):
            raise ValueError("Invalid OutboxItem: text is required")
            
        return cls(
            text=data["text"],
            channel=data.get("channel", "whatsapp"),
            meta=data.get("meta", {}),
            idempotency_key=data.get("idempotency_key")
        )


def ensure_outbox(state: Dict[str, Any]) -> None:
    """
    Ensure outbox exists in state with proper structure
    
    Args:
        state: Conversation state to ensure outbox in
    """
    if "outbox" not in state:
        state["outbox"] = []
    elif not isinstance(state["outbox"], list):
        # Force to list if corrupted
        state["outbox"] = []


def enqueue_to_outbox(state: Dict[str, Any], item: OutboxItem) -> None:
    """
    Enqueue an item to the state's outbox with telemetry
    
    Args:
        state: Conversation state
        item: OutboxItem to enqueue
    """
    import logging
    logger = logging.getLogger(__name__)
    
    ensure_outbox(state)
    state["outbox"].append(item.to_dict())
    
    # OUTBOX_TRACE for planner phase
    logger.info(
        "OUTBOX_TRACE|phase=planner|conv=%s|idem=%s|state_id=%s|outbox_count=%d",
        state.get("conversation_id", "unknown"),
        item.idempotency_key,
        id(state),
        len(state["outbox"])
    )


def rehydrate_outbox_if_needed(state: Dict[str, Any]) -> None:
    """
    Rehydrate outbox from planner snapshot if delivery finds it empty
    
    This prevents the critical bug where outbox is lost between planner and delivery.
    
    Args:
        state: Conversation state to check and potentially rehydrate
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Check if we have a planner snapshot and current outbox is empty
    planner_snapshot = state.get("_planner_snapshot_outbox", [])
    current_outbox = state.get("outbox", [])
    
    if planner_snapshot and not current_outbox:
        logger.error(
            "OUTBOX_BRIDGE_DESYNC detected: restoring %d items from planner snapshot",
            len(planner_snapshot)
        )
        state["outbox"] = list(planner_snapshot)
        
        # Track this critical event
        state.setdefault("_outbox_desyncs", 0)
        state["_outbox_desyncs"] += 1