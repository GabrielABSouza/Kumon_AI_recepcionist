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

        # Extract message data with type safety
        data = body.get("data", {})

        # Ensure data is a dict, handle Evolution API sending lists
        if not isinstance(data, dict):
            print(f"WEBHOOK|skip|data_type={type(data).__name__}")
            response = {
                "status": "ignored",
                "reason": "invalid_data_type",
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

        # Check if it's a received message (not from me)
        key = data.get("key", {})
        if not isinstance(key, dict):
            key = {}
        if key.get("fromMe", False):
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

        # Extract message details with type safety
        message_id = key.get("id", "")
        remote_jid = key.get("remoteJid", "")
        phone = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid

        # Get message text with type safety
        message = data.get("message", {})
        if not isinstance(message, dict):
            message = {}

        # Extract text content safely
        text = ""
        if isinstance(message.get("conversation"), str):
            text = message.get("conversation")
        elif isinstance(message.get("extendedTextMessage"), dict):
            extended = message.get("extendedTextMessage", {})
            if isinstance(extended.get("text"), str):
                text = extended.get("text")

        text = text.strip()

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

        # Build state for LangGraph with all required fields initialized
        state = {
            "phone": phone,
            "message_id": message_id,
            "text": text,
            "instance": instance,
            # ARCHITECTURAL FIX: Initialize collected_data at the source
            "collected_data": {},
        }

        # DEBUG: Log state before LangGraph execution
        print(f"DEBUG|before_langgraph|state_keys={list(state.keys())}")
        print(f"DEBUG|before_langgraph|text='{state.get('text')}'")
        print(f"DEBUG|before_langgraph|phone={state.get('phone')}")

        # Run the ONE_TURN flow asynchronously
        result = await langgraph_flow.run(state)

        # DEBUG: Log result after LangGraph execution
        print(f"DEBUG|after_langgraph|result_keys={list(result.keys())}")
        print(
            f"DEBUG|after_langgraph|response='{result.get('response', 'NO_RESPONSE')}'"
        )
        print(f"DEBUG|after_langgraph|sent={result.get('sent', 'NO_SENT')}")
        print(
            f"DEBUG|after_langgraph|response_length={len(str(result.get('response', '')))}"
        )

        # Mark as replied if any message was sent during the flow
        # This centralized approach prevents multi-node flows from being interrupted
        if result.get("sent") == "true":
            turn_controller.mark_replied(message_id)
            print(f"PIPELINE|turn_replied|message_id={message_id}")

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
