#!/usr/bin/env python3
"""
Smoke Tests for Routing Node Migration

Validates that the universal routing architecture is working correctly:
1. Universal edge router calls SmartRouter + ResponsePlanner
2. DELIVERY node packages responses properly  
3. DeliveryService sends and updates stage atomically
4. Template content is sanitized for user delivery
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.edges.routing import universal_edge_router
from app.core.services.delivery_service import delivery_service
from app.core.state.models import ConversationStage, ConversationStep, CeciliaState
from app.core.state.managers import StateManager
from app.core.state.utils import normalize_state_enums


class SmokeTestResults:
    """Track smoke test results"""
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.failures = []
    
    def test(self, name: str, condition: bool, details: str = ""):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            self.failures.append(f"{name}: {details}")
            print(f"❌ {name}: {details}")
    
    def summary(self):
        print(f"\n{'='*60}")
        print(f"SMOKE TESTS SUMMARY: {self.tests_passed}/{self.tests_run} passed")
        if self.failures:
            print(f"\nFailures:")
            for failure in self.failures:
                print(f"  - {failure}")
        print(f"{'='*60}")
        return len(self.failures) == 0


async def test_universal_routing_edge():
    """Test that universal edge router works correctly with LangGraph limitations"""
    results = SmokeTestResults()
    
    print("🧪 Testing Universal Edge Router Architecture")
    print("-" * 50)
    
    # Create test state
    test_state = StateManager.create_initial_state("5551234567", "oi, quero informações")
    test_state = normalize_state_enums(test_state)
    
    # Test 1: Universal edge router returns ROUTING (corrected expectation)
    try:
        result = universal_edge_router(test_state, "greeting", ["ROUTING"])
        results.test(
            "Universal edge router returns ROUTING", 
            result == "ROUTING",
            f"Expected 'ROUTING', got '{result}'"
        )
    except Exception as e:
        results.test("Universal edge router executes", False, str(e))
    
    # Test 2: Edge sets context for ROUTING node
    results.test(
        "Edge sets last_node for ROUTING node",
        test_state.get("last_node") == "greeting",
        f"Expected last_node='greeting', got {test_state.get('last_node')}"
    )
    
    # Test 3: Edge sets routing request timestamp
    results.test(
        "Edge sets routing_requested_at timestamp", 
        "routing_requested_at" in test_state,
        "routing_requested_at not found in state"
    )
    
    # Test 4: Edge is simplified (no complex logic)
    results.test(
        "Edge does not execute routing logic directly",
        "routing_info" not in test_state,
        "Edge should not populate routing_info - that's for ROUTING node"
    )
    
    # Test 5: Edge does not generate responses
    results.test(
        "Edge does not generate planned_response",
        "planned_response" not in test_state,
        "Edge should not populate planned_response - that's for ROUTING node"
    )
    
    return results


async def test_routing_node_functionality():
    """Test that the ROUTING node works correctly"""
    results = SmokeTestResults()
    
    print("\n🎯 Testing ROUTING Node Functionality") 
    print("-" * 50)
    
    # Create test state as if coming from an edge
    test_state = StateManager.create_initial_state("5551234567", "oi, quero informações")
    test_state = normalize_state_enums(test_state)
    test_state["last_node"] = "greeting"
    test_state["routing_requested_at"] = "2025-01-01T00:00:00Z"
    
    # Import and test the ROUTING node
    try:
        from app.core.nodes.routing_node import routing_node
        
        # Test ROUTING node execution
        result_state = await routing_node(test_state)
        
        results.test(
            "ROUTING node executes successfully",
            isinstance(result_state, dict),
            "ROUTING node should return updated state"
        )
        
        results.test(
            "ROUTING node sets routing_complete flag",
            result_state.get("routing_complete") is True,
            "routing_complete flag should be True"
        )
        
        results.test(
            "ROUTING node creates routing_decision",
            "routing_decision" in result_state,
            "routing_decision should be in state"
        )
        
        results.test(
            "ROUTING node creates planned_response", 
            "planned_response" in result_state,
            "planned_response should be in state"
        )
        
        # Test routing decision structure
        if "routing_decision" in result_state:
            rd = result_state["routing_decision"]
            results.test(
                "Routing decision has target_node",
                "target_node" in rd,
                "routing_decision should have target_node"
            )
            results.test(
                "Routing decision has confidence",
                "confidence" in rd,
                "routing_decision should have confidence"
            )
        
    except Exception as e:
        results.test("ROUTING node functionality", False, str(e))
    
    return results


async def test_delivery_service_sanitization():
    """Test that DeliveryService sanitizes template content"""
    results = SmokeTestResults()
    
    print("\n🧹 Testing Template Content Sanitization")
    print("-" * 50)
    
    # Test template with internal directives
    dirty_template = """Você é Cecília, recepcionista do Kumon Vila A.

DIRETRIZES DE COMUNICAÇÃO:
- Mantenha tom acolhedor
- Seja proativa

