"""
🧪 TDD Test for Flexible Master Router - Explicit Intent Prioritization

This test validates that the master_router correctly prioritizes explicit user intent
over rigid continuation rules, enabling more natural conversation flow.

Following TDD Step 1.1: Create test_router_prioritizes_explicit_intent_over_continuation
"""

from unittest.mock import patch

from app.core.langgraph_flow import master_router


class TestMasterRouterFlexible:
    """Test suite for flexible master router behavior."""

    def test_router_prioritizes_explicit_intent_over_continuation(self):
        """
        🚨 RED PHASE TDD TEST: Prove current rigid behavior is broken.

        This test will FAIL with current implementation because master_router
        rigidly forces qualification continuation, ignoring explicit user intent.

        Scenario: User is mid-qualification but explicitly asks for information.
        Expected: Should honor explicit intent and route to information_node.
        Current Bug: Routes to qualification_node ignoring user intent.
        """

        # ARRANGE: Create qualification-in-progress state
        qualification_in_progress_state = {
            "phone": "+5511999888777",
            "text": "Ok, mas antes de continuar, qual o valor da mensalidade?",
            "message_id": "MSG_EXPLICIT_INFO_REQUEST",
        }

        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier.classify"
        ) as mock_classifier:
            # Mock conversation state showing qualification in progress
            mock_get_state.return_value = {
                "greeting_sent": True,  # Greeting completed
                "parent_name": "Maria Silva",  # Parent name collected
                "student_name": None,  # Still missing student info
                "student_age": None,  # Still missing age
                "program_interests": None,  # Still missing interests
                "qualification_attempts": 1,  # Qualification in progress
            }

            # Mock Gemini classifier detecting explicit information intent
            mock_classifier.return_value = {
                "primary_intent": "information",
                "secondary_intent": None,
                "entities": {},
                "confidence": 0.95,
            }

            # ACT: Call master_router
            result = master_router(qualification_in_progress_state)

            # ASSERT: Should prioritize explicit intent over continuation
            # 🚨 THIS WILL FAIL - Current router ignores user intent
            assert result == "information_node", (
                f"CRITICAL BUG: Router should honor explicit information request "
                f"but got '{result}'. User said 'qual o valor da mensalidade?' "
                f"but router ignored their explicit intent!"
            )

            print("✅ SUCCESS: Router correctly prioritizes explicit user intent")
            print(f"✅ User Request: {qualification_in_progress_state['text']}")
            print(f"✅ AI Classification: information (confidence: 0.95)")
            print(f"✅ Router Decision: {result}")

    def test_router_maintains_continuation_when_no_explicit_intent(self):
        """
        ✅ VALIDATION TEST: Ensure continuation logic still works.

        This test ensures that when there's NO explicit intent,
        the router still correctly continues qualification flow.
        """

        # ARRANGE: Create qualification continuation scenario
        qualification_continuation_state = {
            "phone": "+5511888999777",
            "text": "Gabriel",  # Simple response to qualification question
            "message_id": "MSG_QUALIFICATION_RESPONSE",
        }

        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier.classify"
        ) as mock_classifier:
            # Mock conversation state showing qualification in progress
            mock_get_state.return_value = {
                "greeting_sent": True,  # Greeting completed
                "parent_name": "Maria Silva",  # Parent name collected
                "student_name": None,  # Expecting student name response
                "student_age": None,
                "program_interests": None,
                "qualification_attempts": 2,  # Mid-qualification
            }

            # Mock Gemini classifier detecting qualification response (not explicit intent)
            mock_classifier.return_value = {
                "primary_intent": "qualification",
                "secondary_intent": None,
                "entities": {"student_name": "Gabriel"},
                "confidence": 0.85,
            }

            # ACT: Call master_router
            result = master_router(qualification_continuation_state)

            # ASSERT: Should continue qualification flow
            assert result == "qualification_node", (
                f"Expected qualification continuation for simple response 'Gabriel', "
                f"got '{result}'"
            )

            print(
                "✅ SUCCESS: Router correctly continues qualification when appropriate"
            )
            print(f"✅ User Response: {qualification_continuation_state['text']}")
            print(f"✅ AI Classification: qualification (confidence: 0.85)")
            print(f"✅ Router Decision: {result}")


if __name__ == "__main__":
    print("🧪 Running TDD tests for flexible master_router...")

    test_suite = TestMasterRouterFlexible()

    try:
        print("\n1️⃣ Testing explicit intent prioritization (should FAIL initially)...")
        test_suite.test_router_prioritizes_explicit_intent_over_continuation()

        print("\n2️⃣ Testing continuation logic preservation...")
        test_suite.test_router_maintains_continuation_when_no_explicit_intent()

        print("\n🎯 All tests PASSED! Router flexibility implemented correctly.")

    except AssertionError as e:
        print(f"\n❌ Test FAILED as expected (TDD Red Phase): {e}")
        print("🔧 Now implement flexible routing logic in master_router.")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
