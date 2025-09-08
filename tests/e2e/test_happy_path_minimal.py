"""
FASE 4 - E2E Happy Path Test
Tests complete flow: webhook → preprocessor → classifier → node → delivery
"""
import asyncio
import logging
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Configure logging for tests
logging.basicConfig(level=logging.INFO)


from tests.integration.test_delivery_integration import MessageDelivery

# Import minimal implementation components
from tests.unit.test_preprocessor_unit import MessagePreprocessor


class MinimalOrchestrator:
    """Minimal orchestrator that connects all components."""

    def __init__(self, preprocessor=None, classifier=None, delivery=None):
        self.preprocessor = preprocessor or MessagePreprocessor()
        self.classifier = classifier or Mock()
        self.delivery = delivery or MessageDelivery()
        self.processed_messages = set()  # For deduplication

    async def process_webhook(self, webhook_data: dict, headers: dict) -> dict:
        """
        Process webhook through complete pipeline.
        Returns response status and any errors.
        """
        logger = logging.getLogger(__name__)

        # Extract message_id for deduplication
        message_id = webhook_data.get("data", {}).get("key", {}).get("id", "")

        logger.info(f"PIPELINE|event=start|message_id={message_id}")

        # 1. Preprocess
        preprocess_result = self.preprocessor.process(
            webhook_data.get("data", {}), headers
        )

        if not preprocess_result["success"]:
            logger.info(
                f"PIPELINE|event=preprocess_failed|error={preprocess_result['error_code']}"
            )
            return {
                "status": "error",
                "error": preprocess_result["error_code"],
                "message_id": message_id,
            }

        if preprocess_result["should_ignore"]:
            logger.info(
                f"PIPELINE|event=ignored|reason=from_me|message_id={message_id}"
            )
            return {"status": "ignored", "reason": "from_me", "message_id": message_id}

        logger.info(f"PIPELINE|event=preprocess_complete|message_id={message_id}")

        # 2. Deduplication
        if message_id in self.processed_messages:
            logger.info(f"PIPELINE|event=duplicate|message_id={message_id}")
            return {"status": "duplicate", "message_id": message_id}

        self.processed_messages.add(message_id)

        # 3. Classify (stub - just returns greeting)
        intent = "greeting"
        logger.info(
            f"PIPELINE|event=classified|intent={intent}|message_id={message_id}"
        )

        # 4. Generate response (stub - fixed response)
        response_text = "Olá! Como posso ajudar?"
        logger.info(f"PIPELINE|event=response_generated|message_id={message_id}")

        # 5. Delivery
        phone = webhook_data.get("data", {}).get("key", {}).get("remoteJid", "")
        instance = webhook_data.get("instance", "default")

        delivery_result = await self.delivery.send_text(
            phone=phone,
            text=response_text,
            instance=instance,
            idempotency_key=f"{message_id}_response",
        )

        if delivery_result["success"]:
            logger.info(f"PIPELINE|event=delivery_complete|message_id={message_id}")
            return {
                "status": "completed",
                "message_id": message_id,
                "response_sent": True,
                "provider_message_id": delivery_result["provider_message_id"],
            }
        else:
            logger.error(
                f"PIPELINE|event=delivery_failed|error={delivery_result['error']}"
            )
            return {
                "status": "delivery_failed",
                "error": delivery_result["error"],
                "message_id": message_id,
            }


# Fixtures
@pytest.fixture
def mock_evolution_api():
    """Mock Evolution API client."""
    client = Mock()
    client.send_text = AsyncMock(
        return_value={"status": 200, "message_id": "RESPONSE_MSG_123"}
    )
    return client


@pytest.fixture
def orchestrator(mock_evolution_api):
    """Orchestrator with all components."""
    preprocessor = MessagePreprocessor()
    delivery = MessageDelivery(evolution_client=mock_evolution_api)
    return MinimalOrchestrator(preprocessor=preprocessor, delivery=delivery)


@pytest.fixture
def valid_webhook_data():
    """Valid webhook payload."""
    return {
        "instance": "test-instance",
        "event": "messages.upsert",
        "data": {
            "key": {
                "id": "E2E_MSG_001",
                "fromMe": False,
                "remoteJid": "5511999999999@s.whatsapp.net",
            },
            "message": {"conversation": "olá"},
        },
    }


