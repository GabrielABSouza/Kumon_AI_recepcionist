"""
🧪 TDD Test for master_router with structured NLU classifier.

This test validates that master_router correctly handles the new structured
NLU output from GeminiClassifier instead of the old (Intent, confidence) tupla.
"""
from unittest.mock import patch


def test_master_router_uses_structured_nlu_output():
    """
    🎯 TDD TEST: master_router should use new structured NLU format.

    This test ensures master_router correctly processes the new dict output:
    {
        "primary_intent": "qualification",
        "secondary_intent": "information",
        "entities": {"beneficiary_type": "child", "student_name": "João"},
        "confidence": 0.85
    }
    Instead of the old (Intent, confidence) tupla.
    """

    # Test state that will go to AI classification
    test_state = {
        "text": "Quero informações sobre o método",
        "phone": "+5511999999999",
        "message_id": "MSG_STRUCT_TEST",
    }

    # Expected structured NLU response
    structured_nlu_response = {
        "primary_intent": "information",
        "secondary_intent": None,
        "entities": {},
        "confidence": 0.85,
    }

    with patch("app.core.langgraph_flow.classify_intent") as mock_classify_intent:
        with patch("app.core.langgraph_flow.classifier.classify") as mock_classifier:
            # Setup: business rules return None (forces AI classification)
            mock_classify_intent.return_value = None

            # Setup: classifier returns new structured format
            mock_classifier.return_value = structured_nlu_response

            # Execute master_router
            from app.core.langgraph_flow import master_router

            result = master_router(test_state)

            # Validate: should route to information_node
            assert (
                result == "information_node"
            ), f"Expected 'information_node', got '{result}'"

            # Validate: classifier was called with correct parameters
            assert mock_classifier.called, "Classifier should be called"

            # Validate: classifier received text and context
            call_args = mock_classifier.call_args
            assert (
                call_args[0][0] == test_state["text"]
            ), "Text should be passed to classifier"

            print("✅ SUCCESS: master_router correctly uses structured NLU output")
            print(f"✅ Input: {test_state['text']}")
            print(f"✅ NLU Response: {structured_nlu_response}")
            print(f"✅ Routing Decision: {result}")


def test_master_router_handles_multi_intent_nlu():
    """
    🚀 ADVANCED TEST: master_router with multi-intent NLU response.

    Tests that master_router can handle complex NLU responses with
    primary and secondary intents plus extracted entities.
    """

    test_state = {
        "text": "É para o meu filho João. A propósito, quais são os horários?",
        "phone": "+5511888888888",
        "message_id": "MSG_MULTI_INTENT",
    }

    # Complex structured NLU with multi-intent + entities
    complex_nlu_response = {
        "primary_intent": "qualification",
        "secondary_intent": "information",
        "entities": {"beneficiary_type": "child", "student_name": "João"},
        "confidence": 0.9,
    }

    with patch("app.core.langgraph_flow.classify_intent") as mock_classify_intent:
        with patch("app.core.langgraph_flow.classifier.classify") as mock_classifier:
            mock_classify_intent.return_value = None
            mock_classifier.return_value = complex_nlu_response

            from app.core.langgraph_flow import master_router

            result = master_router(test_state)

            # Should route based on primary_intent
            assert (
                result == "qualification_node"
            ), f"Expected 'qualification_node' based on primary_intent, got '{result}'"

            print("✅ SUCCESS: master_router handles multi-intent NLU")
            print(f"✅ Primary Intent: {complex_nlu_response['primary_intent']}")
            print(f"✅ Secondary Intent: {complex_nlu_response['secondary_intent']}")
            print(f"✅ Entities: {complex_nlu_response['entities']}")
            print(f"✅ Final Routing: {result}")


if __name__ == "__main__":
    print("🧪 Running TDD tests for structured NLU in master_router...")

    try:
        test_master_router_uses_structured_nlu_output()
        test_master_router_handles_multi_intent_nlu()
        print("🎯 All tests PASSED! Ready to implement structured NLU in master_router.")
    except Exception as e:
        print(f"❌ Test FAILED as expected (TDD Red Phase): {e}")
        print("🔧 Now implement the structured NLU support in master_router.")
