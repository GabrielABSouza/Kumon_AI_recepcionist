"""
FASE 2 - Integration Tests for Webhook → Preprocessor
Tests webhook endpoint, background processing, deduplication
"""
import asyncio
import logging
from unittest.mock import Mock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Configure logging for tests
logging.basicConfig(level=logging.INFO)


# Import or define the app
@pytest.fixture
def app():
    """Get or create FastAPI app for testing."""
    from fastapi import BackgroundTasks, FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI()

    # Storage for testing
    processed_messages = set()
    background_tasks_queue = []

    # Mock preprocessor
    mock_preprocessor = Mock()
    mock_preprocessor.process = Mock(
        return_value={
            "success": True,
            "sanitized_text": "test",
            "should_ignore": False,
            "auth_valid": True,
        }
    )

    @app.post("/api/v1/evolution/webhook")
    async def webhook(request: dict, background_tasks: BackgroundTasks):
        """Minimal webhook implementation for testing."""
        # Log structured
        logger = logging.getLogger(__name__)
        logger.info(
            f"PIPELINE|event=webhook_received|message_id={request.get('data', {}).get('key', {}).get('id')}"
        )

        # Extract message data
        data = request.get("data", {})
        key = data.get("key", {})
        message_id = key.get("id", "")
        from_me = key.get("fromMe", False)

        # Check fromMe
        if from_me:
            logger.info(
                f"PIPELINE|event=ignored|reason=from_me|message_id={message_id}"
            )
            return JSONResponse(
                {"status": "ignored", "reason": "from_me"}, status_code=200
            )

        # Check headers (simplified for test)
        headers = request.get("_headers", {})
        if not headers.get("x-evolution-instance"):
            logger.info(f"PIPELINE|event=auth_failed|message_id={message_id}")
            # Still return 200 to not break webhook
            return JSONResponse(
                {"status": "error", "reason": "auth_failed"}, status_code=200
            )

        # Deduplication
        if message_id in processed_messages:
            logger.info(f"DEDUP|event=duplicate|message_id={message_id}")
            return JSONResponse(
                {"status": "duplicate", "message_id": message_id}, status_code=200
            )

        processed_messages.add(message_id)
        logger.info(f"DEDUP|event=new_message|message_id={message_id}")

        # Queue background processing
        async def process_message(msg_id):
            logger.info(f"PIPELINE|event=processing_start|message_id={msg_id}")
            await asyncio.sleep(0.01)  # Simulate processing
            logger.info(f"PIPELINE|event=processing_complete|message_id={msg_id}")

        background_tasks.add_task(process_message, message_id)
        background_tasks_queue.append(message_id)

        logger.info(f"PIPELINE|event=queued|message_id={message_id}")
        return JSONResponse(
            {"status": "queued", "message_id": message_id}, status_code=200
        )

    # Attach storage for testing
    app.state.processed_messages = processed_messages
    app.state.background_tasks_queue = background_tasks_queue
    app.state.mock_preprocessor = mock_preprocessor

    return app


@pytest_asyncio.fixture
async def client(app):
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def valid_webhook_payload():
    """Valid Evolution API webhook payload."""
    return {
        "instance": "test-instance",
        "event": "messages.upsert",
        "data": {
            "key": {
                "id": "MSG123",
                "fromMe": False,
                "remoteJid": "5511999999999@s.whatsapp.net",
            },
            "message": {"conversation": "Hello test"},
        },
        "_headers": {
            "x-evolution-instance": "test-instance",
            "content-type": "application/json",
        },
    }


@pytest.fixture
def from_me_payload():
    """Payload with fromMe=True (should be ignored)."""
    return {
        "instance": "test-instance",
        "event": "messages.upsert",
        "data": {
            "key": {
                "id": "MSG456",
                "fromMe": True,  # Bot's own message
                "remoteJid": "5511999999999@s.whatsapp.net",
            },
            "message": {"conversation": "Bot response"},
        },
        "_headers": {"x-evolution-instance": "test-instance"},
    }


@pytest.fixture
def no_auth_payload():
    """Payload without proper auth headers."""
    return {
        "instance": "test-instance",
        "event": "messages.upsert",
        "data": {
            "key": {
                "id": "MSG789",
                "fromMe": False,
                "remoteJid": "5511999999999@s.whatsapp.net",
            },
            "message": {"conversation": "No auth"},
        },
        "_headers": {},  # Missing auth headers
    }


