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
            with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
                with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                    with patch("app.core.langgraph_flow.send_text") as mock_send:
                        # Mock do Redis retornando apenas parent_name
                        mock_get_state.return_value = {"parent_name": "Maria"}
                        mock_turn.has_replied.return_value = False
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
                        mock_get_state.assert_called_once_with("+5511999999999")
                        
                        # Should ask about beneficiary type
                        response = result.get("response", "").lower()
                        assert any(
                            phrase in response
                            for phrase in [
                                "para você mesmo",
                                "para outra pessoa", 
                                "beneficiário",
                                "para quem é"
                            ]
                        ), f"Should ask about beneficiary type, got: {response}"

    def test_qualification_updates_state_correctly_for_self_beneficiary(self):
        """Test que qualification salva beneficiary_type='self' e auto-preenche student_name no Redis."""
        # Entrada simulando resposta "para mim mesmo"
        state_input = {
            "text": "para mim",
            "phone": "+5511999999999",
            "message_id": "MSG_002",
            "instance": "test",
        }

        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.save_conversation_state") as mock_save:
                with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
                    with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                        with patch("app.core.langgraph_flow.send_text") as mock_send:
                            # Mock do Redis retornando parent_name já coletado
                            mock_get_state.return_value = {"parent_name": "Maria"}
                            mock_turn.has_replied.return_value = False
                            mock_send.return_value = {
                                "sent": "true", 
                                "status_code": 200,
                            }

                            mock_client = MagicMock()
                            # Mock que simula pergunta sobre idade após auto-fill
                            async def mock_chat(*args, **kwargs):
                                return "Perfeito Maria! Qual é a sua idade?"
                            mock_client.chat = mock_chat
                            mock_openai.return_value = mock_client

                            # Execute qualification_node
                            result = qualification_node(state_input)

                            # Verifica que save_conversation_state foi chamado
                            assert mock_save.called, "Should save state to Redis"
                            
                            # Verifica o estado salvo
                            save_call_args = mock_save.call_args
                            phone_number = save_call_args[0][0]
                            saved_state = save_call_args[0][1]
                            
                            assert phone_number == "+5511999999999", "Should save for correct phone"
                            assert saved_state.get("beneficiary_type") == "self", "Should save beneficiary_type=self"
                            assert saved_state.get("student_name") == "Maria", "Should auto-fill student_name with parent_name"
                            
                            # Should ask about age next
                            response = result.get("response", "").lower()
                            assert any(
                                word in response
                                for word in ["idade", "anos", "quantos anos"]
                            ), f"Should ask about age next, got: {response}"

    def test_qualification_autofills_student_name_when_beneficiary_is_self(self):
        """Test that qualification autofills student_name when beneficiary_type is self."""
        # State with parent_name and beneficiary response "para mim"  
        state_with_self = {
            "text": "para mim",
            "phone": "+5511999999999",
            "message_id": "MSG_002", 
            "instance": "test",
            "parent_name": "Maria",
            # Should extract beneficiary_type=self and auto-fill student_name
        }

        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
                with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                    with patch("app.core.langgraph_flow.send_text") as mock_send:
                        with patch("app.core.langgraph_flow.save_conversation_state") as mock_save:
                            # Setup mocks
                            mock_get_state.return_value = {"parent_name": "Maria"}
                            mock_turn.has_replied.return_value = False
                            mock_send.return_value = {
                                "sent": "true",
                                "status_code": 200,
                            }

                            mock_client = MagicMock()
                            # Create async mock
                            async def mock_chat(*args, **kwargs):
                                return "Perfeito Maria! Qual é a sua idade?"
                            mock_client.chat = mock_chat
                            mock_openai.return_value = mock_client

                            # Execute qualification_node
                            result = qualification_node(state_with_self)

                            # Check that save_conversation_state was called
                            assert mock_save.called, "Should save conversation state"
                            
                            # Get the state that was saved
                            save_call_args = mock_save.call_args
                            saved_state = save_call_args[0][1]  # Second argument is the state

                            # Should autofill student_name with parent_name
                            assert (
                                saved_state.get("student_name") == "Maria"
                            ), f"Should autofill student_name=Maria, got {saved_state.get('student_name')}"
                            
                            assert (
                                saved_state.get("beneficiary_type") == "self"
                            ), f"Should set beneficiary_type=self, got {saved_state.get('beneficiary_type')}"

                            # Should ask about age next
                            response = result.get("response", "").lower()
                            assert any(
                                word in response
                                for word in ["idade", "anos", "quantos anos"]
                            ), f"Should ask about age next, got: {response}"

    def test_qualification_updates_state_correctly_for_child_beneficiary(self):
        """Test que qualification salva beneficiary_type='child' e NÃO auto-preenche student_name."""
        # Entrada simulando resposta "para minha filha"
        state_input = {
            "text": "para minha filha",
            "phone": "+5511999999999",
            "message_id": "MSG_003",
            "instance": "test",
        }

        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.save_conversation_state") as mock_save:
                with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
                    with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                        with patch("app.core.langgraph_flow.send_text") as mock_send:
                            # Mock do Redis retornando parent_name já coletado
                            mock_get_state.return_value = {"parent_name": "Carlos"}
                            mock_turn.has_replied.return_value = False
                            mock_send.return_value = {
                                "sent": "true", 
                                "status_code": 200,
                            }

                            mock_client = MagicMock()
                            # Mock que simula pergunta sobre nome da criança
                            async def mock_chat(*args, **kwargs):
                                return "Carlos, qual é o nome da sua filha?"
                            mock_client.chat = mock_chat
                            mock_openai.return_value = mock_client

                            # Execute qualification_node
                            result = qualification_node(state_input)

                            # Verifica que save_conversation_state foi chamado
                            assert mock_save.called, "Should save state to Redis"
                            
                            # Verifica o estado salvo
                            save_call_args = mock_save.call_args
                            phone_number = save_call_args[0][0]
                            saved_state = save_call_args[0][1]
                            
                            assert phone_number == "+5511999999999", "Should save for correct phone"
                            assert saved_state.get("beneficiary_type") == "child", "Should save beneficiary_type=child"
                            assert not saved_state.get("student_name"), "Should NOT auto-fill student_name for child"
                            
                            # Should ask for student name
                            response = result.get("response", "").lower()
                            assert any(
                                word in response
                                for word in ["nome", "chama", "filha", "filho"]
                            ), f"Should ask for student name, got: {response}"

    def test_qualification_asks_student_name_when_beneficiary_is_child(self):
        """Test that qualification asks for student name when beneficiary_type is child."""
        # State with parent_name and beneficiary response "para minha filha"  
        state_with_child = {
            "text": "para minha filha",
            "phone": "+5511999999999",
            "message_id": "MSG_003", 
            "instance": "test",
            "parent_name": "Carlos",
            # Should extract beneficiary_type=child and ask for student_name
        }

        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
                with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                    with patch("app.core.langgraph_flow.send_text") as mock_send:
                        with patch("app.core.langgraph_flow.save_conversation_state") as mock_save:
                            # Setup mocks
                            mock_get_state.return_value = {"parent_name": "Carlos"}
                            mock_turn.has_replied.return_value = False
                            mock_send.return_value = {
                                "sent": "true",
                                "status_code": 200,
                            }

                            mock_client = MagicMock()
                            # Create async mock
                            async def mock_chat(*args, **kwargs):
                                return "Carlos, qual é o nome da sua filha?"
                            mock_client.chat = mock_chat
                            mock_openai.return_value = mock_client

                            # Execute qualification_node
                            result = qualification_node(state_with_child)

                            # Check that save_conversation_state was called
                            assert mock_save.called, "Should save conversation state"
                            
                            # Get the state that was saved
                            save_call_args = mock_save.call_args
                            saved_state = save_call_args[0][1]  # Second argument is the state
                            
                            assert (
                                saved_state.get("beneficiary_type") == "child"
                            ), f"Should set beneficiary_type=child, got {saved_state.get('beneficiary_type')}"

                            # Should NOT autofill student_name when beneficiary_type=child
                            assert not saved_state.get("student_name"), \
                                "Should NOT autofill student_name when beneficiary_type=child"

                            # Should ask for student name
                            response = result.get("response", "").lower()
                            assert any(
                                word in response
                                for word in ["nome", "chama", "filha", "filho"]
                            ), f"Should ask for student name, got: {response}"