"""
Tests for async invocation of information_node.

This test validates that the async fix for information_node works correctly
without "Cannot invoke a coroutine function synchronously" errors.
"""

from unittest.mock import patch

import pytest

from app.core.langgraph_flow import information_node


class TestAsyncInformationNode:
    """Test suite for async information_node execution."""

    @pytest.mark.asyncio
    async def test_information_node_executes_async_without_errors(self):
        """
        ASYNC VALIDATION TEST: Validate information_node executes without async errors.

        This is the core test that validates our async invocation fix works correctly.
        The primary goal is ensuring no "Cannot invoke a coroutine function synchronously" errors.
        """

        # ARRANGE: Create conversation state
        conversation_state = {
            "phone": "5511999999999",
            "message_id": "MSG_ASYNC_001",
            "instance": "kumon_assistant",
            "text": "Quais são os horários de funcionamento?",
            "parent_name": "Maria Silva",
            "qualification_attempts": 1,
        }

        # ARRANGE: Mock external dependencies
        with patch(
            "app.core.state_manager.get_conversation_state"
        ) as mock_get_state, patch("app.core.delivery.send_text") as mock_send_text:
            # Configure mocks
            mock_get_state.return_value = {"parent_name": "Maria Silva"}
            mock_send_text.return_value = {"sent": "true", "status_code": 200}

            # ACT: Execute information_node with await (this is the critical test)
            result = await information_node(conversation_state)

            # ASSERT: Primary validation - async execution worked
            assert result is not None, "information_node should complete execution"
            assert isinstance(result, dict), "Result should be a dictionary"

            # ASSERT: Response should be generated
            response_text = result.get("last_bot_response", "")
            assert response_text, "Response should be generated"

            print(
                "✅ CRITICAL SUCCESS: information_node executed with await - no async errors!"
            )
            print(f"🎯 ASYNC VALIDATION SUCCESS: Returned {len(response_text)} chars")
            print(
                "✅ ASYNC INVOCATION TEST PASSED: information_node executed with await successfully"
            )
