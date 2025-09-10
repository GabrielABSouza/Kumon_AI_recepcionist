"""
Integration Test - Rules First, AI After Orchestration

This test validates that the refactored architecture correctly implements
the "Rules First, AI After" principle by testing the integration between
classify_intent (business logic) and GeminiClassifier (AI classification).
"""

from unittest.mock import patch


from app.core.gemini_classifier import Intent
from app.core.langgraph_flow import build_graph


class TestOrchestrationIntegration:
    """Test suite for the integrated routing orchestration."""

    def test_business_rule_takes_precedence_over_ai_classification(self):
        """
        CRITICAL INTEGRATION TEST: Business rules should override AI classification.

        When classify_intent returns a business rule decision, that should be used
        even if Gemini would classify differently.
        """
        # STEP 1: Set up state where business rule applies (greeting_sent=True)
        state_with_business_rule = {
            "phone": "5511999999999",
            "text": "João",  # Could be classified as many things by AI
            "message_id": "orchestration_test_001",
            "instance": "test_instance",
        }

        # STEP 2: Mock saved state that triggers business rule
        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier, patch(
            "app.core.langgraph_flow.send_text"
        ) as mock_send:
            # Business rule should apply: greeting_sent=True → qualification_node
            mock_get_state.return_value = {
                "greeting_sent": True,
                "parent_name": None,
                "student_name": None,
                "student_age": None,
                "program_interests": None,
            }

            # AI would classify this as something different (e.g., fallback)
            mock_classifier.classify.return_value = (Intent.FALLBACK, 0.6)
            mock_send.return_value = {"sent": "true", "status_code": 200}

            # STEP 3: Execute graph (should use business rule, not AI)
            graph = build_graph()
            graph.invoke(state_with_business_rule)

            # STEP 4: CRITICAL ASSERTIONS

            # ASSERTION 1: Classifier should NOT be called (business rule takes precedence)
            assert not mock_classifier.classify.called, (
                f"CRITICAL FAILURE: AI classifier was called when business rule applied! "
                f"This violates 'Rules First, AI After' principle."
            )

            # ASSERTION 2: Should route to qualification_node (business rule)
            assert (
                mock_send.call_count == 1
            ), f"Expected qualification_node to send 1 message"

            print("✅ SUCCESS: Business rule took precedence over AI classification")
            print(f"   Business rule applied: greeting_sent=True → qualification_node")
            print(
                f"   AI classifier bypassed: {mock_classifier.classify.call_count} calls"
            )

    def test_ai_classification_when_no_business_rules_apply(self):
        """
        Test that AI classification is used when no business rules apply.

        This validates the "AI After" part of "Rules First, AI After".
        """
        # STEP 1: Set up state with no business rules (new conversation)
        state_new_conversation = {
            "phone": "5511888888888",  # Different number = new conversation
            "text": "oi, boa tarde!",
            "message_id": "orchestration_test_002",
            "instance": "test_instance",
        }

        # STEP 2: Mock no saved state (no business rules apply)
        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier, patch(
            "app.core.langgraph_flow.send_text"
        ) as mock_send:
            # No saved state = no business rules apply
            mock_get_state.return_value = {}

            # AI should classify this as greeting
            mock_classifier.classify.return_value = (Intent.GREETING, 0.9)
            mock_send.return_value = {"sent": "true", "status_code": 200}

            # STEP 3: Execute graph (should use AI classification)
            graph = build_graph()
            graph.invoke(state_new_conversation)

            # STEP 4: CRITICAL ASSERTIONS

            # ASSERTION 1: Classifier should be called (no business rules apply)
            assert mock_classifier.classify.called, (
                f"CRITICAL FAILURE: AI classifier was not called when no business rules applied! "
                f"This violates 'Rules First, AI After' principle."
            )

            # ASSERTION 2: Should use AI classification result
            call_args = mock_classifier.classify.call_args[0]
            classified_text = call_args[0]
            assert (
                classified_text == "oi, boa tarde!"
            ), f"AI classifier should receive the user text for classification"

            # ASSERTION 3: Should send greeting message
            assert (
                mock_send.call_count == 1
            ), f"Expected greeting_node to send 1 message"

            print("✅ SUCCESS: AI classification used when no business rules applied")
            print(f"   Business rules checked first: classify_intent returned None")
            print(
                f"   AI classification used: {mock_classifier.classify.call_count} calls"
            )

    def test_orchestration_flow_with_qualification_continuation(self):
        """
        Test the complete orchestration flow for qualification continuation.

        This validates that partial qualification data triggers business rule
        without involving AI classification.
        """
        # STEP 1: Set up state with partial qualification data
        state_partial_qualification = {
            "phone": "5511999999999",
            "text": "ele tem 8 anos",
            "message_id": "orchestration_test_003",
            "instance": "test_instance",
        }

        # STEP 2: Mock saved state with partial qualification
        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier, patch(
            "app.core.langgraph_flow.send_text"
        ) as mock_send:
            # Partial qualification data = business rule applies
            mock_get_state.return_value = {
                "parent_name": "Gabriel",  # ✅ Collected
                "student_name": "João",  # ✅ Collected
                "student_age": None,  # ❌ Missing (triggers continuation)
                "program_interests": None,  # ❌ Missing
            }

            # AI classification should not be called
            mock_send.return_value = {"sent": "true", "status_code": 200}

            # STEP 3: Execute graph
            graph = build_graph()
            result = graph.invoke(state_partial_qualification)

            # STEP 4: CRITICAL ASSERTIONS

            # ASSERTION 1: No AI classification (business rule applies)
            assert not mock_classifier.classify.called, (
                f"CRITICAL FAILURE: AI classifier called for qualification continuation! "
                f"Business rule should handle this case."
            )

            # ASSERTION 2: Should continue qualification
            assert (
                mock_send.call_count == 1
            ), f"Expected qualification_node to continue qualification"

            # ASSERTION 3: Should extract age from user response
            assert (
                result.get("student_age") == 8
            ), f"Expected to extract student_age=8 from 'ele tem 8 anos'"

            print("✅ SUCCESS: Qualification continuation via business rule")
            print(f"   Business rule applied: partial data → continue qualification")
            print(f"   AI bypassed: {mock_classifier.classify.call_count} calls")

    def test_orchestration_flow_with_qualification_complete(self):
        """
        Test orchestration when qualification is complete.

        This validates advancement to scheduling via business rule.
        """
        # STEP 1: Set up state with scheduling request
        state_complete_qualification = {
            "phone": "5511999999999",
            "text": "quero agendar uma visita",
            "message_id": "orchestration_test_004",
            "instance": "test_instance",
        }

        # STEP 2: Mock saved state with complete qualification
        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier, patch(
            "app.core.langgraph_flow.send_text"
        ) as mock_send:
            # Complete qualification = advance to scheduling
            mock_get_state.return_value = {
                "parent_name": "Gabriel",  # ✅ Complete
                "student_name": "João",  # ✅ Complete
                "student_age": 8,  # ✅ Complete
                "program_interests": ["mathematics"],  # ✅ Complete
            }

            mock_send.return_value = {"sent": "true", "status_code": 200}

            # STEP 3: Execute graph
            graph = build_graph()
            graph.invoke(state_complete_qualification)

            # STEP 4: CRITICAL ASSERTIONS

            # ASSERTION 1: No AI classification needed
            assert not mock_classifier.classify.called, (
                f"CRITICAL FAILURE: AI classifier called when qualification complete! "
                f"Business rule should advance to scheduling."
            )

            # ASSERTION 2: Should advance to scheduling
            assert (
                mock_send.call_count == 1
            ), f"Expected scheduling_node to handle scheduling"

            print("✅ SUCCESS: Advancement to scheduling via business rule")
            print(f"   Business rule applied: complete qualification → scheduling")
            print(f"   AI bypassed: {mock_classifier.classify.call_count} calls")

    def test_fallback_to_ai_when_business_rules_fail(self):
        """
        Test that AI classification is used when business rule evaluation fails.

        This ensures robustness when business logic encounters errors.
        """
        # STEP 1: Set up state that could trigger business rule
        state = {
            "phone": "5511999999999",
            "text": "olá",
            "message_id": "orchestration_test_005",
            "instance": "test_instance",
        }

        # STEP 2: Mock business rule failure
        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier, patch(
            "app.core.langgraph_flow.send_text"
        ) as mock_send:
            # Business rule fails (exception in get_conversation_state)
            mock_get_state.side_effect = Exception("Database connection failed")

            # AI should classify as fallback
            mock_classifier.classify.return_value = (Intent.GREETING, 0.85)
            mock_send.return_value = {"sent": "true", "status_code": 200}

            # STEP 3: Execute graph (should gracefully fallback to AI)
            graph = build_graph()
            graph.invoke(state)

            # STEP 4: CRITICAL ASSERTIONS

            # ASSERTION 1: Should fallback to AI classification
            assert mock_classifier.classify.called, (
                f"CRITICAL FAILURE: AI classifier not called when business rules failed! "
                f"Should fallback to AI when business logic fails."
            )

            # ASSERTION 2: Should still send a response
            assert (
                mock_send.call_count == 1
            ), f"Expected fallback to still work and send response"

            print("✅ SUCCESS: Graceful fallback to AI when business rules fail")
            print(f"   Business rule failed gracefully")
            print(
                f"   AI classification used as fallback: {mock_classifier.classify.call_count} calls"
            )

    def test_orchestration_performance_business_rules_faster(self):
        """
        Test that business rules are faster than AI classification.

        This validates the performance benefit of "Rules First" approach.
        """
        import time

        # STEP 1: Set up state with business rule
        state = {
            "phone": "5511999999999",
            "text": "meu nome é Gabriel",
            "message_id": "performance_test_001",
            "instance": "test_instance",
        }

        # STEP 2: Mock fast business rule and slow AI
        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.classifier"
        ) as mock_classifier, patch(
            "app.core.langgraph_flow.send_text"
        ) as mock_send:
            # Fast business rule response
            mock_get_state.return_value = {"greeting_sent": True}

            # Slow AI response (should not be called)
            def slow_ai_classify(*args, **kwargs):
                time.sleep(0.1)  # Simulate AI latency
                return (Intent.QUALIFICATION, 0.9)

            mock_classifier.classify.side_effect = slow_ai_classify
            mock_send.return_value = {"sent": "true", "status_code": 200}

            # STEP 3: Measure execution time
            start_time = time.time()
            graph = build_graph()
            graph.invoke(state)
            execution_time = time.time() - start_time

            # STEP 4: PERFORMANCE ASSERTIONS

            # ASSERTION 1: Should be fast (no AI call)
            assert (
                execution_time < 0.05
            ), f"Expected fast execution via business rules, got {execution_time:.3f}s"

            # ASSERTION 2: AI should not be called
            assert (
                not mock_classifier.classify.called
            ), f"AI classifier should not be called when business rule applies"

            print("✅ SUCCESS: Business rules provide faster routing")
            print(f"   Execution time: {execution_time:.3f}s (fast business rule)")
            print(f"   AI calls avoided: {mock_classifier.classify.call_count}")