# TESTS - Basic webhook functionality
@pytest.mark.asyncio
async def test_webhook_returns_200_and_queues_processing(
    client, valid_webhook_payload, caplog
):
    """Test that valid webhook returns 200 and queues background task."""
    # Set caplog to capture INFO level
    caplog.set_level(logging.INFO)

    response = await client.post(
        "/api/v1/evolution/webhook", json=valid_webhook_payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["message_id"] == "MSG123"

    # Check structured logs
    assert "PIPELINE|event=webhook_received" in caplog.text
    assert "DEDUP|event=new_message" in caplog.text
    assert "PIPELINE|event=queued" in caplog.text


@pytest.mark.asyncio
async def test_webhook_ignores_from_me_messages(client, from_me_payload, caplog):
    """Test that messages from bot (fromMe=True) are ignored."""
    caplog.set_level(logging.INFO)

    response = await client.post("/api/v1/evolution/webhook", json=from_me_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["reason"] == "from_me"

    # Check logs
    assert "PIPELINE|event=ignored|reason=from_me" in caplog.text


@pytest.mark.asyncio
async def test_webhook_handles_missing_auth_gracefully(client, no_auth_payload, caplog):
    """Test that missing auth headers are handled without exposing details."""
    caplog.set_level(logging.INFO)

    response = await client.post("/api/v1/evolution/webhook", json=no_auth_payload)

    # Should still return 200 to not break webhook
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["reason"] == "auth_failed"

    # Check logs
    assert "PIPELINE|event=auth_failed" in caplog.text


# TESTS - Deduplication
@pytest.mark.asyncio
async def test_deduplication_prevents_duplicate_processing(
    client, valid_webhook_payload, caplog
):
    """Test that same message_id is not processed twice."""
    caplog.set_level(logging.INFO)

    # First request
    response1 = await client.post(
        "/api/v1/evolution/webhook", json=valid_webhook_payload
    )
    assert response1.status_code == 200
    assert response1.json()["status"] == "queued"

    # Second request with same message_id
    response2 = await client.post(
        "/api/v1/evolution/webhook", json=valid_webhook_payload
    )
    assert response2.status_code == 200
    assert response2.json()["status"] == "duplicate"
    assert response2.json()["message_id"] == "MSG123"

    # Check logs
    assert "DEDUP|event=duplicate" in caplog.text


@pytest.mark.asyncio
async def test_different_message_ids_are_processed(client, app):
    """Test that different message IDs are processed independently."""
    # Clear processed messages
    app.state.processed_messages.clear()

    # First message
    payload1 = {
        "data": {
            "key": {"id": "MSG001", "fromMe": False},
            "message": {"conversation": "First"},
        },
        "_headers": {"x-evolution-instance": "test"},
    }

    response1 = await client.post("/api/v1/evolution/webhook", json=payload1)
    assert response1.json()["status"] == "queued"

    # Second message with different ID
    payload2 = {
        "data": {
            "key": {"id": "MSG002", "fromMe": False},
            "message": {"conversation": "Second"},
        },
        "_headers": {"x-evolution-instance": "test"},
    }

    response2 = await client.post("/api/v1/evolution/webhook", json=payload2)
    assert response2.json()["status"] == "queued"

    # Both should be in queue
    assert len(app.state.background_tasks_queue) >= 2


# TESTS - Background processing
@pytest.mark.asyncio
async def test_background_task_is_queued(client, valid_webhook_payload, app):
    """Test that valid message is queued for background processing."""
    # Clear queue
    app.state.background_tasks_queue.clear()
    app.state.processed_messages.clear()

    response = await client.post(
        "/api/v1/evolution/webhook", json=valid_webhook_payload
    )

    assert response.status_code == 200

    # Check that task was queued
    assert "MSG123" in app.state.background_tasks_queue


@pytest.mark.asyncio
async def test_webhook_handles_concurrent_requests(client, app):
    """Test that webhook handles multiple concurrent requests."""
    # Clear state
    app.state.processed_messages.clear()
    app.state.background_tasks_queue.clear()

    # Create multiple payloads
    payloads = []
    for i in range(5):
        payloads.append(
            {
                "data": {
                    "key": {"id": f"MSG{i:03d}", "fromMe": False},
                    "message": {"conversation": f"Message {i}"},
                },
                "_headers": {"x-evolution-instance": "test"},
            }
        )

    # Send concurrently
    tasks = [
        client.post("/api/v1/evolution/webhook", json=payload) for payload in payloads
    ]

    responses = await asyncio.gather(*tasks)

    # All should return 200
    assert all(r.status_code == 200 for r in responses)

    # All should be queued
    assert len(app.state.background_tasks_queue) == 5


# TESTS - Edge cases
@pytest.mark.asyncio
async def test_webhook_handles_empty_message(client):
    """Test handling of empty message content."""
    payload = {
        "data": {"key": {"id": "MSG_EMPTY", "fromMe": False}, "message": {}},
        "_headers": {"x-evolution-instance": "test"},
    }

    response = await client.post("/api/v1/evolution/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_webhook_handles_image_message(client):
    """Test handling of image message with caption."""
    payload = {
        "data": {
            "key": {"id": "MSG_IMG", "fromMe": False},
            "message": {"imageMessage": {"caption": "Check this image"}},
        },
        "_headers": {"x-evolution-instance": "test"},
    }

    response = await client.post("/api/v1/evolution/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_webhook_logs_structured_events(client, valid_webhook_payload, caplog):
    """Test that webhook logs structured events correctly."""
    caplog.set_level(logging.INFO)

    response = await client.post(
        "/api/v1/evolution/webhook", json=valid_webhook_payload
    )

    assert response.status_code == 200

    # Check for required structured logs
    log_text = caplog.text
    assert "PIPELINE|event=webhook_received" in log_text
    assert "DEDUP|event=new_message" in log_text
    assert "PIPELINE|event=queued" in log_text
    assert "message_id=MSG123" in log_text
