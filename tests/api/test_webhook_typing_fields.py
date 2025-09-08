"""
Tests for webhook field typing normalization.
Ensures the webhook correctly normalizes malformed internal types to valid contract types.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


class TestWebhookTypingFields:
    """Test that webhook normalizes incorrect field types."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app.main import app

        return TestClient(app)

    @pytest.fixture
    def valid_request(self):
        """Valid webhook request."""
        return {
            "event": "messages.upsert",
            "instance": "test-instance",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "MSG_ID_123",
                },
                "message": {"conversation": "Olá"},
                "messageType": "conversation",
                "messageTimestamp": 1704800000,
                "owner": "test-instance",
            },
        }

    def test_sent_boolean_to_string_normalization(self, client, valid_request):
        """Test that boolean sent field gets normalized to string."""
        test_cases = [
            (True, "true"),
            (False, "false"),
            (1, "true"),
            (0, "false"),
            ("True", "true"),
            ("False", "false"),
            ("TRUE", "true"),
            ("FALSE", "false"),
        ]

        for input_value, expected_value in test_cases:
            with patch(
                "app.workflows.workflow_orchestrator.WorkflowOrchestrator.execute"
            ) as mock_execute:
                # Return malformed response with boolean/int sent
                mock_execute.return_value = {
                    "message_id": "MSG_ID_123",
                    "turn_id": "turn_001",
                    "trace_id": "trace_123",
                    "intent": "greeting",
                    "confidence": 0.9,
                    "response_text": "Olá! Como posso ajudar?",
                    "routing_hint": None,
                    "entities": {},
                    "sent": input_value,  # Wrong type!
                }

                response = client.post(
                    "/api/v1/evolution/webhook",
                    json=valid_request,
                    headers={"x-api-key": "test-key"},
                )

                assert response.status_code == 200
                data = response.json()

                # Verify sent was normalized to string
                assert "sent" in data
                assert isinstance(
                    data["sent"], str
                ), f"sent must be string, got {type(data['sent'])}"
                assert (
                    data["sent"] == expected_value
                ), f"Expected {expected_value}, got {data['sent']}"

    def test_confidence_string_to_float_normalization(self, client, valid_request):
        """Test that string confidence gets normalized to float."""
        test_cases = [
            ("0.8", 0.8),
            ("0.95", 0.95),
            ("1", 1.0),
            ("0", 0.0),
            ("not_a_number", 0.0),  # Invalid -> 0.0
            ("2.5", 1.0),  # Out of range -> clamp to 1.0
            ("-0.5", 0.0),  # Negative -> clamp to 0.0
            (None, 0.0),  # None -> 0.0
        ]

        for input_value, expected_value in test_cases:
            with patch(
                "app.workflows.workflow_orchestrator.WorkflowOrchestrator.execute"
            ) as mock_execute:
                mock_execute.return_value = {
                    "message_id": "MSG_ID_123",
                    "turn_id": "turn_001",
                    "trace_id": "trace_123",
                    "intent": "greeting",
                    "confidence": input_value,  # Wrong type or invalid!
                    "response_text": "Olá!",
                    "routing_hint": None,
                    "entities": {},
                    "sent": "true",
                }

                response = client.post(
                    "/api/v1/evolution/webhook",
                    json=valid_request,
                    headers={"x-api-key": "test-key"},
                )

                assert response.status_code == 200
                data = response.json()

                # Verify confidence was normalized
                if "confidence" in data:
                    assert isinstance(data["confidence"], (float, int))
                    assert 0.0 <= float(data["confidence"]) <= 1.0
                    # For invalid values, intent should fallback
                    if input_value == "not_a_number":
                        assert data.get("intent") == "fallback"

    def test_entities_list_to_dict_normalization(self, client, valid_request):
        """Test that entities list/None gets normalized to dict."""
        test_cases = [
            ([], {}),  # Empty list -> empty dict
            (None, {}),  # None -> empty dict
            ([1, 2, 3], {}),  # List with values -> empty dict
            ("not_a_dict", {}),  # String -> empty dict
            (123, {}),  # Number -> empty dict
            ({"key": "value"}, {"key": "value"}),  # Valid dict stays
        ]

        for input_value, expected_value in test_cases:
            with patch(
                "app.workflows.workflow_orchestrator.WorkflowOrchestrator.execute"
            ) as mock_execute:
                mock_execute.return_value = {
                    "message_id": "MSG_ID_123",
                    "turn_id": "turn_001",
                    "trace_id": "trace_123",
                    "intent": "greeting",
                    "confidence": 0.9,
                    "response_text": "Olá!",
                    "routing_hint": None,
                    "entities": input_value,  # Wrong type!
                    "sent": "true",
                }

                response = client.post(
                    "/api/v1/evolution/webhook",
                    json=valid_request,
                    headers={"x-api-key": "test-key"},
                )

                assert response.status_code == 200
                data = response.json()

                # Verify entities was normalized to dict
                if "entities" in data:
                    assert isinstance(
                        data["entities"], dict
                    ), f"entities must be dict, got {type(data['entities'])}"
                    assert data["entities"] == expected_value

    def test_routing_hint_empty_string_to_null(self, client, valid_request):
        """Test that empty routing_hint gets normalized to None/null."""
        test_cases = [
            ("", None),  # Empty string -> None
            ("  ", None),  # Whitespace -> None
            ("invalid_hint", None),  # Invalid value -> None
            ("handle_price_objection", "handle_price_objection"),  # Valid stays
            ("ask_clarification", "ask_clarification"),  # Valid stays
            ("handoff_human", "handoff_human"),  # Valid stays
        ]

        for input_value, expected_value in test_cases:
            with patch(
                "app.workflows.workflow_orchestrator.WorkflowOrchestrator.execute"
            ) as mock_execute:
                mock_execute.return_value = {
                    "message_id": "MSG_ID_123",
                    "turn_id": "turn_001",
                    "trace_id": "trace_123",
                    "intent": "greeting",
                    "confidence": 0.9,
                    "response_text": "Olá!",
                    "routing_hint": input_value,
                    "entities": {},
                    "sent": "true",
                }

                response = client.post(
                    "/api/v1/evolution/webhook",
                    json=valid_request,
                    headers={"x-api-key": "test-key"},
                )

                assert response.status_code == 200
                data = response.json()

                # Verify routing_hint normalization
                if expected_value is None:
                    assert (
                        data.get("routing_hint") is None
                        or data.get("routing_hint") == "null"
                    )
                else:
                    assert data.get("routing_hint") == expected_value

    def test_response_text_none_to_fallback_string(self, client, valid_request):
        """Test that None response_text gets normalized to PT-BR fallback."""
        test_cases = [
            (None, "fallback"),
            ("", "fallback"),
            ("Hello, how are you?", "fallback"),  # English detected
            ("The price is high", "fallback"),  # English detected
            ("None", "fallback"),  # String "None"
            ("Olá, como vai?", "ok"),  # Valid PT-BR stays
        ]

        for input_value, expected_type in test_cases:
            with patch(
                "app.workflows.workflow_orchestrator.WorkflowOrchestrator.execute"
            ) as mock_execute:
                mock_execute.return_value = {
                    "message_id": "MSG_ID_123",
                    "turn_id": "turn_001",
                    "trace_id": "trace_123",
                    "intent": "greeting",
                    "confidence": 0.9,
                    "response_text": input_value,
                    "routing_hint": None,
                    "entities": {},
                    "sent": "true",
                }

                response = client.post(
                    "/api/v1/evolution/webhook",
                    json=valid_request,
                    headers={"x-api-key": "test-key"},
                )

                assert response.status_code == 200
                data = response.json()

                # Verify response_text normalization
                assert "response_text" in data
                assert isinstance(data["response_text"], str)
                assert data["response_text"], "response_text cannot be empty"

                if expected_type == "fallback":
                    # Should not contain English
                    text_lower = data["response_text"].lower()
                    english_tokens = ["the", "and", "hello", "price", "none"]
                    for token in english_tokens:
                        assert token not in text_lower

    def test_intent_invalid_to_fallback(self, client, valid_request):
        """Test that invalid intent gets normalized to fallback."""
        test_cases = [
            ("invalid_intent", "fallback"),
            ("", "fallback"),
            (None, "fallback"),
            (123, "fallback"),
            ("GREETING", "greeting"),  # Case normalization
            ("Information_Request", "information_request"),  # Case normalization
        ]

        for input_value, expected_value in test_cases:
            with patch(
                "app.workflows.workflow_orchestrator.WorkflowOrchestrator.execute"
            ) as mock_execute:
                mock_execute.return_value = {
                    "message_id": "MSG_ID_123",
                    "turn_id": "turn_001",
                    "trace_id": "trace_123",
                    "intent": input_value,
                    "confidence": 0.9,
                    "response_text": "Olá!",
                    "routing_hint": None,
                    "entities": {},
                    "sent": "true",
                }

                response = client.post(
                    "/api/v1/evolution/webhook",
                    json=valid_request,
                    headers={"x-api-key": "test-key"},
                )

                assert response.status_code == 200
                data = response.json()

                # Verify intent normalization
                assert "intent" in data
                assert isinstance(data["intent"], str)
                valid_intents = {
                    "greeting",
                    "information_request",
                    "qualification",
                    "scheduling",
                    "fallback",
                    "objection",
                }
                assert data["intent"] in valid_intents

                # Check if normalized correctly
                if input_value not in valid_intents:
                    assert data["intent"] == expected_value

    def test_multiple_field_normalization(self, client, valid_request):
        """Test normalization of multiple fields at once."""
        with patch(
            "app.workflows.workflow_orchestrator.WorkflowOrchestrator.execute"
        ) as mock_execute:
            # Return response with multiple wrong types
            mock_execute.return_value = {
                "message_id": "MSG_ID_123",
                "turn_id": "turn_001",
                "trace_id": "trace_123",
                "intent": "INVALID",  # Invalid intent
                "confidence": "not_a_number",  # String instead of float
                "response_text": None,  # None instead of string
                "routing_hint": "",  # Empty string instead of None
                "entities": [1, 2, 3],  # List instead of dict
                "sent": False,  # Boolean instead of string
            }

            response = client.post(
                "/api/v1/evolution/webhook",
                json=valid_request,
                headers={"x-api-key": "test-key"},
            )

            assert response.status_code == 200
            data = response.json()

            # All fields should be normalized
            assert isinstance(data.get("sent"), str)
            assert data.get("sent") in {"true", "false"}

            assert isinstance(data.get("entities"), dict)

            assert data.get("intent") in {
                "greeting",
                "information_request",
                "qualification",
                "scheduling",
                "fallback",
                "objection",
            }

            if "confidence" in data:
                assert isinstance(data["confidence"], (float, int))
                assert 0.0 <= float(data["confidence"]) <= 1.0

            assert isinstance(data.get("response_text"), str)
            assert data.get("response_text")  # Not empty

    def test_error_response_maintains_contract(self, client, valid_request):
        """Test that error responses maintain the contract."""
        with patch(
            "app.workflows.workflow_orchestrator.WorkflowOrchestrator.execute"
        ) as mock_execute:
            # Simulate an exception
            mock_execute.side_effect = Exception("Database connection failed")

            response = client.post(
                "/api/v1/evolution/webhook",
                json=valid_request,
                headers={"x-api-key": "test-key"},
            )

            # Should return 200, not 500
            assert response.status_code == 200
            data = response.json()

            # Should have sent="false" as string
            if "sent" in data:
                assert isinstance(data["sent"], str)
                assert data["sent"] == "false"

            # Should have status field
            assert "status" in data
            assert isinstance(data["status"], str)
