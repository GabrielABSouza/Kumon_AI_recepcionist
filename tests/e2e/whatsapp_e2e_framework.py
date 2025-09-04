"""
End-to-End WhatsApp Testing Framework

Framework para testes E2E completos do sistema WhatsApp em staging/produção controlada.
Valida pipeline completo: StageResolver → SmartRouter → ResponsePlanner → Delivery

CRÍTICO: Testa que Safety → Outbox → Delivery funciona sem loops e com conteúdo preservado.
"""

import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from unittest.mock import patch, MagicMock
import aiohttp
import logging

from app.core.config import settings
from app.clients.evolution_api import evolution_api_client
from app.core.logger import app_logger


@dataclass
class E2ETestResult:
    """Resultado de um teste E2E"""
    test_name: str
    success: bool
    duration_ms: int
    logs_captured: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    assertions_passed: int
    assertions_failed: int
    error_message: Optional[str] = None
    whatsapp_message_received: Optional[str] = None


@dataclass
class LogAssertion:
    """Assertion para validar logs específicos"""
    pattern: str
    expected_count: int = 1
    must_contain: Optional[List[str]] = None
    must_not_contain: Optional[List[str]] = None
    timeout_seconds: int = 10


class WhatsAppE2EFramework:
    """Framework para testes E2E do sistema WhatsApp"""
    
    def __init__(self, environment: str = "staging"):
        self.environment = environment
        self.test_phone = self._get_test_phone()
        self.instance_name = self._get_test_instance()
        self.captured_logs = []
        self.test_session_ids = set()
        
        # Setup logging capture
        self._setup_log_capture()
        
    def _get_test_phone(self) -> str:
        """Get test phone number for environment"""
        test_phones = {
            "staging": "5551999999999",  # Número de teste staging
            "production": "5551888888888"  # Número de teste produção (controlada)
        }
        return test_phones.get(self.environment, "5551999999999")
    
    def _get_test_instance(self) -> str:
        """Get Evolution API instance for environment"""
        instances = {
            "staging": "staging_instance",
            "production": "production_test_instance"
        }
        return instances.get(self.environment, "staging_instance")
    
    def _setup_log_capture(self):
        """Setup log capture for test validation"""
        # Custom log handler to capture logs
        class E2ELogHandler(logging.Handler):
            def __init__(self, framework):
                super().__init__()
                self.framework = framework
            
            def emit(self, record):
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": getattr(record, 'module', 'unknown'),
                    "function": getattr(record, 'funcName', 'unknown'),
                    "line": getattr(record, 'lineno', 0)
                }
                self.framework.captured_logs.append(log_entry)
        
        # Add handler to app logger
        self.log_handler = E2ELogHandler(self)
        app_logger.addHandler(self.log_handler)
        
        # Also capture root logger for comprehensive coverage
        logging.getLogger().addHandler(self.log_handler)
    
    def clear_logs(self):
        """Clear captured logs"""
        self.captured_logs.clear()
    
    def find_logs(self, pattern: str, timeout_seconds: int = 10) -> List[Dict]:
        """Find logs matching pattern with timeout"""
        start_time = time.time()
        found_logs = []
        
        while time.time() - start_time < timeout_seconds:
            for log_entry in self.captured_logs:
                if re.search(pattern, log_entry["message"], re.IGNORECASE):
                    found_logs.append(log_entry)
            
            if found_logs:
                break
            time.sleep(0.1)
        
        return found_logs
    
    def assert_log_pattern(self, assertion: LogAssertion) -> bool:
        """Assert that logs match expected pattern"""
        found_logs = self.find_logs(assertion.pattern, assertion.timeout_seconds)
        
        # Check count
        if len(found_logs) != assertion.expected_count:
            app_logger.error(f"Log assertion failed: expected {assertion.expected_count} matches for '{assertion.pattern}', found {len(found_logs)}")
            return False
        
        # Check must_contain
        if assertion.must_contain:
            for log_entry in found_logs:
                for required_text in assertion.must_contain:
                    if required_text not in log_entry["message"]:
                        app_logger.error(f"Log assertion failed: '{required_text}' not found in log: {log_entry['message']}")
                        return False
        
        # Check must_not_contain
        if assertion.must_not_contain:
            for log_entry in found_logs:
                for forbidden_text in assertion.must_not_contain:
                    if forbidden_text in log_entry["message"]:
                        app_logger.error(f"Log assertion failed: forbidden text '{forbidden_text}' found in log: {log_entry['message']}")
                        return False
        
        return True
    
    async def send_whatsapp_message(self, message: str, session_id: Optional[str] = None) -> str:
        """Send message via Evolution API and return session_id"""
        if not session_id:
            session_id = f"e2e_test_{uuid.uuid4().hex[:8]}"
        
        self.test_session_ids.add(session_id)
        
        try:
            # Simulate WhatsApp webhook payload
            webhook_payload = {
                "event": "messages.upsert",
                "instance": self.instance_name,
                "data": {
                    "key": {
                        "remoteJid": f"{self.test_phone}@s.whatsapp.net",
                        "fromMe": False,
                        "id": f"test_msg_{uuid.uuid4().hex[:8]}"
                    },
                    "messageTimestamp": int(time.time()),
                    "pushName": "E2E Test User",
                    "message": {
                        "conversation": message
                    }
                }
            }
            
            # Send to webhook endpoint
            webhook_url = f"{settings.FRONTEND_URL}/api/v1/evolution/webhook"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=webhook_payload) as response:
                    if response.status != 200:
                        raise Exception(f"Webhook failed with status {response.status}")
                    
                    app_logger.info(f"E2E: Sent WhatsApp message '{message}' for session {session_id}")
                    return session_id
                    
        except Exception as e:
            app_logger.error(f"E2E: Failed to send WhatsApp message: {e}")
            raise
    
    async def wait_for_response(self, session_id: str, timeout_seconds: int = 30) -> Optional[str]:
        """Wait for WhatsApp response message"""
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            # Look for delivery logs
            delivery_logs = self.find_logs("Message delivered successfully", 1)
            if delivery_logs:
                # Try to extract message content from logs
                for log in delivery_logs:
                    if session_id in str(log):
                        # Extract message content if possible
                        return "Response received (check logs for content)"
            
            await asyncio.sleep(0.5)
        
        return None
    
    def validate_no_async_warnings(self) -> bool:
        """Validate no 'coroutine was never awaited' warnings"""
        warning_logs = [log for log in self.captured_logs 
                       if "coroutine" in log["message"] and "never awaited" in log["message"]]
        
        if warning_logs:
            app_logger.error(f"Found {len(warning_logs)} async warnings")
            for log in warning_logs[:3]:  # Show first 3
                app_logger.error(f"Async warning: {log['message']}")
            return False
        return True
    
    def validate_no_recursion_warnings(self) -> bool:
        """Validate no recursion limit warnings"""
        recursion_logs = [log for log in self.captured_logs 
                         if "RECURSION" in log["message"] or "recursion" in log["message"]]
        
        if recursion_logs:
            app_logger.error(f"Found {len(recursion_logs)} recursion warnings")
            for log in recursion_logs[:3]:  # Show first 3
                app_logger.error(f"Recursion warning: {log['message']}")
            return False
        return True
    
    def validate_enum_usage(self) -> bool:
        """Validate proper enum usage (no string attribute errors)"""
        enum_error_logs = [log for log in self.captured_logs 
                          if "str' object has no attribute 'value'" in log["message"]]
        
        if enum_error_logs:
            app_logger.error(f"Found {len(enum_error_logs)} enum errors")
            for log in enum_error_logs[:3]:  # Show first 3
                app_logger.error(f"Enum error: {log['message']}")
            return False
        return True
    
    def get_telemetry_metrics(self) -> Dict[str, Any]:
        """Extract telemetry metrics from logs"""
        metrics = {
            "outbox_before_planning": 0,
            "outbox_after_planning": 0,
            "outbox_before_delivery": 0,
            "messages_delivered": 0,
            "idempotency_hits": 0,
            "emergency_fallbacks": 0,
            "safety_blocks": 0,
            "enum_violations": 0
        }
        
        for log in self.captured_logs:
            message = log["message"]
            
            # Extract metrics from log patterns
            if "planner_outbox_count_before:" in message:
                try:
                    metrics["outbox_before_planning"] = int(re.search(r'planner_outbox_count_before:\s*(\d+)', message).group(1))
                except: pass
                
            if "planner_outbox_count_after:" in message:
                try:
                    metrics["outbox_after_planning"] = int(re.search(r'planner_outbox_count_after:\s*(\d+)', message).group(1))
                except: pass
                
            if "delivery_outbox_count_before:" in message:
                try:
                    metrics["outbox_before_delivery"] = int(re.search(r'delivery_outbox_count_before:\s*(\d+)', message).group(1))
                except: pass
                
            if "delivery_sent_count:" in message:
                try:
                    metrics["messages_delivered"] = int(re.search(r'delivery_sent_count:\s*(\d+)', message).group(1))
                except: pass
                
            if "idempotency_dedup_hits:" in message:
                try:
                    metrics["idempotency_hits"] = int(re.search(r'idempotency_dedup_hits:\s*(\d+)', message).group(1))
                except: pass
                
            if "delivery_emergency_fallback_added:" in message:
                metrics["emergency_fallbacks"] += 1
                
            if "BLOCKED configuration template" in message:
                metrics["safety_blocks"] += 1
        
        return metrics
    
    async def run_test_scenario(self, test_name: str, test_function) -> E2ETestResult:
        """Run a test scenario and collect results"""
        start_time = time.time()
        self.clear_logs()
        
        app_logger.info(f"🧪 Starting E2E test: {test_name}")
        
        try:
            # Run test function
            assertions_result = await test_function()
            
            # Calculate results
            duration_ms = int((time.time() - start_time) * 1000)
            metrics = self.get_telemetry_metrics()
            
            # Validate system health
            no_async_warnings = self.validate_no_async_warnings()
            no_recursion_warnings = self.validate_no_recursion_warnings()
            proper_enum_usage = self.validate_enum_usage()
            
            # Count assertions
            assertions_passed = sum(1 for result in assertions_result if result)
            assertions_failed = sum(1 for result in assertions_result if not result)
            
            success = all(assertions_result) and no_async_warnings and no_recursion_warnings and proper_enum_usage
            
            result = E2ETestResult(
                test_name=test_name,
                success=success,
                duration_ms=duration_ms,
                logs_captured=self.captured_logs.copy(),
                metrics=metrics,
                assertions_passed=assertions_passed,
                assertions_failed=assertions_failed
            )
            
            app_logger.info(f"🧪 Test {test_name} completed: {'✅ PASSED' if success else '❌ FAILED'} ({duration_ms}ms)")
            return result
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            result = E2ETestResult(
                test_name=test_name,
                success=False,
                duration_ms=duration_ms,
                logs_captured=self.captured_logs.copy(),
                metrics=self.get_telemetry_metrics(),
                assertions_passed=0,
                assertions_failed=1,
                error_message=str(e)
            )
            
            app_logger.error(f"🧪 Test {test_name} failed with error: {e}")
            return result
    
    def cleanup(self):
        """Cleanup test environment"""
        # Remove log handler
        if hasattr(self, 'log_handler'):
            app_logger.removeHandler(self.log_handler)
            logging.getLogger().removeHandler(self.log_handler)
        
        # Clear session data
        self.test_session_ids.clear()
        self.captured_logs.clear()


def print_test_report(results: List[E2ETestResult]):
    """Print comprehensive test report"""
    print("\n" + "="*80)
    print("🧪 E2E WHATSAPP TEST REPORT")
    print("="*80)
    
    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed
    total_duration = sum(r.duration_ms for r in results)
    
    print(f"📊 Summary: {passed} passed, {failed} failed, {len(results)} total")
    print(f"⏱️ Total time: {total_duration}ms ({total_duration/1000:.2f}s)")
    print()
    
    for result in results:
        status = "✅ PASS" if result.success else "❌ FAIL"
        print(f"{status} {result.test_name} ({result.duration_ms}ms)")
        
        if result.error_message:
            print(f"     Error: {result.error_message}")
        
        print(f"     Assertions: {result.assertions_passed} passed, {result.assertions_failed} failed")
        
        # Key metrics
        m = result.metrics
        print(f"     Metrics: outbox_after_planning={m.get('outbox_after_planning', 0)}, "
              f"messages_delivered={m.get('messages_delivered', 0)}, "
              f"safety_blocks={m.get('safety_blocks', 0)}")
        print()
    
    print("="*80)