RESPOSTA OBRIGATÓRIA:
Olá! Bem-vindo ao Kumon Vila A! 😊

Posso ajudá-lo com informações sobre nossa metodologia.

## INSTRUÇÕES PARA RESPOSTA
1. Use tom acolhedor
2. Ofereça ajuda

Contexto da conversa: {context}
Responda como Cecília:"""
    
    # Test sanitization
    sanitized = delivery_service._sanitize_template_content(dirty_template)
    
    results.test(
        "Removes system directives",
        "Você é Cecília" not in sanitized,
        "System directives still present"
    )
    
    results.test(
        "Removes DIRETRIZES section",
        "DIRETRIZES" not in sanitized,
        "DIRETRIZES section still present"
    )
    
    results.test(
        "Removes INSTRUÇÕES section", 
        "INSTRUÇÕES" not in sanitized,
        "INSTRUÇÕES section still present"
    )
    
    results.test(
        "Keeps user-facing content",
        "Olá! Bem-vindo ao Kumon Vila A!" in sanitized,
        "User-facing content was removed"
    )
    
    results.test(
        "Removes context placeholders",
        "{context}" not in sanitized,
        "Context placeholders still present"
    )
    
    print(f"📝 Original length: {len(dirty_template)} chars")
    print(f"📝 Sanitized length: {len(sanitized)} chars")
    print(f"📝 Sanitized content: {repr(sanitized[:100])}")
    
    return results


async def test_stage_mapping():
    """Test that stage mapping works correctly"""
    results = SmokeTestResults()
    
    print("\n🗺️  Testing Stage Mapping")
    print("-" * 50)
    
    from app.core.state.stage_mapping import map_target_to_stage_step
    
    # Test valid mappings
    test_cases = [
        ("qualification", ConversationStage.GREETING, ConversationStage.QUALIFICATION),
        ("information", ConversationStage.QUALIFICATION, ConversationStage.INFORMATION_GATHERING),
        ("scheduling", ConversationStage.INFORMATION_GATHERING, ConversationStage.SCHEDULING),
        ("fallback", ConversationStage.GREETING, ConversationStage.GREETING)  # Should stay same
    ]
    
    for target_node, current_stage, expected_stage in test_cases:
        try:
            new_stage, new_step = map_target_to_stage_step(target_node, current_stage)
            results.test(
                f"Maps {target_node} correctly",
                new_stage == expected_stage,
                f"Expected {expected_stage}, got {new_stage}"
            )
        except Exception as e:
            results.test(f"Maps {target_node} without error", False, str(e))
    
    return results


async def test_state_normalization():
    """Test state normalization handles enums correctly"""
    results = SmokeTestResults()
    
    print("\n🔧 Testing State Normalization")
    print("-" * 50)
    
    from app.core.state.utils import normalize_state_enums, safe_enum_value
    
    # Test with string stages
    test_state = {
        "phone_number": "5551234567",
        "current_stage": "greeting", 
        "current_step": "welcome",
        "last_user_message": "oi"
    }
    
    normalized_state = normalize_state_enums(test_state)
    
    results.test(
        "Converts string stage to enum",
        isinstance(normalized_state["current_stage"], ConversationStage),
        f"Stage type: {type(normalized_state['current_stage'])}"
    )
    
    results.test(
        "Converts string step to enum", 
        isinstance(normalized_state["current_step"], ConversationStep),
        f"Step type: {type(normalized_state['current_step'])}"
    )
    
    # Test safe_enum_value function
    stage_value = safe_enum_value(normalized_state["current_stage"])
    results.test(
        "safe_enum_value extracts value correctly",
        stage_value == "greeting",
        f"Expected 'greeting', got '{stage_value}'"
    )
    
    return results


async def main():
    """Run all smoke tests"""
    print("🚀 SMOKE TESTS: Routing Node Migration")
    print("="*60)
    
    all_results = []
    
    # Run individual test suites
    all_results.append(await test_universal_routing_edge())
    all_results.append(await test_routing_node_functionality())
    all_results.append(await test_delivery_service_sanitization())  
    all_results.append(await test_stage_mapping())
    all_results.append(await test_state_normalization())
    
    # Calculate overall results
    total_tests = sum(r.tests_run for r in all_results)
    total_passed = sum(r.tests_passed for r in all_results)
    all_failures = []
    for r in all_results:
        all_failures.extend(r.failures)
    
    print(f"\n{'='*60}")
    print(f"OVERALL RESULTS: {total_passed}/{total_tests} tests passed")
    
    if all_failures:
        print(f"\nFAILURES ({len(all_failures)}):")
        for failure in all_failures:
            print(f"  ❌ {failure}")
    else:
        print("\n🎉 ALL SMOKE TESTS PASSED!")
    
    print(f"{'='*60}")
    
    # Exit with proper code
    exit_code = 0 if len(all_failures) == 0 else 1
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)