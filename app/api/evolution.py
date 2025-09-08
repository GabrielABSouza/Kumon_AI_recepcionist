"""
Minimal Evolution API webhook handler.
Receives WhatsApp messages and triggers ONE_TURN flow.
"""
from typing import Dict

from fastapi import APIRouter, Request

from app.core import langgraph_flow
from app.core.dedup import turn_controller

router = APIRouter()


@router.post("/webhook")
async def webhook(request: Request) -> Dict[str, str]:
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
            return {"status": "ignored", "reason": "from_me"}

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
            return {"status": "ignored", "reason": "no_text"}

        # Get instance name
        instance = body.get("instance", "recepcionistakumon")

        print(f"WEBHOOK|received|message_id={message_id}|phone=****{phone[-4:]}")

        # Start turn (deduplication)
        if not turn_controller.start_turn(message_id):
            print(f"PIPELINE|turn_duplicate|message_id={message_id}")
            return {"status": "duplicate", "message_id": message_id}

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

        return {
            "status": "processed",
            "message_id": message_id,
            "sent": result.get("sent", False),
        }

    except Exception as e:
        print(f"WEBHOOK|error|exception={str(e)}")
        return {"status": "error", "error": str(e)}
