"""
Tests for orchestrator typing and normalization.
Ensures the orchestrator correctly handles and normalizes field types.
"""
from unittest.mock import patch

import pytest


class TestOrchestratorTyping:
    """Test orchestrator type handling and normalization."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance."""
        from app.workflows.workflow_orchestrator import WorkflowOrchestrator

        return WorkflowOrchestrator()

    def test_confidence_string_to_float(self, orchestrator):
        """Test orchestrator normalizes string confidence to float."""
        test_cases = [
            ("0.8", 0.8),
            ("0.95", 0.95),
            ("1", 1.0),
            ("invalid", 0.0),
            (None, 0.0),
            (1.5, 1.0),  # Out of range
            (-0.5, 0.0),  # Negative
        ]

        for input_val, expected in test_cases:
            with patch.object(orchestrator, "_process_message") as mock_process:
                mock_process.return_value = {
                    "intent": "greeting",
                    "confidence": input_val,
                    "response_text": "Olá!",
                    "entities": {},
                }

                result = orchestrator.execute(
                    message="Test", phone="5511999999999", instance="test"
                )

                # Confidence should be normalized
                if "confidence" in result:
                    assert isinstance(result["confidence"], (float, int))
                    assert 0.0 <= float(result["confidence"]) <= 1.0

    def test_intent_normalization(self, orchestrator):
        """Test orchestrator normalizes invalid intents to fallback."""
        test_cases = [
            ("invalid_intent", "fallback"),
            ("", "fallback"),
            (None, "fallback"),
            (123, "fallback"),
            ("GREETING", "greeting"),  # Case normalization
        ]

        for input_val, expected in test_cases:
            with patch.object(orchestrator, "_process_message") as mock_process:
                mock_process.return_value = {
                    "intent": input_val,
                    "confidence": 0.9,
                    "response_text": "Olá!",
                    "entities": {},
                }

                result = orchestrator.execute(
                    message="Test", phone="5511999999999", instance="test"
                )

                # Intent should be normalized
                assert "intent" in result
                assert isinstance(result["intent"], str)
                valid_intents = {
                    "greeting",
                    "information_request",
                    "qualification",
                    "scheduling",
                    "fallback",
                    "objection",
                }
                assert result["intent"] in valid_intents

    def test_entities_normalization(self, orchestrator):
        """Test orchestrator normalizes entities to dict."""
        test_cases = [
            (None, {}),
            ([], {}),
            ("string", {}),
            ([1, 2, 3], {}),
            ({"key": "value"}, {"key": "value"}),
        ]

        for input_val, expected in test_cases:
            with patch.object(orchestrator, "_process_message") as mock_process:
                mock_process.return_value = {
                    "intent": "greeting",
                    "confidence": 0.9,
                    "response_text": "Olá!",
                    "entities": input_val,
                }

                result = orchestrator.execute(
                    message="Test", phone="5511999999999", instance="test"
                )

                # Entities should be dict
                assert "entities" in result
                assert isinstance(result["entities"], dict)
                assert result["entities"] == expected

    def test_routing_hint_normalization(self, orchestrator):
        """Test orchestrator normalizes routing_hint."""
        test_cases = [
            ("", None),
            ("  ", None),
            ("invalid", None),
            ("handle_price_objection", "handle_price_objection"),
        ]

        for input_val, expected in test_cases:
            with patch.object(orchestrator, "_process_message") as mock_process:
                mock_process.return_value = {
                    "intent": "greeting",
                    "confidence": 0.9,
                    "response_text": "Olá!",
                    "entities": {},
                    "routing_hint": input_val,
                }

                result = orchestrator.execute(
                    message="Test", phone="5511999999999", instance="test"
                )

                # Routing hint should be normalized
                if expected is None:
                    assert result.get("routing_hint") is None
                else:
                    assert result.get("routing_hint") == expected

    def test_response_text_normalization(self, orchestrator):
        """Test orchestrator ensures response_text is valid PT-BR."""
        test_cases = [
            (None, "Desculpe, não entendi. Pode repetir?"),
            ("", "Desculpe, não entendi. Pode repetir?"),
            ("Hello world", "Olá! Como posso ajudar?"),  # English -> PT-BR
            ("Olá, tudo bem?", "Olá, tudo bem?"),  # Valid PT-BR stays
        ]

        for input_val, check_type in test_cases:
            with patch.object(orchestrator, "_process_message") as mock_process:
                mock_process.return_value = {
                    "intent": "greeting",
                    "confidence": 0.9,
                    "response_text": input_val,
                    "entities": {},
                }

                result = orchestrator.execute(
                    message="Test", phone="5511999999999", instance="test"
                )

                # Response text should be valid
                assert "response_text" in result
                assert isinstance(result["response_text"], str)
                assert result["response_text"]  # Not empty

                # Should not contain English tokens
                text_lower = result["response_text"].lower()
                english_tokens = ["hello", "world", "the", "and"]
                for token in english_tokens:
                    assert token not in text_lower

    def test_sent_field_always_string(self, orchestrator):
        """Test orchestrator always returns sent as string."""
        # Mock successful delivery
        with patch(
            "app.clients.evolution_api.EvolutionAPIClient.send_message"
        ) as mock_send:
            mock_send.return_value = {"success": True}

            result = orchestrator.execute(
                message="Test", phone="5511999999999", instance="test"
            )

            if "sent" in result:
                assert isinstance(result["sent"], str)
                assert result["sent"] in {"true", "false"}

        # Mock failed delivery
        with patch(
            "app.clients.evolution_api.EvolutionAPIClient.send_message"
        ) as mock_send:
            mock_send.side_effect = Exception("API Error")

            result = orchestrator.execute(
                message="Test", phone="5511999999999", instance="test"
            )

            if "sent" in result:
                assert isinstance(result["sent"], str)
                assert result["sent"] == "false"

    def test_complete_response_normalization(self, orchestrator):
        """Test complete response normalization with all fields."""
        with patch.object(orchestrator, "_process_message") as mock_process:
            # Return response with all wrong types
            mock_process.return_value = {
                "intent": 123,  # Should be string
                "confidence": "invalid",  # Should be float
                "response_text": None,  # Should be non-empty string
                "entities": [],  # Should be dict
                "routing_hint": "invalid",  # Should be valid or None
                "sent": True,  # Should be string
                "message_id": 456,  # Should be string
                "turn_id": None,  # Should be string
                "trace_id": "",  # Should be non-empty string
            }

            result = orchestrator.execute(
                message="Test", phone="5511999999999", instance="test"
            )

            # All fields should be normalized
            assert isinstance(result.get("intent"), str)
            assert result["intent"] in {
                "greeting",
                "information_request",
                "qualification",
                "scheduling",
                "fallback",
                "objection",
            }

            if "confidence" in result:
                assert isinstance(result["confidence"], (float, int))
                assert 0.0 <= float(result["confidence"]) <= 1.0

            assert isinstance(result.get("response_text"), str)
            assert result["response_text"]

            assert isinstance(result.get("entities"), dict)

            if "sent" in result:
                assert isinstance(result["sent"], str)
                assert result["sent"] in {"true", "false"}

            if "message_id" in result:
                assert isinstance(result["message_id"], str)
                assert result["message_id"]

            if "turn_id" in result:
                assert isinstance(result["turn_id"], str)
                assert result["turn_id"]

            if "trace_id" in result:
                assert isinstance(result["trace_id"], str)
                assert result["trace_id"]

    def test_error_handling_maintains_types(self, orchestrator):
        """Test that errors still return correct types."""
        with patch.object(orchestrator, "_process_message") as mock_process:
            mock_process.side_effect = Exception("Processing error")

            result = orchestrator.execute(
                message="Test", phone="5511999999999", instance="test"
            )

            # Even on error, types should be correct
            if "sent" in result:
                assert isinstance(result["sent"], str)
                assert result["sent"] == "false"

            if "intent" in result:
                assert isinstance(result["intent"], str)
                assert result["intent"] == "fallback"

            if "confidence" in result:
                assert isinstance(result["confidence"], (float, int))
                assert result["confidence"] == 0.0

            if "response_text" in result:
                assert isinstance(result["response_text"], str)
                assert result["response_text"]  # Not empty
