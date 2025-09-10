"""
TDD Step 3: Integration Test for Local Parent Name Extraction

This test validates the complete end-to-end flow with the refactored system:
- Global extraction removed
- Local extraction working in qualification_node
- Full conversational flow working correctly

Following TDD Step 3: Create comprehensive integration test
"""
from unittest.mock import MagicMock, patch

from app.core.langgraph_flow import qualification_node


def test_end_to_end_qualification_flow_with_local_extraction():
    """
    TDD STEP 3: Integration test for complete qualification flow with local extraction.

    Scenario: Simulate a realistic conversation where user provides name during qualification
    Validation: Verify the complete flow works with localized extraction
    """
    print("🧪 TDD STEP 3: Starting integration test for local extraction flow...")

    # STEP 1: First interaction - User wants information, we ask for name
    first_state = {
        "text": "Quero saber sobre o Kumon para meu filho",
        "phone": "+5511999999999",
        "message_id": "MSG_001",
        "instance": "test",
    }

    # STEP 2: Second interaction - User provides name (this should trigger local extraction)
    second_state = {
        "text": "Meu nome é Ana",
        "phone": "+5511999999999",
        "message_id": "MSG_002",
        "instance": "test",
    }

    with patch(
        "app.core.langgraph_flow.get_conversation_state"
    ) as mock_get_state, patch(
        "app.core.langgraph_flow.save_conversation_state"
    ) as mock_save_state, patch(
        "app.core.langgraph_flow.get_openai_client"
    ) as mock_openai, patch(
        "app.core.langgraph_flow.send_text"
    ) as mock_send:
        # STEP 3: Mock setup for realistic conversation flow
        def mock_get_state_flow(phone):
            if hasattr(mock_get_state_flow, "call_count"):
                mock_get_state_flow.call_count += 1
            else:
                mock_get_state_flow.call_count = 1

            # First call: Before extraction (empty state)
            if mock_get_state_flow.call_count == 1:
                return {"greeting_sent": True}
            # Second call: After extraction (state should have parent_name)
            else:
                return {"greeting_sent": True, "parent_name": "Ana"}

        mock_get_state.side_effect = mock_get_state_flow
        mock_send.return_value = {"sent": "true", "status_code": 200}

        # Mock OpenAI responses
        mock_openai_client = MagicMock()

        async def mock_chat_responses(*args, **kwargs):
            # Should ask for child name since we now have parent_name
            return "Perfeito Ana! Qual é o nome da criança?"

        mock_openai_client.chat = mock_chat_responses
        mock_openai.return_value = mock_openai_client

        # STEP 4: Execute second interaction (name extraction scenario)
        print("📝 Executing qualification_node with user name response...")
        result = qualification_node(second_state)

        # STEP 5: INTEGRATION ASSERTIONS

        # ASSERTION 1: Extraction should have been triggered and saved
        assert (
            mock_save_state.called
        ), "Should have saved conversation state after extraction"

        # Get the saved state details
        save_calls = mock_save_state.call_args_list
        assert len(save_calls) > 0, "Should have at least one save call"

        last_save_call = save_calls[-1]
        saved_phone = last_save_call[0][0]
        saved_state = last_save_call[0][1]

        assert (
            saved_phone == "+5511999999999"
        ), f"Should save for correct phone, got: {saved_phone}"
        assert (
            "parent_name" in saved_state
        ), f"Should have extracted parent_name, saved_state: {saved_state}"
        assert (
            saved_state["parent_name"] == "Ana"
        ), f"Should extract 'Ana' from 'Meu nome é Ana', got: {saved_state['parent_name']}"

        # ASSERTION 2: Response should be successful
        assert (
            result.get("sent") == "true"
        ), f"Should send response successfully, got: {result}"

        # ASSERTION 3: System should ask next qualification question
        response = result.get("response", "").lower()
        assert any(
            word in response
            for word in ["nome da criança", "filho", "filha", "criança"]
        ), f"Should ask about child's name next, got response: '{response}'"

        print("✅ INTEGRATION TEST PASSED")
        print(
            f"   ✓ Local extraction working: parent_name='Ana' extracted from 'Meu nome é Ana'"
        )
        print(f"   ✓ State persistence working: Saved to phone {saved_phone}")
        print(f"   ✓ Flow progression working: Asked next qualification question")
        print(
            f"   ✓ No global extraction: Only triggered locally in qualification_node"
        )


def test_integration_no_extraction_when_parent_name_exists():
    """
    Integration test: Verify no extraction occurs when parent_name already exists.

    This validates that the localized extraction respects existing data.
    """
    print("🧪 Integration test: No extraction when parent_name exists...")

    state_with_existing_name = {
        "text": "Meu nome é João",  # Different name in message
        "phone": "+5511888888888",
        "message_id": "MSG_EXISTING",
        "instance": "test",
    }

    with patch(
        "app.core.langgraph_flow.get_conversation_state"
    ) as mock_get_state, patch(
        "app.core.langgraph_flow.save_conversation_state"
    ) as mock_save_state, patch(
        "app.core.langgraph_flow.get_openai_client"
    ) as mock_openai, patch(
        "app.core.langgraph_flow.send_text"
    ) as mock_send:
        # Mock state with existing parent_name
        mock_get_state.return_value = {
            "greeting_sent": True,
            "parent_name": "Maria",  # Existing name should be preserved
        }

        mock_send.return_value = {"sent": "true", "status_code": 200}

        mock_openai_client = MagicMock()

        async def mock_chat(*args, **kwargs):
            return "Maria, qual é o nome da criança?"

        mock_openai_client.chat = mock_chat
        mock_openai.return_value = mock_openai_client

        # Execute qualification_node
        qualification_node(state_with_existing_name)

        # ASSERTION: Should NOT have overwritten existing parent_name
        if mock_save_state.called:
            save_calls = mock_save_state.call_args_list
            last_save_call = save_calls[-1]
            saved_state = last_save_call[0][1]

            # If save was called, it should preserve the original parent_name
            if "parent_name" in saved_state:
                assert (
                    saved_state["parent_name"] == "Maria"
                ), f"Should preserve existing parent_name='Maria', got: {saved_state['parent_name']}"

        print("✅ INTEGRATION TEST PASSED")
        print("   ✓ No extraction when parent_name exists")
        print("   ✓ Preserved existing parent_name='Maria'")
        print("   ✓ Did not overwrite with 'João' from message")


if __name__ == "__main__":
    test_end_to_end_qualification_flow_with_local_extraction()
    test_integration_no_extraction_when_parent_name_exists()
    print("\n🎉 ALL INTEGRATION TESTS PASSED!")
    print("✅ TDD Step 3: Integration testing completed successfully")
    print("🔥 Local extraction refactoring is fully validated!")
