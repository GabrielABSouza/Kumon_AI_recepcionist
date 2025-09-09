"""
Integration tests for multi-turn conversation flows.

Tests that validate proper execution of multi-node flows within a single webhook turn,
ensuring turn_controller logic doesn't interfere with internal graph transitions.
"""

import json
from unittest.mock import MagicMock, patch


from app.api.evolution import webhook


class TestMultiTurnConversation:
    """Integration test suite for multi-turn conversation flows."""

    def test_single_message_triggers_multi_node_flow_without_skips(self):
        """
        CRITICAL BUG DETECTION TEST: Ensure single webhook message can trigger multiple nodes.

        This test addresses the ROOT CAUSE where turn_controller checks inside each node
        cause subsequent nodes to be skipped with 'already_replied=true', corrupting
        the conversation flow and causing infinite loops.

        Expected Flow: webhook → greeting_node → qualification_node (both should execute)
        Current Bug: webhook → greeting_node → qualification_node (SKIPPED due to turn_controller)
        """

        # STEP 1: Create payload that should trigger greeting → qualification flow
        webhook_payload = {
            "instance": "kumon_assistant",
            "data": {
                "key": {
                    "id": "MSG_MULTINODE_001",
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                },
                "message": {
                    "conversation": "Olá, meu nome é Gabriel"  # Should trigger greeting → qualification
                },
            },
        }

        # STEP 2: Mock external dependencies
        with patch("app.core.delivery.send_text") as mock_send_text:
            with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                # Configure Evolution API mock
                mock_send_text.return_value = {
                    "sent": "true",
                    "status_code": 200,
                    "provider_message_id": "PROV_001",
                }

                # Configure OpenAI mock
                mock_client = MagicMock()
                mock_client.chat.return_value = "Olá Gabriel! Que bom conhecê-lo. Preciso de mais algumas informações..."
                mock_openai.return_value = mock_client

                # STEP 3: Mock qualification_node internal function to detect execution
                with patch(
                    "app.core.langgraph_flow.get_qualification_prompt"
                ) as mock_qualification_prompt:
                    mock_qualification_prompt.return_value = {
                        "system": "Pergunta para qualificação",
                        "user": "Olá, meu nome é Gabriel",
                    }

                    # STEP 4: Create mock request
                    class MockRequest:
                        async def json(self):
                            return webhook_payload

                    request = MockRequest()

                    # STEP 5: Execute webhook - this should trigger both nodes
                    import asyncio

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(webhook(request))

                        # STEP 6: CRITICAL ASSERTIONS

                        # CRITICAL ASSERTIONS: Validate multi-node execution without turn_controller interference

                        # ASSERTION 1: Qualification prompt should be called (proves qualification_node executed)
                        assert mock_qualification_prompt.called, (
                            "TURN_CONTROLLER BUG: get_qualification_prompt should be called "
                            "when greeting transitions to qualification, but turn_controller "
                            "may have skipped qualification_node execution."
                        )

                        # ASSERTION 2: Multiple qualification prompt calls indicate loop execution
                        qualification_calls = mock_qualification_prompt.call_count
                        assert qualification_calls >= 1, (
                            f"Expected qualification_prompt to be called at least once, "
                            f"got {qualification_calls} calls. This indicates qualification_node "
                            f"was not executed due to turn_controller interference."
                        )

                        # ASSERTION 3: Webhook should process without duplicate/skip status
                        assert (
                            result.get("status") != "duplicate"
                        ), "Webhook should not return duplicate status for new message"
                        assert (
                            result.get("status") != "skipped"
                        ), "Webhook should not skip processing for new message"

                        print(
                            "✅ SUCCESS: Multi-node flow executed completely without turn_controller interference"
                        )

                    except Exception as e:
                        # Expected failure due to turn_controller bug
                        print(f"EXPECTED TDD FAILURE: {str(e)}")
                        print(
                            "This test should FAIL initially due to turn_controller bug in nodes"
                        )
                        print(
                            "After centralizing turn_controller logic, this test should PASS"
                        )

                        # Re-raise to make test fail visibly
                        raise AssertionError(
                            f"TURN_CONTROLLER BUG CONFIRMED: {str(e)}\n"
                            f"The turn_controller is checking 'already_replied' inside each node, "
                            f"causing subsequent nodes to be skipped and breaking multi-node flows.\n"
                            f"Webhook payload: {json.dumps(webhook_payload, indent=2)}"
                        )

                    finally:
                        loop.close()

    def test_duplicate_message_properly_blocked_at_webhook_level(self):
        """
        Test that after fix, duplicate messages are blocked at webhook entry, not node level.

        This test validates the corrected architecture where turn_controller logic
        is centralized at the webhook entry point.
        """

        # STEP 1: Same message payload
        webhook_payload = {
            "instance": "kumon_assistant",
            "data": {
                "key": {
                    "id": "MSG_DUPLICATE_001",  # Same message_id
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                },
                "message": {"conversation": "Primeira mensagem"},
            },
        }

        # STEP 2: Mock dependencies
        with patch("app.core.delivery.send_text") as mock_send_text:
            with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                mock_send_text.return_value = {"sent": "true", "status_code": 200}
                mock_client = MagicMock()
                mock_client.chat.return_value = "Resposta inicial"
                mock_openai.return_value = mock_client

                # STEP 3: First execution should work
                class MockRequest:
                    async def json(self):
                        return webhook_payload

                request = MockRequest()

                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # First call - should execute normally
                    result1 = loop.run_until_complete(webhook(request))

                    # Second call - should be blocked at webhook level
                    result2 = loop.run_until_complete(webhook(request))

                    # CRITICAL ASSERTIONS: Validate duplicate blocking at webhook level

                    # ASSERTION 1: First call should be processed (regardless of success)
                    assert (
                        result1.get("status") == "processed"
                    ), f"First call should be processed, got status: {result1.get('status')}"

                    # ASSERTION 2: Second call should be blocked as duplicate
                    assert (
                        result2.get("status") == "duplicate"
                    ), f"Second call should be blocked as duplicate, got status: {result2.get('status')}"

                    # ASSERTION 3: Second call should not trigger new processing
                    assert (
                        result2.get("sent") == "false"
                    ), "Second call should not send any message (blocked duplicate)"

                    print(
                        "✅ SUCCESS: Duplicate message properly blocked at webhook level"
                    )

                finally:
                    loop.close()
