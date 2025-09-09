"""
Integration tests for conversational flow behavior.

Tests that validate the graph stops and waits for user input after making questions,
behaving like a true conversational assistant rather than executing all steps at once.
"""

from unittest.mock import MagicMock, patch

from app.core.langgraph_flow import workflow


class TestConversationalFlow:
    """Integration test suite for conversational flow behavior."""

    def test_graph_stops_and_waits_for_user_input_after_qualification_question(self):
        """
        CRITICAL BEHAVIOR TEST: Ensure graph stops execution after asking a question.

        This test addresses the fundamental conversational flow issue where the graph
        executes all steps at once instead of stopping and waiting for user responses.

        Expected Behavior: Graph should execute greeting → qualification (ask question) → END
        Current Problem: Graph executes greeting → qualification → qualification → qualification (loop)
        """

        # STEP 1: Initial user message that should trigger greeting → qualification flow
        initial_state = {
            "text": "Oi",
            "phone": "5511999999999",
            "message_id": "MSG_CONVERSATIONAL_001",
            "instance": "kumon_assistant",
        }

        # STEP 2: Mock external dependencies
        with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
            with patch("app.core.langgraph_flow.send_text") as mock_send_text:
                # Configure mocks for successful message sending
                mock_send_text.return_value = {"sent": "true", "status_code": 200}

                mock_client = MagicMock()
                # Greeting response
                mock_client.chat.side_effect = [
                    "Olá! Eu sou a Cecília. Para começarmos, qual é o seu nome?",
                    "Ótimo! Agora preciso saber qual é o nome da criança para quem será o curso?",
                ]
                mock_openai.return_value = mock_client

                # STEP 3: Mock qualification prompt to track executions
                with patch(
                    "app.core.langgraph_flow.get_qualification_prompt"
                ) as mock_qualification_prompt:
                    mock_qualification_prompt.return_value = {
                        "system": "Pergunta para qualificação de nome",
                        "user": "Oi",
                    }

                    # STEP 4: Execute workflow - this should stop after asking a question
                    result = workflow.invoke(initial_state)

                    # STEP 5: CRITICAL ASSERTIONS - Validate conversational stopping behavior

                    # ASSERTION 1: Workflow should complete successfully
                    assert result.get("sent") in [
                        "true",
                        "false",
                    ], f"Workflow should complete and return sent status, got: {result}"

                    # ASSERTION 2: OpenAI should be called EXACTLY TWICE (greeting + qualification)
                    # NOT multiple times due to internal qualification loops
                    expected_calls = (
                        2  # greeting + qualification (ask question then STOP)
                    )
                    actual_calls = mock_client.chat.call_count

                    assert actual_calls == expected_calls, (
                        f"CONVERSATIONAL FLOW BUG: Expected exactly {expected_calls} LLM calls "
                        f"(greeting + qualification question), but got {actual_calls} calls. "
                        f"This indicates the graph is looping internally instead of stopping "
                        f"to wait for user input after asking a question."
                    )

                    # ASSERTION 3: Qualification prompt should be called EXACTLY ONCE
                    # The graph should ask one question then stop, not keep looping
                    qualification_calls = mock_qualification_prompt.call_count
                    assert qualification_calls == 1, (
                        f"CONVERSATIONAL FLOW BUG: Expected qualification_prompt to be called "
                        f"exactly once (ask question then stop), but got {qualification_calls} calls. "
                        f"Multiple calls indicate the graph is looping internally instead of "
                        f"stopping to wait for user response."
                    )

                    # ASSERTION 4: Evolution API should be called EXACTLY TWICE (greeting + qualification)
                    evolution_calls = mock_send_text.call_count
                    expected_evolution_calls = 2

                    assert evolution_calls == expected_evolution_calls, (
                        f"CONVERSATIONAL FLOW BUG: Expected {expected_evolution_calls} Evolution API calls "
                        f"(greeting response + qualification question), but got {evolution_calls} calls. "
                        f"Multiple calls indicate internal looping instead of conversational stopping."
                    )

                    print(
                        "✅ SUCCESS: Graph stops and waits for user input after asking qualification question"
                    )

    def test_graph_continues_from_saved_state_on_next_message(self):
        """
        Test that graph intelligently continues from where it left off using Redis state.

        This validates the "smart entry point" behavior where the graph resumes
        qualification based on saved conversation state.
        """

        # STEP 1: First message establishes context (parent name provided)
        first_message_state = {
            "text": "Oi, meu nome é Carlos",
            "phone": "5511888888888",
            "message_id": "MSG_RESUME_001",
            "instance": "kumon_assistant",
        }

        # STEP 2: Mock dependencies
        with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
            with patch("app.core.langgraph_flow.send_text") as mock_send_text:
                mock_send_text.return_value = {"sent": "true", "status_code": 200}

                mock_client = MagicMock()
                mock_client.chat.return_value = (
                    "Prazer, Carlos! Agora preciso saber o nome da criança."
                )
                mock_openai.return_value = mock_client

                # Execute first message (should establish parent_name in Redis)
                first_result = workflow.invoke(first_message_state)
                assert (
                    first_result.get("sent") == "true"
                ), "First message should be processed"

        # STEP 3: Second message should intelligently route to qualification (not greeting)
        second_message_state = {
            "text": "O nome dela é Ana",
            "phone": "5511888888888",  # Same phone - should load saved state
            "message_id": "MSG_RESUME_002",
            "instance": "kumon_assistant",
        }

        with patch("app.core.langgraph_flow.get_openai_client") as mock_openai_2:
            with patch("app.core.langgraph_flow.send_text") as mock_send_text_2:
                mock_send_text_2.return_value = {"sent": "true", "status_code": 200}

                mock_client_2 = MagicMock()
                mock_client_2.chat.return_value = (
                    "Perfeito, Ana! Agora preciso saber a idade dela."
                )
                mock_openai_2.return_value = mock_client_2

                # Mock classification to track routing decisions
                with patch("app.core.langgraph_flow.classify_intent") as mock_classify:
                    # Should route directly to qualification based on saved state
                    mock_classify.return_value = "qualification_node"

                    # Execute second message
                    second_result = workflow.invoke(second_message_state)

                    # CRITICAL ASSERTIONS for intelligent continuation

                    # ASSERTION 1: Classification should route to qualification (not greeting)
                    assert (
                        mock_classify.called
                    ), "classify_intent should be called for routing"

                    # ASSERTION 2: Second message should be processed successfully
                    assert (
                        second_result.get("sent") == "true"
                    ), "Second message should be processed successfully"

                    # ASSERTION 3: Only ONE LLM call (qualification response)
                    # Should not call greeting since we're continuing qualification
                    assert mock_client_2.chat.call_count == 1, (
                        f"Expected exactly 1 LLM call for qualification continuation, "
                        f"got {mock_client_2.chat.call_count} calls"
                    )

                    print("✅ SUCCESS: Graph intelligently continues from saved state")

    def test_fresh_conversation_starts_with_greeting(self):
        """
        Test that completely new conversations (no saved state) start with greeting.

        This validates that the intelligent entry point correctly identifies new vs continuing conversations.
        """

        # STEP 1: Completely fresh conversation (new phone number)
        fresh_state = {
            "text": "Olá",
            "phone": "5511777777777",  # New phone number - no saved state
            "message_id": "MSG_FRESH_001",
            "instance": "kumon_assistant",
        }

        # STEP 2: Mock dependencies
        with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
            with patch("app.core.langgraph_flow.send_text") as mock_send_text:
                mock_send_text.return_value = {"sent": "true", "status_code": 200}

                mock_client = MagicMock()
                mock_client.chat.return_value = (
                    "Olá! Eu sou a Cecília. Qual é o seu nome?"
                )
                mock_openai.return_value = mock_client

                # Mock classification to track routing decisions
                with patch("app.core.langgraph_flow.classify_intent") as mock_classify:
                    # Should route to greeting for fresh conversations
                    mock_classify.return_value = "greeting_node"

                    # Execute fresh conversation
                    result = workflow.invoke(fresh_state)

                    # CRITICAL ASSERTIONS for fresh conversation handling

                    # ASSERTION 1: Should be processed successfully
                    assert (
                        result.get("sent") == "true"
                    ), "Fresh conversation should be processed"

                    # ASSERTION 2: Classification should route to greeting
                    assert mock_classify.called, "classify_intent should be called"

                    # ASSERTION 3: Exactly one LLM call (greeting only)
                    assert mock_client.chat.call_count == 1, (
                        f"Expected exactly 1 LLM call for fresh greeting, "
                        f"got {mock_client.chat.call_count} calls"
                    )

                    print(
                        "✅ SUCCESS: Fresh conversations start correctly with greeting"
                    )
