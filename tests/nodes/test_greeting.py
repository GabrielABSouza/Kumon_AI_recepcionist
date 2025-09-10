"""
Tests for greeting node functionality.
Updated for new architecture - greeting_node no longer extracts entities globally.
Entity extraction is now localized to specific nodes that need specific information.
"""
from unittest.mock import MagicMock, patch

from app.core.langgraph_flow import greeting_node


class TestGreetingNode:
    """Test suite for greeting node functionality in new architecture."""

    def test_greeting_node_generates_response_and_sets_flag(self):
        """Test that greeting node generates response and sets greeting_sent flag."""
        # Input state simulating webhook data
        state_input = {
            "text": "Oi, boa tarde!",
            "phone": "+5511999999999",
            "message_id": "MSG_GREETING",
            "instance": "test",
        }

        # Mock dependencies
        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                with patch("app.core.langgraph_flow.send_text") as mock_send:
                    with patch(
                        "app.core.langgraph_flow.save_conversation_state"
                    ) as mock_save:
                        # Setup mocks
                        mock_get_state.return_value = {}  # New conversation
                        mock_send.return_value = {
                            "sent": "true",
                            "status_code": 200,
                        }

                        mock_client = MagicMock()

                        # Create async mock for OpenAI response
                        async def mock_chat(*args, **kwargs):
                            return "Olá! Eu sou a Cecília do Kumon Vila A. Qual é o seu nome?"

                        mock_client.chat = mock_chat
                        mock_openai.return_value = mock_client

                        # Execute greeting node
                        result = greeting_node(state_input)

                        # ASSERTION 1: Should return result with greeting_sent flag
                        assert (
                            "greeting_sent" in result
                        ), "greeting_node should set greeting_sent flag"
                        assert (
                            result["greeting_sent"] is True
                        ), "greeting_sent should be True"

                        # ASSERTION 2: Should send a response
                        assert mock_send.called, "Should send a greeting response"

                        # ASSERTION 3: Should save state (standard flow)
                        assert mock_save.called, "Should save conversation state"

    def test_greeting_node_handles_empty_text(self):
        """Test that greeting node handles empty or missing text gracefully."""
        state_input = {
            "text": "",  # Empty text
            "phone": "+5511999999999",
            "message_id": "MSG_EMPTY",
            "instance": "test",
        }

        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                with patch("app.core.langgraph_flow.send_text") as mock_send:
                    with patch(
                        "app.core.langgraph_flow.save_conversation_state"
                    ) as mock_save:
                        mock_get_state.return_value = {}
                        mock_send.return_value = {"sent": "true", "status_code": 200}

                        mock_client = MagicMock()

                        async def mock_chat(*args, **kwargs):
                            return "Olá! Como posso ajudar?"

                        mock_client.chat = mock_chat
                        mock_openai.return_value = mock_client

                        # Should not crash
                        result = greeting_node(state_input)

                        # Should still set the flag and process normally
                        assert result.get("greeting_sent") is True

    def test_greeting_node_uses_execute_node_framework(self):
        """Test that greeting node properly uses the _execute_node framework."""
        state_input = {
            "text": "Olá",
            "phone": "+5511999999999",
            "message_id": "MSG_FRAMEWORK",
            "instance": "test",
        }

        with patch("app.core.langgraph_flow._execute_node") as mock_execute:
            with patch("app.core.langgraph_flow.get_greeting_prompt"):
                # Mock _execute_node to return a basic result
                mock_execute.return_value = {
                    "response": "Test response",
                    "phone": "+5511999999999",
                }

                result = greeting_node(state_input)

                # ASSERTION 1: Should call _execute_node with correct parameters
                mock_execute.assert_called_once()
                call_args = mock_execute.call_args[0]
                assert call_args[0] == state_input, "Should pass input state"
                assert call_args[1] == "greeting", "Should use 'greeting' as node name"

                # ASSERTION 2: Should add greeting_sent flag to result
                assert result["greeting_sent"] is True, "Should add greeting_sent flag"
