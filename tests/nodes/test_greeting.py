"""
Tests for greeting node functionality.
Updated for new architecture - greeting_node no longer extracts entities globally.
Entity extraction is now localized to specific nodes that need specific information.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.langgraph_flow import greeting_node


class TestGreetingNode:
    """Test suite for greeting node functionality in new architecture."""

    def test_greeting_node_generates_response_and_sets_flag(self):
        """Test that greeting node generates response and sets greeting_sent flag."""
        # Input state simulating webhook data
        state_input = {
            "text": "Oi, boa tarde!",
            "phone": "+5511999999999",
            "message_id": "MSG_GREETING",
            "instance": "test",
        }

        # Mock dependencies
        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                with patch("app.core.langgraph_flow.send_text") as mock_send:
                    with patch(
                        "app.core.langgraph_flow.save_conversation_state"
                    ) as _mock_save:
                        # Setup mocks
                        mock_get_state.return_value = {}  # New conversation
                        mock_send.return_value = {
                            "sent": "true",
                            "status_code": 200,
                        }

                        mock_client = MagicMock()

                        # Create async mock for OpenAI response
                        async def mock_chat(*_args, **_kwargs):
                            return "Olá! Eu sou a Cecília do Kumon Vila A. Qual é o seu nome?"

                        mock_client.chat = mock_chat
                        mock_openai.return_value = mock_client

                        # Execute greeting node
                        result = greeting_node(state_input)

                        # ASSERTION 1: Should return result with greeting_sent flag
                        assert (
                            "greeting_sent" in result
                        ), "greeting_node should set greeting_sent flag"
                        assert (
                            result["greeting_sent"] is True
                        ), "greeting_sent should be True"

                        # ASSERTION 2: Should send a response
                        assert mock_send.called, "Should send a greeting response"

                        # ASSERTION 3: Should save state (standard flow)
                        assert _mock_save.called, "Should save conversation state"

    def test_greeting_node_handles_empty_text(self):
        """Test that greeting node handles empty or missing text gracefully."""
        state_input = {
            "text": "",  # Empty text
            "phone": "+5511999999999",
            "message_id": "MSG_EMPTY",
            "instance": "test",
        }

        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                with patch("app.core.langgraph_flow.send_text") as mock_send:
                    with patch(
                        "app.core.langgraph_flow.save_conversation_state"
                    ) as _mock_save:
                        mock_get_state.return_value = {}
                        mock_send.return_value = {"sent": "true", "status_code": 200}

                        mock_client = MagicMock()

                        async def mock_chat(*_args, **_kwargs):
                            return "Olá! Como posso ajudar?"

                        mock_client.chat = mock_chat
                        mock_openai.return_value = mock_client

                        # Should not crash
                        result = greeting_node(state_input)

                        # Should still set the flag and process normally
                        assert result.get("greeting_sent") is True

    def test_greeting_node_uses_execute_node_framework(self):
        """Test that greeting node properly uses the _execute_node framework."""
        state_input = {
            "text": "Olá",
            "phone": "+5511999999999",
            "message_id": "MSG_FRAMEWORK",
            "instance": "test",
        }

        with patch("app.core.langgraph_flow._execute_node") as mock_execute:
            with patch("app.core.langgraph_flow.get_greeting_prompt"):
                # Mock _execute_node to return a basic result
                mock_execute.return_value = {
                    "response": "Test response",
                    "phone": "+5511999999999",
                }

                result = greeting_node(state_input)

                # ASSERTION 1: Should call _execute_node with correct parameters
                mock_execute.assert_called_once()
                call_args = mock_execute.call_args[0]
                assert call_args[0] == state_input, "Should pass input state"
                assert call_args[1] == "greeting", "Should use 'greeting' as node name"

                # ASSERTION 2: Should add greeting_sent flag to result
                assert result["greeting_sent"] is True, "Should add greeting_sent flag"

    def test_greeting_node_uses_pre_extracted_entities_from_classifier(self):
        """
        🚨 RED PHASE TEST: Greeting node deve usar entidades já extraídas pelo GeminiClassifier.

        PROBLEMA ATUAL: greeting_node tem lógica de NLU duplicada em _get_business_updates_for_greeting
        que analisa keywords - deve ser eliminado.

        NOVA ARQUITETURA: greeting_node deve ler entidades do state['intent_result']['entities']
        e usar essa informação para atualizar o estado.

        🔥 ESTE TESTE VAI FALHAR até refatorarmos _get_business_updates_for_greeting
        """
        from app.core.nodes.greeting import GreetingNode
        from app.core.state.models import CeciliaState, ConversationStep

        # ARRANGE: Criar estado onde o GeminiClassifier contradiz as keywords
        # 🔥 PROBLEMA: Se greeting_node ainda usa keywords, vai interpretar mal
        state = CeciliaState(
            {
                "phone_number": "5511999999999",
                # 🎯 CRÍTICO: Mensagem confusa que keywords interpretariam como "self"
                "last_user_message": "é para mim, mas na verdade para minha sobrinha",
                "current_step": ConversationStep.INITIAL_RESPONSE,
                "collected_data": {
                    "parent_name": "Maria"  # Nome já coletado na etapa anterior
                },
                # 🧠 INTELIGÊNCIA: GeminiClassifier é mais inteligente e identifica corretamente
                "intent_result": {
                    "primary_intent": "qualification",
                    "entities": {
                        "beneficiary_type": "child",  # GeminiClassifier identifica corretamente
                        "parent_name": "Maria",
                    },
                },
            }
        )

        # ACT: Executar greeting_node
        node = GreetingNode()
        updates = node._get_business_updates_for_greeting(state)

        # 🔍 DEBUG: Vamos ver o que está sendo retornado
        print(f"🔍 DEBUG - Updates retornados: {updates}")
        print(f"🔍 DEBUG - Estado atual: current_step={state.get('current_step')}")
        print(f"🔍 DEBUG - intent_result: {state.get('intent_result')}")

        # ASSERT 1: Deve usar entidade extraída pelo GeminiClassifier
        assert "is_for_self" in updates, (
            f"greeting_node deve processar beneficiary_type do GeminiClassifier. "
            f"Updates atuais: {updates}"
        )
        assert (
            updates["is_for_self"] is False
        ), f"Com beneficiary_type='child', is_for_self deve ser False. Got: {updates}"

        # ASSERT 2: Deve transicionar para próximo step baseado na entidade
        assert updates["current_step"] == ConversationStep.CHILD_NAME_COLLECTION, (
            f"Com beneficiary_type='child', deve ir para CHILD_NAME_COLLECTION. "
            f"Got: {updates['current_step']}"
        )

        # ASSERT 3: Deve definir relationship corretamente baseado na entidade
        assert updates["relationship"] == "responsável por filho(a)", (
            f"Com beneficiary_type='child', relationship deve ser definido. "
            f"Got: {updates.get('relationship')}"
        )

        print("✅ RED PHASE: Teste criado - vai falhar até refatorarmos greeting_node")
        return True


@pytest.mark.asyncio
async def test_greeting_node_sends_only_one_message():
    """
    🧪 TESTE RED PHASE: Prova o bug de duplicação no greeting_node

    Este teste irá FALHAR até corrigirmos o bug de chamada assíncrona
    que causa duplicação de resposta.
    """
    # Arrange - Estado de entrada simples
    state = {"phone": "5511999999999", "instance": "kumon_assistant"}

    # Act & Assert - Espionar a função send_text
    with patch(
        "app.core.nodes.greeting.send_text", new_callable=AsyncMock
    ) as mock_send_text:
        # Executar o greeting_node
        result = await greeting_node(state)

        # ASSERTIVA QUE IRÁ FALHAR: send_text deve ser chamado apenas UMA vez
        # O bug atual faz com que seja chamado duas vezes (normal + fallback)
        mock_send_text.assert_called_once()

        # Verificar que a resposta foi definida no estado
        assert "response" in result or "last_bot_response" in result
        assert result["greeting_sent"] is True

        # Verificar quantas vezes foi chamado (aqui vamos ver o bug)
        print(f"🔍 send_text foi chamado {mock_send_text.call_count} vezes")
        if mock_send_text.call_count > 0:
            print(f"🔍 Chamadas: {mock_send_text.call_args_list}")

        # Verificar o conteúdo da mensagem enviada
        if mock_send_text.called:
            call_args = mock_send_text.call_args
            assert "Cecília" in str(call_args)  # Verificar que tem Cecília na chamada


@pytest.mark.asyncio
async def test_greeting_node_fallback_sends_only_one_message():
    """
    🧪 TESTE RED PHASE: Força condição de erro para provar bug de duplicação no fallback

    Simula erro no simplified_greeting_node para acionar o fallback e
    verificar que send_text não é chamado duas vezes.
    """
    from app.core.langgraph_flow import greeting_node as langgraph_greeting_node

    # Arrange - Estado de entrada simples
    state = {"phone": "5511999999999", "instance": "kumon_assistant"}

    # Mock para forçar exceção no simplified_greeting_node
    with patch(
        "app.core.langgraph_flow.simplified_greeting_node",
        side_effect=Exception("Simulated error"),
    ) as mock_simplified:
        with patch(
            "app.core.langgraph_flow.send_text", new_callable=AsyncMock
        ) as mock_send_text:
            with patch("app.core.langgraph_flow.save_conversation_state") as mock_save:
                # Act - Executar o langgraph greeting_node (que vai para fallback)
                result = await langgraph_greeting_node(state)

                # Assert - DEVE chamar send_text apenas UMA vez (no fallback)
                # Se houvesse o bug (sem await), chamaria duas vezes
                mock_send_text.assert_called_once()

                # Verificar que foi para o fallback
                assert "error_reason" in result
                assert (
                    result["response"]
                    == "Olá! Eu sou a Cecília do Kumon Vila A. Qual é o seu nome?"
                )

                print(
                    f"✅ Fallback executado com {mock_send_text.call_count} chamada(s) a send_text"
                )
