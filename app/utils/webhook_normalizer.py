"""
Webhook response normalizer to ensure type safety.
Prevents ResponseValidationError by normalizing all field types.
"""
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def normalize_webhook_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize webhook payload to ensure all types are correct.

    Critical normalizations:
    - sent: MUST be string "true"/"false", never boolean
    - confidence: float between 0.0 and 1.0
    - entities: dict, never list or None
    - intent: valid enum value or "fallback"
    - response_text: non-empty PT-BR string
    - routing_hint: valid string or None

    Args:
        payload: Raw payload that may have incorrect types

    Returns:
        Normalized payload with correct types
    """
    out = dict(payload or {})

    # CRITICAL: sent -> "true"/"false" string (never boolean!)
    sent_value = out.get("sent")
    if isinstance(sent_value, bool):
        out["sent"] = "true" if sent_value else "false"
    elif isinstance(sent_value, str):
        out["sent"] = "true" if sent_value.lower() == "true" else "false"
    elif isinstance(sent_value, (int, float)):
        out["sent"] = "true" if sent_value else "false"
    else:
        out["sent"] = "false"  # Default to false for any other type

    # confidence -> float [0.0, 1.0]
    try:
        confidence = float(out.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    out["confidence"] = max(0.0, min(1.0, confidence))

    # entities -> dict (never list or None)
    if not isinstance(out.get("entities"), dict):
        out["entities"] = {}

    # routing_hint -> str or None
    routing_hint = out.get("routing_hint")
    if routing_hint and isinstance(routing_hint, str):
        valid_hints = {"handle_price_objection", "ask_clarification", "handoff_human"}
        if routing_hint not in valid_hints:
            out["routing_hint"] = None
    else:
        out["routing_hint"] = None

    # intent -> valid enum or "fallback"
    valid_intents = {
        "greeting",
        "information_request",
        "qualification",
        "scheduling",
        "fallback",
        "objection",
    }
    intent = out.get("intent")
    if not intent or intent not in valid_intents:
        out["intent"] = "fallback"

    # response_text -> non-empty PT-BR string
    response_text = out.get("response_text")
    if not isinstance(response_text, str) or not response_text.strip():
        out[
            "response_text"
        ] = "Desculpe, tive um probleminha ao responder. Pode repetir, por favor?"

    # Ensure required fields exist
    if "message_id" not in out:
        out["message_id"] = "unknown"
    if "turn_id" not in out:
        out["turn_id"] = "turn_00000"
    if "trace_id" not in out:
        out["trace_id"] = "trace_00000"

    # Log normalization for debugging
    if sent_value != out["sent"]:
        logger.warning(
            f"NORMALIZER: sent field normalized from {type(sent_value).__name__} "
            f"{sent_value!r} to string {out['sent']!r}"
        )

    return out
