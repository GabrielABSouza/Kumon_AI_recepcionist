# app/core/shadow_traffic_demo.py
"""
Shadow Traffic Demo - Demonstração do Sistema Shadow Traffic

Script demonstrativo para validar o funcionamento do shadow traffic:
- Execução paralela V1 + V2 shadow
- Logs comparativos 
- Métricas de performance
- Validação SLA (≥95% functional parity, handoff ≤3%, p95 latency ≤baseline+15%)
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from .feature_flags import feature_flags, shadow_traffic_manager
from .shadow_integration import shadow_integration
from .nodes.greeting_migrated import greeting_node_migrated
from .nodes.qualification_migrated import qualification_node_migrated

logger = logging.getLogger(__name__)


async def demonstrate_shadow_traffic():
    """
    Demonstra o funcionamento do shadow traffic com casos de teste
    """
    print("🌒 SHADOW TRAFFIC DEMONSTRATION")
    print("=" * 60)
    
    # Test cases
    test_scenarios = [
        {
            "name": "New Greeting - Missing Parent Name",
            "session_id": "demo_001",
            "state": {
                "session_id": "demo_001",
                "current_stage": "greeting",
                "last_user_message": "Olá, gostaria de informações sobre o Kumon",
                "outbox": []
            }
        },
        {
            "name": "Greeting Complete - Parent Name Provided",
            "session_id": "demo_002", 
            "state": {
                "session_id": "demo_002",
                "current_stage": "greeting",
                "parent_name": "Maria Santos",
                "last_user_message": "Meu nome é Maria Santos",
                "outbox": []
            }
        },
        {
            "name": "Qualification - Child Name and Age",
            "session_id": "demo_003",
            "state": {
                "session_id": "demo_003",
                "current_stage": "qualification",
                "parent_name": "João Silva",
                "last_user_message": "Minha filha chama Ana e tem 8 anos",
                "outbox": []
            }
        }
    ]
    
    # Check feature flags configuration
    print(f"📊 FEATURE FLAGS CONFIG:")
    print(f"   ROUTER_V2_ENABLED: {feature_flags.router_v2_enabled}")
    print(f"   ROUTER_V2_SHADOW: {feature_flags.router_v2_shadow}")
    print(f"   ROUTER_V2_PERCENTAGE: {feature_flags.router_v2_percentage}%")
    print(f"   V2_TIMEOUT_MS: {feature_flags.v2_timeout_ms}ms")
    print("")
    
    for scenario in test_scenarios:
        print(f"🧪 TEST: {scenario['name']}")
        print(f"   Session: {scenario['session_id']}")
        
        # Check architecture mode for this session
        architecture_mode = feature_flags.get_architecture_mode(scenario['session_id'])
        print(f"   Architecture Mode: {architecture_mode}")
        
        if architecture_mode == "v2_shadow":
            print(f"   ✅ Shadow Traffic Enabled - Running V1 + V2 Shadow")
            
            # Demonstrate shadow execution
            try:
                start_time = datetime.now()
                
                # Get original node function (simulated legacy V1)
                if scenario['state']['current_stage'] == 'greeting':
                    legacy_result = await simulate_legacy_greeting_node(scenario['state'])
                    v2_result = greeting_node_migrated(scenario['state'].copy())
                else:
                    legacy_result = await simulate_legacy_qualification_node(scenario['state'])
                    v2_result = qualification_node_migrated(scenario['state'].copy())
                
                end_time = datetime.now()
                latency_ms = (end_time - start_time).total_seconds() * 1000
                
                # Compare results
                print(f"   📈 V1 Legacy Result:")
                print(f"      current_step: {legacy_result.get('current_step', 'N/A')}")
                print(f"      status: {legacy_result.get('greeting_status', legacy_result.get('qualification_status', 'N/A'))}")
                
                print(f"   📉 V2 Shadow Result:")
                print(f"      current_step: {v2_result.get('current_step', 'N/A')}")
                print(f"      status: {v2_result.get('greeting_status', v2_result.get('qualification_status', 'N/A'))}")
                print(f"      latency: {latency_ms:.2f}ms")
                
                # Calculate comparison metrics
                steps_match = legacy_result.get('current_step') == v2_result.get('current_step')
                print(f"   🔍 Comparison: Steps Match = {steps_match}")
                
            except Exception as e:
                print(f"   ❌ Shadow Execution Error: {e}")
                
        elif architecture_mode == "v2_live":
            print(f"   🚀 V2 Live Mode - Using V2 Architecture")
            
        else:
            print(f"   🔄 V1 Only Mode - Legacy Architecture")
            
        print("")
    
    print("📋 SHADOW TRAFFIC TELEMETRY SAMPLE")
    print("=" * 60)
    print("Expected log format:")
    print("""
    INFO:root:SHADOW_V2: {
        "event_type": "shadow_v2_execution",
        "session_id": "demo_001",
        "user_message_hash": "a1b2c3d4e5f6",
        "original_stage": "greeting",
        "shadow_stage": "greeting", 
        "shadow_status": "success",
        "shadow_latency_ms": 45.2,
        "decision_comparison": {
            "original_target": "qualification",
            "shadow_target": "qualification",
            "decisions_match": true
        },
        "timestamp": "2025-01-09T10:30:45.123Z"
    }
    """)
    
    print("")
    print("🎯 SLA VALIDATION CRITERIA:")
    print("=" * 60)
    print("✅ Functional Parity: ≥95% (decisions_match rate)")
    print("✅ Handoff Rate: ≤3% (fallback to V1 due to V2 errors)")
    print("✅ Latency Impact: p95 ≤ baseline + 15% (shadow execution overhead)")
    print("✅ No Production Impact: V1 responses always served to users")
    
    print("")
    print("🔧 MANUAL TESTING COMMANDS:")
    print("=" * 60)
    print("# Enable shadow traffic (default)")
    print("export ROUTER_V2_ENABLED=false")
    print("export ROUTER_V2_SHADOW=true")
    print("export ROUTER_V2_PERCENTAGE=0")
    print("")
    print("# Enable V2 live for 10% of users")
    print("export ROUTER_V2_ENABLED=true")
    print("export ROUTER_V2_PERCENTAGE=10")
    print("")
    print("# Monitor shadow traffic logs")
    print("grep 'SHADOW_V2\\|SHADOW_COMPARISON' app.log | jq .")


async def simulate_legacy_greeting_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate legacy V1 greeting node behavior"""
    await asyncio.sleep(0.01)  # Simulate processing time
    
    parent_name = state.get("parent_name")
    
    if not parent_name:
        state["current_step"] = "initial_contact"
        state["greeting_status"] = "awaiting_parent_name"
    else:
        state["current_step"] = "name_collected"
        state["greeting_status"] = "completed"
    
    # Legacy nodes might add more fields
    state["legacy_greeting_processed"] = True
    
    return state


async def simulate_legacy_qualification_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate legacy V1 qualification node behavior"""
    await asyncio.sleep(0.015)  # Simulate processing time
    
    child_name = state.get("child_name") 
    student_age = state.get("student_age")
    
    if not child_name:
        state["current_step"] = "child_name_collection"
        state["qualification_status"] = "awaiting_child_name"
    elif not student_age:
        state["current_step"] = "age_collection"
        state["qualification_status"] = "awaiting_age"
    else:
        state["current_step"] = "qualification_complete"
        state["qualification_status"] = "completed"
    
    # Legacy qualification processing
    state["legacy_qualification_processed"] = True
    
    return state


if __name__ == "__main__":
    asyncio.run(demonstrate_shadow_traffic())