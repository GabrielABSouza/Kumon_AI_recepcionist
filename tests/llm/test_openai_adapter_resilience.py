"""
Resilience tests for OpenAI adapter.
"""
from unittest.mock import Mock, patch

import pytest


class TestOpenAIAdapterResilience:
    """Test suite for OpenAI adapter resilience and error handling."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_then_success(self):
        """Test retry logic on rate limit errors."""
        import openai

        from app.core.llm.openai_adapter import OpenAIClient

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Success after retry"

        with patch("app.core.llm.openai_adapter.OpenAI") as mock_openai_class:
            mock_client = Mock()

            # First call: rate limit error
            # Second call: success
            mock_client.chat.completions.create = Mock(
                side_effect=[
                    openai.RateLimitError(
                        message="Rate limit exceeded",
                        response=Mock(status_code=429),
                        body={},
                    ),
                    mock_response,
                ]
            )
            mock_openai_class.return_value = mock_client

            adapter = OpenAIClient(api_key="test_key")
            result = await adapter.chat(
                model="gpt-3.5-turbo", system_prompt="Test", user_prompt="Test"
            )

            # Should succeed after retry
            assert result == "Success after retry"
            # Should have been called twice
            assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_bad_request_400(self):
        """Test that 400 errors don't trigger retry."""
        import openai

        from app.core.llm.openai_adapter import OpenAIClient

        with patch("app.core.llm.openai_adapter.OpenAI") as mock_openai_class:
            mock_client = Mock()

            # BadRequest error (400)
            mock_client.chat.completions.create = Mock(
                side_effect=openai.BadRequestError(
                    message="Invalid request", response=Mock(status_code=400), body={}
                )
            )
            mock_openai_class.return_value = mock_client

            adapter = OpenAIClient(api_key="test_key")
            result = await adapter.chat(
                model="gpt-3.5-turbo", system_prompt="Test", user_prompt="Test"
            )

            # Should return fallback without retry
            assert isinstance(result, str)
            assert "desculpe" in result.lower() or "erro" in result.lower()
            # Should only be called once (no retry)
            assert mock_client.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_api_connection_error(self):
        """Test retry on connection errors."""
        import openai

        from app.core.llm.openai_adapter import OpenAIClient

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Success after connection retry"

        with patch("app.core.llm.openai_adapter.OpenAI") as mock_openai_class:
            mock_client = Mock()

            # First call: connection error
            # Second call: success
            mock_client.chat.completions.create = Mock(
                side_effect=[
                    openai.APIConnectionError(
                        message="Connection failed", request=Mock(url="test")
                    ),
                    mock_response,
                ]
            )
            mock_openai_class.return_value = mock_client

            adapter = OpenAIClient(api_key="test_key")
            result = await adapter.chat(
                model="gpt-3.5-turbo", system_prompt="Test", user_prompt="Test"
            )

            # Should succeed after retry
            assert result == "Success after connection retry"
            assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_logs_on_error_and_success(self, capsys):
        """Test that proper logs are generated."""
        import openai

        from app.core.llm.openai_adapter import OpenAIClient

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Success"

        with patch("app.core.llm.openai_adapter.OpenAI") as mock_openai_class:
            mock_client = Mock()

            # Simulate success
            mock_client.chat.completions.create = Mock(return_value=mock_response)
            mock_openai_class.return_value = mock_client

            adapter = OpenAIClient(api_key="test_key")

            # Test success logging
            result = await adapter.chat(
                model="gpt-3.5-turbo", system_prompt="Test", user_prompt="Test"
            )

            captured = capsys.readouterr()
            assert "LLM|req|model=gpt-3.5-turbo" in captured.out
            assert "LLM|res|" in captured.out

            # Test error logging
            mock_client.chat.completions.create = Mock(
                side_effect=openai.APIError(
                    message="Test error", request=Mock(url="test"), body=None
                )
            )

            await adapter.chat(
                model="gpt-3.5-turbo", system_prompt="Test", user_prompt="Test"
            )

            captured = capsys.readouterr()
            assert "LLM|error|" in captured.out
            assert "APIError" in captured.out

    @pytest.mark.asyncio
    async def test_max_retry_attempts_respected(self):
        """Test that retry stops after max attempts."""
        import openai

        from app.core.llm.openai_adapter import OpenAIClient

        with patch("app.core.llm.openai_adapter.OpenAI") as mock_openai_class:
            mock_client = Mock()

            # Always fail with rate limit
            mock_client.chat.completions.create = Mock(
                side_effect=openai.RateLimitError(
                    message="Rate limit", response=Mock(status_code=429), body={}
                )
            )
            mock_openai_class.return_value = mock_client

            adapter = OpenAIClient(api_key="test_key")
            result = await adapter.chat(
                model="gpt-3.5-turbo", system_prompt="Test", user_prompt="Test"
            )

            # Should return fallback after max attempts
            assert isinstance(result, str)
            # Should have tried 3 times (initial + 2 retries)
            assert mock_client.chat.completions.create.call_count == 3
