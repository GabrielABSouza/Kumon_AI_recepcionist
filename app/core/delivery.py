"""
Simple delivery service using Evolution API.
Sends text messages to WhatsApp.
"""
import json
import os
from typing import Any, Dict

import requests

from .phone import format_e164


def send_text(
    phone: str, text: str, instance: str = "recepcionistakumon"
) -> Dict[str, Any]:
    """
    Send text message via Evolution API.

    Returns:
        Dict with keys:
        - sent: "true" or "false" (string)
        - status_code: HTTP status code (int)
        - error_reason: Optional error description (string or None)
    """
    result = {"sent": "false", "status_code": 0, "error_reason": None}

    # Validate text input
    if not text or not text.strip():
        print("DELIVERY|error|empty_text")
        result["error_reason"] = "empty_text"
        return result

    # Strip and check length
    text = text.strip()
    if len(text) > 4096:
        print(f"DELIVERY|error|text_too_long|length={len(text)}")
        result["error_reason"] = "text_too_long"
        return result

    try:
        # Get Evolution API config from environment
        api_url = os.getenv("EVOLUTION_API_URL", "https://evo.whatlead.com.br")
        api_key = os.getenv("EVOLUTION_API_KEY")

        if not api_key:
            print("DELIVERY|error|missing_api_key")
            result["error_reason"] = "missing_api_key"
            return result

        # Format phone to E.164
        try:
            e164_phone = format_e164(phone)
        except ValueError as e:
            print(f"DELIVERY|error|invalid_phone_format|phone={phone}|error={str(e)}")
            result["error_reason"] = "invalid_phone_format"
            return result

        # Build request
        url = f"{api_url}/message/sendText/{instance}"
        headers = {"apikey": api_key, "Content-Type": "application/json"}

        # Evolution API expects EXACT format with textMessage
        payload = {"number": e164_phone.lstrip("+"), "textMessage": {"text": text}}

        # Debug log payload (without PII)
        if os.getenv("DEBUG_DELIVERY") == "true":
            print(
                f"DELIVERY|debug|payload_keys={list(payload.keys())}|text_len={len(text)}"
            )

        # Send request
        response = requests.post(url, json=payload, headers=headers, timeout=5)

        result["status_code"] = response.status_code

        # Accept any 2xx as success
        if 200 <= response.status_code < 300:
            # Try to extract messageId/queueId from response
            provider_id = ""
            try:
                if response.status_code != 204:  # 204 has no content
                    resp_body = response.json()
                    provider_id = resp_body.get("messageId", "") or resp_body.get(
                        "queueId", ""
                    )
            except Exception:
                pass  # Ignore JSON parse errors for 2xx

            print(
                f"DELIVERY|ok|status={response.status_code}|id={provider_id}|chars={len(text)}"
            )
            result["sent"] = "true"
            result["provider_status"] = str(response.status_code)
            result["provider_id"] = provider_id
            return result
        elif response.status_code == 400:
            # Parse error from response body
            try:
                error_body = response.json()
                error_code = error_body.get("error", "unknown")
                error_msg = error_body.get("message", "")
                body_str = json.dumps(error_body)
            except Exception:
                error_code = "parse_error"
                error_msg = response.text[:200]
                body_str = response.text[:500]

            # Log with full details for 400 errors
            print(
                f"DELIVERY|error|status=400|code={error_code}|msg={error_msg}|body={body_str}"
            )
            result["error_reason"] = error_code
            # No retry for 400 errors
            return result
        else:
            print(f"DELIVERY|error|status={response.status_code}")
            result["error_reason"] = f"http_{response.status_code}"
            return result

    except requests.exceptions.Timeout:
        print("DELIVERY|error|timeout")
        result["error_reason"] = "timeout"
        return result
    except Exception as e:
        print(f"DELIVERY|error|exception={str(e)}")
        result["error_reason"] = str(e)
        return result
