"""
Core Contracts for Kumon Assistant
Defines the interfaces between Intent Classifier, Delivery Service and other components.
"""

from typing import Any, Literal, Optional, TypedDict, List


class DeliveryPayload(TypedDict, total=False):
    """Payload for message delivery to channels"""
    channel: Literal["web", "app", "whatsapp"]
    content: dict[str, Any]  # texto+rich, já adaptado por canal
    attachments: List[dict[str, Any]]
    meta: dict[str, Any]


class DeliveryResult(TypedDict):
    """Result from message delivery attempt"""
    success: bool
    channel: str
    message_id: Optional[str]
    status: Literal["ok", "degraded", "failed"]
    reason: Optional[str]


class IntentResult(TypedDict, total=False):
    """Result from intent classification with delivery payload"""
    category: str
    confidence: float
    delivery_payload: Optional[DeliveryPayload]
    policy_action: Optional[str]
    slots: dict[str, Any]


def build_intent_result(
    category: str, 
    confidence: float, 
    channel: str, 
    content: dict[str, Any], 
    **kwargs
) -> IntentResult:
    """Build complete IntentResult with delivery payload"""
    return {
        "category": category,
        "confidence": confidence,
        "delivery_payload": {
            "channel": channel,
            "content": content,
            "attachments": kwargs.get("attachments", []),
            "meta": kwargs.get("meta", {})
        },
        "policy_action": kwargs.get("policy_action"),
        "slots": kwargs.get("slots", {})
    }