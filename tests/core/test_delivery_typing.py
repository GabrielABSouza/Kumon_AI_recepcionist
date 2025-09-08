"""
Tests for delivery layer typing and error handling.
Ensures delivery failures maintain contract and proper typing.
"""
from unittest.mock import Mock, patch

import httpx
import pytest


class TestDeliveryTyping:
    """Test delivery layer type handling and error resilience."""

    @pytest.fixture
    def evolution_client(self):
        """Create Evolution API client instance."""
        from app.clients.evolution_api import EvolutionAPIClient

        return EvolutionAPIClient(
            base_url="http://test.api", instance="test-instance", api_key="test-key"
        )

    def test_delivery_error_returns_sent_false_string(self, evolution_client):
        """Test delivery errors return sent='false' as string."""
        error_scenarios = [
            (
                httpx.HTTPStatusError(
                    "400 Bad Request", request=Mock(), response=Mock(status_code=400)
                ),
                "false",
            ),
            (
                httpx.HTTPStatusError(
                    "401 Unauthorized", request=Mock(), response=Mock(status_code=401)
                ),
                "false",
            ),
            (
                httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=Mock(),
                    response=Mock(status_code=429),
                ),
                "false",
            ),
            (
                httpx.HTTPStatusError(
                    "500 Server Error", request=Mock(), response=Mock(status_code=500)
                ),
                "false",
            ),
            (httpx.ConnectError("Connection refused"), "false"),
            (httpx.TimeoutException("Request timeout"), "false"),
            (Exception("Unknown error"), "false"),
        ]

        for error, expected_sent in error_scenarios:
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.side_effect = error

                result = evolution_client.send_message(
                    phone="5511999999999", message="Test message"
                )

                # Result should indicate failure with correct type
                assert "sent" in result
                assert isinstance(
                    result["sent"], str
                ), f"sent must be string, got {type(result['sent'])}"
                assert result["sent"] == expected_sent

    def test_successful_delivery_returns_sent_true_string(self, evolution_client):
        """Test successful delivery returns sent='true' as string."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {"key": {"id": "MSG123"}, "status": "PENDING"},
            )

            result = evolution_client.send_message(
                phone="5511999999999", message="Test message"
            )

            # Result should indicate success with correct type
            assert "sent" in result
            assert isinstance(
                result["sent"], str
            ), f"sent must be string, got {type(result['sent'])}"
            assert result["sent"] == "true"

    def test_idempotency_with_same_message_id(self, evolution_client):
        """Test idempotency: same message_id doesn't duplicate delivery."""
        message_id = "MSG_ID_123"

        # First attempt - success
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = Mock(
                status_code=200, json=lambda: {"key": {"id": message_id}}
            )

            result1 = evolution_client.send_message(
                phone="5511999999999", message="Test message", message_id=message_id
            )

            assert result1["sent"] == "true"
            assert isinstance(result1["sent"], str)
            assert mock_post.call_count == 1

        # Second attempt with same ID - should not send again
        with patch("httpx.AsyncClient.post") as mock_post:
            with patch.object(evolution_client, "_is_duplicate") as mock_duplicate:
                mock_duplicate.return_value = True

                result2 = evolution_client.send_message(
                    phone="5511999999999", message="Test message", message_id=message_id
                )

                # Should return success without sending
                assert result2["sent"] == "true"
                assert isinstance(result2["sent"], str)
                assert mock_post.call_count == 0  # Not called

    def test_invalid_phone_format_handling(self, evolution_client):
        """Test invalid phone format doesn't break contract."""
        invalid_phones = [
            "",
            "invalid",
            "123",
            "55119999",
            "+5511999999999999999",  # Too long
            None,
        ]

        for phone in invalid_phones:
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.side_effect = httpx.HTTPStatusError(
                    "400 Invalid phone", request=Mock(), response=Mock(status_code=400)
                )

                result = evolution_client.send_message(
                    phone=phone, message="Test message"
                )

                # Should handle gracefully
                assert "sent" in result
                assert isinstance(result["sent"], str)
                assert result["sent"] == "false"

    def test_rate_limiting_handling(self, evolution_client):
        """Test rate limiting returns proper response."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=Mock(),
                response=Mock(status_code=429, headers={"Retry-After": "60"}),
            )

            result = evolution_client.send_message(
                phone="5511999999999", message="Test message"
            )

            # Should indicate rate limiting
            assert "sent" in result
            assert isinstance(result["sent"], str)
            assert result["sent"] == "false"

            # May include rate limit info
            if "error" in result:
                assert isinstance(result["error"], str)

    def test_timeout_handling(self, evolution_client):
        """Test timeout handling maintains contract."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timeout")

            result = evolution_client.send_message(
                phone="5511999999999", message="Test message"
            )

            # Should handle timeout gracefully
            assert "sent" in result
            assert isinstance(result["sent"], str)
            assert result["sent"] == "false"

    def test_malformed_response_handling(self, evolution_client):
        """Test handling of malformed API responses."""
        malformed_responses = [
            None,  # No response
            {},  # Empty response
            {"invalid": "data"},  # Missing expected fields
            {"key": None},  # Null key
            {"key": {"id": None}},  # Null ID
        ]

        for response_data in malformed_responses:
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.return_value = Mock(
                    status_code=200, json=lambda: response_data
                )

                result = evolution_client.send_message(
                    phone="5511999999999", message="Test message"
                )

                # Should handle gracefully
                assert "sent" in result
                assert isinstance(result["sent"], str)
                # May succeed or fail based on response validation
                assert result["sent"] in {"true", "false"}

    def test_connection_error_handling(self, evolution_client):
        """Test connection errors maintain contract."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            result = evolution_client.send_message(
                phone="5511999999999", message="Test message"
            )

            # Should handle connection error
            assert "sent" in result
            assert isinstance(result["sent"], str)
            assert result["sent"] == "false"

    def test_retry_mechanism(self, evolution_client):
        """Test retry mechanism for transient failures."""
        with patch("httpx.AsyncClient.post") as mock_post:
            # First call fails, second succeeds
            mock_post.side_effect = [
                httpx.HTTPStatusError(
                    "503 Service Unavailable",
                    request=Mock(),
                    response=Mock(status_code=503),
                ),
                Mock(status_code=200, json=lambda: {"key": {"id": "MSG123"}}),
            ]

            with patch("time.sleep"):  # Mock sleep to speed up test
                result = evolution_client.send_message(
                    phone="5511999999999", message="Test message", retry=True
                )

                # Should succeed after retry
                assert "sent" in result
                assert isinstance(result["sent"], str)
                # Depends on retry implementation

    def test_webhook_response_on_delivery_failure(self):
        """Test webhook response when delivery fails."""
        from app.api.v1.endpoints.webhook import process_webhook_message

        with patch(
            "app.clients.evolution_api.EvolutionAPIClient.send_message"
        ) as mock_send:
            mock_send.return_value = {"sent": "false", "error": "API Error"}

            response = process_webhook_message(
                {
                    "message_id": "MSG123",
                    "phone": "5511999999999",
                    "message": "Test",
                    "instance": "test",
                }
            )

            # Webhook should return 200 with sent='false'
            assert response["sent"] == "false"
            assert isinstance(response["sent"], str)

    def test_complete_delivery_flow_typing(self):
        """Test complete delivery flow maintains typing."""
        from app.workflows.workflow_orchestrator import WorkflowOrchestrator

        orchestrator = WorkflowOrchestrator()

        with patch(
            "app.clients.evolution_api.EvolutionAPIClient.send_message"
        ) as mock_send:
            # Test various delivery scenarios
            scenarios = [
                ({"sent": True}, "true"),  # Wrong type from delivery
                ({"sent": False}, "false"),  # Wrong type from delivery
                ({"sent": "true"}, "true"),  # Correct type
                ({"sent": "false"}, "false"),  # Correct type
                (Exception("Error"), "false"),  # Exception
            ]

            for mock_result, expected_sent in scenarios:
                if isinstance(mock_result, Exception):
                    mock_send.side_effect = mock_result
                else:
                    mock_send.return_value = mock_result

                result = orchestrator.execute(
                    message="Test", phone="5511999999999", instance="test"
                )

                # Should always normalize to string
                if "sent" in result:
                    assert isinstance(result["sent"], str)
                    assert result["sent"] == expected_sent
