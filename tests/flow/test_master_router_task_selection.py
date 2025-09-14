# tests/flow/test_master_router_task_selection.py

from unittest.mock import AsyncMock, patch

import pytest

from app.core.nodes.master_router import master_router


@pytest.mark.asyncio
async def test_router_selects_correct_nlu_task_based_on_state():
    """
    🧪 RED PHASE: Teste que prova que master_router NÃO está passando task para GeminiClassifier.

    Este teste irá FALHAR até implementarmos a funcionalidade de "Triagem" no master_router
    que lê o `pending_input_for` do estado e o passa como parâmetro `task` para o classifier.

    PROBLEMA ATUAL:
    - master_router chama: classifier.classify(text, context=context)
    - DEVERIA chamar: classifier.classify(text, context=context, task=pending_input_for)

    SOLUÇÃO REQUERIDA:
    - Ler pending_input_for do estado unificado
    - Passar como parâmetro task para o classifier
    - Permitir que a "Clínica de Especialistas" use o prompt correto
    """

    # ARRANGE: Estado indicando que próximo input esperado é parent_name
    state = {
        "text": "Maria da Silva",
        "phone": "5511999999999",
        "message_id": "test_task_selection",
        "instance": "test_instance",
        "pending_input_for": "parent_name",  # 🎯 CRUCIAL: Indica que esperamos nome do responsável
        "greeting_sent": True,
        "collected_data": {},
    }

    # Mock do GeminiClassifier para espionar as chamadas
    with patch("app.core.state_manager.get_conversation_state") as mock_get_state:
        with patch(
            "app.core.state_manager.get_conversation_history"
        ) as mock_get_history:
            # Setup mocks de estado
            mock_get_state.return_value = {
                "pending_input_for": "parent_name",
                "greeting_sent": True,
                "collected_data": {},
            }
            mock_get_history.return_value = [
                {"role": "assistant", "content": "Qual é o seu nome?"},
            ]

            # Mock do classifier para espionar chamadas
            mock_classifier = AsyncMock()
            mock_classifier.classify = AsyncMock(
                return_value={
                    "primary_intent": "qualification",
                    "secondary_intent": None,
                    "entities": {"parent_name": "Maria da Silva"},
                    "confidence": 0.95,
                }
            )

            # Act - Executar master_router
            await master_router(state, mock_classifier)

            # ASSERT 1: Verificar que classify foi chamado (básico)
            mock_classifier.classify.assert_called_once()

            # ASSERT 2: 🚨 RED PHASE - Verificar se task foi passado
            call_args = mock_classifier.classify.call_args

            # Verificar argumentos posicionais e nomeados
            args, kwargs = call_args

            # ESTE ASSERT VAI FALHAR porque master_router ainda não implementa task
            print(f"🔍 DEBUG - Args: {args}")
            print(f"🔍 DEBUG - Kwargs: {kwargs}")

            # Verificar se task foi passado como keyword argument
            assert "task" in kwargs, (
                f"master_router deveria passar 'task' como parâmetro para classifier.classify(). "
                f"Argumentos atuais: args={args}, kwargs={kwargs}"
            )

            # Verificar valor correto do task
            assert kwargs["task"] == "parent_name", (
                f"com pending_input_for='parent_name', master_router deveria passar "
                f"task='parent_name' para classifier. Got task='{kwargs.get('task')}'"
            )

            print("✅ GREEN PHASE: master_router triagem implementada com sucesso!")


@pytest.mark.asyncio
async def test_router_uses_general_classification_when_no_pending_input():
    """
    ✅ GREEN PHASE: Teste que verifica que master_router usa classificação geral
    quando não há pending_input_for definido.

    Este teste garante que quando não há task específica esperada,
    o master_router chama o classifier sem parâmetro task, usando o prompt geral.
    """

    # ARRANGE: Estado SEM pending_input_for (classificação geral)
    state = {
        "text": "Olá, boa tarde!",
        "phone": "5511999999999",
        "message_id": "test_general_classification",
        "instance": "test_instance",
        # 🎯 SEM pending_input_for - deve usar classificação geral
        "collected_data": {},
    }

    # Mock do GeminiClassifier para espionar as chamadas
    with patch("app.core.state_manager.get_conversation_state") as mock_get_state:
        with patch(
            "app.core.state_manager.get_conversation_history"
        ) as mock_get_history:
            # Setup mocks de estado (sem pending_input_for)
            mock_get_state.return_value = {
                "collected_data": {}
                # 🎯 SEM pending_input_for no estado persistido também
            }
            mock_get_history.return_value = []

            # Mock do classifier para espionar chamadas
            mock_classifier = AsyncMock()
            mock_classifier.classify = AsyncMock(
                return_value={
                    "primary_intent": "greeting",
                    "secondary_intent": None,
                    "entities": {},
                    "confidence": 0.90,
                }
            )

            # Act - Executar master_router
            await master_router(state, mock_classifier)

            # ASSERT 1: Verificar que classify foi chamado (básico)
            mock_classifier.classify.assert_called_once()

            # ASSERT 2: ✅ GREEN PHASE - Verificar que NÃO passou task
            call_args = mock_classifier.classify.call_args
            args, kwargs = call_args

            print(f"🔍 DEBUG - Args: {args}")
            print(f"🔍 DEBUG - Kwargs: {kwargs}")

            # Verificar que task NÃO foi passado (classificação geral)
            assert "task" not in kwargs, (
                f"Sem pending_input_for, master_router NÃO deveria passar 'task'. "
                f"Argumentos atuais: args={args}, kwargs={kwargs}"
            )

            # Verificar que context foi passado normalmente
            assert "context" in kwargs, "Context deve estar presente sempre"

            print("✅ GREEN PHASE: Classificação geral funcionando sem task!")
