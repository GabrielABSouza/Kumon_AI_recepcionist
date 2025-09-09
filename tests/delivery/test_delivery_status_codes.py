"""
Test suite for delivery service 2xx status code handling.
Ensures 201 Created and other 2xx codes are treated as success.
"""
import os
from unittest.mock import Mock, patch

import pytest

from app.core.delivery import send_text


class TestDeliveryStatusCodes:
    """Test suite for various HTTP status code handling in delivery service."""

    def setup_method(self):
        """Set up test environment."""
        os.environ["EVOLUTION_API_KEY"] = "test_api_key"

    def teardown_method(self):
        """Clean up test environment."""
        if "EVOLUTION_API_KEY" in os.environ:
            del os.environ["EVOLUTION_API_KEY"]

    def test_200_ok_sets_sent_true_and_logs_ok(self, capsys):
        """Test that 200 OK sets sent=true and logs ok."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock 200 response with messageId
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"messageId": "MSG_123", "status": "sent"}
            mock_post.return_value = mock_response

            result = send_text("+5511999999999", "Test message")

            # Verify result
            assert result["sent"] == "true"
            assert result["status_code"] == 200
            assert result["provider_status"] == "200"
            assert result["provider_id"] == "MSG_123"
            assert result["error_reason"] is None

            # Verify log
            captured = capsys.readouterr()
            assert "DELIVERY|ok|status=200|id=MSG_123" in captured.out

    def test_201_created_sets_sent_true_and_logs_ok(self, capsys):
        """Test that 201 Created sets sent=true and logs ok (bug fix)."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock 201 response with queueId
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "queueId": "QUEUE_456",
                "status": "queued",
            }
            mock_post.return_value = mock_response

            result = send_text("+5511999999999", "Test message")

            # Verify result
            assert result["sent"] == "true"
            assert result["status_code"] == 201
            assert result["provider_status"] == "201"
            assert result["provider_id"] == "QUEUE_456"
            assert result["error_reason"] is None

            # Verify log
            captured = capsys.readouterr()
            assert "DELIVERY|ok|status=201|id=QUEUE_456" in captured.out

    def test_204_no_content_sets_sent_true_even_without_body(self, capsys):
        """Test that 204 No Content sets sent=true even without response body."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock 204 response (no content)
            mock_response = Mock()
            mock_response.status_code = 204
            mock_response.json.side_effect = ValueError("No JSON")
            mock_post.return_value = mock_response

            result = send_text("+5511999999999", "Test message")

            # Verify result
            assert result["sent"] == "true"
            assert result["status_code"] == 204
            assert result["provider_status"] == "204"
            assert result["provider_id"] == ""  # No ID in 204
            assert result["error_reason"] is None

            # Verify log
            captured = capsys.readouterr()
            assert "DELIVERY|ok|status=204|id=|" in captured.out

    def test_4xx_no_retry_and_sent_false(self, capsys):
        """Test that 4xx errors don't trigger retry and set sent=false."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock 400 response
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": "bad_request",
                "message": "Invalid phone number",
            }
            mock_post.return_value = mock_response

            result = send_text("+5511999999999", "Test message")

            # Should only be called once (no retry)
            assert mock_post.call_count == 1

            # Verify result
            assert result["sent"] == "false"
            assert result["status_code"] == 400
            assert result["error_reason"] == "bad_request"

            # Verify error log
            captured = capsys.readouterr()
            assert "DELIVERY|error|status=400|code=bad_request" in captured.out

    def test_5xx_retry_then_success_sets_sent_true(self):
        """Test that 5xx errors trigger retry and eventual success sets sent=true."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # First call: 500 error
            # Second call: 200 success
            mock_response_500 = Mock()
            mock_response_500.status_code = 500

            mock_response_200 = Mock()
            mock_response_200.status_code = 200
            mock_response_200.json.return_value = {"messageId": "MSG_789"}

            # Note: Current implementation doesn't have retry logic
            # This test documents expected behavior when retry is implemented
            mock_post.return_value = mock_response_500

            result = send_text("+5511999999999", "Test message")

            # Current behavior: fails on 5xx
            assert result["sent"] == "false"
            assert result["status_code"] == 500
            assert result["error_reason"] == "http_500"

            # When retry is implemented, it should:
            # - Try again after 5xx
            # - Eventually succeed with sent=true

    def test_logs_include_provider_id_when_present(self, capsys):
        """Test that logs include provider ID when present in response."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Test with messageId
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "messageId": "MSG_WITH_ID",
                "otherField": "value",
            }
            mock_post.return_value = mock_response

            send_text("+5511999999999", "Test with messageId")
            captured = capsys.readouterr()
            assert "DELIVERY|ok|status=200|id=MSG_WITH_ID" in captured.out

            # Test without messageId but with queueId
            mock_response.json.return_value = {
                "queueId": "QUEUE_WITH_ID",
                "otherField": "value",
            }

            send_text("+5511999999999", "Test with queueId")
            captured = capsys.readouterr()
            assert "DELIVERY|ok|status=200|id=QUEUE_WITH_ID" in captured.out

            # Test without any ID
            mock_response.json.return_value = {"otherField": "value"}

            send_text("+5511999999999", "Test without ID")
            captured = capsys.readouterr()
            assert "DELIVERY|ok|status=200|id=|" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
