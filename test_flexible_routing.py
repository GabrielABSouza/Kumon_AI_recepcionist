#!/usr/bin/env python3
"""
Quick manual test of the flexible routing functionality.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import patch

from app.core.langgraph_flow import master_router


def test_flexible_routing_manually():
    """Test the flexible routing behavior manually."""

    print("🧪 Testing Flexible Routing Behavior...")

    # Test Case 1: Explicit information request during qualification
    print("\n1️⃣ Testing Explicit Intent Prioritization:")
    qualification_state = {
        "phone": "+5511999888777",
        "text": "Ok, mas antes de continuar, qual o valor da mensalidade?",
        "message_id": "MSG_EXPLICIT_INFO",
    }

    with patch("app.core.langgraph_flow.get_conversation_state") as mock_state, patch(
        "app.core.langgraph_flow.classifier.classify"
    ) as mock_classifier:
        # Mock qualification in progress
        mock_state.return_value = {
            "greeting_sent": True,
            "parent_name": "Maria",
            "student_name": None,  # Missing data = qualification should continue
        }

        # Mock AI detecting explicit information intent
        mock_classifier.return_value = {
            "primary_intent": "information",
            "secondary_intent": None,
            "entities": {},
            "confidence": 0.95,
        }

        result = master_router(qualification_state)
        print(f"   User: {qualification_state['text']}")
        print(f"   AI Classification: information (confidence: 0.95)")
        print(f"   Router Decision: {result}")

        if result == "information_node":
            print("   ✅ SUCCESS: Explicit intent honored!")
        else:
            print(f"   ❌ FAIL: Expected information_node, got {result}")

    # Test Case 2: Simple qualification continuation
    print("\n2️⃣ Testing Continuation Logic:")
    continuation_state = {
        "phone": "+5511888777666",
        "text": "Gabriel",
        "message_id": "MSG_CONTINUATION",
    }

    with patch("app.core.langgraph_flow.get_conversation_state") as mock_state2, patch(
        "app.core.langgraph_flow.classifier.classify"
    ) as mock_classifier2:
        # Mock qualification in progress
        mock_state2.return_value = {
            "greeting_sent": True,
            "parent_name": "Maria",
            "student_name": None,  # Expecting student name
        }

        # Mock AI detecting qualification response
        mock_classifier2.return_value = {
            "primary_intent": "qualification",
            "secondary_intent": None,
            "entities": {"student_name": "Gabriel"},
            "confidence": 0.85,
        }

        result = master_router(continuation_state)
        print(f"   User: {continuation_state['text']}")
        print(f"   AI Classification: qualification (confidence: 0.85)")
        print(f"   Router Decision: {result}")

        if result == "qualification_node":
            print("   ✅ SUCCESS: Continuation logic preserved!")
        else:
            print(f"   ❌ FAIL: Expected qualification_node, got {result}")


if __name__ == "__main__":
    test_flexible_routing_manually()
    print("\n🏆 Flexible routing test complete!")
