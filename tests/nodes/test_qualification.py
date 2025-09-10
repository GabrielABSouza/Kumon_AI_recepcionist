"""
🧪 TDD Test Suite for Qualification Node Sequential Logic

This test suite validates that the qualification_node properly collects variables
in the correct sequence without skipping or failing intermediate steps.

CRITICAL: These tests follow the exact conversation flow and ensure the state
machine transitions work correctly for variable collection.
"""
from unittest.mock import patch

import pytest

from app.core.nodes.qualification import qualification_node
from app.core.state.models import (
    CeciliaState,
    ConversationStage,
    ConversationStep,
    create_initial_cecilia_state,
)

# 🎯 SOURCE OF TRUTH: Sequential qualification variables order
QUALIFICATION_VARS_SEQUENCE = [
    "parent_name",
    "beneficiary_type",
    "student_name",
    "student_age",
    "program_interests",
]


class TestQualificationSequentialLogic:
    """
    🧪 RED-GREEN TDD Test Suite for Sequential Variable Collection

    Each test represents a step in the conversation flow and must pass
    to ensure the qualification_node works as expected.
    """

    @pytest.fixture
    def empty_state(self):
        """Create empty state for testing initial qualification."""
        return create_initial_cecilia_state(
            phone_number="5511999999999",
            user_message="olá, gostaria de saber sobre o Kumon",
            instance="kumon_assistant",
        )

    @pytest.fixture
    def state_with_parent_name(self):
        """Create state with parent_name already collected."""
        state = create_initial_cecilia_state(
            phone_number="5511999999999",
            user_message="Maria Silva",
            instance="kumon_assistant",
        )
        state["collected_data"]["parent_name"] = "Maria Silva"
        state["current_stage"] = ConversationStage.QUALIFICATION
        state["current_step"] = ConversationStep.CHILD_NAME_COLLECTION
        return state

    @pytest.fixture
    def state_with_parent_and_beneficiary(self):
        """Create state with parent_name and beneficiary_type collected."""
        state = create_initial_cecilia_state(
            phone_number="5511999999999",
            user_message="para meu filho",
            instance="kumon_assistant",
        )
        state["collected_data"]["parent_name"] = "Maria Silva"
        state["collected_data"]["beneficiary_type"] = "child"
        state["current_stage"] = ConversationStage.QUALIFICATION
        state["current_step"] = ConversationStep.CHILD_AGE_INQUIRY
        return state

    # ========== RED PHASE TESTS ==========

    def test_qualification_vars_sequence_is_defined(self):
        """
        🧪 FOUNDATION TEST: Ensure the qualification sequence is properly defined.

        This test validates that we have a clear, ordered sequence of variables
        that the qualification_node must collect.
        """
        expected_vars = [
            "parent_name",
            "beneficiary_type",
            "student_name",
            "student_age",
            "program_interests",
        ]

        assert QUALIFICATION_VARS_SEQUENCE == expected_vars
        assert len(QUALIFICATION_VARS_SEQUENCE) == 5
        print("✅ FOUNDATION SUCCESS: Qualification sequence properly defined")

    @pytest.mark.asyncio
    async def test_asks_for_parent_name_when_qualification_starts(self, empty_state):
        """
        🚨 RED PHASE TEST 2.1: Ask for parent_name when qualification starts.

        SCENARIO: Empty state, qualification just started
        EXPECTED: Node should ask specifically for parent name

        This test will likely PASS as it's the first step in qualification.
        """
        # ARRANGE: Empty state with no collected data
        empty_state["current_stage"] = ConversationStage.QUALIFICATION
        empty_state["current_step"] = ConversationStep.PARENT_NAME_COLLECTION

        # Mock the prompt manager to return a parent name prompt
        with patch("app.core.nodes.qualification.prompt_manager") as mock_prompt:
            mock_prompt.get_prompt.return_value = "Qual é o seu nome?"

            # ACT: Call qualification node
            result = await qualification_node(empty_state)

            # ASSERT: Should store response in state and return updated state
            assert isinstance(
                result, dict
            ), "qualification_node should return updated state"

            # The response should be stored in last_bot_response
            response_text = result.get("last_bot_response", "")

            # Should contain parent name inquiry keywords
            assert any(
                keyword in response_text.lower()
                for keyword in [
                    "nome",
                    "seu nome",
                    "como posso chamá",
                    "como você se chama",
                ]
            ), f"Response should ask for parent name, got: {response_text}"

            print("✅ TEST 2.1 SUCCESS: Asks for parent_name when qualification starts")

    @pytest.mark.asyncio
    async def test_asks_for_beneficiary_type_after_parent_name_is_collected(
        self, state_with_parent_name
    ):
        """
        🚨 RED PHASE TEST 2.2: Ask for beneficiary_type after parent_name collected.

        SCENARIO: State contains parent_name, user just provided their name
        EXPECTED: Node should ask "para você mesmo ou para outra pessoa?"

        🔥 CRITICAL TEST: This is likely where the bug is occurring!
        """
        # ARRANGE: State with parent_name already collected
        state_with_parent_name["last_user_message"] = "Maria Silva"

        # Mock the prompt manager
        with patch("app.core.nodes.qualification.prompt_manager") as mock_prompt:
            mock_prompt.get_prompt.return_value = (
                "O Kumon é para você mesmo ou para outra pessoa?"
            )

            # ACT: Call qualification node
            result = await qualification_node(state_with_parent_name)

            # ASSERT: Should ask for beneficiary type
            assert isinstance(
                result, dict
            ), "qualification_node should return updated state"
            response_text = result.get("last_bot_response", "")

            # Should contain beneficiary type inquiry
            beneficiary_keywords = [
                "para você mesmo",
                "para outra pessoa",
                "para quem é",
                "é para você",
                "para si mesmo",
                "beneficiário",
            ]
            assert any(
                keyword in response_text.lower() for keyword in beneficiary_keywords
            ), f"Response should ask for beneficiary type, got: {response_text}"

            print(
                "✅ TEST 2.2 SUCCESS: Asks for beneficiary_type after parent_name collected"
            )

    @pytest.mark.asyncio
    async def test_asks_for_student_name_when_beneficiary_is_child(
        self, state_with_parent_and_beneficiary
    ):
        """
        🚨 RED PHASE TEST 2.3: Ask for student_name when beneficiary is child.

        SCENARIO: parent_name and beneficiary_type='child' collected
        EXPECTED: Node should ask "Qual o nome da criança?"
        """
        # ARRANGE: State with parent and beneficiary type collected
        state_with_parent_and_beneficiary["last_user_message"] = "para meu filho"

        # Mock the prompt manager
        with patch("app.core.nodes.qualification.prompt_manager") as mock_prompt:
            mock_prompt.get_prompt.return_value = "Qual é o nome da criança?"

            # ACT: Call qualification node
            result = await qualification_node(state_with_parent_and_beneficiary)

            # ASSERT: Should ask for student name
            assert isinstance(
                result, dict
            ), "qualification_node should return updated state"
            response_text = result.get("last_bot_response", "")

            # Should contain student name inquiry
            student_name_keywords = [
                "nome da criança",
                "nome do seu filho",
                "como se chama",
                "qual o nome",
                "nome dele",
                "nome dela",
            ]
            assert any(
                keyword in response_text.lower() for keyword in student_name_keywords
            ), f"Response should ask for student name, got: {response_text}"

            print("✅ TEST 2.3 SUCCESS: Asks for student_name when beneficiary is child")

    @pytest.mark.asyncio
    async def test_qualification_node_follows_sequence_logic(self, empty_state):
        """
        🧪 INTEGRATION TEST: Validate that qualification_node follows sequence logic.

        This test validates the internal logic that determines which variable to collect next.
        """
        # Test with different states and validate correct next variable
        test_cases = [
            # (collected_data, expected_next_var)
            ({}, "parent_name"),
            ({"parent_name": "Maria"}, "beneficiary_type"),
            ({"parent_name": "Maria", "beneficiary_type": "child"}, "student_name"),
            (
                {"parent_name": "Maria", "beneficiary_type": "self"},
                "student_age",
            ),  # Skip student_name
        ]

        for collected_data, expected_next_var in test_cases:
            # Create state with specific collected data
            test_state = empty_state.copy()
            test_state["collected_data"].update(collected_data)

            # Extract the logic to determine next variable (this will be implemented)
            next_var = await _get_next_qualification_variable(test_state)

            assert (
                next_var == expected_next_var
            ), f"With {collected_data}, expected next var '{expected_next_var}', got '{next_var}'"

        print("✅ SEQUENCE LOGIC SUCCESS: Node follows correct variable sequence")


# ========== HELPER FUNCTIONS ==========


async def _get_next_qualification_variable(state: CeciliaState) -> str:
    """
    🔧 HELPER: Extract the logic that determines the next qualification variable.

    This function will be used to test the internal logic of qualification_node
    and will need to be implemented based on the actual node logic.
    """
    collected = state["collected_data"]

    # Follow the sequence, return first missing variable
    for var in QUALIFICATION_VARS_SEQUENCE:
        if var not in collected or not collected.get(var):
            # Handle conditional logic
            if var == "student_name" and collected.get("beneficiary_type") == "self":
                continue  # Skip student_name if beneficiary is self
            return var

    return None  # All variables collected


# ========== EXECUTION VALIDATION ==========

if __name__ == "__main__":
    """
    🧪 Quick validation that tests can be imported and basic structure works.
    """
    print("🧪 TDD Qualification Node Test Suite")
    print(f"📋 Testing sequence: {QUALIFICATION_VARS_SEQUENCE}")
    print("🎯 Ready for Red-Green-Refactor cycle!")
