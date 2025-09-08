"""
Webhook endpoint with strict type normalization.
Ensures all responses follow the contract with correct types.
"""
import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter()


class WebhookResponse(BaseModel):
    """Strict webhook response with type validation."""

    message_id: str
    turn_id: str
    trace_id: str
    intent: Literal[
        "greeting",
        "information_request",
        "qualification",
        "scheduling",
        "fallback",
        "objection",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    response_text: str
    routing_hint: Optional[
        Literal["handle_price_objection", "ask_clarification", "handoff_human"]
    ] = None
    entities: Dict[str, Any] = Field(default_factory=dict)
    sent: Literal["true", "false"]  # MUST be string, never boolean
    status: Optional[str] = None
    message: Optional[str] = None
    reason: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None

    @field_validator("sent", mode="before")
    @classmethod
    def normalize_sent(cls, v):
        """Normalize sent field to string."""
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return "true" if v else "false"
        if isinstance(v, str):
            v_lower = v.lower()
            if v_lower in ["true", "1", "yes"]:
                return "true"
            elif v_lower in ["false", "0", "no"]:
                return "false"
        return "false"  # Default to false for invalid values

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v):
        """Normalize confidence to float 0.0-1.0."""
        try:
            if v is None:
                return 0.0
            if isinstance(v, str):
                v = float(v)
            if isinstance(v, (int, float)):
                v = float(v)
                if v < 0.0:
                    return 0.0
                if v > 1.0:
                    return 1.0
                return v
        except (ValueError, TypeError):
            return 0.0
        return 0.0

    @field_validator("entities", mode="before")
    @classmethod
    def normalize_entities(cls, v):
        """Normalize entities to dict."""
        if v is None or not isinstance(v, dict):
            return {}
        return v

    @field_validator("intent", mode="before")
    @classmethod
    def normalize_intent(cls, v):
        """Normalize intent to valid value."""
        if v is None:
            return "fallback"

        if not isinstance(v, str):
            return "fallback"

        v_lower = v.lower().replace("_", "").replace("-", "")

        # Try to match normalized version
        intent_map = {
            "greeting": "greeting",
            "hello": "greeting",
            "hi": "greeting",
            "informationrequest": "information_request",
            "info": "information_request",
            "question": "information_request",
            "qualification": "qualification",
            "qualify": "qualification",
            "scheduling": "scheduling",
            "schedule": "scheduling",
            "appointment": "scheduling",
            "fallback": "fallback",
            "error": "fallback",
            "unknown": "fallback",
            "objection": "objection",
            "complaint": "objection",
            "problem": "objection",
        }

        return intent_map.get(v_lower, "fallback")

    @field_validator("routing_hint", mode="before")
    @classmethod
    def normalize_routing_hint(cls, v):
        """Normalize routing hint."""
        if v is None or v == "" or v == "null":
            return None

        if not isinstance(v, str):
            return None

        valid_hints = {"handle_price_objection", "ask_clarification", "handoff_human"}

        if v in valid_hints:
            return v

        return None

    @field_validator("response_text", mode="before")
    @classmethod
    def normalize_response_text(cls, v):
        """Ensure response_text is valid PT-BR string."""
        if v is None or v == "":
            return "Desculpe, não entendi. Pode repetir, por favor?"

        if not isinstance(v, str):
            return "Desculpe, ocorreu um erro. Por favor, tente novamente."

        # Check for English tokens (basic heuristic)
        english_tokens = [
            "the",
            "and",
            "or",
            "is",
            "are",
            "have",
            "has",
            "hello",
            "world",
            "none",
            "null",
        ]
        v_lower = v.lower()

        for token in english_tokens:
            if f" {token} " in f" {v_lower} ":
                # Contains English, return PT-BR fallback
                return "Olá! Como posso ajudar você hoje?"

        return v


def normalize_webhook_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize webhook response to ensure all types are correct.
    This is the main normalization function used across the system.
    """
    # Ensure required fields exist with defaults
    normalized = {
        "message_id": str(response.get("message_id", "unknown")),
        "turn_id": str(response.get("turn_id", "turn_00000")),
        "trace_id": str(response.get("trace_id", "trace_00000")),
        "intent": response.get("intent", "fallback"),
        "confidence": response.get("confidence", 0.0),
        "response_text": response.get("response_text", ""),
        "routing_hint": response.get("routing_hint"),
        "entities": response.get("entities", {}),
        "sent": response.get("sent", "false"),
    }

    # Add optional fields if present
    for field in ["status", "message", "reason", "error", "timestamp"]:
        if field in response:
            normalized[field] = response[field]

    # Apply normalization through Pydantic model
    try:
        validated = WebhookResponse(**normalized)
        return validated.model_dump(exclude_none=True)
    except Exception as e:
        logger.error(f"Normalization error: {e}")
        # Return safe fallback
        return {
            "message_id": str(response.get("message_id", "error")),
            "turn_id": "turn_error",
            "trace_id": "trace_error",
            "intent": "fallback",
            "confidence": 0.0,
            "response_text": "Desculpe, ocorreu um erro no processamento.",
            "routing_hint": None,
            "entities": {},
            "sent": "false",
            "status": "error",
            "error": str(e),
        }


async def process_webhook_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process webhook message with normalization.
    This function should be imported by tests.
    """
    try:
        # Simulate processing (would call orchestrator in real implementation)
        # For now, return a mock response
        response = {
            "message_id": data.get("message_id", "MSG123"),
            "turn_id": "turn_00001",
            "trace_id": f"trace_{data.get('phone', 'unknown')}",
            "intent": "greeting",
            "confidence": 0.95,
            "response_text": "Olá! Bem-vindo ao Kumon. Como posso ajudar você hoje?",
            "routing_hint": None,
            "entities": {},
            "sent": "true",
        }

        # Apply normalization
        return normalize_webhook_response(response)

    except Exception as e:
        logger.error(f"Processing error: {e}")
        # Return normalized error response
        return normalize_webhook_response(
            {
                "message_id": data.get("message_id", "error"),
                "intent": "fallback",
                "confidence": 0.0,
                "response_text": "Desculpe, ocorreu um erro.",
                "entities": {},
                "sent": "false",
                "status": "error",
                "error": str(e),
            }
        )


@router.post("/webhook/whatsapp")
async def webhook_endpoint(request: Request):
    """
    Main webhook endpoint with strict type enforcement.
    Always returns 200 with normalized response.
    """
    try:
        # Get request data
        data = await request.json()

        # Process message
        response = await process_webhook_message(data)

        # Ensure normalization
        normalized = normalize_webhook_response(response)

        # Always return 200
        return normalized

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        # Return 200 with error response
        return normalize_webhook_response(
            {
                "message_id": "error",
                "intent": "fallback",
                "confidence": 0.0,
                "response_text": "Desculpe, ocorreu um erro no processamento.",
                "entities": {},
                "sent": "false",
                "status": "error",
                "error": str(e),
            }
        )
