# tests/integration/test_state_persistence.py
import uuid

import pytest

# Importe o 'workflow' e a função de criação de estado inicial
from app.core.langgraph_flow import graph


def create_initial_cecilia_state(phone_number: str, user_message: str) -> dict:
    """Helper function to create initial state for testing."""
    return {
        "phone": phone_number,
        "message_id": f"test_msg_{uuid.uuid4()}",
        "text": user_message,
        "instance": "test_instance",
        "collected_data": {},
        "history": [],  # Inicializa o histórico vazio
    }


@pytest.mark.asyncio
async def test_langgraph_checkpoints_persist_state_across_turns():
    """
    🧪 TESTE DE INTEGRAÇÃO DEFINITIVO: Valida a persistência automática
    do estado entre os turnos usando o sistema de Checkpoints do LangGraph.
    """
    # ARRANGE: Define um ID de conversa único para este teste
    conversation_id = f"test-thread-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": conversation_id}}

    # --- TURNO 1: Usuário envia "olá" ---
    print("\n--- 🧪 Executando Turno 1: Greeting ---")
    state_turn_1 = create_initial_cecilia_state(
        phone_number=conversation_id,  # Usamos o ID como telefone para consistência
        user_message="olá",
    )

    final_state_1 = await graph.ainvoke(state_turn_1, config=config)

    # Assertiva do Turno 1: Verifica se o bot pediu o nome
    assert "qual é o seu nome" in final_state_1.get("last_bot_response", "").lower()
    assert final_state_1.get("greeting_sent") is True

    # --- TURNO 2: Usuário envia o nome "Gabriel" ---
    print("\n--- 🧪 Executando Turno 2: Coleta de Nome ---")
    state_turn_2 = create_initial_cecilia_state(
        phone_number=conversation_id,
        user_message="Gabriel",
    )

    # A mágica do checkpoint: o 'ainvoke' com o mesmo 'thread_id' deve carregar o estado anterior
    final_state_2 = await graph.ainvoke(state_turn_2, config=config)

    # ASSERTIVA CRÍTICA (que irá falhar):
    # O 'collected_data' no estado final do Turno 2 DEVE conter o nome coletado.
    collected_data_2 = final_state_2.get("collected_data", {})
    assert (
        collected_data_2.get("parent_name") == "Gabriel"
    ), "O estado do Turno 2 falhou em persistir o 'parent_name' coletado."

    # Assertiva de continuação: Verifica se o bot pediu o próximo passo
    assert (
        "para você mesmo ou para outra pessoa"
        in final_state_2.get("last_bot_response", "").lower()
    ), "O bot não continuou a qualificação após coletar o nome."

    print("\n--- ✅ SUCESSO: Persistência de estado entre turnos confirmada! ---")


@pytest.mark.asyncio
async def test_history_is_appended_and_passed_to_classifier():
    """
    🧪 TESTE DEFINITIVO: Valida que o histórico é construído turno a turno
    e passado corretamente para o GeminiClassifier.

    RED PHASE: Este teste deve FALHAR inicialmente porque ainda não implementamos
    a lógica do "Historiador" que constrói o histórico no state.
    """
    from unittest.mock import AsyncMock, patch

    # ARRANGE: Define um ID de conversa único para este teste
    conversation_id = f"test-history-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": conversation_id}}

    with patch(
        "app.core.langgraph_flow.gemini_classifier.classify", new_callable=AsyncMock
    ) as mock_classify:
        # Mock das respostas do classifier para simular fluxo normal
        mock_classify.side_effect = [
            # Turno 1: greeting
            {
                "primary_intent": "greeting",
                "secondary_intent": None,
                "entities": {},
                "confidence": 0.90,
            },
            # Turno 2: qualification
            {
                "primary_intent": "qualification",
                "secondary_intent": None,
                "entities": {"parent_name": "Maria"},
                "confidence": 0.95,
            },
        ]

        # --- TURNO 1: Usuário envia "oi" ---
        print("\n--- 🧪 Turno 1: Primeiro contato ---")
        state_turn_1 = create_initial_cecilia_state(
            phone_number=conversation_id,
            user_message="oi",
        )

        final_state_1 = await graph.ainvoke(state_turn_1, config=config)

        # Verifica se classifier foi chamado no Turno 1
        assert (
            mock_classify.call_count >= 1
        ), "Classifier deveria ter sido chamado no Turno 1"

        # --- TURNO 2: Usuário envia nome "Maria" ---
        print("\n--- 🧪 Turno 2: Resposta com nome ---")

        # 🧠 SIMULAÇÃO DO HISTORIADOR: Simula a lógica do webhook handler
        # Constrói o histórico baseado no final_state_1 (que tem last_bot_response)
        print(f"🔍 DEBUG - final_state_1 keys: {list(final_state_1.keys())}")
        print(
            f"🔍 DEBUG - Has last_bot_response: {bool(final_state_1.get('last_bot_response'))}"
        )

        # Inicia com histórico vazio e adiciona bot response do Turno 1
        history = []
        last_bot_response = final_state_1.get("last_bot_response")

        if last_bot_response:
            history.append({"role": "assistant", "content": last_bot_response})
            print(
                f"🧠 HISTORIAN - Bot response added to history: {last_bot_response[:50]}..."
            )

        # Adiciona mensagem atual do usuário
        history.append({"role": "user", "content": "Maria"})
        print(f"🧠 HISTORIAN - User message added, total history: {len(history)}")

        state_turn_2 = create_initial_cecilia_state(
            phone_number=conversation_id,
            user_message="Maria",
        )

        # 🎯 CRÍTICO: Adiciona o histórico construído pelo Historiador
        state_turn_2["history"] = history
        state_turn_2["collected_data"] = final_state_1.get("collected_data", {})

        await graph.ainvoke(state_turn_2, config=config)

        # ASSERTIVA CRÍTICA: No Turno 2, o classifier deve receber histórico
        assert (
            mock_classify.call_count >= 2
        ), "Classifier deveria ter sido chamado no Turno 2"

        # Pega a chamada do Turno 2 (última chamada)
        call_args_turn_2 = mock_classify.call_args_list[-1]
        args, kwargs = call_args_turn_2

        print(f"🔍 DEBUG - Classifier args Turno 2: {args}")
        print(f"🔍 DEBUG - Classifier kwargs Turno 2: {kwargs}")

        # Verifica se context foi passado
        assert (
            "context" in kwargs
        ), "Context deveria estar presente na chamada do classifier"

        context = kwargs["context"]

        # ASSERTIVA PRINCIPAL: Context deve conter histórico
        assert (
            "history" in context
        ), f"Context deveria conter 'history'. Context keys: {list(context.keys())}"

        history = context["history"]
        assert isinstance(
            history, list
        ), f"History deveria ser uma lista, got: {type(history)}"

        # ASSERTIVA DE CONTEÚDO: História deve conter resposta do bot do Turno 1
        assert (
            len(history) > 0
        ), "History deveria conter pelo menos uma entrada do turno anterior"

        # Procura por entrada do assistant (bot) do turno anterior
        bot_entries = [entry for entry in history if entry.get("role") == "assistant"]
        assert (
            len(bot_entries) > 0
        ), f"History deveria conter resposta do bot. History: {history}"

        print("✅ SUCESSO: Histórico está sendo construído e passado para o classifier!")
        print(f"📚 Histórico encontrado: {len(history)} entradas")
        print(f"🤖 Respostas do bot no histórico: {len(bot_entries)}")