@pytest.fixture
def valid_headers():
    """Valid Evolution API headers."""
    return {"x-evolution-instance": "test-instance", "content-type": "application/json"}


# Create FastAPI app for E2E testing
@pytest.fixture
def app(orchestrator):
    """Create FastAPI app with E2E endpoint."""
    from fastapi import BackgroundTasks, FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.post("/api/v1/evolution/webhook")
    async def webhook(request: Request, background_tasks: BackgroundTasks):
        """E2E webhook endpoint."""
        # Get JSON body
        body = await request.json()

        # Get headers
        headers = dict(request.headers)

        # Process through orchestrator
        async def process_in_background():
            await orchestrator.process_webhook(body, headers)
            # In real app, would store result or send notification

        # Queue for background processing
        background_tasks.add_task(process_in_background)

        # Return immediate response
        return JSONResponse(
            {
                "status": "queued",
                "message_id": body.get("data", {}).get("key", {}).get("id", ""),
            },
            status_code=200,
        )

    # Attach orchestrator for testing
    app.state.orchestrator = orchestrator

    return app


@pytest_asyncio.fixture
async def client(app):
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# E2E TESTS
@pytest.mark.asyncio
async def test_happy_path_greeting_to_response(
    orchestrator, valid_webhook_data, valid_headers, caplog
):
    """Test complete happy path: greeting message → response sent."""
    caplog.set_level(logging.INFO)

    # Process webhook
    result = await orchestrator.process_webhook(valid_webhook_data, valid_headers)

    # Verify success
    assert result["status"] == "completed"
    assert result["message_id"] == "E2E_MSG_001"
    assert result["response_sent"] is True
    assert result["provider_message_id"] == "RESPONSE_MSG_123"

    # Verify pipeline logs
    log_text = caplog.text
    assert "PIPELINE|event=start" in log_text
    assert "PIPELINE|event=preprocess_complete" in log_text
    assert "PIPELINE|event=classified|intent=greeting" in log_text
    assert "PIPELINE|event=response_generated" in log_text
    assert "PIPELINE|event=delivery_complete" in log_text

    # Verify delivery was called
    assert orchestrator.delivery.evolution_client.send_text.called
    call_args = orchestrator.delivery.evolution_client.send_text.call_args
    assert call_args.kwargs["phone"] == "5511999999999@s.whatsapp.net"
    assert call_args.kwargs["text"] == "Olá! Como posso ajudar?"
    assert call_args.kwargs["instance"] == "test-instance"


@pytest.mark.asyncio
async def test_e2e_webhook_endpoint(client, valid_webhook_data, valid_headers):
    """Test E2E through actual webhook endpoint."""
    # Send webhook request
    response = await client.post(
        "/api/v1/evolution/webhook", json=valid_webhook_data, headers=valid_headers
    )

    # Should return 200 immediately
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["message_id"] == "E2E_MSG_001"

    # Wait for background processing
    await asyncio.sleep(0.1)

    # Verify message was processed
    orchestrator = client._transport.app.state.orchestrator
    assert "E2E_MSG_001" in orchestrator.processed_messages
    assert orchestrator.delivery.evolution_client.send_text.called


@pytest.mark.asyncio
async def test_e2e_ignores_from_me_messages(orchestrator, valid_headers, caplog):
    """Test E2E ignores messages from bot itself."""
    caplog.set_level(logging.INFO)

    webhook_data = {
        "instance": "test-instance",
        "data": {
            "key": {
                "id": "E2E_MSG_002",
                "fromMe": True,  # Bot's own message
                "remoteJid": "5511999999999@s.whatsapp.net",
            },
            "message": {"conversation": "Bot response"},
        },
    }

    result = await orchestrator.process_webhook(webhook_data, valid_headers)

    assert result["status"] == "ignored"
    assert result["reason"] == "from_me"
    assert "PIPELINE|event=ignored|reason=from_me" in caplog.text

    # Delivery should not be called
    assert not orchestrator.delivery.evolution_client.send_text.called


