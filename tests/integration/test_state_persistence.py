# tests/integration/test_state_persistence.py
from unittest.mock import MagicMock, patch

import pytest

# O caminho para o webhook handler pode precisar de ajuste
from app.api.evolution import webhook


@pytest.mark.asyncio
# Mockamos as duas dependências externas do webhook: o fluxo e a função de salvar
@patch("app.api.evolution.save_conversation_state")
@patch("app.core.langgraph_flow.run_flow")
async def test_webhook_handler_saves_state_after_flow_completes(
    mock_run_flow, mock_save_state
):
    """
    Garante que o webhook handler CUMPRA sua responsabilidade de chamar
    save_conversation_state com o resultado final do fluxo.
    """
    # ARRANGE:
    # Simulamos que o grafo rodou e retornou um estado final com dados coletados
    final_state_from_graph = {
        "phone": "12345",
        "collected_data": {"parent_name": "Gabriel"},
        "last_bot_response": "Ótimo, Gabriel! E para quem é o curso?",
    }
    mock_run_flow.return_value = final_state_from_graph

    # Criamos um mock de um request do FastAPI com payload correto
    mock_request = MagicMock()

    async def json():
        return {
            "instance": "cecilia_nova",
            "data": {
                "key": {
                    "remoteJid": "12345@s.whatsapp.net",
                    "fromMe": False,
                    "id": "ABC",
                },
                "message": {"conversation": "Gabriel"},
            },
        }

    mock_request.json = json

    # ACT:
    await webhook(mock_request)

    # ASSERT (Isto irá falhar com o código atual):
    # A assertiva é simples: a função de salvar foi chamada uma vez?
    mock_save_state.assert_called_once()

    # E ela foi chamada com os dados corretos que vieram do grafo?
    saved_phone_arg = mock_save_state.call_args[0][0]
    saved_state_arg = mock_save_state.call_args[0][1]

    assert saved_phone_arg == "12345"
    assert saved_state_arg["collected_data"].get("parent_name") == "Gabriel"
