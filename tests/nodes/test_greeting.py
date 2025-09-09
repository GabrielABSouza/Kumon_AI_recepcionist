"""
Tests for greeting node entity extraction.
Ensures the greeting node correctly extracts parent name from user messages.
"""
from unittest.mock import MagicMock, patch

from app.core.langgraph_flow import _execute_node, get_greeting_prompt


class TestGreetingNode:
    """Test suite for greeting node functionality."""

    def test_greeting_extracts_parent_name_from_state(self):
        """Test that greeting node extracts parent name from user message."""
        # Initial state with user providing name
        state = {
            "text": "Oi, meu nome é Maria",
            "phone": "+5511999999999",
            "message_id": "MSG_001",
            "instance": "test",
        }

        # Mock dependencies
        with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
            with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                with patch("app.core.langgraph_flow.send_text") as mock_send:
                    with patch(
                        "app.core.langgraph_flow.get_conversation_state"
                    ) as mock_get_state:
                        with patch(
                            "app.core.langgraph_flow.save_conversation_state"
                        ) as mock_save:
                            # Setup mocks
                            mock_get_state.return_value = {}  # No existing state
                            mock_turn.has_replied.return_value = False
                            mock_send.return_value = {
                                "sent": "true",
                                "status_code": 200,
                            }

                            # Mock OpenAI response (async)
                            mock_client = MagicMock()

                            # Create async mock that returns a coroutine
                            async def mock_chat():
                                return "Prazer em conhecê-la, Maria! Como posso ajudar?"

                            mock_client.chat = mock_chat
                            mock_openai.return_value = mock_client

                            # Execute greeting node
                            _execute_node(state, "greeting", get_greeting_prompt)

                            # ASSERTION: Check that parent_name was extracted
                            # The save_conversation_state should be called with state
                            assert (
                                mock_save.called
                            ), "State should be saved after extraction"

                            # Get the state that was saved
                            saved_state = mock_save.call_args[0][
                                1
                            ]  # Second argument is the state dict

                            # Verify parent_name was extracted
                            assert (
                                "parent_name" in saved_state
                            ), "parent_name should be in saved state"
                            assert (
                                saved_state["parent_name"] == "Maria"
                            ), f"Expected 'Maria', got {saved_state.get('parent_name')}"

    def test_greeting_extracts_name_from_simple_answer(self):
        """Test extraction when user just answers with their name."""
        state = {
            "text": "João",  # Simple name as answer
            "phone": "+5511999999999",
            "message_id": "MSG_002",
            "instance": "test",
        }

        with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
            with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                with patch("app.core.langgraph_flow.send_text") as mock_send:
                    with patch(
                        "app.core.langgraph_flow.get_conversation_state"
                    ) as mock_get_state:
                        with patch(
                            "app.core.langgraph_flow.save_conversation_state"
                        ) as mock_save:
                            # Setup mocks
                            mock_get_state.return_value = {}  # No existing state
                            mock_turn.has_replied.return_value = False
                            mock_send.return_value = {
                                "sent": "true",
                                "status_code": 200,
                            }

                            mock_client = MagicMock()

                            # Create async mock that returns a coroutine
                            async def mock_chat():
                                return "Olá João!"

                            mock_client.chat = mock_chat
                            mock_openai.return_value = mock_client

                            # Execute
                            _execute_node(state, "greeting", get_greeting_prompt)

                            # Check saved state
                            saved_state = mock_save.call_args[0][1]
                            assert (
                                saved_state.get("parent_name") == "João"
                            ), "Should extract 'João' from simple answer"

    def test_greeting_preserves_existing_state(self):
        """Test that greeting node preserves other state fields."""
        state = {
            "text": "Me chamo Ana",
            "phone": "+5511999999999",
            "message_id": "MSG_003",
            "instance": "test",
            "custom_field": "should_be_preserved",
        }

        with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
            with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                with patch("app.core.langgraph_flow.send_text") as mock_send:
                    with patch(
                        "app.core.langgraph_flow.get_conversation_state"
                    ) as mock_get_state:
                        with patch(
                            "app.core.langgraph_flow.save_conversation_state"
                        ) as mock_save:
                            # Setup mocks
                            mock_get_state.return_value = {}  # No existing state
                            mock_turn.has_replied.return_value = False
                            mock_send.return_value = {
                                "sent": "true",
                                "status_code": 200,
                            }

                            mock_client = MagicMock()

                            # Create async mock that returns a coroutine
                            async def mock_chat():
                                return "Olá Ana!"

                            mock_client.chat = mock_chat
                            mock_openai.return_value = mock_client

                            # Execute
                            _execute_node(state, "greeting", get_greeting_prompt)

                            # Check that custom field is preserved
                            saved_state = mock_save.call_args[0][1]
                            assert (
                                saved_state.get("custom_field") == "should_be_preserved"
                            ), "Custom fields should be preserved"
                            assert (
                                saved_state.get("parent_name") == "Ana"
                            ), "Name should be extracted"
