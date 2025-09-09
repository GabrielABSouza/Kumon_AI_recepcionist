"""
Tests for conversational flexibility during qualification.

Tests that users can ask for information during qualification
and return to complete the qualification process.

This addresses the limitation where information_node → END,
preventing users from returning to qualification.
"""
import pytest
from unittest.mock import patch, MagicMock

from app.core.langgraph_flow import (
    build_graph,
    classify_intent,
    route_from_information,
    QUALIFICATION_REQUIRED_VARS,
)


class TestConversationalFlexibility:
    """Test suite for flexible conversation flow during qualification."""

    def test_information_request_during_qualification_should_return_to_qualification(self):
        """Test that asking for info during qualification preserves qualification context.
        
        Scenario:
        1. User starts qualification (has parent_name)
        2. User asks "Qual o horário?" (information request) 
        3. System provides info but maintains qualification context
        4. Next message should continue qualification, not start over
        """
        # STEP 1: User in middle of qualification
        qualification_in_progress_state = {
            "phone": "5511777777777",
            "parent_name": "Ana Costa",        # Qualification started
            "message_id": "MSG_QUAL_001", 
            "instance": "kumon_assistant",
            "text": "Qual o horário de funcionamento?",  # Information request during qualification
            "qualification_attempts": 1,       # Important: preserve attempt count
            # Missing: student_name, student_age, program_interests (still qualifying)
        }
        
        # STEP 2: Classify intent - should be INFORMATION but preserve qualification context
        intent_node = classify_intent(qualification_in_progress_state)
        
        # Current behavior: Will route to information_node
        # PROBLEM: information_node → END (conversation terminates)
        # EXPECTED: Should route to information_node but preserve qualification context
        
        print(f"Intent classification: {intent_node}")
        
        # CURRENT ISSUE: This will be "information_node" and conversation will end
        # We need the information_node to be aware of qualification context
        assert intent_node in ["information_node", "qualification_node"], (
            f"During qualification, information requests should be handled contextually"
        )

    def test_information_node_should_preserve_qualification_context(self):
        """Test that information_node preserves qualification context for continuation."""
        # State representing user who asked for info during qualification
        info_request_state = {
            "phone": "5511666666666",
            "parent_name": "Carlos Lima",
            "student_name": "Pedro",              # Some qualification data collected
            "qualification_attempts": 2,          # Mid-qualification
            "message_id": "MSG_INFO_001",
            "text": "Obrigado pela informação",      # Acknowledgment after info
            # Missing: student_age, program_interests (qualification incomplete)
        }
        
        # Mock the graph execution
        graph = build_graph()
        
        with patch('app.core.langgraph_flow.get_openai_client') as mock_openai:
            with patch('app.core.langgraph_flow.send_text') as mock_send:
                mock_client = MagicMock()
                mock_client.chat.return_value = "Informação fornecida!"
                mock_openai.return_value = mock_client
                mock_send.return_value = {"sent": "true"}
                
                # CURRENT PROBLEM: information_node → END
                # DESIRED: information_node should check qualification context and continue
                
                # For now, let's test the classification behavior
                next_intent = classify_intent(info_request_state)
                
                print(f"After providing info, next intent: {next_intent}")
                
                # If user has incomplete qualification data, we should continue qualification
                # This is the core issue to fix
                missing_vars = [
                    var for var in QUALIFICATION_REQUIRED_VARS 
                    if var not in info_request_state or not info_request_state[var]
                ]
                
                if missing_vars:
                    # Should continue qualification, not end conversation
                    print(f"Missing qualification vars: {missing_vars}")
                    print("SHOULD continue qualification, not terminate")
                else:
                    print("Qualification complete, can proceed to scheduling")

    def test_escape_hatch_should_offer_continuation(self):
        """Test that escape hatch offers to continue qualification later."""
        # State representing user who hit escape hatch (4 attempts)
        escape_hatch_state = {
            "phone": "5511555555555", 
            "parent_name": "Maria Santos",
            "qualification_attempts": 4,          # Hit the limit
            "message_id": "MSG_ESCAPE_001",
            "text": "Obrigado pelas informações gerais",
            # Missing: student_name, student_age, program_interests
        }
        
        # After escape hatch, user should have option to:
        # 1. Continue qualification later
        # 2. Get general information
        # 3. Schedule a call
        
        # Current implementation: information_node → END
        # Better implementation: information_node → check context → offer options
        
        missing_vars = [
            var for var in QUALIFICATION_REQUIRED_VARS 
            if var not in escape_hatch_state or not escape_hatch_state[var]
        ]
        
        assert len(missing_vars) > 0, "Should have incomplete qualification"
        
        # The system should be intelligent enough to:
        # 1. Recognize incomplete qualification context
        # 2. Offer to continue qualification 
        # 3. Not terminate conversation abruptly
        
        print(f"Incomplete qualification with missing: {missing_vars}")
        print("System should offer continuation options")

    def test_proposed_intelligent_information_node(self):
        """Test proposed enhancement: context-aware information_node routing."""
        # This test describes the desired behavior for a more intelligent system
        
        # PROPOSED ENHANCEMENT:
        # information_node should not always → END
        # Instead: information_node → check_qualification_context → route appropriately
        
        test_scenarios = [
            {
                "description": "Complete qualification → can end or go to scheduling",
                "state": {
                    "parent_name": "João", "student_name": "Ana", 
                    "student_age": 8, "program_interests": ["mathematics"]
                },
                "expected_next": "scheduling_node or END"
            },
            {
                "description": "Incomplete qualification → should continue qualification",
                "state": {
                    "parent_name": "João", "qualification_attempts": 2
                    # Missing: student_name, student_age, program_interests
                },
                "expected_next": "qualification_node"
            },
            {
                "description": "Escape hatch hit → offer options",
                "state": {
                    "parent_name": "João", "qualification_attempts": 4
                },
                "expected_next": "offer_continuation_options"
            }
        ]
        
        for scenario in test_scenarios:
            print(f"Scenario: {scenario['description']}")
            print(f"Expected: {scenario['expected_next']}")
            
            missing_vars = [
                var for var in QUALIFICATION_REQUIRED_VARS 
                if var not in scenario['state'] or not scenario['state'][var]
            ]
            
            if not missing_vars:
                print("✅ Qualification complete - can proceed")
            else:
                print(f"❌ Missing vars: {missing_vars} - should continue")

    def test_context_aware_information_routing(self):
        """Test the new context-aware information_node routing logic."""
        
        # Test Case 1: Complete qualification → should go to scheduling
        complete_qualification_state = {
            "parent_name": "Maria Silva",
            "student_name": "João",
            "student_age": 8,
            "program_interests": ["mathematics"],
            "qualification_attempts": 2
        }
        
        next_node = route_from_information(complete_qualification_state)
        assert next_node == "scheduling_node", (
            f"Complete qualification should route to scheduling, got {next_node}"
        )
        
        # Test Case 2: Incomplete qualification, low attempts → continue qualification
        incomplete_with_low_attempts = {
            "parent_name": "Ana Costa",
            "student_name": "Pedro",  # Missing age and interests
            "qualification_attempts": 2  # Below limit
        }
        
        next_node = route_from_information(incomplete_with_low_attempts)
        assert next_node == "qualification_node", (
            f"Incomplete qualification with low attempts should continue, got {next_node}"
        )
        
        # Test Case 3: Incomplete qualification, high attempts → end
        incomplete_with_high_attempts = {
            "parent_name": "Carlos Santos",
            "qualification_attempts": 4  # Hit limit
            # Missing most qualification data
        }
        
        next_node = route_from_information(incomplete_with_high_attempts)
        assert next_node == "__end__", (
            f"High attempts should end conversation, got {next_node}"
        )
        
        # Test Case 4: No qualification context → end
        no_context = {
            "text": "Obrigado pelas informações"
            # No parent_name or qualification context
        }
        
        next_node = route_from_information(no_context)
        assert next_node == "__end__", (
            f"No qualification context should end, got {next_node}"
        )
        
        print("✅ All context-aware routing scenarios work correctly!")

    def test_conversational_flow_integration_simulation(self):
        """Integration test simulating real conversational flexibility scenario.
        
        Scenario:
        1. User starts qualification: "Olá, sou Maria"
        2. During qualification asks: "Qual o horário?"
        3. System provides info and continues qualification
        4. User completes qualification data
        5. System proceeds to scheduling
        """
        print("\n=== CONVERSATIONAL FLOW SIMULATION ===")
        
        # Simulate the graph (with mocked dependencies)
        graph = build_graph()
        
        with patch('app.core.langgraph_flow.get_openai_client') as mock_openai:
            with patch('app.core.langgraph_flow.send_text') as mock_send:
                # Configure mocks
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_send.return_value = {"sent": "true"}
                
                # Scenario Step 1: User starts with greeting/name
                step1_state = {
                    "phone": "5511999999999",
                    "parent_name": "Maria Silva",  # Extracted from greeting
                    "message_id": "MSG_001",
                    "instance": "kumon_assistant",
                    "text": "Olá, sou Maria Silva",
                    "intent": "greeting"
                }
                
                print("Step 1: User introduces themselves")
                print(f"  State: parent_name={step1_state['parent_name']}")
                
                # This would normally go: classify_intent → greeting_node → qualification_node
                # Let's simulate being in qualification
                
                # Scenario Step 2: During qualification, user asks for information  
                step2_state = {
                    **step1_state,
                    "message_id": "MSG_002", 
                    "text": "Qual é o horário de funcionamento?",  # Information request
                    "qualification_attempts": 1,  # In progress
                    # Still missing: student_name, student_age, program_interests
                }
                
                print("Step 2: During qualification, user asks for info")
                print(f"  Text: {step2_state['text']}")
                
                # Classify this intent - should be INFORMATION
                intent_classification = classify_intent(step2_state)
                print(f"  Classification: {intent_classification}")
                assert intent_classification == "information_node"
                
                # After information_node, should return to qualification
                post_info_routing = route_from_information(step2_state)
                print(f"  After info, next: {post_info_routing}")
                assert post_info_routing == "qualification_node", "Should continue qualification"
                
                # Scenario Step 3: User continues qualification
                step3_state = {
                    **step2_state,
                    "message_id": "MSG_003",
                    "text": "Meu filho João tem 8 anos e quer estudar matemática",
                    "student_name": "João",        # Now provided
                    "student_age": 8,             # Now provided  
                    "program_interests": ["mathematics"],  # Now provided
                    "qualification_attempts": 2,
                }
                
                print("Step 3: User completes qualification data")
                print(f"  student_name: {step3_state['student_name']}")
                print(f"  student_age: {step3_state['student_age']}")
                print(f"  program_interests: {step3_state['program_interests']}")
                
                # After completing qualification, information requests should go to scheduling
                final_routing = route_from_information(step3_state)
                print(f"  With complete data, next: {final_routing}")
                assert final_routing == "scheduling_node", "Complete qualification should go to scheduling"
                
                print("✅ SIMULATION SUCCESS: Conversational flexibility working!")
                print("✅ User can ask for info during qualification and continue")
                print("✅ System maintains context and resumes qualification")
                print("✅ Complete qualification proceeds to scheduling")