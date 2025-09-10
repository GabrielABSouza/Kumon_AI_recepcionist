"""
Tests for Gemini LLM classifier with contextual prompts.

These tests validate that the Gemini classifier receives rich contextual prompts
containing conversation history and current qualification state, enabling intelligent
intent classification rather than operating "blind" on individual messages.
"""

from unittest.mock import MagicMock, patch


class TestGeminiClassifier:
    """Test suite for contextual Gemini intent classification."""

    # Legacy integration tests removed - replaced by direct structured NLU tests

    def test_classifier_extracts_structured_data_from_multi_intent_message(self):
        """
        🚨 RED PHASE TDD TEST: Define new structured NLU behavior.

        This test defines the expected behavior for the new structured GeminiClassifier.
        Instead of returning just Intent + confidence, it should return a structured
        dictionary with primary/secondary intents and extracted entities.

        Scenario: User provides multi-intent message during qualification process.
        Message: "É para o meu filho João. A propósito, quais são os horários?"
        Expected: Extract beneficiary_type, student_name, AND detect secondary intent.
        """

        # ARRANGE: Setup conversation state in progress
        conversation_state = {
            "parent_name": "Maria Silva",  # Already collected
            "qualification_attempts": 1,  # Qualification in progress
            "greeting_sent": True,
        }

        # Conversation history showing last question was about beneficiary
        conversation_history = [
            {
                "role": "assistant",
                "content": "Perfeito, Maria! O Kumon é para você mesmo ou para outra pessoa?",
            },
            {
                "role": "user",
                "content": "É para o meu filho João. A propósito, quais são os horários?",
            },
        ]

        # Complete context for classification
        classification_context = {
            "state": conversation_state,
            "history": conversation_history,
        }

        # Current multi-intent user message
        user_message = "É para o meu filho João. A propósito, quais são os horários?"

        # Expected structured output from new NLU engine
        expected_output = {
            "primary_intent": "qualification",
            "secondary_intent": "information",
            "entities": {"beneficiary_type": "child", "student_name": "João"},
            "confidence": 0.85,  # Should be > 0.8 for high confidence
        }

        # ACT & ASSERT: Call classifier and validate structured response
        from app.core.gemini_classifier import GeminiClassifier

        # Mock Gemini to return structured JSON response
        with patch("google.generativeai.GenerativeModel") as mock_gemini_model:
            mock_model_instance = MagicMock()
            mock_response = MagicMock()

            # Mock Gemini to return structured JSON (what we want it to learn)
            mock_response.text = """
            {
                "primary_intent": "qualification",
                "secondary_intent": "information",
                "entities": {
                    "beneficiary_type": "child",
                    "student_name": "João"
                },
                "confidence": 0.85
            }
            """

            mock_model_instance.generate_content.return_value = mock_response
            mock_gemini_model.return_value = mock_model_instance

            # Create classifier instance
            classifier = GeminiClassifier()

            # 🚨 THIS WILL FAIL: Current classify() returns (Intent, float)
            # We want it to return structured dict
            result = classifier.classify(user_message, classification_context)

            # CRITICAL ASSERTIONS: Validate new structured behavior

            # Assert result is a dictionary (not tuple)
            assert isinstance(
                result, dict
            ), f"Expected dict, got {type(result)}: {result}"

            # Assert primary intent is correct
            assert (
                result["primary_intent"] == expected_output["primary_intent"]
            ), f"Expected primary_intent='{expected_output['primary_intent']}', got '{result.get('primary_intent')}'"

            # Assert secondary intent is detected
            assert (
                result["secondary_intent"] == expected_output["secondary_intent"]
            ), f"Expected secondary_intent='{expected_output['secondary_intent']}', got '{result.get('secondary_intent')}'"

            # Assert entities are extracted correctly
            assert "entities" in result, "Result should contain 'entities' key"
            assert (
                result["entities"]["student_name"] == "João"
            ), f"Expected student_name='João', got '{result.get('entities', {}).get('student_name')}'"
            assert (
                result["entities"]["beneficiary_type"] == "child"
            ), f"Expected beneficiary_type='child', got '{result.get('entities', {}).get('beneficiary_type')}'"

            # Assert confidence is reasonable
            assert isinstance(result["confidence"], float), "Confidence should be float"
            assert (
                result["confidence"] > 0.8
            ), f"Expected confidence > 0.8, got {result['confidence']}"

            print("✅ SUCCESS: GeminiClassifier returns structured NLU data")
            print(f"✅ Primary Intent: {result['primary_intent']}")
            print(f"✅ Secondary Intent: {result['secondary_intent']}")
            print(f"✅ Extracted Entities: {result['entities']}")
            print(f"✅ Confidence: {result['confidence']}")

        # This test should FAIL initially, driving us to implement the new behavior
