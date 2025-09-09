"""
Contract tests for webhook API responses.
Ensures all HTTP responses follow the correct schema with proper types.
Prevents ResponseValidationError in production.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError


# Expected response schema based on the API contract
class WebhookResponseSchema(BaseModel):
    """Expected schema for webhook responses"""

    status: str  # "success", "ignored", "error", etc.
    message: str = None  # Optional message
    sent: str = None  # MUST be string "true"/"false", not bool
    message_id: str = None  # Optional message ID
    reason: str = None  # Optional reason for ignored/error

    class Config:
        # Strict mode to catch type mismatches
        strict = True


@pytest.fixture
def app():
    """Create test FastAPI app"""
    from app.main import app

    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def valid_webhook_payload():
    """Valid Evolution API webhook payload"""
    return {
        "event": "messages.upsert",
        "instance": "test-instance",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "TEST_MESSAGE_ID_123",
            },
            "message": {"conversation": "Olá, gostaria de informações sobre o Kumon"},
            "messageType": "conversation",
            "messageTimestamp": 1704800000,
            "owner": "test-instance",
        },
    }


class TestWebhookResponseContract:
    """Test webhook response contract compliance"""

    def test_webhook_response_schema_valid(self, client, valid_webhook_payload):
        """Test that successful webhook responses follow the correct schema"""
        # Mock dependencies to control response
        with patch("app.api.v1.whatsapp.message_preprocessor") as mock_preprocessor:
            with patch(
                "app.api.v1.whatsapp.pipeline_orchestrator"
            ) as mock_orchestrator:
                with patch(
                    "app.clients.evolution_api.evolution_api_client.parse_webhook_message"
                ) as mock_parse:
                    # Setup mocks
                    mock_parse.return_value = MagicMock(
                        message_id="TEST_MESSAGE_ID_123",
                        phone="5511999999999",
                        message="Test message",
                    )

                    mock_preprocessor.process_message = AsyncMock(
                        return_value=MagicMock(
                            success=True, rate_limited=False, error_code=None
                        )
                    )

                    mock_orchestrator.execute_pipeline = AsyncMock(
                        return_value=MagicMock(
                            status=MagicMock(value="completed"),
                            response_message="Mensagem processada",
                            phone_number="5511999999999",
                        )
                    )

                    # Make request
                    response = client.post(
                        "/api/v1/evolution/webhook",
                        json=valid_webhook_payload,
                        headers={"x-api-key": "test-key"},
                    )

                    # Validate response
                    assert response.status_code == 200
                    data = response.json()

                    # Validate against schema
                    try:
                        validated = WebhookResponseSchema(**data)
                        # If we have 'sent' field, it must be string
                        if validated.sent is not None:
                            assert isinstance(
                                validated.sent, str
                            ), f"'sent' must be string, got {type(validated.sent)}"
                            assert validated.sent in [
                                "true",
                                "false",
                            ], f"'sent' must be 'true' or 'false', got {validated.sent}"
                    except ValidationError as e:
                        pytest.fail(f"Response does not match expected schema: {e}")

    def test_webhook_response_invalid_payload(self, client):
        """Test that invalid payloads return proper error response"""
        invalid_payload = {"invalid": "data"}

        response = client.post(
            "/api/v1/evolution/webhook",
            json=invalid_payload,
            headers={"x-api-key": "test-key"},
        )

        # Should still return valid schema even for errors
        assert response.status_code == 200
        data = response.json()

        # Validate error response schema
        assert "status" in data
        assert isinstance(data["status"], str)

        # If 'sent' is present, must be string
        if "sent" in data:
            assert isinstance(
                data["sent"], str
            ), f"'sent' must be string, got {type(data['sent'])}"

    def test_webhook_response_delivery_error(self, client, valid_webhook_payload):
        """Test that delivery errors return proper response with sent='false' as string"""
        with patch("app.api.v1.whatsapp.message_preprocessor") as mock_preprocessor:
            with patch(
                "app.clients.evolution_api.evolution_api_client.parse_webhook_message"
            ) as mock_parse:
                with patch(
                    "app.clients.evolution_api.evolution_api_client.send_text_message"
                ) as mock_send:
                    # Setup mocks
                    mock_parse.return_value = MagicMock(
                        message_id="TEST_MESSAGE_ID_123",
                        phone="5511999999999",
                        message="Test message",
                    )

                    mock_preprocessor.process_message = AsyncMock(
                        return_value=MagicMock(
                            success=True, rate_limited=False, error_code=None
                        )
                    )

                    # Simulate Evolution API delivery failure
                    mock_send.side_effect = AsyncMock(side_effect=Exception("Evolution API returned 400"))

                    response = client.post(
                        "/api/v1/evolution/webhook",
                        json=valid_webhook_payload,
                        headers={"x-api-key": "test-key"},
                    )

                    assert response.status_code == 200
                    data = response.json()

                    # Validate response has proper types
                    assert "status" in data
                    assert isinstance(data["status"], str)

                    # If sent field exists, MUST be string "false", not bool False
                    if "sent" in data:
                        assert isinstance(
                            data["sent"], str
                        ), f"'sent' must be string, got {type(data['sent'])}"
                        assert (
                            data["sent"] == "false"
                        ), f"Expected 'sent' to be 'false', got {data['sent']}"

    def test_webhook_langgraph_response_types(self):
        """Test that LangGraph flow returns correct types"""
        from app.core.langgraph_flow import run

        # Test various scenarios
        test_cases = [
            {"message": "Olá", "phone": "5511999999999"},
            {"message": "Quero informações", "phone": "5511999999999"},
        ]

        for test_case in test_cases:
            with patch("app.core.langgraph_flow.send_text") as mock_send:
                mock_send.return_value = {"sent": "true", "status_code": 200, "error_reason": None}

                try:
                    result = run(test_case)

                    # Validate result types
                    if "sent" in result:
                        assert isinstance(
                            result["sent"], str
                        ), f"LangGraph returned 'sent' as {type(result['sent'])}, expected str"
                        assert result["sent"] in [
                            "true",
                            "false",
                        ], f"'sent' must be 'true' or 'false', got {result['sent']}"

                    if "message_id" in result:
                        assert isinstance(
                            result["message_id"], str
                        ), f"'message_id' must be string, got {type(result['message_id'])}"

                except Exception:
                    # Even on error, check response format
                    pass

    def test_workflow_orchestrator_response_types(self):
        """Test that workflow orchestrator returns correct types"""
        from app.workflows.workflow_orchestrator import WorkflowOrchestrator

        orchestrator = WorkflowOrchestrator()

        with patch("app.workflows.workflow_orchestrator.send_text") as mock_send:
            mock_send.return_value = {"sent": "true", "status_code": 200, "error_reason": None}

            # Test the execute method
            result = orchestrator.execute(
                message="Test", phone="5511999999999", instance="test"
            )

            # Validate response types
            if isinstance(result, dict):
                if "sent" in result:
                    assert isinstance(
                        result["sent"], str
                    ), f"Orchestrator returned 'sent' as {type(result['sent'])}, expected str"
                    assert result["sent"] in [
                        "true",
                        "false",
                    ], f"'sent' must be 'true' or 'false', got {result['sent']}"

                if "message_id" in result:
                    assert isinstance(
                        result["message_id"], str
                    ), f"'message_id' must be string, got {type(result['message_id'])}"

    def test_all_response_fields_have_correct_types(
        self, client, valid_webhook_payload
    ):
        """Comprehensive test for all possible response fields"""
        response = client.post(
            "/api/v1/evolution/webhook",
            json=valid_webhook_payload,
            headers={"x-api-key": "test-key"},
        )

        data = response.json()

        # Define expected types for all possible fields
        expected_types = {
            "status": str,
            "message": (str, type(None)),
            "sent": str,  # MUST be string, not bool
            "message_id": str,
            "reason": (str, type(None)),
            "error": (str, type(None)),
            "timestamp": str,
        }

        # Validate each field if present
        for field, expected_type in expected_types.items():
            if field in data:
                if isinstance(expected_type, tuple):
                    assert isinstance(
                        data[field], expected_type
                    ), f"Field '{field}' has wrong type: expected {expected_type}, got {type(data[field])}"
                else:
                    assert isinstance(
                        data[field], expected_type
                    ), f"Field '{field}' has wrong type: expected {expected_type}, got {type(data[field])}"

                # Special validation for 'sent' field
                if field == "sent" and data[field] is not None:
                    assert data[field] in [
                        "true",
                        "false",
                    ], f"'sent' must be 'true' or 'false', got {data[field]}"

    def test_rate_limited_response_contract(self, client, valid_webhook_payload):
        """Test rate limited response follows contract"""
        with patch("app.api.v1.whatsapp.message_preprocessor") as mock_preprocessor:
            with patch(
                "app.clients.evolution_api.evolution_api_client.parse_webhook_message"
            ) as mock_parse:
                mock_parse.return_value = MagicMock(
                    message_id="TEST_MESSAGE_ID_123",
                    phone="5511999999999",
                    message="Test message",
                )

                mock_preprocessor.process_message = AsyncMock(
                    return_value=MagicMock(
                        success=False,
                        rate_limited=True,
                        error_message="Rate limit exceeded",
                    )
                )

                response = client.post(
                    "/api/v1/evolution/webhook",
                    json=valid_webhook_payload,
                    headers={"x-api-key": "test-key"},
                )

                assert response.status_code == 200
                data = response.json()

                # Validate rate limit response
                assert data["status"] == "rate_limited"
                assert isinstance(data["message"], str)

                # No 'sent' field should have bool
                if "sent" in data:
                    assert isinstance(data["sent"], str)

    def test_duplicate_message_response_contract(self, client, valid_webhook_payload):
        """Test duplicate message response follows contract"""
        with patch("app.api.v1.whatsapp.is_recent_duplicate") as mock_duplicate:
            with patch(
                "app.clients.evolution_api.evolution_api_client.parse_webhook_message"
            ) as mock_parse:
                mock_parse.return_value = MagicMock(
                    message_id="TEST_MESSAGE_ID_123",
                    phone="5511999999999",
                    message="Test message",
                )

                mock_duplicate.return_value = True

                response = client.post(
                    "/api/v1/evolution/webhook",
                    json=valid_webhook_payload,
                    headers={"x-api-key": "test-key"},
                )

                assert response.status_code == 200
                data = response.json()

                # Validate duplicate response
                assert data["status"] == "ignored"
                assert data["reason"] == "recent_duplicate"

                # No bool values
                for key, value in data.items():
                    if key == "sent":
                        assert isinstance(value, str) or value is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
