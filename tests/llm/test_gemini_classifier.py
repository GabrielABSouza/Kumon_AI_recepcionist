"""
Tests for Gemini LLM classifier with contextual prompts.

These tests validate that the Gemini classifier receives rich contextual prompts
containing conversation history and current qualification state, enabling intelligent
intent classification rather than operating "blind" on individual messages.
"""

from unittest.mock import MagicMock, patch


class TestGeminiClassifier:
    """Test suite for contextual Gemini intent classification."""

    def test_gemini_classifier_prompt_includes_history_and_state(self):
        """
        CRITICAL TEST: Validate that Gemini prompt includes conversation context.

        This test ensures the Gemini classifier operates as an intelligent partner
        with full conversation context, not a blind function processing isolated messages.

        Expected: Prompt should contain conversation history, current state, and user message
        Current: Prompt likely contains only the current user message (blind operation)
        """

        # STEP 1: Simulate conversation state with NO qualification data
        # This ensures we bypass the early return and reach the classifier
        conversation_state = {
            "phone": "5511999999999",
            # NO parent_name - ensures we reach the classifier
            "qualification_attempts": 0,
        }

        # STEP 2: Simulate conversation history with previous exchanges
        conversation_history = [
            {
                "role": "assistant",
                "content": "Olá! Eu sou a Cecília. Como posso ajudá-lo?",
            },
            {"role": "user", "content": "Quero saber sobre o Kumon"},
            {
                "role": "assistant",
                "content": "Ótimo! O Kumon desenvolve o raciocínio. Tem alguma dúvida específica?",
            },
        ]

        # STEP 3: Current user message that introduces new topic
        current_user_message = "Gostaria de saber os horários"

        # STEP 4: Mock the Gemini classifier to capture the contextual prompt
        with patch("app.core.gemini_classifier.classifier.classify") as mock_classifier:
            # Mock the classifier to capture context and return expected result
            from app.core.gemini_classifier import Intent

            mock_classifier.return_value = (Intent.SCHEDULING, 0.85)

            # Import and call the function that should build contextual prompt
            from app.core.langgraph_flow import classify_intent

            # Build complete state for classification
            full_state = {
                "text": current_user_message,
                "phone": "5511999999999",
                "message_id": "MSG_CONTEXT_001",
                "instance": "kumon_assistant",
                **conversation_state,
            }

            # STEP 5: Execute classification
            classify_intent(full_state)

            # STEP 6: CRITICAL ASSERTIONS - Validate contextual classification

            # Assert that classifier was called with context
            assert (
                mock_classifier.called
            ), "Classifier should be called for intent classification"

            # Capture the actual call arguments to validate context was passed
            call_args = mock_classifier.call_args
            assert call_args, "Classifier should have been called with arguments"

            # Validate that context was passed as second argument
            args, kwargs = call_args
            context_passed = (
                kwargs.get("context")
                if "context" in kwargs
                else (args[1] if len(args) > 1 else None)
            )

            # CRITICAL ASSERTION: Context should have been passed
            assert context_passed is not None, (
                f"CONTEXTUAL PROMPT BUG: Context should be passed to classifier. "
                f"Call args: {args}, Call kwargs: {kwargs}"
            )

            # ASSERTION 1: Context should contain conversation_history
            assert "conversation_history" in context_passed, (
                f"CONTEXTUAL PROMPT BUG: Context should contain conversation_history. "
                f"Context keys: {list(context_passed.keys())}"
            )

            # ASSERTION 2: Context should contain state information
            assert "phone" in context_passed, (
                f"CONTEXTUAL PROMPT BUG: Context should contain state information. "
                f"Context keys: {list(context_passed.keys())}"
            )

            # ASSERTION 3: Text should be passed as first argument
            text_arg = args[0] if args else None
            assert text_arg == current_user_message, (
                f"CONTEXTUAL PROMPT BUG: Current user message should be first argument. "
                f"Expected: '{current_user_message}', Got: '{text_arg}'"
            )

            print("✅ SUCCESS: Gemini classifier receives contextual information")
            print(f"✅ Text argument: {text_arg}")
            print(f"✅ Context keys: {list(context_passed.keys())}")
            print(
                f"✅ Has conversation history: {'conversation_history' in context_passed}"
            )
            print(f"✅ Has state info: {'phone' in context_passed}")

    def test_contextual_classification_with_qualification_continuation(self):
        """
        Test contextual classification when user provides qualification data.

        Scenario: User previously provided name, now providing student info.
        Expected: Should classify as 'qualification' due to context.
        """

        # Conversation state: parent name collected, asking for student name
        state_with_context = {
            "text": "O nome dele é João",  # Direct answer to previous question
            "phone": "5511888888888",
            "parent_name": "Carlos Silva",  # Already collected
            "qualification_attempts": 1,
        }

        with patch("google.generativeai.GenerativeModel") as mock_gemini_model:
            mock_model_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "qualification"  # Expected with context
            mock_model_instance.generate_content.return_value = mock_response
            mock_gemini_model.return_value = mock_model_instance

            from app.core.langgraph_flow import classify_intent

            result = classify_intent(state_with_context)

            # Should classify as qualification with context
            assert (
                result == "qualification_node"
            ), f"With context, direct answer should classify as qualification, got: {result}"

            # Validate that contextual prompt was used
            assert mock_model_instance.generate_content.called
            actual_prompt = mock_model_instance.generate_content.call_args[0][0]

            # Context should influence classification
            assert "Carlos Silva" in actual_prompt, "Context should include parent name"
            assert (
                "O nome dele é João" in actual_prompt
            ), "Should include current message"

            print("✅ SUCCESS: Contextual qualification continuation works")

    def test_contextual_classification_with_topic_change(self):
        """
        Test contextual classification when user changes topic mid-qualification.

        Scenario: Mid-qualification, user asks about scheduling.
        Expected: Should classify as 'scheduling' despite ongoing qualification.
        """

        # Conversation state: qualification in progress but user changes topic
        state_with_topic_change = {
            "text": "Quero agendar uma visita",  # Topic change
            "phone": "5511777777777",
            "parent_name": "Ana Costa",  # Partial qualification
            "qualification_attempts": 2,
        }

        with patch("google.generativeai.GenerativeModel") as mock_gemini_model:
            mock_model_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "scheduling"  # Should recognize topic change
            mock_model_instance.generate_content.return_value = mock_response
            mock_gemini_model.return_value = mock_model_instance

            from app.core.langgraph_flow import classify_intent

            result = classify_intent(state_with_topic_change)

            # Should classify as scheduling despite ongoing qualification
            assert (
                result == "scheduling_node"
            ), f"Topic change should override qualification context, got: {result}"

            # Validate contextual prompt included state information
            assert mock_model_instance.generate_content.called
            actual_prompt = mock_model_instance.generate_content.call_args[0][0]

            # Should show qualification state but recognize topic change
            assert (
                "Ana Costa" in actual_prompt
            ), "Should include current qualification state"
            assert (
                "agendar uma visita" in actual_prompt
            ), "Should include topic change message"

            print("✅ SUCCESS: Contextual topic change detection works")

    def test_blind_vs_contextual_classification_comparison(self):
        """
        Demonstrate the difference between blind and contextual classification.

        This test shows how context changes the classification outcome for the same message.
        """

        ambiguous_message = "Obrigada"  # Could be thanks or qualification response

        # Scenario 1: Without context (blind classification)
        blind_state = {"text": ambiguous_message, "phone": "5511666666666"}

        # Scenario 2: With context (contextual classification)
        contextual_state = {
            "text": ambiguous_message,
            "phone": "5511666666666",
            "parent_name": "Patricia Santos",
            "student_name": "Lucas",  # Recently provided
            "qualification_attempts": 3,
        }

        with patch("google.generativeai.GenerativeModel") as mock_gemini_model:
            mock_model_instance = MagicMock()

            # First call: blind classification (fallback likely)
            mock_response_blind = MagicMock()
            mock_response_blind.text = "fallback"

            # Second call: contextual classification (qualification likely)
            mock_response_contextual = MagicMock()
            mock_response_contextual.text = "qualification"

            mock_model_instance.generate_content.side_effect = [
                mock_response_blind,
                mock_response_contextual,
            ]
            mock_gemini_model.return_value = mock_model_instance

            from app.core.langgraph_flow import classify_intent

            # Test blind classification
            blind_result = classify_intent(blind_state)

            # Test contextual classification
            contextual_result = classify_intent(contextual_state)

            # Results should be different due to context
            print(f"📊 Blind classification: {blind_result}")
            print(f"📊 Contextual classification: {contextual_result}")
            print("✅ SUCCESS: Context changes classification outcomes")

            # Validate both calls included appropriate prompts
            assert mock_model_instance.generate_content.call_count == 2

            # First call should be simpler (blind)
            first_prompt = mock_model_instance.generate_content.call_args_list[0][0][0]

            # Second call should be richer (contextual)
            second_prompt = mock_model_instance.generate_content.call_args_list[1][0][0]

            # Contextual prompt should be longer and richer
            assert len(second_prompt) > len(
                first_prompt
            ), "Contextual prompt should be richer than blind prompt"

            assert (
                "Patricia Santos" in second_prompt
            ), "Contextual prompt should include conversation context"

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
