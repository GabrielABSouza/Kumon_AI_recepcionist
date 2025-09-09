#!/usr/bin/env python3
"""
Test script to verify webhook response normalization for delivery errors.
Tests that when delivery fails (400 error), the webhook returns sent="false" as string.
"""
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

# Import the normalizer
from app.utils.webhook_normalizer import normalize_webhook_payload


def test_direct_normalization():
    """Test the normalizer directly"""
    print("=" * 60)
    print("Testing webhook normalizer...")

    # Test case 1: Boolean False -> string "false"
    payload1 = {
        "message_id": "MSG123",
        "intent": "greeting",
        "confidence": 0.9,
        "response_text": "Olá!",
        "entities": {},
        "sent": False,  # Boolean!
    }

    normalized1 = normalize_webhook_payload(payload1)
    assert (
        normalized1["sent"] == "false"
    ), f"Expected 'false', got {normalized1['sent']}"
    assert isinstance(
        normalized1["sent"], str
    ), f"Expected str, got {type(normalized1['sent'])}"
    print("✅ Boolean False -> string 'false'")

    # Test case 2: Boolean True -> string "true"
    payload2 = payload1.copy()
    payload2["sent"] = True

    normalized2 = normalize_webhook_payload(payload2)
    assert normalized2["sent"] == "true", f"Expected 'true', got {normalized2['sent']}"
    assert isinstance(
        normalized2["sent"], str
    ), f"Expected str, got {type(normalized2['sent'])}"
    print("✅ Boolean True -> string 'true'")

    # Test case 3: Invalid confidence -> normalized
    payload3 = payload1.copy()
    payload3["confidence"] = "invalid"

    normalized3 = normalize_webhook_payload(payload3)
    assert normalized3["confidence"] == 0.0
    print("✅ Invalid confidence -> 0.0")

    # Test case 4: List entities -> dict
    payload4 = payload1.copy()
    payload4["entities"] = []

    normalized4 = normalize_webhook_payload(payload4)
    assert normalized4["entities"] == {}
    assert isinstance(normalized4["entities"], dict)
    print("✅ List entities -> empty dict")

    print("\nAll normalization tests passed! ✅")


def test_webhook_with_delivery_error():
    """Test webhook response when delivery fails with 400 error"""
    print("\n" + "=" * 60)
    print("Testing webhook with delivery error (400)...")

    from app.main import app

    client = TestClient(app)

    # Mock Evolution API to return 400 error
    with patch(
        "app.clients.evolution_api.EvolutionAPIClient.send_text_message"
    ) as mock_send:
        mock_send.return_value = {
            "success": False,
            "sent": False,  # Boolean - this is the problem!
            "error": "400 Bad Request",
            "status_code": 400,
        }

        # Mock the langgraph flow to return a response
        with patch("app.core.langgraph_flow.run") as mock_run:
            mock_run.return_value = {
                "sent": False,  # Boolean from the flow
                "response": "Test message",
                "message_id": "MSG123",
                "intent": "greeting",
                "confidence": 0.9,
                "entities": {},
            }

            # Prepare webhook request
            webhook_data = {
                "event": "messages.upsert",
                "instance": "test",
                "data": {
                    "key": {
                        "remoteJid": "5511999999999@s.whatsapp.net",
                        "fromMe": False,
                        "id": "MSG123",
                    },
                    "message": {"conversation": "Teste"},
                    "messageType": "conversation",
                    "messageTimestamp": 1704800000,
                },
            }

            # Make request to webhook (try the actual Evolution endpoint)
            try:
                response = client.post(
                    "/api/evolution/webhook",  # This is the endpoint in app/api/evolution.py
                    json=webhook_data,
                    headers={"x-api-key": "test-key"},
                )

                print(f"Response status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    print(f"Response data: {json.dumps(data, indent=2)}")

                    # Check if sent is string
                    if "sent" in data:
                        assert isinstance(
                            data["sent"], str
                        ), f"sent must be string, got {type(data['sent'])}"
                        assert data["sent"] in [
                            "true",
                            "false",
                        ], f"sent must be 'true' or 'false', got {data['sent']}"
                        print(
                            f"✅ sent field is correctly typed as string: '{data['sent']}'"
                        )
                    else:
                        print("⚠️ No 'sent' field in response")
                else:
                    print(f"❌ Unexpected status code: {response.status_code}")
                    print(f"Response: {response.text}")

            except Exception as e:
                print(f"❌ Error during test: {e}")
                import traceback

                traceback.print_exc()


if __name__ == "__main__":
    print("Starting webhook normalization tests...")

    # Test the normalizer directly
    test_direct_normalization()

    # Test webhook with delivery error
    test_webhook_with_delivery_error()

    print("\n" + "=" * 60)
    print("All tests completed!")
