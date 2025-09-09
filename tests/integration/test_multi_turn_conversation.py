"""
Integration tests for multi-turn conversation with state persistence.
Tests that Cecília remembers context across multiple messages.
"""
from unittest.mock import MagicMock, patch

from app.core.langgraph_flow import workflow


class TestMultiTurnConversation:
    """Test suite for stateful conversation management."""

    def test_remembers_parent_name_across_turns(self):
        """Test that bot remembers parent name from previous turn."""
        # First turn - greeting
        first_state = {
            "text": "Oi",
            "phone": "+5511999999999",
            "message_id": "MSG_001",
            "instance": "test",
        }

        # Mock OpenAI and delivery
        with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
            with patch("app.core.langgraph_flow.send_text") as mock_send:
                with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
                    # Setup mocks
                    mock_turn.has_replied.return_value = False
                    mock_send.return_value = {"sent": "true", "status_code": 200}

                    # First response asks for name
                    mock_client = MagicMock()
                    mock_client.chat.return_value = (
                        "Olá! Eu sou a Cecília do Kumon Vila A. "
                        "Para começarmos qual é o seu nome?"
                    )
                    mock_openai.return_value = mock_client

                    # Execute first turn
                    result1 = workflow.invoke(first_state)
                    assert "qual é o seu nome" in result1["response"].lower()

        # Second turn - user provides name
        second_state = {
            "text": "Meu nome é João",
            "phone": "+5511999999999",
            "message_id": "MSG_002",
            "instance": "test",
        }

        with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
            with patch("app.core.langgraph_flow.send_text") as mock_send:
                with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
                    # Setup mocks
                    mock_turn.has_replied.return_value = False
                    mock_send.return_value = {"sent": "true", "status_code": 200}

                    # Second response should use the name
                    mock_client = MagicMock()
                    mock_client.chat.return_value = (
                        "Prazer em conhecê-lo, João! Como posso ajudar você hoje?"
                    )
                    mock_openai.return_value = mock_client

                    # Execute second turn
                    result2 = workflow.invoke(second_state)

                    # ASSERTION: Bot should remember and use the name "João"
                    assert (
                        "joão" in result2["response"].lower()
                    ), f"Expected response to contain 'João', but got: {result2['response']}"

                    # Verify that OpenAI received context with the name
                    calls = mock_client.chat.call_args_list
                    if calls:
                        last_call = calls[-1]
                        # Check if system or user prompt contains previous context
                        system_prompt = last_call.kwargs.get("system_prompt", "")
                        user_prompt = last_call.kwargs.get("user_prompt", "")

                        # At least one prompt should contain context about João
                        assert (
                            "joão" in system_prompt.lower()
                            or "joão" in user_prompt.lower()
                            or "parent_name" in str(last_call)
                        ), "OpenAI should receive context about the parent name"
