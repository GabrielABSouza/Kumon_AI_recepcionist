#!/usr/bin/env python3
"""
End-to-End Smoke Test for Production Deployment
Validates complete message flow with observability traces
"""
import os
import sys
import time
import json
import requests
import subprocess
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class E2ETestResult:
    success: bool
    message: str
    details: Optional[Dict] = None
    logs_captured: Optional[List[str]] = None

class SmokeTestE2E:
    """End-to-End smoke test for production deployment"""
    
    def __init__(self, log_file: str = "app.log", evolution_api_base: str = "http://localhost:8080"):
        self.log_file = log_file
        self.evolution_api_base = evolution_api_base
        self.test_phone = None  # Will be set from environment
        self.instance_name = "kumon_assistant"
        
    def setup_test_environment(self) -> E2ETestResult:
        """Setup test environment and validate prerequisites"""
        # Check Evolution API connectivity
        try:
            response = requests.get(f"{self.evolution_api_base}/instance/{self.instance_name}", timeout=10)
            if response.status_code != 200:
                return E2ETestResult(
                    success=False,
                    message=f"❌ Evolution API instance {self.instance_name} not accessible: {response.status_code}",
                    details={"response": response.text}
                )
        except Exception as e:
            return E2ETestResult(
                success=False,
                message=f"❌ Cannot connect to Evolution API: {str(e)}"
            )
        
        # Check test phone number
        self.test_phone = os.getenv("SMOKE_TEST_PHONE")
        if not self.test_phone:
            return E2ETestResult(
                success=False,
                message="❌ SMOKE_TEST_PHONE environment variable not set"
            )
        
        # Clear previous logs
        try:
            with open(self.log_file, "w") as f:
                f.write(f"# Smoke Test E2E Started - {datetime.now()}\n")
        except Exception as e:
            return E2ETestResult(
                success=False,
                message=f"❌ Cannot initialize log file {self.log_file}: {str(e)}"
            )
        
        return E2ETestResult(
            success=True,
            message=f"✅ Test environment ready - phone: {self.test_phone}, instance: {self.instance_name}"
        )
    
    def send_test_message(self, message: str = "oi") -> E2ETestResult:
        """Send test message via Evolution API webhook simulation"""
        webhook_payload = {
            "event": "messages.upsert",
            "instance": self.instance_name,
            "data": {
                "key": {
                    "remoteJid": f"{self.test_phone}@s.whatsapp.net",
                    "fromMe": False,
                    "id": f"smoke_test_{int(time.time())}"
                },
                "message": {
                    "conversation": message
                },
                "messageType": "conversation",
                "messageTimestamp": int(time.time()),
                "pushName": "Smoke Test User"
            }
        }
        
        try:
            # Simulate webhook call to our application
            app_webhook_url = os.getenv("APP_WEBHOOK_URL", "http://localhost:8000/webhook/evolution")
            
            response = requests.post(
                app_webhook_url,
                json=webhook_payload,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return E2ETestResult(
                    success=True,
                    message=f"✅ Test message sent successfully: '{message}'",
                    details={"response": response.text}
                )
            else:
                return E2ETestResult(
                    success=False,
                    message=f"❌ Webhook call failed: {response.status_code}",
                    details={"response": response.text}
                )
                
        except Exception as e:
            return E2ETestResult(
                success=False,
                message=f"❌ Failed to send test message: {str(e)}"
            )
    
    def capture_logs_after_delay(self, delay_seconds: int = 5) -> List[str]:
        """Capture logs after a delay to allow processing"""
        print(f"⏳ Waiting {delay_seconds} seconds for processing...")
        time.sleep(delay_seconds)
        
        try:
            with open(self.log_file, "r") as f:
                return f.readlines()
        except Exception:
            return []
    
    def validate_expected_log_sequence(self, logs: List[str]) -> E2ETestResult:
        """Validate that expected log sequence appears"""
        log_text = "\n".join(logs)
        
        # Required patterns in order
        required_patterns = [
            "OUTBOX_TRACE|phase=planner",
            "OUTBOX_TRACE|phase=delivery", 
            "INSTANCE_TRACE|source=meta|instance=kumon_assistant",
            "DELIVERY_TRACE|action=send|instance=kumon_assistant",
            "DELIVERY_TRACE|action=result|status=success"
        ]
        
        found_patterns = []
        missing_patterns = []
        
        for pattern in required_patterns:
            if pattern in log_text:
                found_patterns.append(pattern)
            else:
                missing_patterns.append(pattern)
        
        if missing_patterns:
            return E2ETestResult(
                success=False,
                message=f"❌ Missing {len(missing_patterns)} required log patterns",
                details={
                    "missing_patterns": missing_patterns,
                    "found_patterns": found_patterns
                }
            )
        
        return E2ETestResult(
            success=True,
            message=f"✅ All {len(required_patterns)} required log patterns found",
            details={"patterns": found_patterns}
        )
    
    def validate_prohibited_patterns(self, logs: List[str]) -> E2ETestResult:
        """Validate that prohibited patterns do not appear"""
        log_text = "\n".join(logs)
        
        # Prohibited patterns (should NOT appear)
        prohibited_patterns = [
            "OUTBOX_GUARD|level=CRITICAL|type=handoff_violation",
            "INSTANCE_GUARD|level=CRITICAL|type=invalid_pattern",
            "instance=default",
            "instance=thread_"
        ]
        
        found_prohibited = []
        
        for pattern in prohibited_patterns:
            if pattern in log_text:
                found_prohibited.append(pattern)
        
        if found_prohibited:
            return E2ETestResult(
                success=False,
                message=f"❌ Found {len(found_prohibited)} prohibited patterns",
                details={"prohibited_patterns": found_prohibited}
            )
        
        return E2ETestResult(
            success=True,
            message="✅ No prohibited patterns detected"
        )
    
    def validate_outbox_state_consistency(self, logs: List[str]) -> E2ETestResult:
        """Validate outbox state consistency between planner and delivery"""
        log_text = "\n".join(logs)
        
        # Extract outbox traces
        planner_traces = []
        delivery_traces = []
        
        for line in logs:
            if "OUTBOX_TRACE|phase=planner" in line:
                planner_traces.append(line.strip())
            elif "OUTBOX_TRACE|phase=delivery" in line:
                delivery_traces.append(line.strip())
        
        if not planner_traces or not delivery_traces:
            return E2ETestResult(
                success=False,
                message="❌ Missing planner or delivery outbox traces"
            )
        
        # Parse and compare most recent traces
        latest_planner = planner_traces[-1]
        latest_delivery = delivery_traces[-1]
        
        try:
            # Extract conv, idem, state_id, outbox_id from traces
            planner_parts = latest_planner.split("|")
            delivery_parts = latest_delivery.split("|")
            
            planner_conv = [part for part in planner_parts if part.startswith("conv=")]
            delivery_conv = [part for part in delivery_parts if part.startswith("conv=")]
            
            planner_state_id = [part for part in planner_parts if part.startswith("state_id=")]
            delivery_state_id = [part for part in delivery_parts if part.startswith("state_id=")]
            
            if (planner_conv and delivery_conv and 
                planner_state_id and delivery_state_id):
                
                if (planner_conv[0] == delivery_conv[0] and 
                    planner_state_id[0] == delivery_state_id[0]):
                    
                    return E2ETestResult(
                        success=True,
                        message="✅ Outbox state consistency maintained",
                        details={
                            "planner_trace": latest_planner,
                            "delivery_trace": latest_delivery
                        }
                    )
            
            return E2ETestResult(
                success=False,
                message="❌ Outbox state inconsistency detected",
                details={
                    "planner_trace": latest_planner,
                    "delivery_trace": latest_delivery
                }
            )
            
        except Exception as e:
            return E2ETestResult(
                success=False,
                message=f"❌ Failed to parse outbox traces: {str(e)}"
            )
    
    def run_complete_smoke_test(self) -> Dict[str, E2ETestResult]:
        """Run complete end-to-end smoke test"""
        results = {}
        
        # Step 1: Setup
        print("🔧 Setting up test environment...")
        results["setup"] = self.setup_test_environment()
        if not results["setup"].success:
            return results
        
        # Step 2: Send test message
        print("📱 Sending test message...")
        results["message"] = self.send_test_message()
        if not results["message"].success:
            return results
        
        # Step 3: Capture logs
        print("📋 Capturing logs...")
        logs = self.capture_logs_after_delay(5)
        
        # Step 4: Validate log sequence
        print("🔍 Validating expected log sequence...")
        results["sequence"] = self.validate_expected_log_sequence(logs)
        
        # Step 5: Validate prohibited patterns
        print("🚫 Checking for prohibited patterns...")
        results["prohibited"] = self.validate_prohibited_patterns(logs)
        
        # Step 6: Validate state consistency
        print("📊 Validating state consistency...")
        results["consistency"] = self.validate_outbox_state_consistency(logs)
        
        return results
    
    def generate_test_report(self, results: Dict[str, E2ETestResult]) -> str:
        """Generate comprehensive test report"""
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result.success)
        
        report_lines = [
            "# End-to-End Smoke Test Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Instance: {self.instance_name}",
            f"Test Phone: {self.test_phone}",
            "",
            f"## Summary",
            f"**Total Tests**: {total_tests}",
            f"**Passed**: {passed_tests}",
            f"**Failed**: {total_tests - passed_tests}",
            f"**Success Rate**: {passed_tests/total_tests:.1%}",
            "",
            f"**Overall Result**: {'🎯 PASS' if passed_tests == total_tests else '❌ FAIL'}",
            "",
            "## Detailed Results",
            ""
        ]
        
        for test_name, result in results.items():
            status_icon = "✅" if result.success else "❌"
            report_lines.append(f"### {test_name.title()}")
            report_lines.append(f"{status_icon} {result.message}")
            
            if result.details:
                report_lines.append("```")
                report_lines.append(json.dumps(result.details, indent=2))
                report_lines.append("```")
            
            report_lines.append("")
        
        return "\n".join(report_lines)

