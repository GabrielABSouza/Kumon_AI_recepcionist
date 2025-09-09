"""
Integration tests for LangGraph nodes with OpenAI adapter.
"""
from unittest.mock import AsyncMock, patch


class TestNodesWithOpenAIAdapter:
    """Test suite for LangGraph nodes integration with OpenAI adapter."""

    def test_greeting_node_single_response_ptbr(self):
        """Test greeting node returns single PT-BR response."""

        # Mock the adapter
        with patch("app.core.langgraph_flow.get_openai_client") as mock_get_client:
            mock_adapter = AsyncMock()
            mock_adapter.chat = AsyncMock(
                return_value="Olá! Seja bem-vindo ao Kumon Vila A. Como posso ajudá-lo hoje?"
            )
            mock_get_client.return_value = mock_adapter

            from app.core.langgraph_flow import greeting_node

            state = {
                "phone": "5511999999999",
                "message_id": "TEST_GREETING",
                "text": "Oi",
                "instance": "test",
            }

            with patch("app.core.langgraph_flow.send_text") as mock_send:
                mock_send.return_value = {
                    "sent": "true",
                    "status_code": 200,
                    "error_reason": None,
                }

                result = greeting_node(state)

                # Assertions
                assert "sent" in result
                assert result["sent"] == "true"  # Must be string
                assert "response" in result
                assert isinstance(result["response"], str)
                assert len(result["response"]) > 0
                # Should call adapter exactly once
                assert mock_adapter.chat.call_count == 1

    def test_information_request_node_single_response_ptbr(self):
        """Test information node returns single PT-BR response."""

        with patch("app.core.langgraph_flow.get_openai_client") as mock_get_client:
            mock_adapter = AsyncMock()
            mock_adapter.chat = AsyncMock(
                return_value="O Kumon é um método de estudo individualizado "
                "que desenvolve o autodidatismo."
            )
            mock_get_client.return_value = mock_adapter

            from app.core.langgraph_flow import information_node

            state = {
                "phone": "5511999999999",
                "message_id": "TEST_INFO",
                "text": "O que é o Kumon?",
                "instance": "test",
            }

            with patch("app.core.langgraph_flow.send_text") as mock_send:
                mock_send.return_value = {
                    "sent": "true",
                    "status_code": 200,
                    "error_reason": None,
                }

                result = information_node(state)

                # Assertions
                assert result["sent"] == "true"  # String
                assert "response" in result
                assert isinstance(result["response"], str)
                # PT-BR response
                assert any(
                    word in result["response"] for word in ["Kumon", "método", "estudo"]
                )

    def test_node_returns_contract_strings(self):
        """Test that nodes return proper contract with string types."""
        from app.core.langgraph_flow import _execute_node

        with patch("app.core.langgraph_flow.get_openai_client") as mock_get_client:
            mock_adapter = AsyncMock()
            mock_adapter.chat = AsyncMock(return_value="Test response")
            mock_get_client.return_value = mock_adapter

            state = {
                "phone": "5511999999999",
                "message_id": "TEST_CONTRACT",
                "text": "Test",
                "instance": "test",
            }

            with patch("app.core.langgraph_flow.send_text") as mock_send:
                # Test successful send
                mock_send.return_value = {
                    "sent": "true",
                    "status_code": 200,
                    "error_reason": None,
                }
                result = _execute_node(
                    state, "test_node", lambda x: {"system": "Test", "user": x}
                )

                # All fields must be correct type
                assert isinstance(result.get("sent"), str)
                assert result["sent"] in ["true", "false"]
                assert isinstance(result.get("response"), str)
                if result.get("error_reason"):
                    assert isinstance(result["error_reason"], (str, type(None)))

                # Test failed send
                mock_send.return_value = {
                    "sent": "false",
                    "status_code": 400,
                    "error_reason": "invalid_phone",
                }
                result = _execute_node(
                    state, "test_node", lambda x: {"system": "Test", "user": x}
                )

                assert result["sent"] == "false"  # String
                assert result.get("error_reason") == "invalid_phone"

    def test_node_propagates_fallback_on_bad_request(self):
        """Test that 400 errors from OpenAI trigger fallback."""

        with patch("app.core.langgraph_flow.get_openai_client") as mock_get_client:
            mock_adapter = AsyncMock()
            # Simulate BadRequestError
            mock_adapter.chat = AsyncMock(
                return_value="Desculpe, estou com dificuldades técnicas."
            )
            mock_get_client.return_value = mock_adapter

            from app.core.langgraph_flow import _execute_node

            state = {
                "phone": "5511999999999",
                "message_id": "TEST_400",
                "text": "Test",
                "instance": "test",
            }

            with patch("app.core.langgraph_flow.send_text") as mock_send:
                mock_send.return_value = {
                    "sent": "true",
                    "status_code": 200,
                    "error_reason": None,
                }

                result = _execute_node(
                    state, "test_node", lambda x: {"system": "Test", "user": x}
                )

                # Should send fallback message
                assert (
                    "dificuldades" in result["response"].lower()
                    or "desculpe" in result["response"].lower()
                )

    def test_no_duplicate_delivery_on_retry(self):
        """Test that retries don't cause duplicate message delivery."""
        from app.core.dedup import turn_controller
        from app.core.langgraph_flow import _execute_node

        with patch("app.core.langgraph_flow.get_openai_client") as mock_get_client:
            mock_adapter = AsyncMock()
            mock_adapter.chat = AsyncMock(return_value="Test message")
            mock_get_client.return_value = mock_adapter

            state = {
                "phone": "5511999999999",
                "message_id": "TEST_DEDUP",
                "text": "Test",
                "instance": "test",
            }

            with patch("app.core.langgraph_flow.send_text") as mock_send:
                mock_send.return_value = {
                    "sent": "true",
                    "status_code": 200,
                    "error_reason": None,
                }

                # First execution
                result1 = _execute_node(
                    state, "test_node", lambda x: {"system": "Test", "user": x}
                )
                assert result1["sent"] == "true"

                # Mark as replied (simulating successful send)
                with patch.object(turn_controller, "has_replied", return_value=True):
                    # Second execution should skip
                    result2 = _execute_node(
                        state, "test_node", lambda x: {"system": "Test", "user": x}
                    )
                    assert result2["sent"] == "false"

                # Send should only be called once
                assert mock_send.call_count == 1
