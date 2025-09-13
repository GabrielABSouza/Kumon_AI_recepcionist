"""
Robust ASYNCHRONOUS delivery service using Evolution API.
Sends text messages to WhatsApp using httpx with retries, timeouts and detailed logging.
"""
import json
import logging
import os
from typing import Any, Dict
import asyncio

import httpx
from httpx import Timeout

from .phone import format_e164

log = logging.getLogger(__name__)

def _mask_token(token: str) -> str:
    """Mask API token for logging - shows first 8 and last 4 chars"""
    if not token or len(token) < 12:
        return "***masked***"
    return f"{token[:8]}...{token[-4:]}"


async def _build_client(max_retries: int, timeout_seconds: float) -> httpx.AsyncClient:
    """Build httpx client with retry configuration"""
    timeout = Timeout(timeout_seconds, connect=timeout_seconds, read=timeout_seconds)
    
    # Create transport with retries
    transport = httpx.AsyncHTTPTransport(retries=max_retries)
    
    return httpx.AsyncClient(
        timeout=timeout,
        transport=transport,
        follow_redirects=True
    )


async def send_text(
    phone: str, text: str, instance: str = "recepcionistakumon"
) -> Dict[str, Any]:
    """
    Send text message via Evolution API asynchronously with retries and robust error handling.

    Args:
        phone: Target phone number 
        text: Message text
        instance: Evolution API instance name

    Returns:
        Dict with keys:
        - sent: "true" or "false" (string)
        - status_code: HTTP status code (int) 
        - error_reason: Optional error description (string or None)
    """
    # Load configuration from environment
    base_url = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
    api_key = os.getenv("EVOLUTION_API_KEY", "")
    timeout_seconds = float(os.getenv("EVOLUTION_API_TIMEOUT_SECONDS", "8"))
    max_retries = int(os.getenv("EVOLUTION_API_MAX_RETRIES", "3"))
    backoff = float(os.getenv("EVOLUTION_API_RETRY_BACKOFF", "0.5"))
    
    result = {"sent": "false", "status_code": 0, "error_reason": None}

    # Input validation
    if not text or not text.strip():
        log.warning("DELIVERY|error|empty_text")
        result["error_reason"] = "empty_text"
        return result

    text = text.strip()
    if len(text) > 4096:
        log.warning("DELIVERY|error|text_too_long|length=%d", len(text))
        result["error_reason"] = "text_too_long"
        return result

    # Configuration validation
    if not base_url:
        log.error("DELIVERY|error|missing_evolution_api_url - EVOLUTION_API_URL não definida em .env-dev")
        result["error_reason"] = "missing_evolution_api_url"
        return result

    if not api_key:
        log.error("DELIVERY|error|missing_api_key")
        result["error_reason"] = "missing_api_key"
        return result

    # Docker networking hint
    if "localhost" in base_url and os.getenv("RUNNING_IN_DOCKER", "1") == "1":
        log.warning("DELIVERY|hint|localhost_in_docker - EVOLUTION_API_URL aponta para localhost. "
                   "Se o serviço roda no host, use 'host.docker.internal' ou ative o mock (USE_EVOLUTION_MOCK=true)")

    # Phone format validation
    try:
        e164_phone = format_e164(phone)
    except ValueError as e:
        log.warning("DELIVERY|error|invalid_phone_format|phone=%s|error=%s", phone, str(e))
        result["error_reason"] = "invalid_phone_format"
        return result

    # Build request
    url = f"{base_url}/message/sendText/{instance}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    payload = {"number": e164_phone.lstrip("+"), "textMessage": {"text": text}}

    # Log request attempt (mask sensitive data)
    log.info("DELIVERY|attempt|url=%s|instance=%s|phone=****%s|chars=%d|timeout=%gs|retries=%d",
             url, instance, phone[-4:] if len(phone) >= 4 else "****", 
             len(text), timeout_seconds, max_retries)

    try:
        # Execute request with retries
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                async with await _build_client(0, timeout_seconds) as client:  # Retries handled manually
                    response = await client.post(url, json=payload, headers=headers)

                result["status_code"] = response.status_code

                if 200 <= response.status_code < 300:
                    provider_id = ""
                    try:
                        if response.status_code != 204:
                            resp_body = response.json()
                            provider_id = resp_body.get("messageId", "") or resp_body.get("queueId", "")
                    except Exception:
                        pass

                    log.info("DELIVERY|success|status=%d|id=%s|chars=%d|attempt=%d/%d",
                            response.status_code, provider_id, len(text), attempt + 1, max_retries + 1)
                    result["sent"] = "true"
                    return result
                else:
                    # HTTP error response
                    error_body = response.text[:1000]  # Limit error body size
                    log.error("DELIVERY|http_error|status=%d|attempt=%d/%d|url=%s|body=%s",
                             response.status_code, attempt + 1, max_retries + 1, url, error_body)
                    
                    if attempt == max_retries:  # Last attempt failed
                        result["error_reason"] = f"http_{response.status_code}"
                        return result
                    
                    # Wait before retry
                    await asyncio.sleep(backoff * (2 ** attempt))

            except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
                last_exception = e
                log.warning("DELIVERY|timeout|attempt=%d/%d|timeout=%gs|error=%s",
                           attempt + 1, max_retries + 1, timeout_seconds, str(e))
                
                if attempt == max_retries:  # Last attempt failed
                    result["error_reason"] = "timeout"
                    return result
                    
                # Wait before retry
                await asyncio.sleep(backoff * (2 ** attempt))

            except (httpx.ConnectError, httpx.NetworkError) as e:
                last_exception = e
                log.warning("DELIVERY|connection_error|attempt=%d/%d|error=%s",
                           attempt + 1, max_retries + 1, str(e))
                
                if attempt == max_retries:  # Last attempt failed
                    result["error_reason"] = "connection_failed"
                    return result
                    
                # Wait before retry
                await asyncio.sleep(backoff * (2 ** attempt))

            except Exception as e:
                last_exception = e
                log.error("DELIVERY|unexpected_error|attempt=%d/%d|error=%s",
                         attempt + 1, max_retries + 1, str(e))
                
                if attempt == max_retries:  # Last attempt failed
                    result["error_reason"] = str(e)
                    return result
                    
                # Wait before retry
                await asyncio.sleep(backoff * (2 ** attempt))

        # All retries exhausted
        log.error("DELIVERY|all_retries_failed|url=%s|timeout=%gs|retries=%d|last_error=%s",
                 url, timeout_seconds, max_retries, str(last_exception))
        result["error_reason"] = "all_connection_attempts_failed"
        return result

    except Exception as e:
        log.exception("DELIVERY|fatal_error|url=%s|error=%s", url, str(e))
        result["error_reason"] = str(e)
        return result