def main():
    """Main CLI interface for smoke testing"""
    if len(sys.argv) < 2:
        print("Usage: python smoke_test_e2e.py <command> [options]")
        print("Commands:")
        print("  test         - Run complete smoke test")
        print("  setup        - Setup test environment only") 
        print("  send         - Send test message only")
        print("  validate     - Validate logs only")
        print("")
        print("Environment variables:")
        print("  SMOKE_TEST_PHONE     - Phone number for testing")
        print("  APP_WEBHOOK_URL      - Application webhook URL (default: http://localhost:8000/webhook/evolution)")
        sys.exit(1)
    
    command = sys.argv[1]
    tester = SmokeTestE2E()
    
    if command == "test":
        print("🚀 Starting complete E2E smoke test...\n")
        
        results = tester.run_complete_smoke_test()
        
        print("\n" + "="*60)
        print("SMOKE TEST RESULTS")
        print("="*60)
        
        all_passed = True
        for test_name, result in results.items():
            status = "✅ PASS" if result.success else "❌ FAIL"
            print(f"{status} {test_name.upper()}: {result.message}")
            
            if not result.success:
                all_passed = False
                if result.details:
                    print(f"   Details: {result.details}")
        
        print("="*60)
        print(f"OVERALL: {'🎯 ALL TESTS PASSED' if all_passed else '🚨 SOME TESTS FAILED'}")
        
        # Generate report
        report = tester.generate_test_report(results)
        report_file = f"smoke_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        with open(report_file, "w") as f:
            f.write(report)
        
        print(f"📊 Detailed report saved: {report_file}")
        
        if not all_passed:
            sys.exit(1)
    
    elif command == "setup":
        result = tester.setup_test_environment()
        print(result.message)
        if not result.success:
            sys.exit(1)
    
    elif command == "send":
        result = tester.send_test_message()
        print(result.message)
        if not result.success:
            sys.exit(1)
    
    elif command == "validate":
        logs = tester.capture_logs_after_delay(0)  # No delay for validation only
        
        sequence_result = tester.validate_expected_log_sequence(logs)
        prohibited_result = tester.validate_prohibited_patterns(logs)
        consistency_result = tester.validate_outbox_state_consistency(logs)
        
        print("🔍 Log Validation Results:")
        print(f"   Sequence: {sequence_result.message}")
        print(f"   Prohibited: {prohibited_result.message}")  
        print(f"   Consistency: {consistency_result.message}")
        
        if not all([sequence_result.success, prohibited_result.success, consistency_result.success]):
            sys.exit(1)
    
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()