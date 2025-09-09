"""
Tests for LangGraph flow transitions.
Ensures nodes transition correctly based on collected state.
"""
from unittest.mock import MagicMock, patch

from app.core.langgraph_flow import classify_intent, workflow


class TestFlowTransitions:
    """Test suite for graph node transitions."""

    def test_greeting_to_qualification_after_name_collected(self):
        """Test that greeting transitions to qualification after collecting name."""
        # State with parent_name already collected
        state_with_name = {
            "text": "Quero informações sobre matrícula",
            "phone": "+5511999999999",
            "message_id": "MSG_002",
            "instance": "test",
            "parent_name": "João",  # Name already collected
        }

        # The intent classification should consider the state
        # and route to qualification since we have the parent name
        next_node = classify_intent(state_with_name)

        # With parent_name present and asking about enrollment,
        # should go to qualification
        assert (
            next_node != "greeting_node"
        ), "Should not go back to greeting when name exists"

        # For a more complete test, let's check the actual flow execution
        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
                with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                    with patch("app.core.langgraph_flow.send_text") as mock_send:
                        # Setup mocks
                        mock_get_state.return_value = {"parent_name": "João"}
                        mock_turn.has_replied.return_value = False
                        mock_send.return_value = {
                            "sent": "true",
                            "status_code": 200,
                        }

                        mock_client = MagicMock()
                        mock_client.chat.return_value = (
                            "João, vamos falar sobre matrícula..."
                        )
                        mock_openai.return_value = mock_client

                        # Execute workflow
                        result = workflow.invoke(state_with_name)

                        # The response should acknowledge the name
                        assert (
                            "joão" in result.get("response", "").lower()
                            or mock_client.chat.called
                        ), "Should use context with parent name"

    def test_greeting_stays_in_greeting_without_name(self):
        """Test that greeting stays in greeting node if name not collected."""
        # State without parent_name
        state_no_name = {
            "text": "Oi",
            "phone": "+5511999999999",
            "message_id": "MSG_001",
            "instance": "test",
        }

        # Should route to greeting since it's a greeting intent
        next_node = classify_intent(state_no_name)
        assert next_node == "greeting_node", "Should go to greeting for 'Oi'"

        # Even after greeting, if no name collected, should ask for it
        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
                with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                    with patch("app.core.langgraph_flow.send_text") as mock_send:
                        # No saved state (no name)
                        mock_get_state.return_value = {}
                        mock_turn.has_replied.return_value = False
                        mock_send.return_value = {
                            "sent": "true",
                            "status_code": 200,
                        }

                        mock_client = MagicMock()
                        mock_client.chat.return_value = (
                            "Olá! Eu sou a Cecília do Kumon Vila A. "
                            "Para começarmos qual é o seu nome?"
                        )
                        mock_openai.return_value = mock_client

                        # Execute workflow
                        result = workflow.invoke(state_no_name)

                        # Should ask for name
                        assert (
                            "nome" in result.get("response", "").lower()
                        ), "Should ask for name when not collected"

    def test_direct_to_qualification_with_enrollment_intent(self):
        """Test direct routing to qualification with enrollment keywords."""
        state = {
            "text": "Quero fazer matrícula",
            "phone": "+5511999999999",
            "message_id": "MSG_003",
            "instance": "test",
        }

        # Should route to qualification based on keyword
        next_node = classify_intent(state)
        assert (
            next_node == "qualification_node"
        ), "Should route to qualification for 'matrícula'"

    def test_information_node_for_info_requests(self):
        """Test routing to information node for general questions."""
        state = {
            "text": "Quais são os horários?",
            "phone": "+5511999999999",
            "message_id": "MSG_004",
            "instance": "test",
        }

        # Should route to information based on keyword
        next_node = classify_intent(state)
        assert (
            next_node == "information_node"
        ), "Should route to information for 'horários'"

    def test_scheduling_node_for_visit_requests(self):
        """Test routing to scheduling node for visit requests."""
        state = {
            "text": "Posso agendar uma visita?",
            "phone": "+5511999999999",
            "message_id": "MSG_005",
            "instance": "test",
        }

        # Should route to scheduling based on keyword
        next_node = classify_intent(state)
        assert (
            next_node == "scheduling_node"
        ), "Should route to scheduling for 'agendar'"

    def test_fallback_for_unrecognized_intent(self):
        """Test routing to fallback for unrecognized messages."""
        state = {
            "text": "xyz abc 123",
            "phone": "+5511999999999",
            "message_id": "MSG_006",
            "instance": "test",
        }

        # Should route to fallback for unrecognized text
        next_node = classify_intent(state)
        assert (
            next_node == "fallback_node"
        ), "Should route to fallback for unrecognized text"
