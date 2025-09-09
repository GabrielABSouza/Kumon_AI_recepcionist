"""
Webhook payload normalization utilities.
Ensures type safety and consistency in webhook response payloads.
"""
from typing import Any, Dict


def normalize_webhook_payload(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize webhook response payload to ensure type safety and consistency.

    Args:
        response: Raw response dictionary

    Returns:
        Normalized response dictionary with consistent types
    """
    return {
        "status": str(response.get("status", "unknown")),
        "message_id": str(response.get("message_id", "unknown")),
        "sent": str(response.get("sent", "false")).lower(),
        "response_text": str(response.get("response_text", "")),
        "intent": str(response.get("intent", "fallback")),
        "confidence": float(response.get("confidence", 0.0)),
        "entities": dict(response.get("entities", {})),
        "turn_id": str(response.get("turn_id", "turn_unknown")),
        "trace_id": str(response.get("trace_id", "trace_unknown")),
        "error_reason": str(response.get("error_reason", ""))
        if response.get("error_reason")
        else None,
        "reason": str(response.get("reason", "")) if response.get("reason") else None,
        "error": str(response.get("error", "")) if response.get("error") else None,
    }
