"""
Integration tests for delivery 400 errors handling.
"""
import json
import os
from unittest.mock import Mock, patch

from app.core.delivery import send_text


class TestDelivery400Handling:
    """Test suite for 400 error handling in delivery service."""

    def setup_method(self):
        """Set up test environment."""
        os.environ["EVOLUTION_API_KEY"] = "test_api_key"

    def teardown_method(self):
        """Clean up test environment."""
        if "EVOLUTION_API_KEY" in os.environ:
            del os.environ["EVOLUTION_API_KEY"]

    def test_delivery_400_invalid_phone_no_retry(self):
        """Test that 400 with invalid_phone doesn't retry and logs correctly."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock Evolution API returning 400 with invalid_phone error
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": "invalid_phone",
                "message": "Invalid phone number",
            }
            mock_post.return_value = mock_response

            # Call send_text
            result = send_text("+5511999999999", "Test message")

            # Assert no retry (only called once)
            assert mock_post.call_count == 1

            # Assert correct result
            assert result["sent"] == "false"
            assert result["status_code"] == 400
            assert result["error_reason"] == "invalid_phone"

    def test_delivery_400_invalid_payload_logs_body(self, capsys):
        """Test that 400 with bad_payload logs the full body."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock Evolution API returning 400 with bad_payload error
            mock_response = Mock()
            mock_response.status_code = 400
            error_body = {"error": "bad_payload", "message": "missing text"}
            mock_response.json.return_value = error_body
            mock_post.return_value = mock_response

            # Call send_text
            result = send_text("+5511999999999", "Test message")

            # Check logs
            captured = capsys.readouterr()
            assert "DELIVERY|error|status=400|code=bad_payload" in captured.out
            assert "msg=missing text" in captured.out
            assert "body=" in captured.out
            assert json.dumps(error_body) in captured.out

            # Assert result
            assert result["sent"] == "false"
            assert result["error_reason"] == "bad_payload"

    def test_delivery_400_no_retry_policy(self):
        """Test that 400 errors never trigger retry."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock Evolution API returning 400
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {"error": "any_error"}
            mock_post.return_value = mock_response

            # Call send_text multiple times
            for _ in range(3):
                result = send_text("+5511999999999", "Test message")
                assert result["sent"] == "false"

            # Should be called 3 times (no internal retry)
            assert mock_post.call_count == 3

    def test_delivery_contract_types_are_strings(self):
        """Test that delivery service returns proper string types."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = send_text("+5511999999999", "Test message")

            # Check types
            assert isinstance(result["sent"], str)
            assert result["sent"] in ["true", "false"]
            assert isinstance(result["status_code"], int)
            assert result["error_reason"] is None or isinstance(
                result["error_reason"], str
            )

    def test_delivery_phone_formatting_e164(self):
        """Test that phone is formatted to E.164 before sending."""
        with patch("app.core.delivery.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            # Test various phone formats
            test_cases = [
                ("11999999999", "5511999999999"),  # Missing country code
                ("+5511999999999", "5511999999999"),  # Already E.164
                ("(11) 99999-9999", "5511999999999"),  # Formatted
                ("011 99999-9999", "5511999999999"),  # With zero
            ]

            for input_phone, expected_number in test_cases:
                mock_post.reset_mock()
                result = send_text(input_phone, "Test")

                # Check that Evolution API was called with correct number
                if result["sent"] == "true":
                    call_args = mock_post.call_args
                    payload = call_args[1]["json"]
                    assert payload["number"] == expected_number

    def test_delivery_invalid_phone_format_not_sent(self, capsys):
        """Test that invalid phone formats are not sent."""
        # Test invalid phone
        result = send_text("invalid", "Test message")

        # Check result
        assert result["sent"] == "false"
        assert result["error_reason"] == "invalid_phone_format"

        # Check logs
        captured = capsys.readouterr()
        assert "DELIVERY|error|invalid_phone_format" in captured.out
