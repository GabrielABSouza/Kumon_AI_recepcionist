"""
Tests for LangGraph flow transitions.
Ensures nodes transition correctly based on collected state.
"""
from unittest.mock import MagicMock, patch

from app.core.langgraph_flow import classify_intent, workflow, qualification_node, greeting_node, route_from_greeting


class TestFlowTransitions:
    """Test suite for graph node transitions."""

    def test_greeting_to_qualification_after_name_collected(self):
        """Test that greeting transitions to qualification after collecting name."""
        # State with parent_name already collected
        state_with_name = {
            "text": "Quero informações sobre matrícula",
            "phone": "+5511999999999",
            "message_id": "MSG_002",
            "instance": "test",
            "parent_name": "João",  # Name already collected
        }

        # The intent classification should consider the state
        # and route to qualification since we have the parent name
        next_node = classify_intent(state_with_name)

        # With parent_name present and asking about enrollment,
        # should go to qualification
        assert (
            next_node != "greeting_node"
        ), "Should not go back to greeting when name exists"

        # Test single turn execution (realistic webhook behavior)
        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
                with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                    with patch("app.core.langgraph_flow.send_text") as mock_send:
                        # Setup mocks
                        mock_get_state.return_value = {"parent_name": "João"}
                        mock_turn.has_replied.return_value = False
                        mock_send.return_value = {
                            "sent": "true",
                            "status_code": 200,
                        }

                        mock_client = MagicMock()
                        # Create async mock que simula pergunta sobre beneficiário
                        chat_called = False
                        async def mock_chat(*args, **kwargs):
                            nonlocal chat_called
                            chat_called = True
                            return "João, você está buscando o Kumon para você mesmo ou para outra pessoa?"
                        mock_client.chat = mock_chat
                        mock_openai.return_value = mock_client

                        # Execute single qualification_node (realistic single turn)
                        result = qualification_node(state_with_name)

                        # Should ask about beneficiary type
                        assert result.get("sent") == "true", "Should send message successfully"
                        # Mock should have been called
                        assert chat_called, "Should call OpenAI client"

    def test_greeting_stays_in_greeting_without_name(self):
        """Test that greeting stays in greeting node if name not collected."""
        # State without parent_name
        state_no_name = {
            "text": "Oi",
            "phone": "+5511999999999",
            "message_id": "MSG_001",
            "instance": "test",
        }

        # Should route to greeting since it's a greeting intent
        next_node = classify_intent(state_no_name)
        assert next_node == "greeting_node", "Should go to greeting for 'Oi'"

        # Even after greeting, if no name collected, should ask for it
        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
                with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                    with patch("app.core.langgraph_flow.send_text") as mock_send:
                        # No saved state (no name)
                        mock_get_state.return_value = {}
                        mock_turn.has_replied.return_value = False
                        mock_send.return_value = {
                            "sent": "true",
                            "status_code": 200,
                        }

                        mock_client = MagicMock()
                        # Create async mock
                        chat_called = False
                        async def mock_chat(*args, **kwargs):
                            nonlocal chat_called
                            chat_called = True
                            return (
                                "Olá! Eu sou a Cecília do Kumon Vila A. "
                                "Para começarmos qual é o seu nome?"
                            )
                        mock_client.chat = mock_chat
                        mock_openai.return_value = mock_client

                        # Execute single greeting_node (realistic single turn)
                        result = greeting_node(state_no_name)

                        # Should ask for name
                        assert result.get("sent") == "true", "Should send greeting successfully"
                        assert chat_called, "Should call OpenAI client"

    def test_direct_to_qualification_with_enrollment_intent(self):
        """Test direct routing to qualification with enrollment keywords."""
        state = {
            "text": "Quero fazer matrícula",
            "phone": "+5511999999999",
            "message_id": "MSG_003",
            "instance": "test",
        }

        # Should route to qualification based on keyword
        next_node = classify_intent(state)
        assert (
            next_node == "qualification_node"
        ), "Should route to qualification for 'matrícula'"

    def test_information_node_for_info_requests(self):
        """Test routing to information node for general questions."""
        state = {
            "text": "Quais são os horários?",
            "phone": "+5511999999999",
            "message_id": "MSG_004",
            "instance": "test",
        }

        # Should route to information based on keyword
        next_node = classify_intent(state)
        assert (
            next_node == "information_node"
        ), "Should route to information for 'horários'"

    def test_scheduling_node_for_visit_requests(self):
        """Test routing to scheduling node for visit requests."""
        state = {
            "text": "Posso agendar uma visita?",
            "phone": "+5511999999999",
            "message_id": "MSG_005",
            "instance": "test",
        }

        # Should route to scheduling based on keyword
        next_node = classify_intent(state)
        assert (
            next_node == "scheduling_node"
        ), "Should route to scheduling for 'agendar'"

    def test_fallback_for_unrecognized_intent(self):
        """Test routing to fallback for unrecognized messages."""
        state = {
            "text": "xyz abc 123",
            "phone": "+5511999999999",
            "message_id": "MSG_006",
            "instance": "test",
        }

        # Should route to fallback for unrecognized text
        next_node = classify_intent(state)
        assert (
            next_node == "fallback_node"
        ), "Should route to fallback for unrecognized text"

    def test_greeting_node_always_transitions_to_qualification(self):
        """Test that greeting_node always transitions to qualification_node."""
        # State with greeting intent
        greeting_state = {
            "text": "Oi",
            "phone": "+5511999999999",
            "message_id": "MSG_007",
            "instance": "test",
        }

        with patch("app.core.langgraph_flow.get_conversation_state") as mock_get_state:
            with patch("app.core.langgraph_flow.turn_controller") as mock_turn:
                with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
                    with patch("app.core.langgraph_flow.send_text") as mock_send:
                        # Setup mocks
                        mock_get_state.return_value = {}  # No existing state
                        mock_turn.has_replied.return_value = False
                        mock_send.return_value = {
                            "sent": "true",
                            "status_code": 200,
                        }

                        mock_client = MagicMock()

                        # Create async mock that returns a coroutine
                        chat_called = False
                        async def mock_chat(*args, **kwargs):
                            nonlocal chat_called
                            chat_called = True
                            return (
                                "Olá! Eu sou a Cecília do Kumon Vila A. "
                                "Para começarmos qual é o seu nome?"
                            )

                        mock_client.chat = mock_chat
                        mock_openai.return_value = mock_client

                        # Execute single greeting_node (realistic single turn)
                        result = greeting_node(greeting_state)

                        # Should process successfully without infinite recursion
                        assert result.get("sent") == "true", "Should send greeting successfully"
                        assert chat_called, "Should call OpenAI client"

                        # Test that routing works correctly
                        next_node_after_greeting = route_from_greeting(greeting_state)
                        assert next_node_after_greeting == "qualification_node", "Greeting should always route to qualification"

    def test_qualification_node_loops_if_required_data_is_missing(self):
        """Test that qualification_node loops back to itself if required data is missing."""
        # Test the routing function directly with partial data
        from app.core.langgraph_flow import route_from_qualification

        # State with only parent_name, missing beneficiary_type, student_name, 
        # student_age, program_interests
        state_partial = {
            "parent_name": "Maria",
            # Missing: beneficiary_type, student_name, student_age, program_interests
        }

        # Test routing decision with incomplete data
        next_node = route_from_qualification(state_partial)

        # Should loop back to qualification_node when data is missing
        assert next_node == "qualification_node", (
            f"Should loop back to qualification_node when required "
            f"data is missing, got {next_node}"
        )

    def test_qualification_node_transitions_when_all_data_is_collected(self):
        """Test that qualification_node transitions to next node when all required data is collected."""
        # Test the routing function directly with complete data
        from app.core.langgraph_flow import route_from_qualification

        # State with all required qualification data (new structure)
        state_complete = {
            "parent_name": "Maria",
            "beneficiary_type": "self",
            "student_name": "Maria",
            "student_age": 30,
            "program_interests": ["mathematics"],
        }

        # Test routing decision with complete data
        next_node = route_from_qualification(state_complete)

        # Should transition to scheduling_node when all qualification data is collected
        assert next_node == "scheduling_node", (
            f"Should transition to scheduling_node when all "
            f"qualification data is collected, got {next_node}"
        )

    def test_greeting_node_always_transitions_to_qualification_simplified(self):
        """Test that greeting_node ALWAYS transitions to qualification_node."""
        # Test the routing function directly
        from app.core.langgraph_flow import route_from_greeting

        # Test various states - all should go to qualification
        test_states = [
            {},  # Empty state
            {"parent_name": "Maria"},  # State with parent name
            {"text": "oi"},  # Simple greeting
            {
                "text": "quero matrícula",
                "parent_name": "João",
            },  # Enrollment interest with name
        ]

        for i, state in enumerate(test_states):
            next_node = route_from_greeting(state)  # type: ignore
            assert next_node == "qualification_node", (
                f"Test {i + 1}: All greeting states should go to "
                f"qualification_node, got {next_node}"
            )
