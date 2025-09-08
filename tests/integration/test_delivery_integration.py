"""
FASE 3 - Integration Tests for Delivery
Tests message delivery via Evolution API with retry and idempotency
"""
import asyncio
import logging
import time
from unittest.mock import AsyncMock, Mock

import pytest

# Configure logging for tests
logging.basicConfig(level=logging.INFO)


class MessageDelivery:
    """Minimal delivery implementation for testing."""

    def __init__(self, evolution_client=None, store=None):
        self.evolution_client = evolution_client or Mock()
        self.store = store or {}  # Simple in-memory store for idempotency
        self.max_retries = 3
        self.retry_delay = 0.1  # seconds

    async def send_text(
        self, phone: str, text: str, instance: str, idempotency_key: str = None
    ) -> dict:
        """
        Send text message via Evolution API.
        Returns dict with: success, provider_message_id, idempotency_key, status
        """
        result = {
            "success": False,
            "provider_message_id": None,
            "idempotency_key": idempotency_key,
            "status": None,
            "error": None,
        }

        # Format phone number
        formatted_phone = self._format_phone(phone)
        if not formatted_phone:
            result["error"] = "INVALID_PHONE"
            return result

        # Check idempotency
        if idempotency_key and idempotency_key in self.store:
            # Already sent, return cached result
            cached = self.store[idempotency_key]
            result.update(cached)
            result["status"] = "ALREADY_SENT"
            logging.info(f"DELIVERY|event=idempotent_skip|key={idempotency_key}")
            return result

        # Try sending with retries
        for attempt in range(self.max_retries):
            try:
                # Mock Evolution API call
                response = await self._call_evolution_api(
                    instance=instance, phone=formatted_phone, text=text
                )

                if response.get("status") == 200:
                    # Success
                    result["success"] = True
                    result["provider_message_id"] = response.get(
                        "message_id", "MSG_" + str(time.time())
                    )
                    result["status"] = "SENT"

                    # Store for idempotency
                    if idempotency_key:
                        self.store[idempotency_key] = {
                            "success": True,
                            "provider_message_id": result["provider_message_id"],
                            "status": "SENT",
                        }

                    logging.info(
                        f"DELIVERY|event=sent|phone={formatted_phone}|attempt={attempt+1}"
                    )
                    return result

                elif response.get("status") in [500, 502, 503, 504]:
                    # Retry on 5xx errors
                    logging.info(
                        f"DELIVERY|event=retry|attempt={attempt+1}|status={response.get('status')}"
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(
                            self.retry_delay * (2**attempt)
                        )  # Exponential backoff
                    continue

                else:
                    # Non-retryable error
                    result["error"] = f"API_ERROR_{response.get('status')}"
                    logging.info(f"DELIVERY|event=failed|error={result['error']}")
                    return result

            except Exception as e:
                logging.error(f"DELIVERY|event=exception|error={str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))
                    continue
                result["error"] = "EXCEPTION"
                return result

        # Max retries exceeded
        result["error"] = "MAX_RETRIES"
        result["status"] = "FAILED"
        logging.info(f"DELIVERY|event=max_retries|phone={formatted_phone}")
        return result

    def _format_phone(self, phone: str) -> str:
        """Format phone number to Evolution API format."""
        import re

        # Remove all non-digits
        digits = re.sub(r"\D", "", phone)

        # Validate length (Brazilian phone)
        if len(digits) < 10 or len(digits) > 13:
            return None

        # Add country code if missing
        if not digits.startswith("55"):
            digits = "55" + digits

        # Format for WhatsApp
        return digits + "@s.whatsapp.net"

    async def _call_evolution_api(self, instance: str, phone: str, text: str) -> dict:
        """Mock Evolution API call."""
        # This would be the actual API call in production
        return await self.evolution_client.send_text(
            instance=instance, phone=phone, text=text
        )


# Test fixtures
@pytest.fixture
def mock_evolution_success():
    """Mock Evolution client that always succeeds."""
    client = Mock()
    client.send_text = AsyncMock(
        return_value={"status": 200, "message_id": "MOCK_MSG_123"}
    )
    return client


@pytest.fixture
def mock_evolution_retry():
    """Mock Evolution client that succeeds after retries."""
    client = Mock()
    # First two calls fail with 503, third succeeds
    client.send_text = AsyncMock(
        side_effect=[
            {"status": 503, "error": "Service unavailable"},
            {"status": 503, "error": "Service unavailable"},
            {"status": 200, "message_id": "MOCK_MSG_RETRY"},
        ]
    )
    return client


@pytest.fixture
def mock_evolution_fail():
    """Mock Evolution client that always fails."""
    client = Mock()
    client.send_text = AsyncMock(return_value={"status": 400, "error": "Bad request"})
    return client


@pytest.fixture
def delivery_success(mock_evolution_success):
    """Delivery service with successful mock."""
    return MessageDelivery(evolution_client=mock_evolution_success)


@pytest.fixture
def delivery_retry(mock_evolution_retry):
    """Delivery service with retry mock."""
    delivery = MessageDelivery(evolution_client=mock_evolution_retry)
    delivery.retry_delay = 0.01  # Faster for tests
    return delivery


@pytest.fixture
def delivery_fail(mock_evolution_fail):
    """Delivery service with failing mock."""
    return MessageDelivery(evolution_client=mock_evolution_fail)


# TESTS - Basic delivery
@pytest.mark.asyncio
async def test_send_text_success(delivery_success, caplog):
    """Test successful message delivery."""
    caplog.set_level(logging.INFO)

    result = await delivery_success.send_text(
        phone="11999999999", text="Test message", instance="test-instance"
    )

    assert result["success"] is True
    assert result["provider_message_id"] == "MOCK_MSG_123"
    assert result["status"] == "SENT"
    assert result["error"] is None

    # Check logs
    assert "DELIVERY|event=sent" in caplog.text


@pytest.mark.asyncio
async def test_send_text_formats_phone_number(delivery_success):
    """Test that phone numbers are properly formatted."""
    # Test various formats
    test_cases = [
        ("11999999999", "5511999999999@s.whatsapp.net"),
        ("+5511999999999", "5511999999999@s.whatsapp.net"),
        ("5511999999999", "5511999999999@s.whatsapp.net"),
        ("(11) 99999-9999", "5511999999999@s.whatsapp.net"),
    ]

    for input_phone, expected_format in test_cases:
        result = await delivery_success.send_text(
            phone=input_phone, text="Test", instance="test"
        )

        assert result["success"] is True
        # Verify the formatted phone was used in the call
        delivery_success.evolution_client.send_text.assert_called_with(
            instance="test", phone=expected_format, text="Test"
        )


@pytest.mark.asyncio
async def test_send_text_invalid_phone_number(delivery_success):
    """Test that invalid phone numbers are rejected."""
    result = await delivery_success.send_text(
        phone="123", text="Test", instance="test"  # Too short
    )

    assert result["success"] is False
    assert result["error"] == "INVALID_PHONE"
    assert result["provider_message_id"] is None


# TESTS - Retry logic
@pytest.mark.asyncio
async def test_retry_on_5xx_errors(delivery_retry, caplog):
    """Test that delivery retries on 5xx errors."""
    caplog.set_level(logging.INFO)

    result = await delivery_retry.send_text(
        phone="11999999999", text="Test message", instance="test-instance"
    )

    assert result["success"] is True
    assert result["provider_message_id"] == "MOCK_MSG_RETRY"

    # Check that retries happened
    assert delivery_retry.evolution_client.send_text.call_count == 3
    assert "DELIVERY|event=retry" in caplog.text
    assert "DELIVERY|event=sent" in caplog.text


@pytest.mark.asyncio
async def test_no_retry_on_4xx_errors(delivery_fail, caplog):
    """Test that delivery doesn't retry on 4xx errors."""
    caplog.set_level(logging.INFO)

    result = await delivery_fail.send_text(
        phone="11999999999", text="Test message", instance="test-instance"
    )

    assert result["success"] is False
    assert result["error"] == "API_ERROR_400"

    # Should only call once (no retry)
    assert delivery_fail.evolution_client.send_text.call_count == 1
    assert "DELIVERY|event=failed" in caplog.text


@pytest.mark.asyncio
async def test_max_retries_exceeded():
    """Test that delivery stops after max retries."""
    client = Mock()
    client.send_text = AsyncMock(return_value={"status": 503})

    delivery = MessageDelivery(evolution_client=client)
    delivery.retry_delay = 0.01

    result = await delivery.send_text(phone="11999999999", text="Test", instance="test")

    assert result["success"] is False
    assert result["error"] == "MAX_RETRIES"
    assert result["status"] == "FAILED"
    assert client.send_text.call_count == 3


# TESTS - Idempotency
@pytest.mark.asyncio
async def test_idempotency_prevents_duplicate_sends(delivery_success, caplog):
    """Test that idempotency key prevents duplicate sends."""
    caplog.set_level(logging.INFO)

    idempotency_key = "test_key_123"

    # First send
    result1 = await delivery_success.send_text(
        phone="11999999999",
        text="Test message",
        instance="test-instance",
        idempotency_key=idempotency_key,
    )

    assert result1["success"] is True
    assert result1["status"] == "SENT"

    # Second send with same key
    result2 = await delivery_success.send_text(
        phone="11999999999",
        text="Test message",
        instance="test-instance",
        idempotency_key=idempotency_key,
    )

    assert result2["success"] is True
    assert result2["status"] == "ALREADY_SENT"
    assert result2["provider_message_id"] == result1["provider_message_id"]

    # Should only call API once
    assert delivery_success.evolution_client.send_text.call_count == 1
    assert "DELIVERY|event=idempotent_skip" in caplog.text


@pytest.mark.asyncio
async def test_different_idempotency_keys_allow_multiple_sends(delivery_success):
    """Test that different idempotency keys allow multiple sends."""
    # First send
    result1 = await delivery_success.send_text(
        phone="11999999999", text="Test 1", instance="test", idempotency_key="key_1"
    )

    # Second send with different key
    result2 = await delivery_success.send_text(
        phone="11999999999", text="Test 2", instance="test", idempotency_key="key_2"
    )

    assert result1["success"] is True
    assert result2["success"] is True
    assert result1["status"] == "SENT"
    assert result2["status"] == "SENT"

    # Should call API twice
    assert delivery_success.evolution_client.send_text.call_count == 2


# TESTS - Edge cases
@pytest.mark.asyncio
async def test_send_without_idempotency_key(delivery_success):
    """Test that sending without idempotency key works."""
    result = await delivery_success.send_text(
        phone="11999999999", text="Test", instance="test"
    )

    assert result["success"] is True
    assert result["idempotency_key"] is None

    # Send again - should not be deduplicated
    result2 = await delivery_success.send_text(
        phone="11999999999", text="Test", instance="test"
    )

    assert result2["success"] is True
    assert delivery_success.evolution_client.send_text.call_count == 2


@pytest.mark.asyncio
async def test_exception_handling():
    """Test that exceptions are handled gracefully."""
    client = Mock()
    client.send_text = AsyncMock(side_effect=Exception("Network error"))

    delivery = MessageDelivery(evolution_client=client)
    delivery.retry_delay = 0.01

    result = await delivery.send_text(phone="11999999999", text="Test", instance="test")

    assert result["success"] is False
    assert result["error"] == "EXCEPTION"
    assert client.send_text.call_count == 3  # Should retry


@pytest.mark.asyncio
async def test_exponential_backoff():
    """Test that retry uses exponential backoff."""
    client = Mock()
    client.send_text = AsyncMock(
        side_effect=[
            {"status": 503},
            {"status": 503},
            {"status": 200, "message_id": "SUCCESS"},
        ]
    )

    delivery = MessageDelivery(evolution_client=client)
    delivery.retry_delay = 0.01

    start_time = time.time()
    result = await delivery.send_text(phone="11999999999", text="Test", instance="test")
    elapsed = time.time() - start_time

    assert result["success"] is True
    # Should take at least 0.01 + 0.02 = 0.03 seconds
    assert elapsed >= 0.03
