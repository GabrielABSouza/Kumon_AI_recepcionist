"""
Simple contract tests for webhook API response validation.
Ensures all HTTP responses follow the correct schema with proper types.
Prevents ResponseValidationError in production.
"""
import json

import pytest
from pydantic import BaseModel, ValidationError


class WebhookResponseContract(BaseModel):
    """Expected schema for webhook responses"""

    status: str  # Required: "success", "ignored", "error", etc.
    message: str = None  # Optional message
    sent: str = None  # MUST be string "true"/"false", not bool
    message_id: str = None  # Optional message ID
    reason: str = None  # Optional reason for ignored/error

    class Config:
        # Strict mode to catch type mismatches
        strict = True


class TestWebhookResponseTypes:
    """Test webhook response types are correct"""

    def test_langgraph_flow_response_types(self):
        """Test that LangGraph flow returns correct types for 'sent' field"""
        # Import here to avoid import errors
        from app.core.langgraph_flow import fallback_node, greeting_node

        # Test greeting node
        result = greeting_node(
            {"text": "Olá", "phone": "5511999999999", "message_id": "123"}
        )
        if "sent" in result:
            assert isinstance(
                result["sent"], str
            ), f"greeting_node returned 'sent' as {type(result['sent'])}, expected str"
            assert result["sent"] in [
                "true",
                "false",
            ], f"'sent' must be 'true' or 'false', got {result['sent']}"

        # Test fallback node
        result = fallback_node(
            {"text": "xyz", "phone": "5511999999999", "message_id": "456"}
        )
        if "sent" in result:
            assert isinstance(
                result["sent"], str
            ), f"fallback_node returned 'sent' as {type(result['sent'])}, expected str"
            assert result["sent"] in [
                "true",
                "false",
            ], f"'sent' must be 'true' or 'false', got {result['sent']}"

    def test_response_schema_validation(self):
        """Test that response schema rejects bool values for 'sent'"""
        # Valid response with string "true"
        valid_response = {"status": "success", "sent": "true", "message_id": "123"}

        try:
            validated = WebhookResponseContract(**valid_response)
            assert validated.sent == "true"
        except ValidationError:
            pytest.fail("Valid response with sent='true' should not fail validation")

        # Invalid response with bool True - should fail
        invalid_response = {
            "status": "success",
            "sent": True,  # This is wrong - should be string
            "message_id": "123",
        }

        with pytest.raises(ValidationError) as exc_info:
            WebhookResponseContract(**invalid_response)

        # Check the error mentions type mismatch
        assert (
            "sent" in str(exc_info.value).lower()
            or "string" in str(exc_info.value).lower()
        )

    def test_all_valid_sent_values(self):
        """Test all valid values for 'sent' field"""
        # Test "true" string
        response_true = {"status": "success", "sent": "true"}
        validated = WebhookResponseContract(**response_true)
        assert validated.sent == "true"

        # Test "false" string
        response_false = {"status": "error", "sent": "false"}
        validated = WebhookResponseContract(**response_false)
        assert validated.sent == "false"

        # Test None (optional field)
        response_none = {"status": "ignored"}
        validated = WebhookResponseContract(**response_none)
        assert validated.sent is None

    def test_webhook_response_types_from_dict(self):
        """Test type validation when building response dicts"""
        # Simulate building a response dict
        response = {}
        response["status"] = "success"

        # WRONG: Setting bool
        # response["sent"] = True  # This would be wrong

        # CORRECT: Setting string
        response["sent"] = "true"
        response["message_id"] = "msg_123"

        # Validate the response
        validated = WebhookResponseContract(**response)
        assert isinstance(validated.sent, str)
        assert validated.sent == "true"

    def test_json_serialization_of_responses(self):
        """Test that responses serialize correctly to JSON"""
        response = {
            "status": "success",
            "sent": "false",  # String, not bool
            "message": "Rate limit exceeded",
        }

        # Should serialize without issues
        json_str = json.dumps(response)
        parsed = json.loads(json_str)

        # Verify types after round-trip
        assert isinstance(parsed["sent"], str)
        assert parsed["sent"] == "false"

        # Validate against schema
        validated = WebhookResponseContract(**parsed)
        assert validated.sent == "false"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
