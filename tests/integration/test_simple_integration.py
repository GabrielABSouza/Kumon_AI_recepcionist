# tests/integration/test_simple_integration.py

from unittest.mock import patch

import pytest

from app.core.langgraph_flow import workflow as graph


@pytest.mark.asyncio
async def test_integration_with_direct_mocks():
    """
    🧪 TESTE DE INTEGRAÇÃO SIMPLES COM MOCKS DIRETOS

    Testa o fluxo completo com mocks explícitos para garantir que funciona.
    """
    print("\n--- 🧪 TESTE DE INTEGRAÇÃO COM MOCKS DIRETOS ---")

    # Mensagem de teste
    user_message = (
        "olá, meu nome é Gabriel, gostaria de informações sobre o kumon de matemática"
    )

    # Estado inicial mínimo
    initial_state = {
        "text": user_message,
        "phone": "5511999999999",
        "message_id": "test_msg_123",
        "instance": "test_instance",
    }

    # Mocks explícitos
    mock_classifier_response = {
        "primary_intent": "information",
        "secondary_intent": None,
        "entities": {"parent_name": "Gabriel", "program_interests": ["Matemática"]},
        "confidence": 0.95,
    }

    mock_llm_response = (
        "Olá Gabriel! O Kumon de Matemática é um método "
        "individualizado que fortalece o raciocínio. "
        "Para que eu possa te ajudar melhor, o Kumon é para "
        "você mesmo ou para outra pessoa?"
    )

    with patch("app.core.routing.master_router.classifier") as mock_classifier, patch(
        "app.core.gemini_classifier.classifier"
    ) as mock_classifier2, patch(
        "app.core.state_manager.get_conversation_state"
    ) as mock_get_state, patch(
        "app.core.state_manager.save_conversation_state"
    ) as mock_save_state, patch(
        "app.core.state_manager.get_conversation_history"
    ) as mock_get_history, patch(
        "app.core.delivery.send_text"
    ) as mock_send_text, patch(
        "app.core.llm.openai_adapter.OpenAIClient.chat"
    ) as mock_llm_chat:
        # Configure mocks
        mock_classifier.classify.return_value = mock_classifier_response
        mock_classifier2.classify.return_value = mock_classifier_response
        mock_get_state.return_value = {}
        mock_save_state.return_value = True
        mock_get_history.return_value = []
        mock_send_text.return_value = {"sent": "true", "status": "success"}
        mock_llm_chat.return_value = mock_llm_response

        # Execute the graph
        final_state = await graph.ainvoke(initial_state)

    # Verify results
    print(f"✅ ESTADO FINAL: {final_state}")
    print(f"✅ RESPOSTA DO BOT: {final_state.get('response')}")

    # Assertions
    assert final_state.get("sent") == "true", "Deveria ter enviado a mensagem"

    # Check if message was sent
    assert mock_send_text.called, "send_text deveria ter sido chamado"

    # Check if LLM was called for blended response
    assert (
        mock_llm_chat.called
    ), "LLM deveria ter sido chamado para gerar resposta blended"

    print("🎉 TESTE DE INTEGRAÇÃO CONCLUÍDO COM SUCESSO!")
    return True


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_integration_with_direct_mocks())
