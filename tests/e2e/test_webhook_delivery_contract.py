"""
End-to-end tests for webhook delivery contract.
"""
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.main import app


class TestWebhookDeliveryContract:
    """Test suite for webhook delivery contract compliance."""

    def setup_method(self):
        """Set up test client."""
        import os

        os.environ["EVOLUTION_API_KEY"] = "test_api_key"
        self.client = TestClient(app)

    def teardown_method(self):
        """Clean up test environment."""
        import os

        if "EVOLUTION_API_KEY" in os.environ:
            del os.environ["EVOLUTION_API_KEY"]

    def test_webhook_returns_200_and_sent_string_false_on_delivery_400(self):
        """Test webhook returns 200 with sent='false' (string) on delivery 400."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock Evolution API returning 400
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": "invalid_recipient",
                "message": "Recipient not on WhatsApp",
            }
            mock_post.return_value = mock_response

            # Prepare webhook payload
            webhook_data = {
                "event": "messages.upsert",
                "instance": "test",
                "data": {
                    "key": {
                        "remoteJid": "5511999999999@s.whatsapp.net",
                        "fromMe": False,
                        "id": "MSG_400_TEST",
                    },
                    "message": {"conversation": "Test message"},
                    "messageType": "conversation",
                    "messageTimestamp": 1704800000,
                },
            }

            # Send webhook request
            response = self.client.post("/webhook", json=webhook_data)

            # Assert HTTP 200 (never 500)
            assert response.status_code == 200

            # Parse response
            data = response.json()

            # Assert sent is string "false", not boolean
            assert "sent" in data
            assert isinstance(data["sent"], str), "sent must be string"
            assert data["sent"] == "false", "sent must be 'false' for delivery 400"

            # Assert error_reason is present
            assert "error_reason" in data
            assert data["error_reason"] == "invalid_recipient"

    def test_no_duplicate_delivery_on_same_message_id(self):
        """Test idempotency - same message_id doesn't trigger duplicate delivery."""
        with patch("app.core.delivery.requests.post") as mock_post:
            # Mock successful delivery
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            # Prepare webhook payload with specific message ID
            webhook_data = {
                "event": "messages.upsert",
                "instance": "test",
                "data": {
                    "key": {
                        "remoteJid": "5511999999999@s.whatsapp.net",
                        "fromMe": False,
                        "id": "DUPLICATE_TEST_123",
                    },
                    "message": {"conversation": "Test duplicate"},
                    "messageType": "conversation",
                    "messageTimestamp": 1704800000,
                },
            }

            # Send first request
            response1 = self.client.post("/webhook", json=webhook_data)
            assert response1.status_code == 200
            response1.json()  # Just call to consume the response

            # Send duplicate request with same message_id
            response2 = self.client.post("/webhook", json=webhook_data)
            assert response2.status_code == 200
            data2 = response2.json()

            # Second response should indicate duplicate
            assert data2.get("status") == "duplicate" or data2.get("sent") == "false"

            # Delivery should only be called once (or not at all for duplicate)
            assert mock_post.call_count <= 1

    def test_webhook_always_returns_200_never_500(self):
        """Test that webhook always returns 200, never 500 even on errors."""
        test_scenarios = [
            # Delivery timeout
            {"side_effect": Exception("Connection timeout"), "expected_sent": "false"},
            # Invalid phone format
            {"phone": "invalid_phone", "expected_sent": "false"},
            # Missing API key
            {"env_patch": {"EVOLUTION_API_KEY": ""}, "expected_sent": "false"},
        ]

        for scenario in test_scenarios:
            with patch("app.core.delivery.requests.post") as mock_post:
                if "side_effect" in scenario:
                    mock_post.side_effect = scenario["side_effect"]

                webhook_data = {
                    "event": "messages.upsert",
                    "instance": "test",
                    "data": {
                        "key": {
                            "remoteJid": scenario.get("phone", "5511999999999")
                            + "@s.whatsapp.net",
                            "fromMe": False,
                            "id": f"ERROR_TEST_{id(scenario)}",
                        },
                        "message": {"conversation": "Test error"},
                        "messageType": "conversation",
                        "messageTimestamp": 1704800000,
                    },
                }

                # Apply environment patches if needed
                env_patches = scenario.get("env_patch", {})
                with patch.dict("os.environ", env_patches, clear=False):
                    response = self.client.post("/webhook", json=webhook_data)

                # Should always return 200
                assert response.status_code == 200, f"Failed for scenario: {scenario}"

                # Should have sent field as string
                data = response.json()
                assert isinstance(data.get("sent"), str)
                assert data["sent"] == scenario["expected_sent"]

    def test_webhook_response_schema_compliance(self):
        """Test that webhook response complies with expected schema."""
        with patch("app.core.delivery.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            webhook_data = {
                "event": "messages.upsert",
                "instance": "test",
                "data": {
                    "key": {
                        "remoteJid": "5511999999999@s.whatsapp.net",
                        "fromMe": False,
                        "id": "SCHEMA_TEST",
                    },
                    "message": {"conversation": "Test schema"},
                    "messageType": "conversation",
                    "messageTimestamp": 1704800000,
                },
            }

            response = self.client.post("/webhook", json=webhook_data)
            assert response.status_code == 200

            data = response.json()

            # Required fields with correct types
            assert isinstance(data.get("sent"), str)
            assert data["sent"] in ["true", "false"]
            assert isinstance(data.get("message_id"), str)
            assert isinstance(data.get("confidence"), (int, float))
            assert isinstance(data.get("entities"), dict)

            # Optional fields
            if "error_reason" in data:
                assert data["error_reason"] is None or isinstance(
                    data["error_reason"], str
                )

    def test_delivery_400_different_error_codes(self):
        """Test various 400 error codes are handled correctly."""
        error_codes = [
            {"error": "invalid_phone", "message": "Invalid phone number"},
            {"error": "blocked_contact", "message": "Contact has blocked this number"},
            {"error": "bad_payload", "message": "Missing required field: text"},
            {"error": "rate_limit", "message": "Too many messages"},
        ]

        for error_body in error_codes:
            with patch("app.core.delivery.requests.post") as mock_post:
                mock_response = Mock()
                mock_response.status_code = 400
                mock_response.json.return_value = error_body
                mock_post.return_value = mock_response

                webhook_data = {
                    "event": "messages.upsert",
                    "instance": "test",
                    "data": {
                        "key": {
                            "remoteJid": "5511999999999@s.whatsapp.net",
                            "fromMe": False,
                            "id": f"ERROR_{error_body['error']}",
                        },
                        "message": {"conversation": "Test"},
                        "messageType": "conversation",
                        "messageTimestamp": 1704800000,
                    },
                }

                response = self.client.post("/webhook", json=webhook_data)

                # Always 200
                assert response.status_code == 200

                data = response.json()
                # sent is string "false"
                assert data["sent"] == "false"
                # error_reason matches error code
                assert data.get("error_reason") == error_body["error"]
