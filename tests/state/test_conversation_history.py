"""
Test Conversation History - TDD implementation for conversation context.

This test validates the get_conversation_history function that provides
conversation context to the Gemini classifier for better routing decisions.

Following TDD Step 1.1: Create test_get_conversation_history
"""

from unittest.mock import patch


from app.core.state_manager import get_conversation_history


class TestConversationHistory:
    """Test suite for conversation history retrieval."""

    def test_get_conversation_history_returns_recent_messages(self):
        """
        TDD STEP 1.1: Test that get_conversation_history returns recent messages.

        Scenario: Simulate saved message exchanges for a phone number.
        Assertion: Verify function returns last N messages in correct format.

        This test will FAIL until we implement get_conversation_history function.
        """
        # STEP 1: Set up simulated conversation history
        phone = "5511999999999"

        # Simulate a conversation with multiple exchanges
        expected_messages = [
            {
                "role": "assistant",
                "content": "Olá! Eu sou a Cecília do Kumon. Qual é o seu nome?",
            },
            {"role": "user", "content": "meu nome é Gabriel"},
            {"role": "assistant", "content": "Olá Gabriel! Qual é o nome da criança?"},
            {"role": "user", "content": "meu filho João"},
        ]

        # STEP 2: Mock the underlying storage to return conversation history
        with patch("app.core.state_manager._get_stored_messages") as mock_get_messages:
            # Simulate that we have stored messages for this phone
            mock_get_messages.return_value = [
                {
                    "timestamp": "2023-01-01T10:00:00Z",
                    "role": "assistant",
                    "content": "Olá! Eu sou a Cecília do Kumon. Qual é o seu nome?",
                },
                {
                    "timestamp": "2023-01-01T10:01:00Z",
                    "role": "user",
                    "content": "meu nome é Gabriel",
                },
                {
                    "timestamp": "2023-01-01T10:02:00Z",
                    "role": "assistant",
                    "content": "Olá Gabriel! Qual é o nome da criança?",
                },
                {
                    "timestamp": "2023-01-01T10:03:00Z",
                    "role": "user",
                    "content": "meu filho João",
                },
                {
                    "timestamp": "2023-01-01T10:04:00Z",
                    "role": "assistant",
                    "content": "Perfeito! Qual é a idade do João?",
                },
            ]

            # STEP 3: Call the function (this will FAIL until implemented)
            result = get_conversation_history(phone, limit=4)

            # STEP 4: CRITICAL ASSERTIONS

            # ASSERTION 1: Should return a list
            assert isinstance(
                result, list
            ), f"get_conversation_history should return a list, got {type(result)}"

            # ASSERTION 2: Should respect the limit parameter
            assert len(result) == 4, f"Expected 4 messages (limit=4), got {len(result)}"

            # ASSERTION 3: Should return most recent 4 messages (the last 4 from the list)
            # The mock has 5 messages, so limit=4 should get the last 4 messages
            expected_last_content = (
                "Perfeito! Qual é a idade do João?"  # This is the most recent message
            )
            actual_last_content = result[-1]["content"]
            assert (
                actual_last_content == expected_last_content
            ), f"Expected last message to be '{expected_last_content}', got: '{actual_last_content}'"

            # ASSERTION 3.1: Should start with the 2nd message from mock (since first is excluded)
            expected_first_content = (
                "meu nome é Gabriel"  # 2nd message in mock becomes 1st in result
            )
            actual_first_content = result[0]["content"]
            assert (
                actual_first_content == expected_first_content
            ), f"Expected first message to be '{expected_first_content}', got: '{actual_first_content}'"

            # ASSERTION 4: Should have correct role/content structure
            for message in result:
                assert "role" in message, f"Message missing 'role' field: {message}"
                assert (
                    "content" in message
                ), f"Message missing 'content' field: {message}"
                assert message["role"] in [
                    "user",
                    "assistant",
                ], f"Invalid role: {message['role']}"

            # ASSERTION 5: Should have correct roles based on the mock data structure
            # Since we're getting the last 4 messages, the first one should be "user" (meu nome é Gabriel)
            assert (
                result[0]["role"] == "user"
            ), "First message in result should be user response"
            assert (
                result[1]["role"] == "assistant"
            ), "Second message should be from assistant"

            print("✅ TDD STEP 1.1: get_conversation_history test structure created")
            print(f"   Expected format validated for {len(result)} messages")

    def test_get_conversation_history_handles_empty_history(self):
        """
        Test that get_conversation_history handles empty conversation gracefully.
        """
        phone = "5511888888888"  # New conversation

        with patch("app.core.state_manager._get_stored_messages") as mock_get_messages:
            # No stored messages for this phone
            mock_get_messages.return_value = []

            # Call function
            result = get_conversation_history(phone, limit=4)

            # Should return empty list
            assert (
                result == []
            ), f"Expected empty list for new conversation, got {result}"

            print("✅ Empty history handled gracefully")

    def test_get_conversation_history_respects_limit_parameter(self):
        """
        Test that get_conversation_history respects the limit parameter.
        """
        phone = "5511777777777"

        with patch("app.core.state_manager._get_stored_messages") as mock_get_messages:
            # Simulate many stored messages (more than limit)
            mock_get_messages.return_value = [
                {
                    "timestamp": f"2023-01-01T10:0{i}:00Z",
                    "role": "user" if i % 2 else "assistant",
                    "content": f"Message {i}",
                }
                for i in range(10)  # 10 messages total
            ]

            # Test different limits
            for limit in [2, 4, 6]:
                result = get_conversation_history(phone, limit=limit)

                assert (
                    len(result) == limit
                ), f"Expected {limit} messages, got {len(result)}"

                # Should get the most recent messages
                assert (
                    result[-1]["content"] == "Message 9"
                ), f"Should get most recent message with limit={limit}"

            print("✅ Limit parameter respected correctly")

    def test_get_conversation_history_invalid_phone_returns_empty(self):
        """
        Test that get_conversation_history handles invalid phone numbers.
        """
        invalid_phones = [None, "", "invalid"]

        for phone in invalid_phones:
            result = get_conversation_history(phone, limit=4)

            assert (
                result == []
            ), f"Expected empty list for invalid phone {phone}, got {result}"

        print("✅ Invalid phone numbers handled gracefully")

    def test_get_conversation_history_default_limit(self):
        """
        Test that get_conversation_history uses appropriate default limit.
        """
        phone = "5511666666666"

        with patch("app.core.state_manager._get_stored_messages") as mock_get_messages:
            # Simulate more messages than default limit
            mock_get_messages.return_value = [
                {
                    "timestamp": f"2023-01-01T10:0{i}:00Z",
                    "role": "user" if i % 2 else "assistant",
                    "content": f"Message {i}",
                }
                for i in range(8)  # 8 messages total
            ]

            # Call without limit parameter
            result = get_conversation_history(phone)

            # Should use default limit (4)
            assert len(result) == 4, f"Expected default limit of 4, got {len(result)}"

            print("✅ Default limit works correctly")
