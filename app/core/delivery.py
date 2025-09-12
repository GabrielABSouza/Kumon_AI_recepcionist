"""
Simple ASYNCHRONOUS delivery service using Evolution API.
Sends text messages to WhatsApp using httpx.
"""
import json
import os
from typing import Any, Dict

import httpx  # Substitui o 'requests' para chamadas assíncronas

from .phone import format_e164

# A CORREÇÃO PRINCIPAL: A função agora é 'async def'
async def send_text(
    phone: str, text: str, instance: str = "recepcionistakumon"
) -> Dict[str, Any]:
    """
    Send text message via Evolution API asynchronously.

    Returns:
        Dict with keys:
        - sent: "true" or "false" (string)
        - status_code: HTTP status code (int)
        - error_reason: Optional error description (string or None)
    """
    result = {"sent": "false", "status_code": 0, "error_reason": None}

    if not text or not text.strip():
        print("DELIVERY|error|empty_text")
        result["error_reason"] = "empty_text"
        return result

    text = text.strip()
    if len(text) > 4096:
        print(f"DELIVERY|error|text_too_long|length={len(text)}")
        result["error_reason"] = "text_too_long"
        return result

    try:
        api_url = os.getenv("EVOLUTION_API_URL", "https://evo.whatlead.com.br")
        api_key = os.getenv("EVOLUTION_API_KEY")

        if not api_key:
            print("DELIVERY|error|missing_api_key")
            result["error_reason"] = "missing_api_key"
            return result

        try:
            e164_phone = format_e164(phone)
        except ValueError as e:
            print(f"DELIVERY|error|invalid_phone_format|phone={phone}|error={str(e)}")
            result["error_reason"] = "invalid_phone_format"
            return result

        url = f"{api_url}/message/sendText/{instance}"
        headers = {"apikey": api_key, "Content-Type": "application/json"}
        payload = {"number": e164_phone.lstrip("+"), "textMessage": {"text": text}}

        # A CORREÇÃO PRINCIPAL: Usa httpx.AsyncClient para a chamada de rede
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10.0)

        result["status_code"] = response.status_code

        if 200 <= response.status_code < 300:
            provider_id = ""
            try:
                if response.status_code != 204:
                    resp_body = response.json()
                    provider_id = resp_body.get("messageId", "") or resp_body.get(
                        "queueId", ""
                    )
            except Exception:
                pass

            print(
                f"DELIVERY|ok|status={response.status_code}|id={provider_id}|chars={len(text)}"
            )
            result["sent"] = "true"
            return result
        else:
            # Tratamento de erro continua o mesmo
            error_msg = response.text[:200]
            print(f"DELIVERY|error|status={response.status_code}|msg={error_msg}")
            result["error_reason"] = f"http_{response.status_code}"
            return result

    except httpx.TimeoutException:
        print("DELIVERY|error|timeout")
        result["error_reason"] = "timeout"
        return result
    except Exception as e:
        print(f"DELIVERY|error|exception={str(e)}")
        result["error_reason"] = str(e)
        return result