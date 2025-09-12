"""
🧪 TDD Test for Simplified Information Node - Blended Response Generation

This test validates that the information_node correctly generates blended responses
combining user questions with qualification continuation.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.nodes.information import information_node


class TestInformationNodeBlended:
    """Test suite for simplified information node blended response generation."""

    @pytest.mark.asyncio
    async def test_information_node_generates_blended_response_correctly(self):
        """
        🚨 TDD TEST: Validate new blended response behavior.

        Scenario: Qualification in progress, user asks informative question.
        Expected: Information node should call LLM with prompt containing both
        the user question and next qualification question.
        """

        # ARRANGE: Create state with qualification in progress
        test_state = {
            "phone": "+5511999888777",
            "text": "Qual é o valor da mensalidade?",
            "phone_number": "+5511999888777",
            "instance": "kumon_assistant",
            "collected_data": {
                "parent_name": "Maria Silva",  # Parent name collected
                # beneficiary_type missing - should be next question
            },
        }

        with patch(
            "app.core.nodes.information.send_text", new_callable=AsyncMock
        ) as mock_send_text, patch(
            "app.core.llm.openai_adapter.OpenAIClient"
        ) as mock_openai_class:
            # Mock OpenAI client
            mock_openai_instance = AsyncMock()
            mock_openai_class.return_value = mock_openai_instance
            mock_openai_instance.chat.return_value = (
                "A mensalidade do Kumon Vila A é R$ 375,00 por disciplina. "
                "Maria Silva, o Kumon é para você mesmo ou para outra pessoa?"
            )

            # Mock send_text success
            mock_send_text.return_value = None

            # ACT: Call information_node
            result_state = await information_node(test_state)

            # ASSERT: LLM should be called with blended prompt
            mock_openai_instance.chat.assert_called_once()
            call_args = mock_openai_instance.chat.call_args

            # Validate system prompt contains both user question and next qualification question
            system_prompt = call_args[1]["system_prompt"]
            assert "Qual é o valor da mensalidade?" in system_prompt
            assert "o Kumon é para você mesmo ou para outra pessoa?" in system_prompt

            # Validate send_text was called correctly
            mock_send_text.assert_called_once_with(
                "+5511999888777",
                "A mensalidade do Kumon Vila A é R$ 375,00 por disciplina. "
                "Maria Silva, o Kumon é para você mesmo ou para outra pessoa?",
                "kumon_assistant",
            )

            # Validate state was updated correctly
            assert result_state["last_bot_response"] == (
                "A mensalidade do Kumon Vila A é R$ 375,00 por disciplina. "
                "Maria Silva, o Kumon é para você mesmo ou para outra pessoa?"
            )

            print("✅ SUCCESS: Information node correctly generated blended response")
            print(f"✅ User Question: {test_state['text']}")
            print("✅ Next Qualification: beneficiary_type")
            print(
                f"✅ Blended Response Generated: {result_state['last_bot_response'][:80]}..."
            )

    @pytest.mark.asyncio
    async def test_information_node_handles_no_qualification_needed(self):
        """
        🧪 VALIDATION TEST: Ensure information node works when qualification is complete.

        This test ensures that when qualification is complete,
        the information node still works correctly.
        """

        # ARRANGE: Create state with complete qualification
        test_state = {
            "phone": "+5511888999777",
            "text": "Como funciona a metodologia?",
            "phone_number": "+5511888999777",
            "instance": "kumon_assistant",
            "collected_data": {
                "parent_name": "João Santos",
                "beneficiary_type": "child",
                "student_name": "Pedro",
                "student_age": 8,
                "program_interests": ["Matemática"],
            },
        }

        with patch(
            "app.core.nodes.information.send_text", new_callable=AsyncMock
        ) as mock_send_text, patch(
            "app.core.llm.openai_adapter.OpenAIClient"
        ) as mock_openai_class:
            # Mock OpenAI client
            mock_openai_instance = AsyncMock()
            mock_openai_class.return_value = mock_openai_instance
            mock_openai_instance.chat.return_value = (
                "A metodologia Kumon é individualizada, respeitando o ritmo de cada aluno. "
                "Começamos com uma avaliação diagnóstica para identificar o ponto ideal."
            )

            # Mock send_text success
            mock_send_text.return_value = None

            # ACT: Call information_node
            result_state = await information_node(test_state)

            # ASSERT: LLM should be called with prompt indicating no qualification needed
            mock_openai_instance.chat.assert_called_once()
            call_args = mock_openai_instance.chat.call_args

            # Validate system prompt contains user question and "Nenhuma" for qualification
            system_prompt = call_args[1]["system_prompt"]
            assert "Como funciona a metodologia?" in system_prompt
            assert "Nenhuma" in system_prompt  # No qualification question needed

            # Validate response generated correctly
            assert (
                "metodologia Kumon é individualizada"
                in result_state["last_bot_response"]
            )

            print(
                "✅ SUCCESS: Information node correctly handled complete qualification"
            )
            print(f"✅ User Question: {test_state['text']}")
            print("✅ Qualification Status: Complete")
            print(f"✅ Response: {result_state['last_bot_response'][:80]}...")

    @pytest.mark.asyncio
    async def test_information_node_handles_llm_failure_gracefully(self):
        """
        🛡️ ERROR HANDLING TEST: Ensure graceful fallback on LLM failure.
        """

        # ARRANGE: Create test state
        test_state = {
            "phone": "+5511777666555",
            "text": "Qual é o horário de funcionamento?",
            "phone_number": "+5511777666555",
            "instance": "kumon_assistant",
            "collected_data": {},
        }

        with patch(
            "app.core.nodes.information.send_text", new_callable=AsyncMock
        ) as mock_send_text, patch(
            "app.core.llm.openai_adapter.OpenAIClient"
        ) as mock_openai_class:
            # Mock OpenAI client to raise exception
            mock_openai_instance = AsyncMock()
            mock_openai_class.return_value = mock_openai_instance
            mock_openai_instance.chat.side_effect = Exception("API Error")

            # Mock send_text success
            mock_send_text.return_value = None

            # ACT: Call information_node
            result_state = await information_node(test_state)

            # ASSERT: Should fallback gracefully
            expected_fallback = (
                "Desculpe, estou com dificuldades técnicas. "
                "Por favor, entre em contato pelo telefone (51) 99692-1999."
            )

            assert result_state["last_bot_response"] == expected_fallback
            mock_send_text.assert_called_once_with(
                "+5511777666555", expected_fallback, "kumon_assistant"
            )

            print("✅ SUCCESS: Information node handled LLM failure gracefully")
            print(f"✅ Fallback Response: {expected_fallback}")


if __name__ == "__main__":
    print("🧪 Running TDD tests for simplified information_node...")

    import asyncio

    async def run_tests():
        test_suite = TestInformationNodeBlended()

        try:
            print("\n1️⃣ Testing blended response generation...")
            await test_suite.test_information_node_generates_blended_response_correctly()

            print("\n2️⃣ Testing complete qualification scenario...")
            await test_suite.test_information_node_handles_no_qualification_needed()

            print("\n3️⃣ Testing error handling...")
            await test_suite.test_information_node_handles_llm_failure_gracefully()

            print("\n🎯 All tests PASSED! Information node refactoring successful.")

        except Exception as e:
            print(f"\n❌ Test FAILED: {e}")

    asyncio.run(run_tests())
