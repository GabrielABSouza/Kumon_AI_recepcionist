"""
Test Gemini Contextual Routing - Tests for post-greeting classification.

This test validates that Gemini correctly routes user responses after greeting
to the qualification_node based on the greeting_sent flag.
"""

from unittest.mock import Mock, patch


from app.core.gemini_classifier import GeminiClassifier, Intent


class TestGeminiContextualRouting:
    """Test suite for contextual routing after greeting."""

    def test_router_sends_to_qualification_after_greeting_is_sent(self):
        """
        Test that Gemini routes name responses to qualification when greeting_sent=True.

        This validates the core contextual rule:
        - If greeting_sent=True, the user message is a response to "what's your name?"
        - Therefore, intent should be QUALIFICATION with high confidence
        """
        # STEP 1: Set up post-greeting context
        context_after_greeting = {
            "greeting_sent": True,  # The key flag for our rule
            "conversation_history": [
                {
                    "role": "assistant",
                    "content": "Olá! Eu sou a Cecília do Kumon. Qual é o seu nome?",
                },
            ],
            "parent_name": None,  # Not collected yet
            "student_name": None,
            "student_age": None,
            "program_interests": None,
        }

        # STEP 2: Test various name responses
        name_responses = [
            "meu nome é Gabriel",
            "Gabriel",
            "sou o João da Silva",
            "me chamo Maria",
            "João",
            "eu sou Pedro",
        ]

        # STEP 3: Mock Gemini response to simulate correct classification
        with patch("google.generativeai.GenerativeModel") as mock_model_class:
            mock_model = Mock()
            mock_model_class.return_value = mock_model

            # Mock the generate_content response to return qualification
            mock_response = Mock()
            mock_response.text = "qualification|0.95"
            mock_model.generate_content.return_value = mock_response

            # STEP 4: Test each name response
            classifier = GeminiClassifier()

            for user_response in name_responses:
                print(f"\nTesting user response: '{user_response}'")

                # STEP 5: Classify with context
                intent, confidence = classifier.classify(
                    user_response, context_after_greeting
                )

                # STEP 6: CRITICAL ASSERTIONS

                # ASSERTION 1: Intent must be QUALIFICATION
                assert intent == Intent.QUALIFICATION, (
                    f"CRITICAL BUG: Expected QUALIFICATION for name response '{user_response}' "
                    f"with greeting_sent=True, but got {intent.value}"
                )

                # ASSERTION 2: Confidence should be high (≥0.9)
                assert confidence >= 0.9, (
                    f"CRITICAL BUG: Expected high confidence (≥0.9) for contextual routing "
                    f"with greeting_sent=True, but got {confidence}"
                )

                print(
                    f"✅ Correctly routed to {intent.value} with confidence {confidence}"
                )

    def test_contextual_prompt_includes_greeting_sent_flag(self):
        """
        Test that the contextual prompt correctly includes the greeting_sent flag.
        This ensures our rule can be applied by Gemini.
        """
        # STEP 1: Set up context with greeting_sent=True
        context = {
            "greeting_sent": True,
            "conversation_history": [],
            "parent_name": None,
            "student_name": None,
            "student_age": None,
            "program_interests": None,
        }

        # STEP 2: Create classifier and build prompt
        classifier = GeminiClassifier()

        # STEP 3: Use _build_contextual_prompt (internal method for testing)
        prompt = classifier._build_contextual_prompt("Gabriel", context)

        # STEP 4: CRITICAL ASSERTIONS

        # ASSERTION 1: Prompt should include the greeting_sent flag
        assert "Flag de Saudação: True" in prompt, (
            f"CRITICAL BUG: Prompt should include 'Flag de Saudação: True' "
            f"when greeting_sent=True. Prompt: {prompt}"
        )

        # ASSERTION 2: Prompt should include the priority rule
        assert "REGRA DE CONTINUAÇÃO DE SAUDAÇÃO" in prompt, (
            f"CRITICAL BUG: Prompt should include the priority greeting continuation rule. "
            f"Prompt: {prompt}"
        )

        # ASSERTION 3: Prompt should mention OBRIGATORIAMENTE
        assert "OBRIGATORIAMENTE" in prompt, (
            f"CRITICAL BUG: Prompt should emphasize mandatory qualification routing. "
            f"Prompt: {prompt}"
        )

        print("✅ Contextual prompt correctly includes greeting_sent flag and rules")
        print(f"Prompt excerpt: ...{prompt[200:400]}...")

    def test_classification_without_greeting_sent_flag(self):
        """
        Test that classification works normally when greeting_sent=False or missing.
        This ensures we don't break normal classification.
        """
        # STEP 1: Set up normal context (no greeting_sent or False)
        contexts = [
            {"greeting_sent": False},  # Explicitly False
            {},  # Missing flag (default behavior)
            {"greeting_sent": None},  # None value
        ]

        # STEP 2: Test normal greeting message
        greeting_message = "oi, boa tarde"

        with patch("google.generativeai.GenerativeModel") as mock_model_class:
            mock_model = Mock()
            mock_model_class.return_value = mock_model

            # Mock normal greeting classification
            mock_response = Mock()
            mock_response.text = "greeting|0.9"
            mock_model.generate_content.return_value = mock_response

            classifier = GeminiClassifier()

            for i, context in enumerate(contexts):
                print(f"\nTesting context {i+1}: {context}")

                # STEP 3: Classify without greeting_sent=True
                intent, confidence = classifier.classify(greeting_message, context)

                # STEP 4: ASSERTIONS - Should work normally
                assert intent == Intent.GREETING, (
                    f"Expected GREETING for normal greeting without greeting_sent=True, "
                    f"but got {intent.value}"
                )

                assert (
                    confidence >= 0.8
                ), f"Expected reasonable confidence for normal greeting, got {confidence}"

                print(
                    f"✅ Normal classification: {intent.value} with confidence {confidence}"
                )

    def test_fallback_classification_when_gemini_disabled(self):
        """
        Test that the system falls back to simple classification when Gemini is disabled.
        This ensures robustness when API is unavailable.
        """
        # STEP 1: Create classifier without GEMINI_API_KEY
        with patch.dict("os.environ", {}, clear=True):  # No API key
            classifier = GeminiClassifier()

            # STEP 2: Test that it's disabled
            assert (
                not classifier.enabled
            ), "Classifier should be disabled without API key"

            # STEP 3: Test fallback classification
            context = {"greeting_sent": True}
            intent, confidence = classifier.classify("Gabriel", context)

            # STEP 4: Should use simple classification as fallback
            # Simple classifier doesn't know about contextual rules,
            # so it will classify "Gabriel" as fallback
            assert (
                intent == Intent.FALLBACK
            ), f"Simple classifier should return FALLBACK for 'Gabriel', got {intent.value}"

            print("✅ Fallback classification works when Gemini is disabled")
