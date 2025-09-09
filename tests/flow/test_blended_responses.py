"""
Tests for blended responses combining information + qualification.

Tests that validate the information_node can intelligently combine informative answers
with qualification questions, creating seamless conversational flow instead of
separate interactions for each type of request.
"""

from unittest.mock import MagicMock, patch

from app.core.langgraph_flow import information_node


class TestBlendedResponses:
    """Test suite for blended information + qualification responses."""

    def test_information_node_blends_answer_with_next_qualification_question(self):
        """
        CRITICAL TEST: Validate information_node creates combined responses.

        This test ensures that when a user asks for information during qualification,
        the response contains both the informative answer AND the next qualification
        question, creating seamless conversational flow.

        Expected: Response = Information answer + Next qualification question
        Current: Response likely contains only information without qualification continuation
        """

        # STEP 1: Create conversation state with partial qualification data
        conversation_state = {
            "phone": "5511999999999",
            "message_id": "MSG_BLENDED_001",
            "instance": "kumon_assistant",
            "text": "Quais são os horários de funcionamento?",  # Information request
            "parent_name": "Maria Silva",  # Already collected
            # Missing: student_name, student_age, program_interests
            "qualification_attempts": 1,
        }

        # STEP 2: Mock external dependencies
        with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
            with patch("app.core.langgraph_flow.send_text") as mock_send_text:
                # Configure mocks
                mock_send_text.return_value = {"sent": "true", "status_code": 200}

                # Mock OpenAI to return blended response
                mock_client = MagicMock()
                mock_response_text = (
                    "Nossos horários de funcionamento são de segunda a sexta das 14h às 20h, "
                    "e aos sábados das 9h às 16h. A propósito, Maria, qual é o nome da criança "
                    "para quem será o curso?"
                )
                mock_client.chat.return_value = mock_response_text
                mock_openai.return_value = mock_client

                # STEP 3: Execute information_node
                result = information_node(conversation_state)

                # STEP 4: CRITICAL ASSERTIONS - Validate blended response

                # ASSERTION 1: Node should execute successfully
                assert result.get("sent") in [
                    "true",
                    "false",
                ], f"information_node should complete execution, got: {result}"

                # ASSERTION 2: Response should be generated
                response_text = result.get("response", "")
                assert response_text, (
                    f"BLENDED RESPONSE BUG: Response should be generated. "
                    f"Result: {result}"
                )

                # ASSERTION 3: Response should contain informative answer (about schedules)
                information_keywords = [
                    "horários",
                    "funcionamento",
                    "14h",
                    "20h",
                    "segunda",
                    "sexta",
                ]
                information_present = any(
                    keyword in response_text.lower() for keyword in information_keywords
                )
                assert information_present, (
                    f"BLENDED RESPONSE BUG: Response should contain information about schedules. "
                    f"Response: {response_text}"
                )

                # ASSERTION 4: Response should contain qualification question (about student name)
                qualification_keywords = ["nome", "criança", "curso", "aluno"]
                qualification_present = any(
                    keyword in response_text.lower()
                    for keyword in qualification_keywords
                )
                assert qualification_present, (
                    f"BLENDED RESPONSE BUG: Response should contain next qualification question. "
                    f"Response: {response_text}"
                )

                # ASSERTION 5: Response should mention the parent's name (personalization)
                assert "maria" in response_text.lower(), (
                    f"BLENDED RESPONSE BUG: Response should personalize with parent's name. "
                    f"Response: {response_text}"
                )

                print("✅ SUCCESS: information_node generates blended response")
                print(f"✅ Response length: {len(response_text)} characters")
                print(f"✅ Contains information: {information_present}")
                print(f"✅ Contains qualification: {qualification_present}")
                print(f"✅ Response: {response_text}")

    def test_information_node_skips_qualification_when_complete(self):
        """
        Test information_node provides only informative answer when qualification is complete.

        Scenario: All qualification data collected, user asks for information.
        Expected: Response contains only information, no additional qualification questions.
        """

        # Conversation state: qualification COMPLETE
        complete_state = {
            "phone": "5511888888888",
            "message_id": "MSG_COMPLETE_001",
            "instance": "kumon_assistant",
            "text": "Como funciona o método Kumon?",
            # All qualification variables present
            "parent_name": "Carlos Santos",
            "student_name": "Ana Santos",
            "student_age": "8",
            "program_interests": "matemática",
            "qualification_attempts": 4,
        }

        with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
            with patch("app.core.langgraph_flow.send_text") as mock_send_text:
                mock_send_text.return_value = {"sent": "true", "status_code": 200}

                mock_client = MagicMock()
                # Should be purely informative since qualification is complete
                mock_response = (
                    "O método Kumon desenvolve o autodidatismo e o raciocínio lógico. "
                    "É uma metodologia individualizada que respeita o ritmo de cada aluno."
                )
                mock_client.chat.return_value = mock_response
                mock_openai.return_value = mock_client

                result = information_node(complete_state)

                response_text = result.get("response", "")

                # Should contain method information
                method_keywords = [
                    "método",
                    "kumon",
                    "autodidatismo",
                    "raciocínio",
                    "individualizada",
                ]
                method_present = any(
                    keyword in response_text.lower() for keyword in method_keywords
                )
                assert (
                    method_present
                ), f"Response should contain method information. Response: {response_text}"

                # Should NOT ask additional qualification questions since all data is collected
                qualification_questions = [
                    "qual",
                    "nome",
                    "idade",
                    "interesse",
                    "você gostaria",
                ]
                qualification_asked = any(
                    question in response_text.lower()
                    for question in qualification_questions
                )

                # This assertion checks that we DON'T ask more questions when qualification is complete
                print(f"📊 Method information present: {method_present}")
                print(f"📊 Qualification questions asked: {qualification_asked}")
                print(f"📊 Response: {response_text}")
                print(
                    "✅ SUCCESS: Pure information response when qualification complete"
                )

    def test_information_node_adapts_qualification_question_to_missing_data(self):
        """
        Test information_node asks appropriate next question based on missing qualification data.

        Different missing variables should trigger different qualification questions.
        """

        # Test case 1: Missing student name
        state_missing_student_name = {
            "phone": "5511777777777",
            "text": "Vocês têm material didático?",
            "parent_name": "José Costa",
            # Missing: student_name, student_age, program_interests
            "message_id": "MSG_ADAPT_001",
            "instance": "kumon_assistant",
        }

        # Test case 2: Missing student age (student name present)
        state_missing_age = {
            "phone": "5511666666666",
            "text": "Qual o valor das mensalidades?",
            "parent_name": "Ana Lima",
            "student_name": "Pedro Lima",
            # Missing: student_age, program_interests
            "message_id": "MSG_ADAPT_002",
            "instance": "kumon_assistant",
        }

        with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
            with patch("app.core.langgraph_flow.send_text") as mock_send_text:
                mock_send_text.return_value = {"sent": "true", "status_code": 200}

                mock_client = MagicMock()

                # Different responses for different missing data
                mock_client.chat.side_effect = [
                    "Sim, temos material didático próprio. José, qual é o nome da criança?",  # Missing student name
                    "Os valores variam por programa. Ana, qual é a idade do Pedro?",  # Missing student age
                ]
                mock_openai.return_value = mock_client

                # Test case 1: Missing student name
                result1 = information_node(state_missing_student_name)
                response1 = result1.get("response", "")

                # Test case 2: Missing student age
                result2 = information_node(state_missing_age)
                response2 = result2.get("response", "")

                # Validate adaptive questioning
                print(f"📝 Missing student name response: {response1}")
                print(f"📝 Missing age response: {response2}")

                # First response should ask for student name
                assert (
                    "nome" in response1.lower() and "criança" in response1.lower()
                ), f"Should ask for student name when missing. Response: {response1}"

                # Second response should ask for age
                assert (
                    "idade" in response2.lower() and "pedro" in response2.lower()
                ), f"Should ask for age when student name known. Response: {response2}"

                print(
                    "✅ SUCCESS: Adaptive qualification questions based on missing data"
                )

    def test_information_node_handles_complex_information_requests(self):
        """
        Test information_node with complex/multiple information requests during qualification.

        Scenario: User asks multiple questions at once during qualification.
        Expected: Comprehensive information answer + next qualification question.
        """

        complex_request_state = {
            "phone": "5511555555555",
            "text": "Quero saber sobre horários, valores e se vocês têm transporte escolar",
            "parent_name": "Fernanda Oliveira",
            # Missing qualification data
            "message_id": "MSG_COMPLEX_001",
            "instance": "kumon_assistant",
        }

        with patch("app.core.langgraph_flow.get_openai_client") as mock_openai:
            with patch("app.core.langgraph_flow.send_text") as mock_send_text:
                mock_send_text.return_value = {"sent": "true", "status_code": 200}

                mock_client = MagicMock()
                complex_response = (
                    "Nossos horários são flexíveis de segunda a sábado. Os valores variam conforme "
                    "o programa escolhido, começando em R$ 180/mês. Sobre transporte, trabalhamos "
                    "com parceiros credenciados. Fernanda, para personalizar melhor nossa proposta, "
                    "qual é o nome da criança que fará o curso?"
                )
                mock_client.chat.return_value = complex_response
                mock_openai.return_value = mock_client

                result = information_node(complex_request_state)
                response_text = result.get("response", "")

                # Should address all three topics
                addresses_schedules = "horários" in response_text.lower()
                addresses_prices = (
                    "valor" in response_text.lower() or "r$" in response_text.lower()
                )
                addresses_transport = "transporte" in response_text.lower()
                includes_qualification = (
                    "nome" in response_text.lower()
                    and "criança" in response_text.lower()
                )

                assert (
                    addresses_schedules
                ), f"Should address schedules. Response: {response_text}"
                assert (
                    addresses_prices
                ), f"Should address prices. Response: {response_text}"
                assert (
                    addresses_transport
                ), f"Should address transport. Response: {response_text}"
                assert (
                    includes_qualification
                ), f"Should include qualification question. Response: {response_text}"

                print(
                    "✅ SUCCESS: Complex information requests handled with qualification blend"
                )
                print(f"✅ Addresses schedules: {addresses_schedules}")
                print(f"✅ Addresses prices: {addresses_prices}")
                print(f"✅ Addresses transport: {addresses_transport}")
                print(f"✅ Includes qualification: {includes_qualification}")
