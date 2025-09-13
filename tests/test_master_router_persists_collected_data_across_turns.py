"""
Teste de integração para verificar se o master_router preserva collected_data entre turnos.
Este teste irá falhar inicialmente (Red Phase) devido ao bug de amnésia.
"""

from unittest.mock import patch

import pytest

from app.core.nodes.master_router import master_router


@pytest.mark.asyncio
async def test_master_router_persists_collected_data_across_turns():
    """
    CENÁRIO: Teste de persistência de dados coletados entre turnos

    - Turno anterior coletou: {"parent_name": "Gabriel"}
    - Turno atual: "para meu filho" (deve extrair beneficiary_type)
    - EXPECTATIVA: Estado final deve conter AMBOS os dados
    """

    # ARRANGE: Estado persistido simulado (dados do turno anterior)
    persisted_state = {
        "phone": "555195211999",
        "collected_data": {"parent_name": "Gabriel"},
    }

    # Estado do turno atual (novo turno)
    current_state = {
        "phone": "555195211999",
        "text": "para meu filho",
        "message_id": "test_123",
        "instance": "kumon_assistant",
        "collected_data": {},  # Vazio no início do turno
    }

    # Mock do Gemini classificando corretamente
    mock_nlu_result = {
        "primary_intent": "qualification",
        "secondary_intent": None,
        "entities": {
            "parent_name": None,  # Não detecta nome nesta mensagem
            "beneficiary_type": "child",  # Detecta que é para o filho
            "student_name": None,
            "student_age": None,
            "program_interests": [],
        },
        "confidence": 0.9,
    }

    # ACT: Simular o master_router com estado persistido
    with patch(
        "app.core.nodes.master_router.get_conversation_state"
    ) as mock_get_state, patch(
        "app.core.nodes.master_router.get_conversation_history"
    ) as mock_get_history, patch(
        "app.core.nodes.master_router.classifier.classify"
    ) as mock_classify:
        # Configurar mocks
        mock_get_state.return_value = persisted_state
        mock_get_history.return_value = []
        mock_classify.return_value = mock_nlu_result

        # Executar master_router
        result_state = await master_router(current_state)

    # ASSERT: O estado final deve preservar dados antigos + novos
    collected_data = result_state.get("collected_data", {})

    # CRÍTICO: Deve conter o dado antigo preservado
    assert (
        "parent_name" in collected_data
    ), "parent_name do turno anterior deve ser preservado"
    assert (
        collected_data["parent_name"] == "Gabriel"
    ), "parent_name deve manter o valor correto"

    # NOTA: O master_router preserva estado mas não processa entidades
    # Isso é feito pelo qualification_node após o roteamento
    # Verificamos que o estado antigo foi preservado (que era o bug principal)

    # Verificação adicional: estado deve ter o resultado do NLU para processamento posterior
    assert result_state.get("nlu_result") == mock_nlu_result
    assert result_state.get("routing_decision") == "qualification_node"

    # O mais importante: o estado antigo não foi perdido!
    assert (
        len(collected_data) > 0
    ), "collected_data não deve estar vazio (bug de amnésia)"
