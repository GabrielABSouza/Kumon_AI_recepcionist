"""
Minimal Evolution API webhook handler.
Receives WhatsApp messages and triggers ONE_TURN flow.
"""
from typing import Any, Dict

from fastapi import APIRouter, Request

from app.core import langgraph_flow
from app.core.dedup import turn_controller
from app.utils.webhook_normalizer import normalize_webhook_payload

router = APIRouter()


@router.post("/webhook")
async def webhook(request: Request) -> Dict[str, Any]:
    """
    Receive webhook from Evolution API.
    Process ONE message → ONE response → END.
    """
    try:
        # Parse webhook payload
        body = await request.json()

        # Extract message data
        data = body.get("data", {})

        # Check if it's a received message (not from me)
        if data.get("key", {}).get("fromMe", True):
            print("WEBHOOK|skip|from_me=true")
            response = {
                "status": "ignored",
                "reason": "from_me",
                "sent": "false",
                "message_id": "unknown",
                "turn_id": "turn_00000",
                "trace_id": "trace_00000",
                "intent": "fallback",
                "confidence": 0.0,
                "response_text": "",
                "entities": {},
            }
            return normalize_webhook_payload(response)

        # Extract message details
        message_id = data.get("key", {}).get("id", "")
        remote_jid = data.get("key", {}).get("remoteJid", "")
        phone = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid

        # Get message text
        message = data.get("message", {})
        text = (
            message.get("conversation")
            or message.get("extendedTextMessage", {}).get("text")
            or ""
        ).strip()

        # Skip if no text
        if not text:
            print("WEBHOOK|skip|no_text")
            response = {
                "status": "ignored",
                "reason": "no_text",
                "sent": "false",
                "message_id": message_id or "unknown",
                "turn_id": f"turn_{message_id or '00000'}",
                "trace_id": f"trace_{message_id or '00000'}",
                "intent": "fallback",
                "confidence": 0.0,
                "response_text": "",
                "entities": {},
            }
            return normalize_webhook_payload(response)

        # Get instance name
        instance = body.get("instance", "recepcionistakumon")

        print(f"WEBHOOK|received|message_id={message_id}|phone=****{phone[-4:]}")

        # Start turn (deduplication)
        if not turn_controller.start_turn(message_id):
            print(f"PIPELINE|turn_duplicate|message_id={message_id}")
            response = {
                "status": "duplicate",
                "message_id": message_id,
                "sent": "false",
                "turn_id": f"turn_{message_id}",
                "trace_id": f"trace_{message_id}",
                "intent": "fallback",
                "confidence": 0.0,
                "response_text": "",
                "entities": {},
            }
            return normalize_webhook_payload(response)

        print(f"PIPELINE|turn_start|message_id={message_id}")

        # Build state for LangGraph
        state = {
            "phone": phone,
            "message_id": message_id,
            "text": text,
            "instance": instance,
        }

        # Run the ONE_TURN flow
        result = langgraph_flow.run(state)

        # End turn
        turn_controller.end_turn(message_id)
        print(f"PIPELINE|turn_end|message_id={message_id}")

        # Build response payload
        response = {
            "status": "processed",
            "message_id": message_id,
            "sent": result.get("sent", False),
            "response_text": result.get("response", ""),
            "intent": result.get("intent", "fallback"),
            "confidence": result.get("confidence", 0.0),
            "entities": result.get("entities", {}),
            "turn_id": f"turn_{message_id}",
            "trace_id": f"trace_{message_id}",
            "error_reason": result.get("error_reason"),
        }

        # CRITICAL: Normalize response to ensure type safety
        normalized_response = normalize_webhook_payload(response)

        return normalized_response

    except Exception as e:
        print(f"WEBHOOK|error|exception={str(e)}")
        response = {
            "status": "error",
            "error": str(e),
            "sent": "false",
            "message_id": "unknown",
            "turn_id": "turn_error",
            "trace_id": "trace_error",
            "intent": "fallback",
            "confidence": 0.0,
            "response_text": "Desculpe, ocorreu um erro ao processar sua mensagem.",
            "entities": {},
        }
        return normalize_webhook_payload(response)
