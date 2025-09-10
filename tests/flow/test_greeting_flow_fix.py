"""
Test Greeting Flow Fix - Regression tests for turn-based conversation.

This test addresses the automatic transition bug:
- greeting_node should STOP the flow after sending its message
- The next turn should start fresh with the user's response
- Gemini classifier should route the name response to qualification_node
"""

from unittest.mock import Mock, patch


from app.core.langgraph_flow import build_graph


class TestGreetingFlowFix:
    """Test suite to ensure turn-based conversation flow."""

    def test_greeting_node_stops_the_flow_after_sending_message(self):
        """
        CRITICAL REGRESSION TEST: greeting_node must stop the flow after sending message.

        This test should FAIL before the fix and PASS after the fix.

        Background:
        The bug is that greeting_node automatically transitions to qualification_node
        within the same turn, causing two messages to be sent to the user.

        Fix: greeting_node should end the graph execution (END) after sending its message.
        """
        # STEP 1: Set up initial state for a new user (first contact)
        initial_state = {
            "phone": "5511999999999",
            "message_id": "greeting_flow_test_001",
            "last_user_message": "oi",
            "intent": "greeting",  # This will route to greeting_node
            "confidence": 0.95,
            "instance": "test_instance",
        }

        # STEP 2: Mock external dependencies and force greeting path
        with patch("app.core.langgraph_flow.send_text") as mock_send, patch(
            "app.core.langgraph_flow.classify_intent"
        ) as mock_classify, patch(
            "app.core.langgraph_flow._execute_node"
        ) as mock_execute:
            mock_send.return_value = {"sent": "true", "status_code": 200}
            # Force the classification to route to greeting_node
            mock_classify.return_value = "greeting_node"

            # Mock the node execution to simulate successful greeting
            def mock_greeting_execution(state, node_name, prompt_func):
                if node_name == "greeting":
                    # Simulate successful greeting execution
                    mock_send(
                        state.get("phone"),
                        "Olá! Eu sou a Cecília do Kumon. Qual é o seu nome?",
                        state.get("instance"),
                    )
                    return {
                        **state,
                        "sent": "true",
                        "response": "Olá! Eu sou a Cecília do Kumon. Qual é o seu nome?",
                    }
                return state

            mock_execute.side_effect = mock_greeting_execution

            # STEP 3: Create graph and execute
            graph = build_graph()

            # STEP 4: Execute the graph - this should ONLY execute greeting_node
            result_state = graph.invoke(initial_state)

            # STEP 5: CRITICAL ASSERTIONS

            # ASSERTION 1: Only ONE message should be sent (greeting only)
            assert mock_send.call_count == 1, (
                f"CRITICAL BUG: Expected 1 message (greeting), but {mock_send.call_count} messages were sent! "
                f"This indicates automatic transition to qualification_node."
            )

            # ASSERTION 2: The sent message should be the greeting message
            call_args = mock_send.call_args[0]  # First positional arguments
            sent_message = call_args[1]  # Second argument is the message text

            assert "nome" in sent_message.lower(), (
                f"CRITICAL BUG: Greeting message should ask for name. "
                f"Actual message: '{sent_message}'"
            )

            # ASSERTION 3: greeting_sent flag should be set for next turn routing
            assert result_state.get("greeting_sent") is True, (
                f"CRITICAL BUG: greeting_sent flag not set! "
                f"This flag is needed for next turn routing. "
                f"State: {result_state}"
            )

            # ASSERTION 4: State should preserve original data
            assert (
                result_state.get("phone") == "5511999999999"
            ), f"CRITICAL BUG: Phone corrupted in greeting flow"

            # ASSERTION 5: Response should indicate successful sending
            assert (
                result_state.get("sent") == "true"
            ), f"CRITICAL BUG: Message not marked as sent"

            print("✅ SUCCESS: greeting_node stopped after sending message")
            print(f"   Message sent: {sent_message}")
            print(f"   greeting_sent flag: {result_state.get('greeting_sent')}")
            print(f"   Flow ended correctly without auto-transition")

    def test_second_turn_routes_to_qualification_after_greeting(self):
        """
        Test that the NEXT TURN after greeting correctly routes to qualification.

        This simulates the user responding with their name after receiving the greeting.
        The Gemini classifier should detect this context and route to qualification_node.
        """
        # STEP 1: Set up state for SECOND TURN (after greeting was sent)
        second_turn_state = {
            "phone": "5511999999999",
            "message_id": "greeting_flow_test_002",  # Different message_id = new turn
            "text": "meu nome é Gabriel",  # User responding with name (this is what classifier expects)
            "last_user_message": "meu nome é Gabriel",  # For completeness
            "greeting_sent": True,  # Flag set by previous greeting_node execution
            "instance": "test_instance",
        }

        # STEP 2: Mock external dependencies
        with patch("app.core.langgraph_flow.send_text") as mock_send, patch(
            "app.core.langgraph_flow.get_openai_client"
        ) as mock_openai:
            # Mock successful message sending
            mock_send.return_value = {"sent": "true", "status_code": 200}

            # Mock OpenAI response for qualification prompt
            mock_client = Mock()
            mock_client.chat.return_value = "Olá Gabriel! Qual é a idade da criança?"
            mock_openai.return_value = mock_client

            # STEP 3: Create graph and execute SECOND TURN
            graph = build_graph()

            # STEP 4: Execute - this should route to qualification_node
            result_state = graph.invoke(second_turn_state)

            # STEP 5: CRITICAL ASSERTIONS

            # ASSERTION 1: Should route to qualification_node (evidenced by qualification logic)
            assert (
                mock_send.call_count == 1
            ), f"Expected 1 message from qualification_node"

            # ASSERTION 2: Should extract parent_name from user's response
            assert result_state.get("parent_name") == "Gabriel", (
                f"CRITICAL BUG: Failed to extract parent_name from user response. "
                f"Expected: 'Gabriel', Got: {result_state.get('parent_name')}"
            )

            # ASSERTION 3: Should preserve greeting_sent flag
            assert (
                result_state.get("greeting_sent") is True
            ), f"greeting_sent flag should be preserved across turns"

            # ASSERTION 4: Should ask next qualification question
            call_args = mock_send.call_args[0]
            sent_message = call_args[1]
            assert any(
                word in sent_message.lower() for word in ["idade", "criança", "anos"]
            ), (
                f"CRITICAL BUG: qualification_node should ask next question. "
                f"Actual message: '{sent_message}'"
            )

            print("✅ SUCCESS: Second turn correctly routed to qualification")
            print(f"   Parent name extracted: {result_state.get('parent_name')}")
            print(f"   Next question sent: {sent_message}")

    def test_flow_execution_trace_validation(self):
        """
        Test that tracks the exact execution path to ensure no unwanted transitions.
        """
        initial_state = {
            "phone": "5511999999999",
            "message_id": "trace_test_001",
            "last_user_message": "olá",
            "intent": "greeting",
            "instance": "test_instance",
        }

        # Track which nodes are executed
        executed_nodes = []

        # STEP 1: Mock all node functions to track execution
        with patch("app.core.langgraph_flow.send_text") as mock_send, patch(
            "app.core.langgraph_flow.greeting_node", wraps=None
        ) as mock_greeting, patch(
            "app.core.langgraph_flow.qualification_node", wraps=None
        ) as mock_qualification:
            # Configure mocks
            mock_send.return_value = {"sent": "true", "status_code": 200}

            def track_greeting(state):
                executed_nodes.append("greeting_node")
                # Simulate the greeting node behavior
                return {
                    **state,
                    "greeting_sent": True,
                    "sent": "true",
                    "response": "Olá! Qual é o seu nome?",
                }

            def track_qualification(state):
                executed_nodes.append("qualification_node")
                return state  # Don't care about qualification behavior for this test

            mock_greeting.side_effect = track_greeting
            mock_qualification.side_effect = track_qualification

            # STEP 2: Execute graph
            graph = build_graph()
            graph.invoke(initial_state)

            # STEP 3: CRITICAL ASSERTIONS - Only greeting_node should execute

            assert (
                "greeting_node" in executed_nodes
            ), "greeting_node should have been executed"

            assert "qualification_node" not in executed_nodes, (
                f"CRITICAL BUG: qualification_node was executed in the same turn! "
                f"Executed nodes: {executed_nodes}. "
                f"This proves automatic transition is happening."
            )

            assert len(executed_nodes) == 1, (
                f"CRITICAL BUG: Expected only 1 node execution (greeting_node), "
                f"but {len(executed_nodes)} nodes were executed: {executed_nodes}"
            )

            print("✅ SUCCESS: Only greeting_node executed in first turn")
            print(f"   Execution trace: {executed_nodes}")
