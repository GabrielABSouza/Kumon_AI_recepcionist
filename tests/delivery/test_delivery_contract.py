"""
Contract tests for delivery service with Evolution API.
Ensures correct payload format and error handling.
"""
import json
import os
from unittest.mock import Mock, patch

from app.core.delivery import send_text


class TestDeliveryContract:
    """Test suite for delivery service contract with Evolution API."""

    def setup_method(self):
        """Set up test environment."""
        os.environ["EVOLUTION_API_KEY"] = "test_api_key"

    def teardown_method(self):
        """Clean up test environment."""
        if "EVOLUTION_API_KEY" in os.environ:
            del os.environ["EVOLUTION_API_KEY"]

    def test_sends_textMessage_contract_ok(self):
        """Test that payload contains textMessage with correct structure."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            # Send message
            result = send_text("+5511999999999", "Test message")

            # Verify the request
            assert mock_post.called
            call_args = mock_post.call_args

            # Extract the payload that was sent
            sent_payload = call_args[1]["json"]

            # Verify exact contract format
            assert sent_payload == {
                "number": "5511999999999",  # Without +
                "textMessage": {"text": "Test message"},
            }

            # Verify headers
            headers = call_args[1]["headers"]
            assert headers["Content-Type"] == "application/json"
            assert "apikey" in headers

            # Verify return
            assert result == {"sent": "true", "status_code": 200, "error_reason": None}

    def test_400_missing_textMessage_now_fixed(self):
        """Test that the textMessage field is now correctly included (regression test)."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # First simulate the old 400 error
            mock_response_400 = Mock()
            mock_response_400.status_code = 400
            mock_response_400.json.return_value = {
                "error": "bad_request",
                "message": 'instance requires property "textMessage"',
            }

            # Then simulate success with correct format
            mock_response_200 = Mock()
            mock_response_200.status_code = 200

            # First call would have failed with old format, now succeeds
            mock_post.return_value = mock_response_200

            result = send_text("5511999999999", "Test message")

            # Verify the payload has textMessage
            sent_payload = mock_post.call_args[1]["json"]
            assert "textMessage" in sent_payload
            assert sent_payload["textMessage"] == {"text": "Test message"}

            # Should succeed now
            assert result["sent"] == "true"

    def test_400_invalid_phone_no_retry(self):
        """Test that 400 errors don't trigger retry."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock 400 response
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": "invalid_phone",
                "message": "Invalid phone number",
            }
            mock_post.return_value = mock_response

            result = send_text("+5511999999999", "Test message")

            # Should only be called once (no retry)
            assert mock_post.call_count == 1

            # Verify return
            assert result == {
                "sent": "false",
                "status_code": 400,
                "error_reason": "invalid_phone",
            }

    def test_empty_text_validation(self):
        """Test that empty text is validated before sending."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Test with empty string
            result = send_text("+5511999999999", "")

            # Should not make HTTP call
            assert not mock_post.called

            # Should return validation error
            assert result == {
                "sent": "false",
                "status_code": 0,
                "error_reason": "empty_text",
            }

            # Test with whitespace only
            result = send_text("+5511999999999", "   ")

            # Should not make HTTP call
            assert not mock_post.called

            # Should return validation error
            assert result == {
                "sent": "false",
                "status_code": 0,
                "error_reason": "empty_text",
            }

    def test_ptbr_characters_and_length(self):
        """Test that PT-BR UTF-8 characters work correctly."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            # Send message with PT-BR characters
            ptbr_text = "Olá! Você está pronto para começar? Ótimo! 😊"
            result = send_text("+5511999999999", ptbr_text)

            # Verify the payload
            sent_payload = mock_post.call_args[1]["json"]
            assert sent_payload["textMessage"]["text"] == ptbr_text

            # Should succeed
            assert result["sent"] == "true"

            # Test text length validation
            mock_post.reset_mock()
            long_text = "a" * 4097  # Over limit
            result = send_text("+5511999999999", long_text)

            # Should not make HTTP call
            assert not mock_post.called

            # Should return validation error
            assert result["sent"] == "false"
            assert result["error_reason"] == "text_too_long"

    def test_logs_on_400(self, capsys):
        """Test that 400 errors are properly logged."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock 400 response
            mock_response = Mock()
            mock_response.status_code = 400
            error_body = {"error": "bad_payload", "message": "Missing required field"}
            mock_response.json.return_value = error_body
            mock_post.return_value = mock_response

            result = send_text("+5511999999999", "Test")

            # Capture logs
            captured = capsys.readouterr()

            # Verify log format
            assert "DELIVERY|error|status=400" in captured.out
            assert "code=bad_payload" in captured.out
            assert "msg=Missing required field" in captured.out
            assert "body=" in captured.out
            assert json.dumps(error_body) in captured.out

            # Verify return
            assert result["sent"] == "false"
            assert result["error_reason"] == "bad_payload"

    def test_payload_structure_with_all_fields(self):
        """Test complete payload structure matches Evolution API contract."""
        with patch("app.core.delivery.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            # Test various phone formats
            test_cases = [
                ("11999999999", "5511999999999"),  # Without country code
                ("+5511999999999", "5511999999999"),  # With +
                ("5511999999999", "5511999999999"),  # With country code
            ]

            for input_phone, expected_number in test_cases:
                mock_post.reset_mock()

                result = send_text(input_phone, "Test")

                # Verify payload structure
                sent_payload = mock_post.call_args[1]["json"]
                assert list(sent_payload.keys()) == ["number", "textMessage"]
                assert sent_payload["number"] == expected_number
                assert sent_payload["textMessage"] == {"text": "Test"}

                # Verify URL structure
                url = mock_post.call_args[0][0]
                assert "/message/sendText/recepcionistakumon" in url

                assert result["sent"] == "true"

    def test_debug_logging(self, capsys):
        """Test debug logging without exposing PII."""
        with patch("app.core.delivery.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            # Enable debug mode
            os.environ["DEBUG_DELIVERY"] = "true"

            send_text("+5511999999999", "Test message with private info")

            # Check debug logs
            captured = capsys.readouterr()

            # Should log payload structure but not content
            assert "DELIVERY|debug|payload_keys=" in captured.out
            assert "['number', 'textMessage']" in captured.out
            assert "text_len=30" in captured.out

            # Should NOT log actual phone or message content
            assert "5511999999999" not in captured.out
            assert "private info" not in captured.out

            # Clean up
            del os.environ["DEBUG_DELIVERY"]
