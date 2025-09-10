"""
Tests for qualification_node logic and behavior.
Focuses on the beneficiary_type flow and variable collection.
"""
from unittest.mock import MagicMock, patch

from app.core.langgraph_flow import qualification_node


class TestQualificationNode:
    """Test suite for qualification_node behavior."""

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
        """
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
                        result = qualification_node(state_input)

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
                                saved_state = call_args[0][1]  # Segundo argumento (state dict)
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
                        
                        print(f"✅ REGRESSION TEST: Saudação 'Olá' não foi extraída como parent_name")


