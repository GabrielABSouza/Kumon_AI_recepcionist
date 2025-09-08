"""
Property-based fuzz testing with Hypothesis.
Tests type normalization under random malformed inputs.
"""
import string
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite


# Custom strategies for generating malformed data
@composite
def malformed_sent(draw):
    """Generate various malformed 'sent' values."""
    return draw(
        st.one_of(
            st.booleans(),  # Boolean instead of string
            st.integers(),  # Integer instead of string
            st.floats(),  # Float instead of string
            st.none(),  # None
            st.text(min_size=0, max_size=10),  # Random string
            st.lists(st.integers()),  # List instead of string
            st.dictionaries(st.text(), st.text()),  # Dict instead of string
        )
    )


@composite
def malformed_confidence(draw):
    """Generate various malformed confidence values."""
    return draw(
        st.one_of(
            st.text(alphabet=string.ascii_letters),  # Non-numeric string
            st.floats(min_value=-100, max_value=100),  # Out of range float
            st.integers(min_value=-100, max_value=100),  # Integer
            st.none(),  # None
            st.lists(st.floats()),  # List of floats
            st.booleans(),  # Boolean
        )
    )


@composite
def malformed_entities(draw):
    """Generate various malformed entities values."""
    return draw(
        st.one_of(
            st.none(),  # None
            st.lists(st.text()),  # List instead of dict
            st.text(),  # String instead of dict
            st.integers(),  # Integer instead of dict
            st.booleans(),  # Boolean instead of dict
            st.lists(st.dictionaries(st.text(), st.text())),  # List of dicts
        )
    )


@composite
def malformed_intent(draw):
    """Generate various malformed intent values."""
    return draw(
        st.one_of(
            st.none(),  # None
            st.integers(),  # Integer instead of string
            st.floats(),  # Float instead of string
            st.booleans(),  # Boolean instead of string
            st.text(min_size=0, max_size=50),  # Random string
            st.lists(st.text()),  # List instead of string
        )
    )


@composite
def malformed_response(draw):
    """Generate a completely malformed response."""
    return {
        "message_id": draw(st.one_of(st.text(), st.integers(), st.none())),
        "turn_id": draw(st.one_of(st.text(), st.integers(), st.none())),
        "trace_id": draw(st.one_of(st.text(), st.integers(), st.none())),
        "intent": draw(malformed_intent()),
        "confidence": draw(malformed_confidence()),
        "response_text": draw(st.one_of(st.text(), st.none(), st.integers())),
        "routing_hint": draw(st.one_of(st.text(), st.none(), st.integers())),
        "entities": draw(malformed_entities()),
        "sent": draw(malformed_sent()),
    }


