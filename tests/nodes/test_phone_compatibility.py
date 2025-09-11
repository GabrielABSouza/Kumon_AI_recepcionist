"""
🔧 PHONE COMPATIBILITY TEST: Validates phone number access works with both formats

This test ensures the qualification_node works correctly with both:
- 'phone_number' format (used by tests/CeciliaState)
- 'phone' format (used by production LangGraph)
"""

import pytest

from app.core.nodes.qualification import _get_phone_from_state, qualification_node
from app.core.state.models import ConversationStage, ConversationStep


class TestPhoneCompatibility:
    """Test phone number access compatibility between test and production formats."""

    @pytest.mark.asyncio
    async def test_qualification_node_works_with_phone_number_format(self):
        """Test that qualification_node works with 'phone_number' format (test format)."""
        # Test format state with 'phone_number'
        state = {
            "phone_number": "5511999999999",
            "text": "olá",
            "current_stage": ConversationStage.QUALIFICATION,
            "current_step": ConversationStep.PARENT_NAME_COLLECTION,
            "collected_data": {},
        }

        # Should not raise KeyError
        result = await qualification_node(state)

        # Should generate a response
        assert "last_bot_response" in result
        assert result["last_bot_response"] is not None

        print("✅ PHONE_NUMBER format works correctly")

    @pytest.mark.asyncio
    async def test_qualification_node_works_with_phone_format(self):
        """Test that qualification_node works with 'phone' format (production format)."""
        # Production format state with 'phone'
        state = {
            "phone": "5511999999999",
            "text": "olá",
            "current_stage": ConversationStage.QUALIFICATION,
            "current_step": ConversationStep.PARENT_NAME_COLLECTION,
            "collected_data": {},
        }

        # Should not raise KeyError
        result = await qualification_node(state)

        # Should generate a response
        assert "last_bot_response" in result
        assert result["last_bot_response"] is not None

        print("✅ PHONE format works correctly")

    def test_get_phone_helper_function_compatibility(self):
        """Test the _get_phone_from_state helper works with both formats."""
        # Test with phone_number format
        state_with_phone_number = {"phone_number": "5511111111"}
        phone1 = _get_phone_from_state(state_with_phone_number)
        assert phone1 == "5511111111"

        # Test with phone format
        state_with_phone = {"phone": "5522222222"}
        phone2 = _get_phone_from_state(state_with_phone)
        assert phone2 == "5522222222"

        # Test with both (phone_number takes precedence)
        state_with_both = {"phone_number": "5511111111", "phone": "5522222222"}
        phone3 = _get_phone_from_state(state_with_both)
        assert phone3 == "5511111111"

        # Test with neither (returns 'unknown')
        state_empty = {}
        phone4 = _get_phone_from_state(state_empty)
        assert phone4 == "unknown"

        print("✅ Helper function handles all cases correctly")
