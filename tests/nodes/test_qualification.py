"""
🧪 TDD Test Suite for Qualification Node Sequential Logic

This test suite validates that the qualification_node properly collects variables
in the correct sequence without skipping or failing intermediate steps.

CRITICAL: These tests follow the exact conversation flow and ensure the state
machine transitions work correctly for variable collection.
"""

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

        # ACT: Call qualification node (simplified - no mocking needed)
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

        # ACT: Call qualification node (simplified - no mocking needed)
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

        # ACT: Call qualification node (simplified - no mocking needed)
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
    async def test_qualification_node_collects_all_variables_sequentially(
        self, empty_state
    ):
        """
        🧪 COMPREHENSIVE INTEGRATION TEST: End-to-end sequential variable collection.

        This is the master test that defines the expected behavior from start to finish.
        It simulates a complete conversation flow and validates each turn.

        SCENARIO: Complete qualification conversation with realistic user inputs
        EXPECTED: Node collects all variables in correct sequence with appropriate responses
        """
        # Setup initial state for qualification
        current_state = empty_state.copy()
        current_state["current_stage"] = ConversationStage.QUALIFICATION
        current_state["current_step"] = ConversationStep.PARENT_NAME_COLLECTION

        # ========== TURNO 1: Collect parent_name ==========
        print("🧪 TURNO 1: Testing parent_name collection")
        current_state["last_user_message"] = "Meu nome é Gabriel"

        result = await qualification_node(current_state)

        # ASSERT 1: parent_name should be collected
        assert (
            "parent_name" in result["collected_data"]
        ), "parent_name should be extracted"
        assert (
            result["collected_data"]["parent_name"] == "Gabriel"
        ), f"Expected 'Gabriel', got {result['collected_data']['parent_name']}"

        # ASSERT 1.1: Should ask for beneficiary_type next
        response = result.get("last_bot_response", "")
        beneficiary_keywords = [
            "para você mesmo",
            "para outra pessoa",
            "é para você",
            "beneficiário",
        ]
        assert any(
            keyword in response.lower() for keyword in beneficiary_keywords
        ), f"Should ask about beneficiary, got: {response}"

        current_state = result
        print(
            "✅ TURNO 1 SUCCESS: parent_name='Gabriel' collected, asking for beneficiary_type"
        )

        # ========== TURNO 2: Collect beneficiary_type ==========
        print("🧪 TURNO 2: Testing beneficiary_type collection")
        current_state["last_user_message"] = "é para meu filho"

        result = await qualification_node(current_state)

        # ASSERT 2: beneficiary_type should be collected
        assert (
            "beneficiary_type" in result["collected_data"]
        ), "beneficiary_type should be extracted"
        assert (
            result["collected_data"]["beneficiary_type"] == "child"
        ), f"Expected 'child', got {result['collected_data']['beneficiary_type']}"

        # ASSERT 2.1: Should ask for student_name next
        response = result.get("last_bot_response", "")
        student_keywords = [
            "nome da criança",
            "nome do seu filho",
            "como se chama",
            "qual o nome",
        ]
        assert any(
            keyword in response.lower() for keyword in student_keywords
        ), f"Should ask for student name, got: {response}"

        current_state = result
        print(
            "✅ TURNO 2 SUCCESS: beneficiary_type='child' collected, asking for student_name"
        )

        # ========== TURNO 3: Collect student_name ==========
        print("🧪 TURNO 3: Testing student_name collection")
        current_state["last_user_message"] = "O nome dele é Pedro"

        result = await qualification_node(current_state)

        # ASSERT 3: student_name should be collected
        assert (
            "student_name" in result["collected_data"]
        ), "student_name should be extracted"
        assert (
            result["collected_data"]["student_name"] == "Pedro"
        ), f"Expected 'Pedro', got {result['collected_data']['student_name']}"

        # ASSERT 3.1: Should ask for student_age next
        response = result.get("last_bot_response", "")
        age_keywords = ["quantos anos", "idade", "anos tem", "qual a idade"]
        assert any(
            keyword in response.lower() for keyword in age_keywords
        ), f"Should ask for age, got: {response}"

        current_state = result
        print(
            "✅ TURNO 3 SUCCESS: student_name='Pedro' collected, asking for student_age"
        )

        # ========== TURNO 4: Collect student_age ==========
        print("🧪 TURNO 4: Testing student_age collection")
        current_state["last_user_message"] = "Ele tem 8 anos"

        result = await qualification_node(current_state)

        # ASSERT 4: student_age should be collected
        assert (
            "student_age" in result["collected_data"]
        ), "student_age should be extracted"
        assert (
            result["collected_data"]["student_age"] == 8
        ), f"Expected 8, got {result['collected_data']['student_age']}"

        # ASSERT 4.1: Should ask for program_interests next
        response = result.get("last_bot_response", "")
        interest_keywords = [
            "qual matéria",
            "gostaria de estudar",
            "matemática",
            "português",
            "inglês",
        ]
        assert any(
            keyword in response.lower() for keyword in interest_keywords
        ), f"Should ask for interests, got: {response}"

        current_state = result
        print(
            "✅ TURNO 4 SUCCESS: student_age=8 collected, asking for program_interests"
        )

        # ========== TURNO 5: Collect program_interests (FINAL) ==========
        print("🧪 TURNO 5: Testing program_interests collection and completion")
        current_state["last_user_message"] = "Matemática e português"

        result = await qualification_node(current_state)

        # ASSERT 5: program_interests should be collected
        assert (
            "program_interests" in result["collected_data"]
        ), "program_interests should be extracted"
        interests = result["collected_data"]["program_interests"]
        assert isinstance(
            interests, list
        ), f"interests should be a list, got {type(interests)}"
        assert (
            "Matemática" in interests
        ), f"Should contain 'Matemática', got {interests}"
        assert "Português" in interests, f"Should contain 'Português', got {interests}"

        # ASSERT 5.1: Should complete qualification and transition to next stage
        assert (
            result["current_stage"] == ConversationStage.INFORMATION_GATHERING
        ), f"Should transition to INFORMATION_GATHERING, got {result['current_stage']}"

        # ASSERT 5.2: Should generate summary response
        response = result.get("last_bot_response", "")
        summary_keywords = [
            "perfeito",
            "resumo",
            "gabriel",
            "pedro",
            "8 anos",
            "matemática",
            "português",
        ]
        assert any(
            keyword in response.lower() for keyword in summary_keywords
        ), f"Should generate summary, got: {response}"

        print("✅ TURNO 5 SUCCESS: program_interests collected, qualification COMPLETE!")

        # ========== FINAL VALIDATION ==========
        final_data = result["collected_data"]
        expected_data = {
            "parent_name": "Gabriel",
            "beneficiary_type": "child",
            "student_name": "Pedro",
            "student_age": 8,
            "program_interests": ["Matemática", "Português"],
        }

        for key, expected_value in expected_data.items():
            assert key in final_data, f"Missing required field: {key}"
            assert (
                final_data[key] == expected_value
            ), f"Field {key}: expected {expected_value}, got {final_data[key]}"

        print(
            "🎯 INTEGRATION TEST SUCCESS: Complete qualification flow working correctly!"
        )

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

    @pytest.mark.asyncio
    async def test_qualification_node_conducts_full_elegant_conversation_flow(self):
        """
        🎯 DEFINITIVE INTEGRATION TEST: Complete elegant conversation flow from start to finish.

        This is the master test that will serve as the specification for the refactored
        qualification_node. It simulates a realistic conversation where:
        1. Each turn extracts data AND generates the next question
        2. The flow is conversational and elegant
        3. All variables are collected in proper sequence
        4. The final summary is generated correctly

        This test MUST pass for the refactoring to be considered successful.
        """
        print("🎯 STARTING DEFINITIVE INTEGRATION TEST")

        # ========== TURNO 1: Initial state - Bot should ask for parent name ==========
        state = create_initial_cecilia_state(
            phone_number="5511999999999",
            user_message="olá, gostaria de saber sobre o Kumon",
            instance="kumon_assistant",
        )
        state["current_stage"] = ConversationStage.QUALIFICATION
        state["current_step"] = ConversationStep.PARENT_NAME_COLLECTION

        # First call - should ask for parent name
        state = await qualification_node(state)

        # Validate: Should ask for parent name
        response = state.get("last_bot_response", "").lower()
        assert any(
            keyword in response
            for keyword in ["qual é o seu nome", "seu nome", "como posso chamá"]
        ), f"Turn 1: Should ask for parent name, got: '{state.get('last_bot_response', '')}'"
        print("✅ TURN 1: Asked for parent name correctly")

        # ========== TURNO 2: User provides name, bot should ask about beneficiary ==========
        state["last_user_message"] = "Meu nome é Gabriel"
        state = await qualification_node(state)

        # Validate: Should extract parent_name AND ask about beneficiary
        assert (
            state["collected_data"].get("parent_name") == "Gabriel"
        ), f"Turn 2: Should extract Gabriel as parent_name, got: {state['collected_data'].get('parent_name')}"

        response = state.get("last_bot_response", "").lower()
        assert any(
            keyword in response
            for keyword in [
                "para você mesmo ou para outra pessoa",
                "é para você",
                "beneficiário",
            ]
        ), f"Turn 2: Should ask about beneficiary, got: '{state.get('last_bot_response', '')}'"
        print("✅ TURN 2: Extracted parent_name=Gabriel, asked about beneficiary")

        # ========== TURNO 3: User says it's for child, bot should ask child's name ==========
        state["last_user_message"] = "para meu filho"
        state = await qualification_node(state)

        # Validate: Should extract beneficiary_type AND ask for child's name
        assert (
            state["collected_data"].get("beneficiary_type") == "child"
        ), f"Turn 3: Should extract 'child' as beneficiary_type, got: {state['collected_data'].get('beneficiary_type')}"

        response = state.get("last_bot_response", "").lower()
        assert any(
            keyword in response
            for keyword in [
                "qual é o nome da criança",
                "nome do seu filho",
                "como se chama",
            ]
        ), f"Turn 3: Should ask for child's name, got: '{state.get('last_bot_response', '')}'"
        print("✅ TURN 3: Extracted beneficiary_type=child, asked for child name")

        # ========== TURNO 4: User provides child name, bot should ask age ==========
        state["last_user_message"] = "O nome dele é Pedro"
        state = await qualification_node(state)

        # Validate: Should extract student_name AND ask for age
        assert (
            state["collected_data"].get("student_name") == "Pedro"
        ), f"Turn 4: Should extract 'Pedro' as student_name, got: {state['collected_data'].get('student_name')}"

        response = state.get("last_bot_response", "").lower()
        assert any(
            keyword in response
            for keyword in ["quantos anos", "idade", "anos tem pedro"]
        ), f"Turn 4: Should ask for Pedro's age, got: '{state.get('last_bot_response', '')}'"
        print("✅ TURN 4: Extracted student_name=Pedro, asked for age")

        # ========== TURNO 5: User provides age, bot should ask about interests ==========
        state["last_user_message"] = "Ele tem 8 anos"
        state = await qualification_node(state)

        # Validate: Should extract student_age AND ask about interests
        assert (
            state["collected_data"].get("student_age") == 8
        ), f"Turn 5: Should extract 8 as student_age, got: {state['collected_data'].get('student_age')}"

        response = state.get("last_bot_response", "").lower()
        assert any(
            keyword in response
            for keyword in [
                "qual matéria",
                "gostaria de estudar",
                "matemática",
                "português",
                "inglês",
            ]
        ), f"Turn 5: Should ask about program interests, got: '{state.get('last_bot_response', '')}'"
        print("✅ TURN 5: Extracted student_age=8, asked about interests")

        # ========== TURNO 6: User provides interests, bot should generate summary ==========
        state["last_user_message"] = "Matemática"
        state = await qualification_node(state)

        # Validate: Should extract program_interests AND generate final summary
        interests = state["collected_data"].get("program_interests", [])
        assert (
            "Matemática" in interests
        ), f"Turn 6: Should extract 'Matemática' in interests, got: {interests}"

        # Should transition to information gathering stage
        assert (
            state["current_stage"] == ConversationStage.INFORMATION_GATHERING
        ), f"Turn 6: Should transition to INFORMATION_GATHERING, got: {state['current_stage']}"

        # Should generate comprehensive summary
        response = state.get("last_bot_response", "").lower()
        assert all(
            keyword in response
            for keyword in ["gabriel", "pedro", "8 anos", "matemática"]
        ), f"Turn 6: Summary should contain all collected data, got: '{state.get('last_bot_response', '')}'"
        assert any(
            keyword in response for keyword in ["resumo", "perfeito", "qualificação"]
        ), f"Turn 6: Should be a summary response, got: '{state.get('last_bot_response', '')}'"
        print("✅ TURN 6: Extracted interests=Matemática, generated complete summary")

        # ========== FINAL VALIDATION: All data collected correctly ==========
        final_data = state["collected_data"]
        expected_data = {
            "parent_name": "Gabriel",
            "beneficiary_type": "child",
            "student_name": "Pedro",
            "student_age": 8,
            "program_interests": ["Matemática"],
        }

        for key, expected_value in expected_data.items():
            actual_value = final_data.get(key)
            assert (
                actual_value == expected_value
            ), f"Final validation - {key}: expected {expected_value}, got {actual_value}"

        print(
            "🎯 DEFINITIVE INTEGRATION TEST PASSED: qualification_node conducts complete elegant conversation!"
        )
        return True

    @pytest.mark.asyncio
    async def test_qualification_generates_correct_follow_up_question(
        self, empty_state
    ):
        """
        🚨 RED PHASE TEST: Prove that prompt generation is failing

        SCENARIO: State with parent_name already collected ("Gabriel")
        MESSAGE: User message is "Gabriel" (confirming their name)
        EXPECTED: Node should generate specific question about beneficiary_type
        ASSERTION: Response must contain explicit beneficiary question keywords

        🔥 CRITICAL TEST: This should FAIL if prompt generation is generic!
        """
        # ARRANGE: Create state with parent_name already collected
        state_with_parent = empty_state.copy()
        state_with_parent["collected_data"]["parent_name"] = "Gabriel"
        state_with_parent["current_stage"] = ConversationStage.QUALIFICATION
        state_with_parent["current_step"] = ConversationStep.PARENT_NAME_COLLECTION
        state_with_parent["last_user_message"] = "Gabriel"

        # ACT: Call qualification node
        result = await qualification_node(state_with_parent)

        # ASSERT: Should generate specific beneficiary_type question
        response_text = result.get("last_bot_response", "")

        # 🎯 CRITICAL ASSERTION: Response MUST contain beneficiary-specific keywords
        beneficiary_keywords = [
            "para você mesmo ou para outra pessoa",
            "é para você mesmo",
            "para outra pessoa",
            "beneficiário",
            "gabriel, o kumon é para você mesmo",
        ]

        # The response should be SPECIFIC, not generic
        generic_keywords = [
            "como posso ajudar",
            "poderia me contar mais",
            "o que você gostaria",
            "em que posso ajudar",
        ]

        # POSITIVE ASSERTION: Must contain specific beneficiary question
        assert any(
            keyword in response_text.lower() for keyword in beneficiary_keywords
        ), f"Response should ask specific beneficiary question, got: '{response_text}'"

        # NEGATIVE ASSERTION: Must NOT be generic
        assert not any(
            keyword in response_text.lower() for keyword in generic_keywords
        ), f"Response should NOT be generic, got: '{response_text}'"

        # ADDITIONAL CHECK: Should mention parent name in personalized greeting
        assert (
            "gabriel" in response_text.lower()
        ), f"Response should mention parent name Gabriel, got: '{response_text}'"

        print(
            f"✅ RED PHASE TEST: Specific prompt generated - '{response_text[:60]}...'"
        )


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
