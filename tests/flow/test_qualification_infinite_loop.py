"""
Integration test for qualification_node infinite loop bug.

This test reproduces the critical issue where users get stuck in qualification_node
after greeting completion, causing continuous AI calls and poor UX.

Test follows TDD approach: Write failing test first, then implement fix.
"""
import asyncio
from unittest.mock import MagicMock, patch


from app.core.langgraph_flow import (
    QUALIFICATION_REQUIRED_VARS,
    qualification_node,
    route_from_qualification,
)


class TestQualificationInfiniteLoop:
    """Test suite for qualification_node infinite loop scenarios."""

    def test_qualification_node_loops_with_missing_data(self):
        """Test that qualification_node loops when required data is missing."""
        # State after greeting - only parent_name collected
        state_after_greeting = {
            "phone": "5511999999999",
            "message_id": "MSG_123",
            "instance": "kumon_assistant",
            "text": "Preciso de informações sobre o Kumon",
            "parent_name": "Maria",  # Collected in greeting
            # Missing: student_name, student_age, program_interests
        }

        # Check that we're missing required variables
        missing_vars = [
            var
            for var in QUALIFICATION_REQUIRED_VARS
            if var not in state_after_greeting or not state_after_greeting[var]
        ]
        assert (
            len(missing_vars) == 3
        ), f"Should have 3 missing vars, got {len(missing_vars)}: {missing_vars}"

        # Route from qualification should return qualification_node (loop)
        next_node = route_from_qualification(state_after_greeting)
        assert (
            next_node == "qualification_node"
        ), f"Should loop back to qualification_node when data missing, got {next_node}"

    def test_qualification_node_exits_with_complete_data(self):
        """Test that qualification_node exits loop when all data is collected."""
        # State with all required qualification data
        complete_state = {
            "phone": "5511999999999",
            "message_id": "MSG_124",
            "instance": "kumon_assistant",
            "text": "Tenho interesse em matemática",
            "parent_name": "Maria",
            "student_name": "João",
            "student_age": 8,
            "program_interests": ["mathematics"],
        }

        # Check that all required variables are present
        missing_vars = [
            var
            for var in QUALIFICATION_REQUIRED_VARS
            if var not in complete_state or not complete_state[var]
        ]
        assert (
            len(missing_vars) == 0
        ), f"Should have no missing vars, got {missing_vars}"

        # Route from qualification should proceed to scheduling_node
        next_node = route_from_qualification(complete_state)
        assert (
            next_node == "scheduling_node"
        ), f"Should proceed to scheduling_node when data complete, got {next_node}"

    def test_qualification_node_execution_with_mock(self):
        """Test qualification_node execution with mocked dependencies."""
        # Mock state with partially collected data
        state = {
            "phone": "5511999999999",
            "message_id": "MSG_125",
            "instance": "kumon_assistant",
            "text": "Meu filho tem 10 anos",  # Should extract student_age
            "parent_name": "Carlos",
            # Missing: student_name, program_interests
        }

        with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
            with patch(
                "app.core.langgraph_flow.get_conversation_state"
            ) as mock_get_state:
                with patch(
                    "app.core.langgraph_flow.save_conversation_state"
                ) as mock_save_state:
                    with patch("app.core.langgraph_flow.send_text") as mock_send:
                        with patch(
                            "app.core.langgraph_flow.get_openai_client"
                        ) as mock_openai:
                            # Mock turn controller
                            mock_turn.has_replied.return_value = False
                            mock_turn.mark_replied.return_value = None

                            # Mock state management
                            mock_get_state.return_value = {}
                            mock_save_state.return_value = None

                            # Mock OpenAI response
                            mock_client = MagicMock()
                            mock_client.chat.return_value = asyncio.Future()
                            mock_client.chat.return_value.set_result(
                                "Perfeito! Agora me conte, qual é o nome do seu filho?"
                            )
                            mock_openai.return_value = mock_client

                            # Mock delivery success
                            mock_send.return_value = {"sent": "true"}

                            # Execute qualification node
                            result = qualification_node(state)

                            # Should execute successfully
                            assert result["sent"] == "true"
                            assert "response" in result

                            # Verify OpenAI was called
                            mock_openai.assert_called_once()
                            mock_client.chat.assert_called_once()

                            # Verify message was sent
                            mock_send.assert_called_once()

                            # Verify state was saved
                            mock_save_state.assert_called_once()

    def test_qualification_infinite_loop_prevention(self):
        """Test that infinite loops are prevented with proper state machine logic."""
        # This test identifies the core issue: qualification_node can loop indefinitely
        # if the routing logic doesn't account for conversation progress

        # Simulate multiple turns in qualification without progress
        states_sequence = [
            {
                "phone": "5511999999999",
                "message_id": "MSG_126_1",
                "parent_name": "Ana",
                "text": "Quero saber mais sobre o Kumon",  # Doesn't provide required info
            },
            {
                "phone": "5511999999999",
                "message_id": "MSG_126_2",
                "parent_name": "Ana",
                "text": "Certo, entendi",  # Still doesn't provide info
            },
            {
                "phone": "5511999999999",
                "message_id": "MSG_126_3",
                "parent_name": "Ana",
                "text": "Ok",  # Generic response, no progress
            },
        ]

        # All these states should route back to qualification_node
        # This is the BUG: user can be stuck indefinitely asking the same questions
        for i, state in enumerate(states_sequence):
            next_node = route_from_qualification(state)
            assert (
                next_node == "qualification_node"
            ), f"Turn {i+1}: Should route to qualification_node, got {next_node}"

        # The fix should include:
        # 1. Turn counter to prevent infinite loops
        # 2. Alternative routing after X failed attempts
        # 3. Fallback to human handoff or simpler flow
        # 4. Better prompt engineering to guide users

        # This test will PASS currently (showing the bug exists)
        # After implementing the fix, we'll add assertions for the prevention logic

    def test_qualification_node_with_conversation_context(self):
        """Test qualification node behavior with conversation history context."""
        # State representing a user who has been in qualification for multiple turns
        state_with_history = {
            "phone": "5511999999999",
            "message_id": "MSG_127",
            "instance": "kumon_assistant",
            "text": "Não sei bem",  # Unhelpful response
            "parent_name": "Ricardo",
            "conversation_turn_count": 3,  # This field should be tracked
            "qualification_attempts": 2,  # Track qualification attempts
            # Still missing required qualification data
        }

        # Current implementation will route back to qualification_node
        next_node = route_from_qualification(state_with_history)
        assert (
            next_node == "qualification_node"
        ), "Current implementation should loop (showing the bug)"

        # TODO: After fix implementation, add assertions for:
        # - Turn count limits
        # - Alternative routing after failed attempts
        # - Escalation to human or fallback flow

    def test_qualification_state_machine_prevents_infinite_loop(self):
        """Test that the new state machine prevents infinite loops."""
        # Simulate 4 attempts in qualification without collecting data
        state = {
            "phone": "5511999999999",
            "message_id": "MSG_128",
            "parent_name": "Patricia",  # Only parent name collected
            "qualification_attempts": 3,  # Already 3 attempts
            # Missing: student_name, student_age, program_interests
        }

        # After 4th attempt, should route to information_node (escape hatch)
        next_node = route_from_qualification(state)

        assert (
            next_node == "information_node"
        ), f"After 4 attempts, should route to information_node for escape, got {next_node}"

        # Verify that the attempt counter is incremented
        assert (
            state["qualification_attempts"] == 4
        ), f"Qualification attempts should be incremented to 4, got {state['qualification_attempts']}"

    def test_qualification_state_machine_continues_with_progress(self):
        """Test that state machine continues when user makes progress."""
        # State showing progress (collected student_name after previous attempts)
        state_with_progress = {
            "phone": "5511999999999",
            "message_id": "MSG_129",
            "parent_name": "Roberto",
            "student_name": "Lucas",  # Progress made
            "qualification_attempts": 2,  # 2 previous attempts
            # Still missing: student_age, program_interests
        }

        # Should continue in qualification since progress was made
        next_node = route_from_qualification(state_with_progress)

        assert (
            next_node == "qualification_node"
        ), f"Should continue qualification when progress made, got {next_node}"

        # Attempt counter should be incremented
        assert (
            state_with_progress["qualification_attempts"] == 3
        ), f"Should increment attempts to 3, got {state_with_progress['qualification_attempts']}"