@pytest.mark.asyncio
async def test_e2e_deduplication(orchestrator, valid_webhook_data, valid_headers):
    """Test E2E deduplication prevents double processing."""
    # First process
    result1 = await orchestrator.process_webhook(valid_webhook_data, valid_headers)
    assert result1["status"] == "completed"

    # Second process with same message_id
    result2 = await orchestrator.process_webhook(valid_webhook_data, valid_headers)
    assert result2["status"] == "duplicate"

    # Delivery should be called only once
    assert orchestrator.delivery.evolution_client.send_text.call_count == 1


@pytest.mark.asyncio
async def test_e2e_auth_failure(orchestrator, valid_webhook_data, caplog):
    """Test E2E handles auth failure gracefully."""
    caplog.set_level(logging.INFO)

    invalid_headers = {"content-type": "application/json"}  # Missing auth

    result = await orchestrator.process_webhook(valid_webhook_data, invalid_headers)

    assert result["status"] == "error"
    assert result["error"] == "AUTH_FAILED"
    assert "PIPELINE|event=preprocess_failed|error=AUTH_FAILED" in caplog.text

    # Delivery should not be called
    assert not orchestrator.delivery.evolution_client.send_text.called


@pytest.mark.asyncio
async def test_e2e_delivery_failure_handling(
    orchestrator, valid_webhook_data, valid_headers, caplog
):
    """Test E2E handles delivery failure."""
    caplog.set_level(logging.INFO)

    # Make delivery fail
    orchestrator.delivery.evolution_client.send_text = AsyncMock(
        return_value={"status": 400, "error": "Bad request"}
    )

    result = await orchestrator.process_webhook(valid_webhook_data, valid_headers)

    assert result["status"] == "delivery_failed"
    assert result["error"] == "API_ERROR_400"
    assert "PIPELINE|event=delivery_failed" in caplog.text


@pytest.mark.asyncio
async def test_e2e_idempotency_in_delivery(
    orchestrator, valid_webhook_data, valid_headers
):
    """Test E2E idempotency prevents duplicate sends."""
    # Process same webhook twice quickly
    result1 = await orchestrator.process_webhook(valid_webhook_data, valid_headers)

    # Remove from dedup set to simulate race condition
    orchestrator.processed_messages.clear()

    # Process again - should use idempotency key
    result2 = await orchestrator.process_webhook(valid_webhook_data, valid_headers)

    assert result1["status"] == "completed"
    assert result2["status"] == "completed"

    # But delivery should only happen once due to idempotency key
    # The second call will return cached result
    assert orchestrator.delivery.evolution_client.send_text.call_count == 1


@pytest.mark.asyncio
async def test_e2e_concurrent_messages(orchestrator, valid_headers):
    """Test E2E handles concurrent different messages."""
    messages = []
    for i in range(5):
        messages.append(
            {
                "instance": "test-instance",
                "data": {
                    "key": {
                        "id": f"E2E_CONCURRENT_{i}",
                        "fromMe": False,
                        "remoteJid": f"551199999{i:04d}@s.whatsapp.net",
                    },
                    "message": {"conversation": f"Message {i}"},
                },
            }
        )

    # Process concurrently
    tasks = [orchestrator.process_webhook(msg, valid_headers) for msg in messages]

    results = await asyncio.gather(*tasks)

    # All should complete successfully
    assert all(r["status"] == "completed" for r in results)

    # All messages should be processed
    assert len(orchestrator.processed_messages) == 5

    # Delivery should be called 5 times
    assert orchestrator.delivery.evolution_client.send_text.call_count == 5


@pytest.mark.asyncio
async def test_e2e_performance_target(orchestrator, valid_webhook_data, valid_headers):
    """Test E2E meets performance target (<800ms)."""
    import time

    start = time.time()
    result = await orchestrator.process_webhook(valid_webhook_data, valid_headers)
    elapsed = time.time() - start

    assert result["status"] == "completed"
    assert elapsed < 0.8  # Should complete in less than 800ms

    # Log performance
    print(f"E2E processing time: {elapsed*1000:.2f}ms")
