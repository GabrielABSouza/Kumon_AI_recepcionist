"""
Test Intent Classifier Refactoring - Separation of Concerns.

This test validates the refactored classify_intent function that implements
the "Rules First, AI After" principle by separating business logic from AI classification.

After refactoring:
- classify_intent: Pure business logic for conversation continuation
- GeminiClassifier: Pure AI-based intent classification from natural language
"""

from unittest.mock import patch


from app.core.langgraph_flow import classify_intent


class TestIntentClassifierRefactoring:
    """Test suite for refactored intent classification logic."""

    def test_classify_intent_returns_continuation_when_greeting_sent(self):
        """
        Test that classify_intent returns qualification_node when greeting_sent=True.

        This validates the business rule: "If we sent a greeting, the next message
        should be processed as qualification (user responding with their name)."
        """
        # STEP 1: Set up state with greeting_sent flag
        state_after_greeting = {
            "phone": "5511999999999",
            "text": "meu nome é Gabriel",
            "greeting_sent": True,  # The key business rule trigger
            "parent_name": None,  # Not collected yet
        }

        # STEP 2: Mock conversation state to simulate greeting was sent
        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            mock_get_state.return_value = {
                "greeting_sent": True,
                "parent_name": None,
                "student_name": None,
                "student_age": None,
                "program_interests": None,
            }

            # STEP 3: Call classify_intent (should only do business logic)
            result = classify_intent(state_after_greeting)

            # STEP 4: CRITICAL ASSERTION - Business rule should trigger
            assert result == "qualification_node", (
                f"CRITICAL BUG: classify_intent should return 'qualification_node' "
                f"when greeting_sent=True (business rule), but got: {result}"
            )

            print("✅ Business Rule Applied: greeting_sent=True → qualification_node")

    def test_classify_intent_returns_continuation_when_qualification_in_progress(self):
        """
        Test that classify_intent continues qualification when partial data exists.

        This validates the business rule: "If we have partial qualification data,
        continue collecting missing variables."
        """
        # STEP 1: Set up state with partial qualification data
        state_partial_qualification = {
            "phone": "5511999999999",
            "text": "ele tem 8 anos",
        }

        # STEP 2: Mock saved state with partial qualification data
        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            mock_get_state.return_value = {
                "parent_name": "Gabriel",  # ✅ Collected
                "student_name": "João",  # ✅ Collected
                "student_age": None,  # ❌ Missing
                "program_interests": None,  # ❌ Missing
            }

            # STEP 3: Call classify_intent
            result = classify_intent(state_partial_qualification)

            # STEP 4: CRITICAL ASSERTION - Should continue qualification
            assert result == "qualification_node", (
                f"CRITICAL BUG: classify_intent should continue qualification "
                f"when partial data exists, but got: {result}"
            )

            print(
                "✅ Business Rule Applied: partial qualification → continue qualification_node"
            )

    def test_classify_intent_returns_scheduling_when_qualification_complete(self):
        """
        Test that classify_intent advances to scheduling when qualification is complete.

        This validates the business rule: "If all qualification variables are collected,
        proceed to scheduling."
        """
        # STEP 1: Set up state with complete qualification
        state_complete_qualification = {
            "phone": "5511999999999",
            "text": "quero agendar uma visita",
        }

        # STEP 2: Mock saved state with complete qualification data
        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            mock_get_state.return_value = {
                "parent_name": "Gabriel",  # ✅ Collected
                "student_name": "João",  # ✅ Collected
                "student_age": 8,  # ✅ Collected
                "program_interests": ["mathematics"],  # ✅ Collected
            }

            # STEP 3: Call classify_intent
            result = classify_intent(state_complete_qualification)

            # STEP 4: CRITICAL ASSERTION - Should advance to scheduling
            assert result == "scheduling_node", (
                f"CRITICAL BUG: classify_intent should advance to scheduling "
                f"when qualification is complete, but got: {result}"
            )

            print("✅ Business Rule Applied: complete qualification → scheduling_node")

    def test_classify_intent_returns_none_for_new_conversation(self):
        """
        Test that classify_intent returns None when no business rules apply.

        This validates that classify_intent only handles business logic and
        defers to AI classification when no continuation rules apply.
        """
        # STEP 1: Set up state for completely new conversation
        state_new_conversation = {
            "phone": "5511888888888",  # Different number = new conversation
            "text": "oi, boa tarde",  # New greeting
        }

        # STEP 2: Mock empty conversation state (new conversation)
        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            mock_get_state.return_value = {}  # No saved state = new conversation

            # STEP 3: Call classify_intent
            result = classify_intent(state_new_conversation)

            # STEP 4: CRITICAL ASSERTION - Should return None (defer to AI)
            assert result is None, (
                f"CRITICAL BUG: classify_intent should return None for new conversations "
                f"(no business rules apply), but got: {result}"
            )

            print("✅ Business Logic: No continuation rules → defer to AI (None)")

    def test_classify_intent_returns_none_when_no_saved_state(self):
        """
        Test that classify_intent handles missing saved state gracefully.

        This validates robustness when conversation state is not available.
        """
        # STEP 1: Set up state
        state = {
            "phone": "5511777777777",
            "text": "olá",
        }

        # STEP 2: Mock get_conversation_state to return None (no saved state)
        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            mock_get_state.return_value = None

            # STEP 3: Call classify_intent
            result = classify_intent(state)

            # STEP 4: CRITICAL ASSERTION - Should handle gracefully
            assert result is None, (
                f"CRITICAL BUG: classify_intent should handle missing saved state gracefully "
                f"and return None, but got: {result}"
            )

            print("✅ Robustness: Missing saved state → defer to AI (None)")

    def test_classify_intent_does_not_call_gemini_classifier(self):
        """
        CRITICAL TEST: Validate that classify_intent does NOT call GeminiClassifier.

        This ensures separation of concerns - classify_intent only does business logic,
        never AI classification.
        """
        # STEP 1: Set up any state
        state = {
            "phone": "5511999999999",
            "text": "qualquer mensagem",
            "greeting_sent": True,
        }

        # STEP 2: Mock dependencies and track calls
        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier:
            mock_get_state.return_value = {"greeting_sent": True}

            # STEP 3: Call classify_intent
            result = classify_intent(state)

            # STEP 4: CRITICAL ASSERTION - GeminiClassifier should NOT be called
            assert not mock_classifier.called, (
                f"CRITICAL ARCHITECTURE VIOLATION: classify_intent called GeminiClassifier! "
                f"This breaks separation of concerns. classify_intent should only handle "
                f"business logic, not AI classification."
            )

            assert (
                not mock_classifier.classify.called
            ), f"CRITICAL ARCHITECTURE VIOLATION: classify_intent called classifier.classify()!"

            print("✅ Architecture: classify_intent maintains separation of concerns")
            print(f"   Result: {result} (business logic only)")

    def test_classify_intent_only_uses_deterministic_rules(self):
        """
        Test that classify_intent is fully deterministic and doesn't use text analysis.

        This validates that the function only inspects state/context,
        never the actual user message content.
        """
        # STEP 1: Set up two identical states with different text
        base_state = {
            "phone": "5511999999999",
        }

        state_1 = {**base_state, "text": "oi"}
        state_2 = {**base_state, "text": "completely different message here"}

        # STEP 2: Mock identical saved state
        saved_state = {"greeting_sent": True}

        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            mock_get_state.return_value = saved_state

            # STEP 3: Call classify_intent with different texts
            result_1 = classify_intent(state_1)
            result_2 = classify_intent(state_2)

            # STEP 4: CRITICAL ASSERTION - Results should be identical
            assert result_1 == result_2, (
                f"CRITICAL BUG: classify_intent is not deterministic! "
                f"Same business state should produce same result regardless of message text. "
                f"Result 1: {result_1}, Result 2: {result_2}"
            )

            print("✅ Determinism: classify_intent ignores message content")
            print(f"   Both different messages → same result: {result_1}")
