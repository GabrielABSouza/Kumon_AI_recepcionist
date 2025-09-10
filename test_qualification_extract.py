"""
TDD Test for parent_name extraction in qualification_node.

This creates the failing test for Step 2.1 of the refactoring plan.
"""
from unittest.mock import MagicMock, patch

from app.core.langgraph_flow import qualification_node


def test_qualification_node_extracts_parent_name_from_message_when_missing():
    """
    TDD STEP 2.1: Test that qualification_node extracts parent_name from user message when missing.
    
    This test validates the core fix: 
    - parent_name extraction should be localized to qualification_node
    - Only extract when parent_name is missing
    - Use the message text to extract the name
    
    This test will FAIL until we implement the local extraction logic.
    """
    # STEP 1: Set up state where parent_name is missing
    state_input = {
        "text": "Meu nome é Gabriel",  # User is responding with their name
        "phone": "+5511999999999",
        "message_id": "MSG_NAME_EXTRACT",
        "instance": "test",
    }

    # STEP 2: Mock Redis state without parent_name (forcing extraction)
    redis_state_without_name = {
        "greeting_sent": True,  # We're in qualification phase
        # parent_name is missing - this should trigger extraction
    }

    with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state, \
         patch("app.core.langgraph_flow.get_openai_client") as mock_openai, \
         patch("app.core.langgraph_flow.send_text") as mock_send, \
         patch("app.core.langgraph_flow.save_conversation_state") as mock_save_state:

        # STEP 3: Set up mocks
        # Use side_effect to return updated state after extraction
        def mock_get_state_side_effect(phone):
            # First call returns empty state, subsequent calls return updated state  
            if hasattr(mock_get_state_side_effect, 'call_count'):
                mock_get_state_side_effect.call_count += 1
            else:
                mock_get_state_side_effect.call_count = 1
            
            if mock_get_state_side_effect.call_count == 1:
                return redis_state_without_name  # First call: empty state
            else:
                return {"greeting_sent": True, "parent_name": "Gabriel"}  # After extraction
        
        mock_get_state.side_effect = mock_get_state_side_effect
        mock_send.return_value = {"sent": "true"}
        
        # Mock OpenAI to return next question
        mock_openai_client = MagicMock()
        
        # Create async mock response
        async def mock_chat(*args, **kwargs):
            return "Perfeito Gabriel! Para quem é a matrícula?"
        
        mock_openai_client.chat = mock_chat
        mock_openai.return_value = mock_openai_client

        # STEP 4: Call qualification_node (this will FAIL until implemented)
        result = qualification_node(state_input)

        # STEP 5: CRITICAL ASSERTIONS
        
        # ASSERTION 1: Should have extracted parent_name from message
        mock_save_state.assert_called()
        saved_state_call = mock_save_state.call_args[0][1]  # Get the state that was saved
        saved_phone_call = mock_save_state.call_args[0][0]  # Get the phone number used
        
        print(f"DEBUG: save_conversation_state called with phone='{saved_phone_call}', state={saved_state_call}")
        
        assert "parent_name" in saved_state_call, "Should have extracted and saved parent_name"
        assert saved_state_call["parent_name"] == "Gabriel", \
            f"Expected parent_name='Gabriel', got: {saved_state_call.get('parent_name')}"
        
        # ASSERTION 2: Should proceed to next qualification question
        assert result.get("sent") == "true", "Should have sent response successfully"
        response = result.get("response", "").lower()
        
        # Should ask about beneficiary since we now have the parent name
        assert any(
            word in response for word in ["quem", "beneficiário", "matrícula", "para quem"]
        ), f"Should ask next qualification question, got: {response}"
        
        print("✅ TDD STEP 2.1: parent_name extraction test structure created")
        print(f"   Validated: Local extraction in qualification_node when parent_name missing")
        print(f"   Expected: parent_name='Gabriel' extracted from 'Meu nome é Gabriel'")


def test_qualification_node_does_not_extract_when_parent_name_already_exists():
    """
    Test that qualification_node does NOT extract parent_name when it already exists.
    
    This validates that we don't overwrite existing data.
    """
    # State where parent_name already exists
    state_input = {
        "text": "Meu nome é João",  # Different name in message
        "phone": "+5511999999999", 
        "message_id": "MSG_NO_EXTRACT",
        "instance": "test",
    }

    # Redis state WITH existing parent_name
    redis_state_with_name = {
        "greeting_sent": True,
        "parent_name": "Maria",  # Already exists - should NOT be overwritten
    }

    with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state, \
         patch("app.core.langgraph_flow.send_text") as mock_send, \
         patch("app.core.langgraph_flow.save_conversation_state") as mock_save_state:

        mock_get_state.return_value = redis_state_with_name
        mock_send.return_value = {"sent": "true"}

        # Call qualification_node
        result = qualification_node(state_input)

        # ASSERTION: Should NOT have changed the parent_name
        if mock_save_state.called:
            saved_state_call = mock_save_state.call_args[0][1]
            assert saved_state_call["parent_name"] == "Maria", \
                f"Should preserve existing parent_name='Maria', but got: {saved_state_call.get('parent_name')}"
        
        print("✅ Existing parent_name preservation validated")
        print("   - Does not overwrite existing parent_name ✅")


if __name__ == "__main__":
    test_qualification_node_extracts_parent_name_from_message_when_missing()
    test_qualification_node_does_not_extract_when_parent_name_already_exists()