class TestTypingFuzz:
    """Property-based tests for type normalization."""

    @given(sent_value=malformed_sent())
    @settings(max_examples=100, deadline=1000)
    def test_sent_normalization_fuzz(self, sent_value):
        """Test that any 'sent' value gets normalized to string 'true'/'false'."""
        from app.api.v1.endpoints.webhook import normalize_webhook_response

        response = {
            "message_id": "MSG123",
            "turn_id": "turn_001",
            "trace_id": "trace_123",
            "intent": "greeting",
            "confidence": 0.9,
            "response_text": "Olá!",
            "routing_hint": None,
            "entities": {},
            "sent": sent_value,
        }

        normalized = normalize_webhook_response(response)

        # Must always be string 'true' or 'false'
        assert isinstance(normalized["sent"], str)
        assert normalized["sent"] in {"true", "false"}

    @given(confidence_value=malformed_confidence())
    @settings(max_examples=100, deadline=1000)
    def test_confidence_normalization_fuzz(self, confidence_value):
        """Test that any confidence value gets normalized to float 0.0-1.0."""
        from app.api.v1.endpoints.webhook import normalize_webhook_response

        response = {
            "message_id": "MSG123",
            "turn_id": "turn_001",
            "trace_id": "trace_123",
            "intent": "greeting",
            "confidence": confidence_value,
            "response_text": "Olá!",
            "routing_hint": None,
            "entities": {},
            "sent": "true",
        }

        normalized = normalize_webhook_response(response)

        # Must always be float between 0.0 and 1.0
        assert isinstance(normalized["confidence"], (float, int))
        assert 0.0 <= float(normalized["confidence"]) <= 1.0

        # Invalid confidence should trigger fallback intent
        if not isinstance(confidence_value, (int, float)) or not (
            0.0 <= float(confidence_value) <= 1.0
        ):
            assert normalized["intent"] == "fallback"

    @given(entities_value=malformed_entities())
    @settings(max_examples=100, deadline=1000)
    def test_entities_normalization_fuzz(self, entities_value):
        """Test that any entities value gets normalized to dict."""
        from app.api.v1.endpoints.webhook import normalize_webhook_response

        response = {
            "message_id": "MSG123",
            "turn_id": "turn_001",
            "trace_id": "trace_123",
            "intent": "greeting",
            "confidence": 0.9,
            "response_text": "Olá!",
            "routing_hint": None,
            "entities": entities_value,
            "sent": "true",
        }

        normalized = normalize_webhook_response(response)

        # Must always be dict
        assert isinstance(normalized["entities"], dict)

    @given(intent_value=malformed_intent())
    @settings(max_examples=100, deadline=1000)
    def test_intent_normalization_fuzz(self, intent_value):
        """Test that any intent value gets normalized to valid intent."""
        from app.api.v1.endpoints.webhook import normalize_webhook_response

        response = {
            "message_id": "MSG123",
            "turn_id": "turn_001",
            "trace_id": "trace_123",
            "intent": intent_value,
            "confidence": 0.9,
            "response_text": "Olá!",
            "routing_hint": None,
            "entities": {},
            "sent": "true",
        }

        normalized = normalize_webhook_response(response)

        # Must always be valid intent
        valid_intents = {
            "greeting",
            "information_request",
            "qualification",
            "scheduling",
            "fallback",
            "objection",
        }
        assert isinstance(normalized["intent"], str)
        assert normalized["intent"] in valid_intents

    @given(response=malformed_response())
    @settings(max_examples=50, deadline=2000)
    def test_complete_response_normalization_fuzz(self, response):
        """Test that completely malformed response gets normalized."""
        from app.api.v1.endpoints.webhook import normalize_webhook_response

        normalized = normalize_webhook_response(response)

        # All required fields must exist and have correct types
        assert isinstance(normalized["message_id"], str)
        assert normalized["message_id"]

        assert isinstance(normalized["turn_id"], str)
        assert normalized["turn_id"]

        assert isinstance(normalized["trace_id"], str)
        assert normalized["trace_id"]

        assert isinstance(normalized["intent"], str)
        assert normalized["intent"] in {
            "greeting",
            "information_request",
            "qualification",
            "scheduling",
            "fallback",
            "objection",
        }

        assert isinstance(normalized["confidence"], (float, int))
        assert 0.0 <= float(normalized["confidence"]) <= 1.0

        assert isinstance(normalized["response_text"], str)
        assert normalized["response_text"]

        if normalized.get("routing_hint") is not None:
            assert isinstance(normalized["routing_hint"], str)
            assert normalized["routing_hint"] in {
                "handle_price_objection",
                "ask_clarification",
                "handoff_human",
            }

        assert isinstance(normalized["entities"], dict)

        assert isinstance(normalized["sent"], str)
        assert normalized["sent"] in {"true", "false"}

    @given(
        sent=malformed_sent(),
        confidence=malformed_confidence(),
        entities=malformed_entities(),
        intent=malformed_intent(),
    )
    @settings(max_examples=50, deadline=2000)
    def test_webhook_never_crashes_fuzz(self, sent, confidence, entities, intent):
        """Test that webhook never crashes regardless of input."""
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)

        with patch(
            "app.workflows.workflow_orchestrator.WorkflowOrchestrator.execute"
        ) as mock_execute:
            # Return malformed response
            mock_execute.return_value = {
                "message_id": "MSG123",
                "turn_id": "turn_001",
                "trace_id": "trace_123",
                "intent": intent,
                "confidence": confidence,
                "response_text": "Test",
                "routing_hint": None,
                "entities": entities,
                "sent": sent,
            }

            request_data = {
                "event": "messages.upsert",
                "instance": "test",
                "data": {
                    "key": {
                        "remoteJid": "5511999999999@s.whatsapp.net",
                        "fromMe": False,
                        "id": "MSG123",
                    },
                    "message": {"conversation": "Test"},
                    "messageType": "conversation",
                },
            }

            # Should never crash
            response = client.post(
                "/api/v1/evolution/webhook",
                json=request_data,
                headers={"x-api-key": "test-key"},
            )

            # Should always return 200
            assert response.status_code == 200

            # Should always have valid response
            data = response.json()
            if "sent" in data:
                assert isinstance(data["sent"], str)
                assert data["sent"] in {"true", "false"}

    @given(st.data())
    @settings(max_examples=20, deadline=3000)
    def test_orchestrator_normalization_chain_fuzz(self, data):
        """Test normalization chain from orchestrator to webhook."""
        from app.api.v1.endpoints.webhook import normalize_webhook_response
        from app.workflows.workflow_orchestrator import WorkflowOrchestrator

        # Generate random malformed data
        malformed_data = {
            "intent": data.draw(malformed_intent()),
            "confidence": data.draw(malformed_confidence()),
            "response_text": data.draw(st.one_of(st.text(), st.none())),
            "entities": data.draw(malformed_entities()),
            "routing_hint": data.draw(st.one_of(st.text(), st.none())),
            "sent": data.draw(malformed_sent()),
        }

        # Pass through normalization chain
        orchestrator = WorkflowOrchestrator()
        with patch.object(orchestrator, "_process_message") as mock_process:
            mock_process.return_value = malformed_data

            # Orchestrator should normalize
            orchestrator_result = orchestrator.execute(
                message="Test", phone="5511999999999", instance="test"
            )

            # Webhook should further normalize if needed
            final_result = normalize_webhook_response(orchestrator_result)

            # Final result must be valid
            assert isinstance(final_result.get("sent"), str)
            assert final_result.get("sent") in {"true", "false"}

            assert isinstance(final_result.get("entities"), dict)

            assert isinstance(final_result.get("intent"), str)
            assert final_result.get("intent") in {
                "greeting",
                "information_request",
                "qualification",
                "scheduling",
                "fallback",
                "objection",
            }

            if "confidence" in final_result:
                assert isinstance(final_result["confidence"], (float, int))
                assert 0.0 <= float(final_result["confidence"]) <= 1.0
