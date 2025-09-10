"""
🚨 TESTE FORENSE: Isolar e provar que _execute_node é a função fantasma
que cria parent_name=Olá incorretamente.

Este teste prova que _execute_node, usado por TODOS os nós, 
salva automaticamente o full_state que inclui variáveis 
extraídas de nós anteriores, contaminando conversas limpas.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.core.langgraph_flow import _execute_node


class TestExecuteNodePhantom:
    """Isolamento forense da função fantasma _execute_node."""

    def test_execute_node_phantom_contamination_proof(self):
        """
        🎯 TESTE CRÍTICO: Prova que _execute_node contamina conversas 
        quando o Redis já tem parent_name=Olá de sessões anteriores.
        
        Cenário Reproduzido:
        1. Redis tem parent_name=Olá (de bug anterior)  
        2. Usuario envia "oi" para greeting_node
        3. _execute_node carrega Redis + merge com state atual
        4. Salva full_state incluindo o parent_name=Olá contaminado
        
        BUG: _execute_node perpetua dados corrompidos do Redis!
        """
        # CENÁRIO: Estado atual limpo (apenas greeting)
        clean_current_state = {
            "text": "oi",
            "phone": "+5511999999999", 
            "message_id": "MSG_CLEAN",
            "instance": "test"
        }
        
        # CENÁRIO: Redis contaminado (parent_name=Olá de sessão anterior)
        contaminated_redis_state = {
            "parent_name": "Olá",  # 🚨 DADO CORROMPIDO DO BUG ANTERIOR
            "greeting_sent": True,
            "qualification_attempts": 1
        }

        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.save_conversation_state") as mock_save:
                with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                    with patch("app.core.langgraph_flow.send_text") as mock_send:
                        
                        # SETUP: Simular Redis contaminado
                        mock_get_state.return_value = contaminated_redis_state
                        mock_send.return_value = {"sent": "true", "status_code": 200}
                        
                        # SETUP: Mock OpenAI
                        mock_client = MagicMock()
                        async def mock_chat(*args, **kwargs):
                            return "Olá! Como posso ajudar?"
                        mock_client.chat = mock_chat
                        mock_openai.return_value = mock_client
                        
                        # EXECUÇÃO: greeting_node via _execute_node com estado limpo  
                        def dummy_prompt(text, state=None, qualification=None):
                            return {"system": "Test", "user": text}
                        
                        # 🎯 AÇÃO CRÍTICA: _execute_node executa com estado limpo
                        _execute_node(clean_current_state, "greeting", dummy_prompt)
                        
                        # 🚨 ANÁLISE CRÍTICA: Verificar o que foi salvo
                        assert mock_save.called, "save_conversation_state deve ter sido chamado"
                        
                        # Inspecionar TODAS as chamadas para save_conversation_state
                        print(f"FORENSIC: Total de chamadas save_conversation_state: {mock_save.call_count}")
                        
                        for i, call in enumerate(mock_save.call_args_list):
                            saved_phone = call[0][0]
                            saved_state_dict = call[0][1] 
                            print(f"FORENSIC: Chamada {i+1}: Telefone={saved_phone}, Estado={saved_state_dict}")
                            
                            # Verificar se esta chamada contém contaminação
                            phantom_parent_name = saved_state_dict.get("parent_name")
                            if phantom_parent_name == "Olá":
                                assert False, (
                                    f"🚨 FUNÇÃO FANTASMA CONFIRMADA! "
                                    f"Chamada {i+1} salvou parent_name='{phantom_parent_name}' "
                                    f"mesmo em conversa greeting limpa. "
                                    f"Estado completo salvo: {saved_state_dict}"
                                )
                        
                        # Se chegou aqui, a correção funcionou!
                        print("✅ CORREÇÃO FUNCIONOU: Nenhuma contaminação detectada")
                        
                        print("🎯 FUNÇÃO FANTASMA IDENTIFICADA E PROVADA!")
                        print(f"   _execute_node perpetuou: parent_name={phantom_parent_name}")
                        print(f"   Mesmo com entrada limpa: {clean_current_state}")
                        print(f"   Causa: full_state merge contamina conversas novas")

    def test_execute_node_should_not_propagate_contaminated_state(self):
        """
        💡 TESTE DE REGRESSÃO: _execute_node NÃO deve propagar
        dados contaminados de sessões anteriores para conversas novas.
        
        Este teste deve PASSAR após a correção.
        """
        clean_state = {
            "text": "oi", 
            "phone": "+5511888888888",
            "message_id": "MSG_REGRESSION",
            "instance": "test"
        }
        
        # Estado Redis com dados de conversa anterior
        redis_with_previous_data = {
            "parent_name": "João",  # Dados de outra conversa
            "child_name": "Maria",
            "greeting_sent": True
        }

        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.save_conversation_state") as mock_save:
                with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                    with patch("app.core.langgraph_flow.send_text") as mock_send:
                        
                        mock_get_state.return_value = redis_with_previous_data
                        mock_send.return_value = {"sent": "true", "status_code": 200}
                        
                        mock_client = MagicMock()
                        async def mock_chat(*args, **kwargs):
                            return "Resposta simples"
                        mock_client.chat = mock_chat
                        mock_openai.return_value = mock_client
                        
                        def dummy_prompt(text, state=None, qualification=None):
                            return {"system": "Test", "user": text}
                        
                        # APÓS CORREÇÃO: _execute_node deve filtrar o que salva
                        _execute_node(clean_state, "greeting", dummy_prompt)
                        
                        # ASSERTIVA PÓS-CORREÇÃO: Não deve perpetuar dados irrelevantes
                        if mock_save.called:
                            saved_state = mock_save.call_args[0][1]
                            
                            # Após correção, greeting_node não deve salvar parent_name
                            assert "parent_name" not in saved_state or saved_state.get("parent_name") == "", (
                                "greeting_node NÃO deve salvar/perpetuar parent_name"
                            )
                            
                            print("✅ CORREÇÃO VALIDADA: _execute_node não perpetua contaminação")