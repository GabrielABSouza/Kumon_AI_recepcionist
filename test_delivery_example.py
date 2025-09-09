#!/usr/bin/env python3
"""
Example script to demonstrate the corrected delivery payload.
Shows the exact structure sent to Evolution API.
"""
import json
from unittest.mock import Mock, patch

from app.core.delivery import send_text


def demonstrate_payload():
    """Demonstrate the correct payload structure."""

    print("=" * 60)
    print("DELIVERY CONTRACT DEMONSTRATION")
    print("=" * 60)

    with patch("app.core.delivery.requests.post") as mock_post:
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Send a test message
        phone = "+5511999999999"
        message = "Olá! Bem-vindo ao Kumon Vila A. Como posso ajudá-lo?"

        print("\nInput:")
        print(f"  Phone: {phone}")
        print(f"  Message: {message}")

        result = send_text(phone, message)

        # Get the actual payload that was sent
        sent_payload = mock_post.call_args[1]["json"]

        print("\nPayload sent to Evolution API:")
        print(json.dumps(sent_payload, indent=2, ensure_ascii=False))

        print("\nResult:")
        print(json.dumps(result, indent=2))

        print("\n" + "=" * 60)
        print("KEY POINTS:")
        print("1. Payload uses 'textMessage' field (not 'text')")
        print("2. textMessage contains nested 'text' field")
        print("3. Phone number is E.164 without + prefix")
        print("4. Content-Type is application/json")
        print("5. No retry on 400 errors")
        print("=" * 60)


if __name__ == "__main__":
    import os

    os.environ["EVOLUTION_API_KEY"] = "test_key"
    demonstrate_payload()
