"""
Test Gemini Full Context - TDD implementation for contextual prompt building.

This test validates that GeminiClassifier builds rich contextual prompts
that include conversation history and current state for better routing decisions.

Following TDD Step 2.1: Create test_classifier_builds_prompt_with_full_context
"""

from unittest.mock import Mock, patch

import pytest

from app.core.gemini_classifier import GeminiClassifier


class TestGeminiFullContext:
    """Test suite for full contextual prompt building."""

    def test_classifier_builds_prompt_with_full_context(self):
        """
        TDD STEP 2.1: Test that classifier builds prompt with full context.

        Scenario: Create rich context with state and history.
        Assertion: Verify prompt contains HISTÓRIA, ESTADO and MENSAGEM sections.

        This test will FAIL until we refactor the GeminiClassifier.
        """
        # STEP 1: Set up rich context with state and history
        full_context = {
            "state": {
                "greeting_sent": True,
                "parent_name": "Gabriel",
                "student_name": None,
                "student_age": None,
                "program_interests": None,
            },
            "history": [
                {
                    "role": "assistant",
                    "content": "Olá! Eu sou a Cecília do Kumon. Qual é o seu nome?",
                },
                {"role": "user", "content": "meu nome é Gabriel"},
                {
                    "role": "assistant",
                    "content": "Olá Gabriel! Qual é o nome da criança?",
                },
                {"role": "user", "content": "meu filho João"},
            ],
        }

        user_message = "ele tem 8 anos"

        # STEP 2: Create classifier instance
        classifier = GeminiClassifier()

        # STEP 3: Call internal prompt building method (this will FAIL until implemented)
        try:
            prompt = classifier._build_contextual_prompt(user_message, full_context)

            # STEP 4: CRITICAL ASSERTIONS - Validate prompt structure

            # ASSERTION 1: Prompt should contain conversation history section
            assert (
                "HISTÓRICO DA CONVERSA" in prompt or "CONVERSATION HISTORY" in prompt
            ), f"Prompt should include conversation history section. Prompt: {prompt[:500]}..."

            # ASSERTION 2: Prompt should contain current state section
            assert (
                "ESTADO ATUAL" in prompt or "CURRENT STATE" in prompt
            ), f"Prompt should include current state section. Prompt: {prompt[:500]}..."

            # ASSERTION 3: Prompt should contain user message section
            assert (
                "MENSAGEM ATUAL" in prompt or "CURRENT MESSAGE" in prompt
            ), f"Prompt should include current message section. Prompt: {prompt[:500]}..."

            # ASSERTION 4: Prompt should include the actual user message
            assert (
                user_message in prompt
            ), f"Prompt should include the user message '{user_message}'. Prompt: {prompt[:500]}..."

            # ASSERTION 5: Prompt should include conversation history content
            assert (
                "meu nome é Gabriel" in prompt
            ), f"Prompt should include history content. Prompt: {prompt[:500]}..."

            # ASSERTION 6: Prompt should include state information
            assert (
                "Gabriel" in prompt
            ), f"Prompt should include state information (parent_name). Prompt: {prompt[:500]}..."

            # ASSERTION 7: Prompt should indicate greeting was sent
            assert (
                "greeting_sent" in prompt.lower() or "saudação" in prompt.lower()
            ), f"Prompt should indicate greeting was sent. Prompt: {prompt[:500]}..."

            print("✅ TDD STEP 2.1: Contextual prompt building test structure created")
            print("   Validated: HISTÓRICO, ESTADO, MENSAGEM sections present")
            print(f"   Prompt length: {len(prompt)} characters")

        except AttributeError as e:
            # Expected failure - method doesn't exist yet
            pytest.fail(
                f"EXPECTED FAILURE: _build_contextual_prompt method not implemented yet: {e}"
            )

    def test_classifier_formats_conversation_history_correctly(self):
        """
        Test that conversation history is formatted correctly in the prompt.
        """
        context = {
            "state": {"greeting_sent": True},
            "history": [
                {"role": "assistant", "content": "Olá! Como posso ajudar?"},
                {"role": "user", "content": "Quero informações sobre Kumon"},
                {"role": "assistant", "content": "Claro! Qual é seu nome?"},
            ],
        }

        classifier = GeminiClassifier()

        try:
            prompt = classifier._build_contextual_prompt("João", context)

            # Should format history with role labels
            assert (
                "Assistente:" in prompt or "Assistant:" in prompt
            ), "History should be formatted with role labels"

            assert (
                "Usuário:" in prompt or "User:" in prompt
            ), "History should include user role labels"

            # Should include actual conversation content
            assert (
                "Quero informações sobre Kumon" in prompt
            ), "Should include user messages from history"

            print("✅ Conversation history formatting validated")

        except AttributeError:
            pytest.fail(
                "EXPECTED FAILURE: _build_contextual_prompt method not implemented yet"
            )

    def test_classifier_includes_state_variables_in_prompt(self):
        """
        Test that current state variables are included in the prompt.
        """
        context = {
            "state": {
                "greeting_sent": True,
                "parent_name": "Maria",
                "student_name": "Pedro",
                "student_age": None,  # Missing
                "program_interests": ["mathematics"],
            },
            "history": [],
        }

        classifier = GeminiClassifier()

        try:
            prompt = classifier._build_contextual_prompt("ele tem 10 anos", context)

            # Should include collected state variables
            assert "Maria" in prompt, "Should include parent_name from state"
            assert "Pedro" in prompt, "Should include student_name from state"
            assert (
                "mathematics" in prompt
            ), "Should include program_interests from state"

            # Should indicate what's missing
            assert (
                "student_age" in prompt.lower() or "idade" in prompt.lower()
            ), "Should indicate missing student_age"

            print("✅ State variables correctly included in prompt")

        except AttributeError:
            pytest.fail(
                "EXPECTED FAILURE: _build_contextual_prompt method not implemented yet"
            )

    def test_classifier_handles_empty_context_gracefully(self):
        """
        Test that classifier handles empty or minimal context gracefully.
        """
        # Test with empty context
        empty_context = {"state": {}, "history": []}

        classifier = GeminiClassifier()

        try:
            prompt = classifier._build_contextual_prompt("olá", empty_context)

            # Should still build a valid prompt
            assert len(prompt) > 0, "Should build prompt even with empty context"
            assert (
                "olá" in prompt
            ), "Should include user message even with empty context"

            print("✅ Empty context handled gracefully")

        except AttributeError:
            pytest.fail(
                "EXPECTED FAILURE: _build_contextual_prompt method not implemented yet"
            )

    def test_classifier_classify_method_accepts_context_parameter(self):
        """
        Test that the classify method accepts the new context parameter.

        This validates the enhanced method signature.
        """
        context = {
            "state": {"greeting_sent": True},
            "history": [{"role": "assistant", "content": "Qual seu nome?"}],
        }

        # Mock environment to enable Gemini
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}), patch(
            "google.generativeai.GenerativeModel"
        ) as mock_model_class, patch("google.generativeai.configure"):
            mock_model = Mock()
            mock_model_class.return_value = mock_model

            # Mock Gemini response - structured JSON format
            mock_response = Mock()
            mock_response.text = """
            {
                "primary_intent": "qualification",
                "secondary_intent": null,
                "entities": {"beneficiary_type": "child", "student_name": "Gabriel"},
                "confidence": 0.9
            }
            """
            mock_model.generate_content.return_value = mock_response

            classifier = GeminiClassifier()

            try:
                # Should accept context parameter without error
                nlu_result = classifier.classify("Gabriel", context=context)

                # Should return valid structured results
                assert isinstance(
                    nlu_result, dict
                ), f"Expected dict, got {type(nlu_result)}"

                primary_intent = nlu_result.get("primary_intent")
                confidence = nlu_result.get("confidence", 0.0)

                assert isinstance(
                    confidence, float
                ), f"Expected float confidence, got {type(confidence)}"
                assert (
                    primary_intent == "qualification"
                ), f"Expected qualification, got {primary_intent}"
                assert confidence == 0.9, f"Expected 0.9 confidence, got {confidence}"

                print("✅ Context parameter accepted by classify method")

            except TypeError as e:
                pytest.fail(
                    f"EXPECTED FAILURE: classify method doesn't accept context parameter yet: {e}"
                )

    def test_classifier_falls_back_without_context(self):
        """
        Test that classifier works normally when no context is provided.

        This ensures backwards compatibility.
        """
        # Mock environment to enable Gemini
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}), patch(
            "google.generativeai.GenerativeModel"
        ) as mock_model_class, patch("google.generativeai.configure"):
            mock_model = Mock()
            mock_model_class.return_value = mock_model

            # Mock Gemini response - structured JSON format
            mock_response = Mock()
            mock_response.text = """
            {
                "primary_intent": "greeting",
                "secondary_intent": null,
                "entities": {},
                "confidence": 0.85
            }
            """
            mock_model.generate_content.return_value = mock_response

            classifier = GeminiClassifier()

            # Should work without context parameter (backwards compatibility)
            nlu_result = classifier.classify("oi, boa tarde")

            primary_intent = nlu_result.get("primary_intent")
            confidence = nlu_result.get("confidence", 0.0)

            assert (
                primary_intent == "greeting"
            ), f"Expected greeting, got {primary_intent}"
            assert confidence == 0.85, f"Expected 0.85 confidence, got {confidence}"

            print("✅ Backwards compatibility maintained (no context)")
