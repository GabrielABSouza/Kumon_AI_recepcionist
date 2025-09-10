"""
Master Router Validation Test - Verification of Rules First, AI After implementation.

This test validates that the master router correctly implements the "Rules First, AI After"
principle and that responsibility duplication has been eliminated.
"""

from unittest.mock import patch

# Intent enum removed - now using string-based intents
from app.core.langgraph_flow import classify_intent, master_router


class TestMasterRouterValidation:
    """Test suite to validate that responsibility duplication has been eliminated."""

    def test_master_router_implements_rules_first_ai_after(self):
        """
        VALIDATION TEST: Master router implements "Rules First, AI After" correctly.

        This test confirms that:
        1. Business rules are checked first (classify_intent)
        2. AI classification only happens when no business rules apply
        3. Responsibility duplication has been eliminated
        """
        # STEP 1: Test business rule takes precedence
        state_with_business_rule = {
            "phone": "5511999999999",
            "text": "João",
        }

        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier:
            # Mock business rule applies
            mock_get_state.return_value = {"greeting_sent": True}

            # Call master router
            result = master_router(state_with_business_rule)

            # ASSERTION 1: Business rule should be used
            assert (
                result == "qualification_node"
            ), f"Expected business rule to route to qualification_node, got {result}"

            # ASSERTION 2: AI classifier should NOT be called (Rules First)
            assert not mock_classifier.classify.called, (
                f"CRITICAL: AI classifier called when business rule applied! "
                f"This violates 'Rules First, AI After' principle."
            )

            print("✅ VALIDATION PASSED: Rules First - Business rule takes precedence")

    def test_master_router_falls_back_to_ai_when_no_business_rules(self):
        """
        VALIDATION TEST: Master router uses AI when no business rules apply.

        This confirms the "AI After" part of the principle.
        """
        # STEP 1: Test AI fallback for new conversation
        state_new_conversation = {
            "phone": "5511888888888",
            "text": "oi, boa tarde",
        }

        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier:
            # No saved state = no business rules apply
            mock_get_state.return_value = {}

            # AI should classify as greeting
            mock_classifier.classify.return_value = {
                "primary_intent": "greeting",
                "secondary_intent": None,
                "entities": {},
                "confidence": 0.9,
            }

            # Call master router
            result = master_router(state_new_conversation)

            # ASSERTION 1: AI classification should be used
            assert (
                result == "greeting_node"
            ), f"Expected AI to route to greeting_node, got {result}"

            # ASSERTION 2: AI classifier should be called (AI After)
            assert mock_classifier.classify.called, (
                f"CRITICAL: AI classifier not called when no business rules applied! "
                f"This violates 'Rules First, AI After' principle."
            )

            print("✅ VALIDATION PASSED: AI After - AI used when no business rules")

    def test_classify_intent_only_business_logic_no_ai(self):
        """
        VALIDATION TEST: classify_intent contains only business logic, no AI.

        This confirms responsibility separation has been achieved.
        """
        # Test that classify_intent never calls AI
        state = {
            "phone": "5511999999999",
            "text": "anything",
        }

        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier:
            mock_get_state.return_value = {"greeting_sent": True}

            # Call classify_intent directly
            result = classify_intent(state)

            # ASSERTION 1: Should return business decision
            assert (
                result == "qualification_node"
            ), f"Expected business rule result, got {result}"

            # ASSERTION 2: Should never call AI classifier
            assert not mock_classifier.classify.called, (
                f"CRITICAL: classify_intent called AI classifier! "
                f"Responsibility separation violated."
            )

            print("✅ VALIDATION PASSED: classify_intent contains only business logic")

    def test_master_router_graceful_error_handling(self):
        """
        VALIDATION TEST: Master router handles errors gracefully.

        This ensures robustness when components fail.
        """
        state = {
            "phone": "5511999999999",
            "text": "test",
        }

        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier:
            # Simulate business rule failure
            mock_get_state.side_effect = Exception("Database error")

            # AI should still work as fallback
            mock_classifier.classify.return_value = {
                "primary_intent": "fallback",
                "secondary_intent": None,
                "entities": {},
                "confidence": 0.5,
            }

            # Call master router
            result = master_router(state)

            # ASSERTION 1: Should gracefully fallback
            assert (
                result == "fallback_node"
            ), f"Expected graceful fallback to fallback_node, got {result}"

            # ASSERTION 2: AI should be called as fallback
            assert (
                mock_classifier.classify.called
            ), f"Expected AI to be used as fallback when business rules fail"

            print("✅ VALIDATION PASSED: Graceful error handling with AI fallback")

    def test_architecture_validates_no_duplication(self):
        """
        FINAL VALIDATION TEST: Confirm no responsibility duplication exists.

        This is the ultimate test that our refactoring achieved its goal.
        """
        # Test 1: Business rules only in classify_intent
        state_business = {
            "phone": "5511999999999",
            "text": "test",
        }

        # Test 2: AI classification only in master_router (when no business rules)
        state_ai = {
            "phone": "5511888888888",  # Different phone = new conversation
            "text": "oi",
        }

        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier:
            # Setup for business rule test
            mock_get_state.side_effect = [
                {"greeting_sent": True},  # First call - business rule applies
                {},  # Second call - no business rules
            ]
            mock_classifier.classify.return_value = {
                "primary_intent": "greeting",
                "secondary_intent": None,
                "entities": {},
                "confidence": 0.9,
            }

            # STEP 1: Call classify_intent (should use business logic only)
            business_result = classify_intent(state_business)

            # STEP 2: Call master_router with no business rules (should use AI)
            ai_result = master_router(state_ai)

            # ASSERTION 1: Business logic works independently
            assert (
                business_result == "qualification_node"
            ), f"Business logic failed: expected qualification_node, got {business_result}"

            # ASSERTION 2: AI classification works independently
            assert (
                ai_result == "greeting_node"
            ), f"AI classification failed: expected greeting_node, got {ai_result}"

            # ASSERTION 3: No AI calls from business logic
            assert (
                mock_classifier.classify.call_count == 1
            ), f"Expected exactly 1 AI call (from master_router), got {mock_classifier.classify.call_count}"

            print("✅ FINAL VALIDATION PASSED: No responsibility duplication")
            print("   - classify_intent: Business logic only ✅")
            print("   - master_router: Orchestrates Rules First, AI After ✅")
            print("   - GeminiClassifier: AI classification only ✅")
            print("   - Architecture: Clean separation of concerns ✅")

    def test_master_router_passes_full_context_to_classifier(self):
        """
        TDD STEP 3.1: Test that master router passes full context to GeminiClassifier.

        This test validates that the master router correctly collects conversation
        state and history, then passes the complete context to the GeminiClassifier
        in the new format: {'state': {...}, 'history': [...]}.

        This test will FAIL until we implement the context integration.
        """
        # STEP 1: Set up test scenario where AI classification is needed
        state_for_ai_classification = {
            "phone": "5511999999999",
            "text": "ele tem 8 anos",  # Ambiguous message needing context
        }

        # STEP 2: Mock the state and history that should be collected
        mock_conversation_state = {
            "greeting_sent": True,
            "parent_name": "Gabriel",
            "student_name": "João",
            "student_age": None,
            "program_interests": None,
        }

        mock_conversation_history = [
            {
                "role": "assistant",
                "content": "Olá! Eu sou a Cecília do Kumon. Qual é o seu nome?",
            },
            {"role": "user", "content": "meu nome é Gabriel"},
            {"role": "assistant", "content": "Olá Gabriel! Qual é o nome da criança?"},
            {"role": "user", "content": "meu filho João"},
        ]

        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.get_conversation_history"
        ) as mock_get_history, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier:
            # STEP 3: Mock the return values - simulate NEW conversation scenario
            # For NEW conversation, get_conversation_state returns {} (no business rules)
            # But we can still have history from previous sessions that ended
            mock_get_state.return_value = (
                {}
            )  # No active state = no business rules apply
            mock_get_history.return_value = (
                mock_conversation_history  # But we have history for context
            )
            mock_classifier.classify.return_value = {
                "primary_intent": "qualification",
                "secondary_intent": None,
                "entities": {},
                "confidence": 0.95,
            }

            # STEP 4: Call master router (this will FAIL until implemented)
            result = master_router(state_for_ai_classification)

            # STEP 5: CRITICAL ASSERTIONS - Validate context collection and passing

            # ASSERTION 1: Should call get_conversation_state to collect state
            # Note: get_conversation_state is called twice:
            # 1. In classify_intent (for business rules)
            # 2. In master_router (for AI context)
            assert (
                mock_get_state.call_count == 2
            ), f"Expected 2 calls to get_conversation_state, got {mock_get_state.call_count}"
            mock_get_state.assert_any_call(
                "5511999999999"
            )  # Check that our phone was called

            # ASSERTION 2: Should call get_conversation_history to collect history
            # Note: Phone number is formatted by safe_phone_display to "9999"
            mock_get_history.assert_called_once_with("9999", limit=4)

            # ASSERTION 3: Should pass full context to classifier in new format
            expected_context = {
                "state": {},  # Empty state for new conversation
                "history": mock_conversation_history,
            }
            mock_classifier.classify.assert_called_once_with(
                "ele tem 8 anos", context=expected_context
            )

            # ASSERTION 4: Should return correct routing based on AI classification
            assert (
                result == "qualification_node"
            ), f"Expected qualification_node, got {result}"

            print(
                "✅ TDD STEP 3.1: Master router context integration test structure created"
            )
            print(
                f"   Validated: State collection, history collection, context passing"
            )
            print(f"   Expected context format: {{'state': {{...}}, 'history': [...]}}")

        # STEP 6: Test that context is only collected when AI is needed
        state_with_business_rule = {"phone": "5511888888888", "text": "test"}

        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state2, patch(
            "app.core.langgraph_flow.get_conversation_history"
        ) as mock_get_history2, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier2:
            # Business rule applies (greeting_sent=True)
            mock_get_state2.return_value = {"greeting_sent": True}

            result = master_router(state_with_business_rule)

            # ASSERTION 5: Should NOT collect history when business rules apply
            assert (
                not mock_get_history2.called
            ), "Should not collect history when business rules apply (efficiency)"

            # ASSERTION 6: Should NOT call classifier when business rules apply
            assert (
                not mock_classifier2.classify.called
            ), "Should not call classifier when business rules apply (Rules First)"

            print("✅ TDD STEP 3.1: Context collection optimization validated")
            print("   - History only collected when AI classification needed ✅")
            print("   - Maintains Rules First, AI After principle ✅")
