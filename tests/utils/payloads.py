"""
Utility functions to create test payloads and headers.
"""
from typing import Any, Dict, Optional


def make_webhook_payload(
    text: str = "oi",
    message_id: str = "3A123",
    phone: str = "555199999999",
    from_me: bool = False,
    type: str = "text",
    caption: Optional[str] = None,
    instance: str = "recepcionistakumon",
) -> Dict[str, Any]:
    """
    Create a webhook payload mimicking Evolution API format.
    """
    # Build message object based on type
    message: Dict[str, Any]
    if type == "text":
        message = {"conversation": text}
    elif type == "image":
        message = {"imageMessage": {"caption": caption or ""}}
    elif type == "video":
        message = {"videoMessage": {"caption": caption or ""}}
    elif type == "audio":
        message = {"audioMessage": {}}
    else:
        message = {"extendedTextMessage": {"text": text}}

    payload = {
        "event": "messages.upsert",
        "instance": instance,
        "data": {
            "key": {
                "id": message_id,
                "fromMe": from_me,
                "remoteJid": f"{phone}@s.whatsapp.net",
            },
            "message": message,
            "pushName": "Test User",
            "messageTimestamp": "1700000000",
        },
    }

    return payload


def evolution_headers_ok() -> Dict[str, str]:
    """
    Return valid headers that should pass authentication.
    Railway/Evolution typical headers.
    """
    return {
        "x-railway-edge": "true",
        "x-forwarded-for": "1.2.3.4",
        "x-forwarded-host": "kumonvilaa-staging.up.railway.app",
        "x-forwarded-proto": "https",
        "content-type": "application/json",
        "user-agent": "evolution-webhook/1.0",
        "x-evolution-instance": "recepcionistakumon",
        "authorization": "Bearer test-token",
    }


def evolution_headers_missing() -> Dict[str, str]:
    """
    Return empty headers (should fail authentication).
    """
    return {}


def evolution_headers_suspicious() -> Dict[str, str]:
    """
    Return suspicious headers that might indicate spoofing.
    """
    return {
        "content-type": "application/json",
        "user-agent": "curl/7.64.1",
        "x-forwarded-for": "127.0.0.1",
    }
