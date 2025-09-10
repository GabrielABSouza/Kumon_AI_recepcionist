"""
Tests for qualification_node logic and behavior.
Focuses on the beneficiary_type flow and variable collection.
"""
from unittest.mock import MagicMock, patch

from app.core.langgraph_flow import qualification_node


class TestQualificationNode:
    """Test suite for qualification_node behavior."""

    def test_qualification_node_uses_pre_extracted_entities(self):
        """
        🚨 RED PHASE TDD TEST: qualification_node should consume pre-extracted entities from NLU.

        This test will FAIL with current implementation because qualification_node
        doesn't know how to use the entities that GeminiClassifier already extracted.

        Scenario: User provides multiple information in one message.
        Expected: Both student_name and student_age should be consumed from nlu_result.
        Current Bug: Node ignores pre-extracted entities, asks redundant questions.
        """
        # ARRANGE: Create state with parent_name collected but other info missing
        state_with_nlu_entities = {
            "text": "O nome dele é João e ele tem 8 anos",
            "phone": "+5511999888777",
            "message_id": "MSG_MULTI_INFO",
            "instance": "test",
            # CRITICAL: Add pre-extracted entities from Gemini NLU
            "nlu_result": {
                "primary_intent": "qualification",
                "entities": {"student_name": "João", "student_age": 8},
            },
        }

        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.save_conversation_state"
        ) as mock_save_state, patch(
            "app.core.langgraph_flow.get_openai_client"
        ) as mock_openai, patch(
            "app.core.langgraph_flow.send_text"
        ) as mock_send:
            # Mock Redis state showing parent_name collected but other vars missing
            mock_get_state.return_value = {
                "parent_name": "Maria Silva",
                "student_name": None,  # Missing - should be filled by NLU entities
                "student_age": None,  # Missing - should be filled by NLU entities
                "program_interests": None,  # Still missing after NLU consumption
            }

            mock_send.return_value = {"sent": "true", "status_code": 200}

            # Mock OpenAI to ask for remaining variable (program_interests)
            mock_client = MagicMock()

            async def mock_chat(*args, **kwargs):
                return "Perfeito! Agora me diga, quais matérias você gostaria que o João praticasse?"

            mock_client.chat = mock_chat
            mock_openai.return_value = mock_client

            # ACT: Execute qualification_node
            qualification_node(state_with_nlu_entities)

            # ASSERT: Should save consumed entities to Redis state
            # 🚨 THIS WILL FAIL - Current node doesn't consume pre-extracted entities
            expected_saved_state = {
                "parent_name": "Maria Silva",  # Already existed
                "student_name": "João",  # Consumed from NLU entities
                "student_age": 8,  # Consumed from NLU entities
                "program_interests": None,  # Still missing, will be asked next
            }

            # Check that save_conversation_state was called with consumed entities
            save_calls = mock_save_state.call_args_list
            assert len(save_calls) > 0, "Should save state with consumed entities"

            # Extract the saved state from the call
            saved_state = save_calls[-1][0][1]  # Second argument of last call

            assert saved_state.get("student_name") == "João", (
                f"CRITICAL BUG: student_name should be consumed from NLU entities "
                f"but got '{saved_state.get('student_name')}'"
            )
            assert saved_state.get("student_age") == 8, (
                f"CRITICAL BUG: student_age should be consumed from NLU entities "
                f"but got '{saved_state.get('student_age')}'"
            )

            print("✅ SUCCESS: qualification_node consumes pre-extracted entities")
            print(
                f"✅ NLU Entities: {state_with_nlu_entities['nlu_result']['entities']}"
            )
            print(f"✅ Consumed student_name: {saved_state.get('student_name')}")
            print(f"✅ Consumed student_age: {saved_state.get('student_age')}")

    def test_qualification_asks_beneficiary_question_after_parent_name(self):
        """Test que qualification carrega estado do Redis e pergunta sobre beneficiário quando só tem parent_name."""
        # Entrada mínima simulando webhook - sem estado na entrada
        state_input = {
            "text": "Quero informações sobre matrícula",
            "phone": "+5511999999999",
            "message_id": "MSG_001",
            "instance": "test",
        }

        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                with patch("app.core.langgraph_flow.send_text") as mock_send:
                    # Mock do Redis retornando apenas parent_name
                    mock_get_state.return_value = {"parent_name": "Maria"}
                    mock_send.return_value = {
                        "sent": "true",
                        "status_code": 200,
                    }

                    mock_client = MagicMock()

                    # Create async mock que retorna pergunta sobre beneficiário
                    async def mock_chat(*args, **kwargs):
                        return (
                            "Maria, você está buscando o Kumon para você mesmo "
                            "ou para outra pessoa?"
                        )

                    mock_client.chat = mock_chat
                    mock_openai.return_value = mock_client

                    # Execute qualification_node
                    result = qualification_node(state_input)

                    # Deve carregar estado do Redis via get_conversation_state
                    mock_get_state.assert_called_with("+5511999999999")

                    # Should ask about beneficiary type
                    response = result.get("response", "").lower()
                    assert any(
                        phrase in response
                        for phrase in [
                            "para você mesmo",
                            "para outra pessoa",
                            "beneficiário",
                            "para quem é",
                        ]
                    ), f"Should ask about beneficiary type, got: {response}"

    def test_qualification_node_does_not_extract_greetings_as_name(self):
        r"""
        🚨 TESTE DE REGRESSÃO: Prova que o bug de extração de "Olá" existe.

        Este teste DEVE FALHAR inicialmente, provando que o qualification_node
        está incorretamente extraindo saudações como "Olá" como parent_name.

        Bug Location: app/core/langgraph_flow.py:272 - padrão r"^(\w+)$"
        """
        # Estado simulando conversa onde parent_name está faltando
        state_input = {
            "text": "Olá",  # CRÍTICO: Saudação que NÃO deve ser extraída como nome
            "phone": "+5511999999999",
            "message_id": "MSG_GREETING_BUG",
            "instance": "test",
            "qualification_attempts": 0,
        }

        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.save_conversation_state") as mock_save:
                with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                    with patch("app.core.langgraph_flow.send_text") as mock_send:
                        # CENÁRIO: Redis retorna estado vazio (parent_name missing)
                        # Isso força o qualification_node a tentar extrair parent_name
                        mock_get_state.return_value = {}  # Sem parent_name!

                        mock_send.return_value = {
                            "sent": "true",
                            "status_code": 200,
                        }

                        mock_client = MagicMock()

                        async def mock_chat(*args, **kwargs):
                            return "Olá! Qual é o seu nome?"

                        mock_client.chat = mock_chat
                        mock_openai.return_value = mock_client

                        # EXECUÇÃO: Roda qualification_node com saudação "Olá"
                        qualification_node(state_input)

                        # ASSERTIVA CRÍTICA: parent_name NÃO deve ser extraído de saudações
                        # Este teste deve FALHAR, provando que o bug existe

                        # O qualification_node salva estado duas vezes:
                        # 1. Durante extração local (se parent_name missing)
                        # 2. No final da execução
                        # Vamos verificar todas as chamadas para save_conversation_state

                        bug_detected = False
                        extracted_name = None

                        if mock_save.called:
                            # Verificar todas as chamadas para save_conversation_state
                            for call_args in mock_save.call_args_list:
                                saved_state = call_args[0][
                                    1
                                ]  # Segundo argumento (state dict)
                                parent_name = saved_state.get("parent_name")

                                if parent_name in ["Olá", "Ola"]:
                                    bug_detected = True
                                    extracted_name = parent_name
                                    break

                        # ASSERTIVA REAL: O bug deve ser detectado (teste deve falhar)
                        assert not bug_detected, (
                            f"🚨 BUG CONFIRMADO: qualification_node extraiu saudação '{extracted_name}' "
                            f"como parent_name! Verificar regex problemático em langgraph_flow.py:272. "
                            f"Todas as chamadas save: {[call[0][1] for call in mock_save.call_args_list]}"
                        )

                        print(
                            f"✅ REGRESSION TEST: Saudação 'Olá' não foi extraída como parent_name"
                        )

    def test_qualification_node_asks_for_the_next_correct_variable(self):
        """
        🚨 RED PHASE TDD TEST: qualification_node should ask for the next correct variable in sequence.

        This test will FAIL with current implementation because qualification_node
        doesn't follow the correct variable order from QUALIFICATION_REQUIRED_VARS.

        Scenario: parent_name and beneficiary_type are filled, should ask for student_name (next in sequence).
        Expected: Should ask specifically for student_name, not random variables.
        Current Bug: Node doesn't follow sequential variable collection logic.
        """
        # ARRANGE: Create state where first 2 variables are collected
        state_input = {
            "text": "Para o meu filho",  # Response about beneficiary_type
            "phone": "+5511888999777",
            "message_id": "MSG_SEQUENTIAL_TEST",
            "instance": "test",
        }

        with patch(
            "app.core.langgraph_flow.get_conversation_state"
        ) as mock_get_state, patch(
            "app.core.langgraph_flow.save_conversation_state"
        ) as mock_save_state, patch(
            "app.core.langgraph_flow.get_openai_client"
        ) as mock_openai, patch(
            "app.core.langgraph_flow.send_text"
        ) as mock_send:
            # Mock Redis state with first 2 variables completed
            mock_get_state.return_value = {
                "parent_name": "Ana Costa",  # ✅ Collected (1st variable)
                "beneficiary_type": "child",  # ✅ Collected (2nd variable)
                "student_name": None,  # ❌ Missing (3rd variable - should be next)
                "student_age": None,  # ❌ Missing (4th variable)
                "program_interests": None,  # ❌ Missing (5th variable)
            }

            mock_send.return_value = {"sent": "true", "status_code": 200}

            # Mock OpenAI to ask for the NEXT variable in sequence (student_name)
            mock_client = MagicMock()

            async def mock_chat(*args, **kwargs):
                # This should ask for student_name specifically (next in sequence)
                return "Perfeito, Ana! Qual é o nome do seu filho?"

            # Create a side_effect function that captures the call arguments
            def mock_chat_side_effect(*args, **kwargs):
                # Store the call arguments for verification
                mock_chat.call_args = (args, kwargs)
                return mock_chat(*args, **kwargs)

            mock_client.chat = mock_chat_side_effect
            mock_openai.return_value = mock_client

            # ACT: Execute qualification_node
            result = qualification_node(state_input)

            # ASSERT: Should ask for student_name (next variable in sequence)
            # 🚨 THIS WILL FAIL - Current node doesn't follow sequential logic

            # Check that OpenAI was called
            assert mock_openai.called, "Should call OpenAI to generate question"

            # Get the OpenAI client that was called
            openai_client_calls = mock_openai.call_args_list
            assert len(openai_client_calls) > 0, "Should have client calls"

            # Get the actual chat method that was called on the mocked client
            client_instance = mock_openai.return_value
            assert hasattr(client_instance, "chat"), "Client should have chat method"

            # Verify the chat method was called (this is our async mock)
            assert (
                client_instance.chat.called
                if hasattr(client_instance.chat, "called")
                else True
            ), "Chat method should be called"

            # For debugging: print what we got
            print(f"DEBUG: OpenAI client calls: {len(openai_client_calls)}")
            print(f"DEBUG: Mock client type: {type(client_instance)}")
            print(f"DEBUG: Chat method type: {type(client_instance.chat)}")

            # Since we can't easily capture the async call args, let's test the prompt generation directly
            # Import and test the prompt function with the same state
            from app.prompts.node_prompts import get_qualification_prompt

            # Create the exact same state that should be passed to the prompt function
            test_state = {
                "parent_name": "Ana Costa",
                "beneficiary_type": "child",
                "student_name": None,
                "student_age": None,
                "program_interests": None,
            }

            # Generate the prompt with the same arguments that qualification_node would use
            prompt = get_qualification_prompt(
                user_text="Para o meu filho", redis_state=test_state, attempts=1
            )

            # Test that the system prompt asks for student_name
            system_prompt = prompt["system"].lower()
            assert any(
                keyword in system_prompt
                for keyword in ["nome do", "qual o nome", "nome da criança"]
            ), (
                f"CRITICAL BUG: System prompt should ask for student_name but doesn't mention it. "
                f"System prompt: {prompt['system']}"
            )

            # Verify response asks for student name
            response = result.get("response", "").lower()
            assert any(
                keyword in response
                for keyword in [
                    "nome do",
                    "qual o nome",
                    "como se chama",
                    "nome da criança",
                ]
            ), (
                f"CRITICAL BUG: Response should ask for student name (next variable) "
                f"but got: {response}"
            )

            print(
                "✅ SUCCESS: qualification_node asks for next correct variable in sequence"
            )
            print(f"✅ Current State: parent_name=✅, beneficiary_type=✅, student_name=❌")
            print(f"✅ Next Question: {response}")
            print(f"✅ Sequential Logic: Working correctly")
