"""
Contract tests for OpenAI adapter.
"""
from unittest.mock import Mock, patch

import pytest


class TestOpenAIAdapterContract:
    """Test suite for OpenAI adapter contract compliance."""

    @pytest.mark.asyncio
    async def test_returns_string_non_empty_ptbr(self):
        """Test that adapter returns non-empty PT-BR string."""
        from app.core.llm.openai_adapter import OpenAIClient

        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Olá! Como posso ajudar você hoje?"

        with patch("app.core.llm.openai_adapter.OpenAI") as mock_openai_class:
            mock_client = Mock()
            mock_client.chat.completions.create = Mock(return_value=mock_response)
            mock_openai_class.return_value = mock_client

            adapter = OpenAIClient(api_key="test_key")
            result = await adapter.chat(
                model="gpt-3.5-turbo", system_prompt="Be helpful", user_prompt="Hello"
            )

            # Assertions
            assert isinstance(result, str)
            assert len(result.strip()) > 0
            assert result == "Olá! Como posso ajudar você hoje?"

    @pytest.mark.asyncio
    async def test_applies_system_prompt_ptbr(self):
        """Test that system prompt enforces PT-BR."""
        from app.core.llm.openai_adapter import OpenAIClient

        captured_messages = []

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Resposta em português"

        with patch("app.core.llm.openai_adapter.OpenAI") as mock_openai_class:
            mock_client = Mock()

            def capture_create(**kwargs):
                captured_messages.extend(kwargs.get("messages", []))
                return mock_response

            mock_client.chat.completions.create = Mock(side_effect=capture_create)
            mock_openai_class.return_value = mock_client

            adapter = OpenAIClient(api_key="test_key")
            await adapter.chat(
                model="gpt-3.5-turbo", system_prompt="Be helpful", user_prompt="Hello"
            )

            # Check that PT-BR was enforced in system prompt
            assert len(captured_messages) == 2
            system_msg = captured_messages[0]
            assert system_msg["role"] == "system"
            # Check for Portuguese enforcement (with or without accent)
            content_lower = system_msg["content"].lower()
            assert (
                "portugues" in content_lower or "português" in content_lower
            ) and "brasil" in content_lower

    @pytest.mark.asyncio
    async def test_respects_temperature_and_max_tokens(self):
        """Test that temperature and max_tokens are passed correctly."""
        from app.core.llm.openai_adapter import OpenAIClient

        captured_params = {}

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"

        with patch("app.core.llm.openai_adapter.OpenAI") as mock_openai_class:
            mock_client = Mock()

            def capture_params(**kwargs):
                captured_params.update(kwargs)
                return mock_response

            mock_client.chat.completions.create = Mock(side_effect=capture_params)
            mock_openai_class.return_value = mock_client

            adapter = OpenAIClient(api_key="test_key")
            await adapter.chat(
                model="gpt-3.5-turbo",
                system_prompt="Test",
                user_prompt="Test",
                temperature=0.7,
                max_tokens=150,
            )

            # Verify parameters
            assert captured_params["temperature"] == 0.7
            assert captured_params["max_tokens"] == 150
            assert captured_params["model"] == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_timeout_enforced(self):
        """Test that timeout is enforced and handled gracefully."""
        import openai

        from app.core.llm.openai_adapter import OpenAIClient

        with patch("app.core.llm.openai_adapter.OpenAI") as mock_openai_class:
            mock_client = Mock()

            # Simulate timeout error
            mock_client.chat.completions.create = Mock(
                side_effect=openai.APITimeoutError(request=Mock(url="test"))
            )
            mock_openai_class.return_value = mock_client

            adapter = OpenAIClient(api_key="test_key", timeout_s=1.0)

            # Should return fallback message on timeout
            result = await adapter.chat(
                model="gpt-3.5-turbo",
                system_prompt="Test",
                user_prompt="Test",
                timeout_s=0.1,  # Very short timeout
            )

            # Should return a fallback message, not raise
            assert isinstance(result, str)
            assert "desculpe" in result.lower() or "erro" in result.lower()
