"""
Teste simples para verificar se a função fantasma foi corrigida.
"""
from unittest.mock import MagicMock, patch


def test_greeting_node_no_contamination():
    """Teste se greeting_node não contamina estado com parent_name."""

    from app.core.langgraph_flow import greeting_node

    # Estado limpo de entrada
    clean_state = {
        "text": "oi",
        "phone": "+5511999999999",
        "message_id": "MSG_TEST",
        "instance": "test",
    }

    # Redis contaminado (simulando bug anterior)
    contaminated_redis = {
        "parent_name": "Olá",  # 🚨 DADO CORROMPIDO
        "greeting_sent": False,
    }

    with patch("app.core.langgraph_flow.get_conversation_state") as mock_get:
        with patch("app.core.langgraph_flow.save_conversation_state") as mock_save:
            with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                with patch("app.core.langgraph_flow.send_text") as mock_send:
                    # Setup mocks com rastreamento completo
                    def mock_get_side_effect(phone):
                        print(
                            f"MOCK: get_conversation_state chamado para phone={phone}"
                        )
                        print(
                            f"MOCK: retornando estado contaminado: {contaminated_redis}"
                        )
                        return contaminated_redis

                    mock_get.side_effect = mock_get_side_effect

                    # Mock rastreamento das chamadas de save
                    def mock_save_side_effect(phone, state):
                        print(f"MOCK: save_conversation_state chamado!")
                        print(f"      phone={phone}")
                        print(f"      state={state}")
                        # Rastrear stack para saber de onde veio
                        import traceback

                        print("STACK TRACE:")
                        for line in traceback.format_stack()[-5:-1]:
                            print(f"      {line.strip()}")
                        return True

                    mock_save.side_effect = mock_save_side_effect
                    mock_send.return_value = {"sent": "true", "status_code": 200}

                    mock_client = MagicMock()

                    async def mock_chat(*args, **kwargs):
                        return "Olá! Como posso ajudar?"

                    mock_client.chat = mock_chat
                    mock_openai.return_value = mock_client

                    # Execute greeting_node - MONITORAR TUDO
                    print("=== EXECUTANDO greeting_node ===")
                    result = greeting_node(clean_state)
                    print(f"=== greeting_node RETORNOU: {result} ===")

                    # ANÁLISE: O que foi salvo?
                    print(f"Total de chamadas save: {mock_save.call_count}")

                    for i, call in enumerate(mock_save.call_args_list):
                        phone = call[0][0]
                        state = call[0][1]
                        print(f"Chamada {i+1}: phone={phone}, state={state}")

                        # CRÍTICO: greeting_node NÃO deve salvar parent_name=Olá
                        if "parent_name" in state and state["parent_name"] == "Olá":
                            print(
                                f"❌ FALHOU: greeting_node salvou parent_name={state['parent_name']}"
                            )
                            return False

                    print("✅ PASSOU: Nenhuma contaminação detectada")
                    return True


if __name__ == "__main__":
    success = test_greeting_node_no_contamination()
    if success:
        print("🎯 CORREÇÃO VALIDADA!")
    else:
        print("🚨 BUG AINDA EXISTE!")
