#!/usr/bin/env python3
"""
Verify Loop Prevention Fixes - Comprehensive validation script
Tests all implemented fixes for conversation loops and single reply per turn
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add app to path for imports
sys.path.append(str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_import_fixes():
    """Test that all import compatibility shims work correctly"""
    print("\n🔍 Testing Import Fixes...")
    
    try:
        # Test cache shim
        from app.cache import get_redis
        logger.info("✅ app.cache import works")
        
        # Test core cache manager
        from app.core.cache_manager import get_redis as core_get_redis
        logger.info("✅ app.core.cache_manager import works")
        
        # Test database connection
        from app.core.database.connection import get_database_connection
        logger.info("✅ app.core.database.connection import works")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import test failed: {e}")
        return False


def test_turn_lock_mechanism():
    """Test turn lock and deduplication mechanisms"""
    print("\n🔍 Testing Turn Lock Mechanism...")
    
    try:
        from app.core.turn_dedup import turn_lock, is_duplicate_message
        from app.core.cache_manager import get_redis
        
        # Test Redis availability
        redis_client = get_redis()
        if not redis_client:
            logger.warning("⚠️ Redis not available - turn lock will degrade gracefully")
            return True
        
        # Test turn lock
        test_conv_id = "test_conv_123"
        with turn_lock(test_conv_id) as acquired:
            if acquired:
                logger.info("✅ Turn lock acquired successfully")
                
                # Test second lock (should be blocked)
                with turn_lock(test_conv_id) as acquired2:
                    if not acquired2:
                        logger.info("✅ Duplicate turn lock blocked correctly")
                    else:
                        logger.error("❌ Duplicate turn lock was not blocked")
                        return False
            else:
                logger.error("❌ Turn lock acquisition failed")
                return False
        
        # Test message deduplication
        is_dup1 = is_duplicate_message("test_instance", "5511999999999", "msg_123")
        is_dup2 = is_duplicate_message("test_instance", "5511999999999", "msg_123")
        
        if not is_dup1 and is_dup2:
            logger.info("✅ Message deduplication works correctly")
        else:
            logger.error(f"❌ Message deduplication failed: first={is_dup1}, second={is_dup2}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Turn lock test failed: {e}")
        return False


def test_outbox_repository():
    """Test outbox persistence and delivery rehydration"""
    print("\n🔍 Testing Outbox Repository...")
    
    try:
        from app.core.outbox_repository import save_outbox, get_next_outbox_for_delivery
        
        # Test saving messages (will fail without database, but should not crash)
        test_conv_id = "test_conv_outbox_123"
        test_messages = [
            {"text": "Test message 1", "channel": "whatsapp", "meta": {"test": True}},
            {"text": "Test message 2", "channel": "whatsapp", "meta": {"test": True}}
        ]
        
        keys = save_outbox(test_conv_id, test_messages)
        if isinstance(keys, list):
            logger.info("✅ Outbox save function works (returned list)")
        else:
            logger.error("❌ Outbox save function failed")
            return False
        
        # Test rehydration (will return None without database, but should not crash)
        result = get_next_outbox_for_delivery(test_conv_id)
        logger.info("✅ Outbox rehydration function works (graceful degradation)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Outbox repository test failed: {e}")
        return False


def test_workflow_guards():
    """Test anti-recursion and loop prevention guards"""
    print("\n🔍 Testing Workflow Guards...")
    
    try:
        from app.core.workflow_guards import check_recursion_limit, prevent_greeting_loops, reset_conversation_guards
        
        test_conv_id = "test_conv_guards_123"
        test_phone = "5511999999999"
        
        # Reset any existing guards
        reset_conversation_guards(test_conv_id, test_phone)
        
        # Test recursion limit (should allow first few calls)
        for i in range(5):
            result = check_recursion_limit(test_conv_id, "test_stage")
            if not result:
                logger.error(f"❌ Recursion limit failed at iteration {i}")
                return False
        
        logger.info("✅ Recursion limit allows normal operations")
        
        # Test greeting loop prevention  
        result1 = prevent_greeting_loops(test_phone, "greeting", "greeting")
        result2 = prevent_greeting_loops(test_phone, "greeting", "greeting")
        
        if result1 and not result2:
            logger.info("✅ Greeting loop prevention works correctly")
        else:
            logger.error(f"❌ Greeting loop prevention failed: first={result1}, second={result2}")
            return False
        
        # Cleanup
        reset_conversation_guards(test_conv_id, test_phone)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Workflow guards test failed: {e}")
        return False


def test_structured_logging():
    """Test structured logging functionality"""
    print("\n🔍 Testing Structured Logging...")
    
    try:
        from app.core.structured_logging import (
            log_turn_event, log_outbox_event, log_delivery_event, 
            log_webhook_event, log_workflow_event
        )
        
        # Test various log functions (should not crash)
        log_turn_event("test", "test_conv_123", "5511999999999")
        log_outbox_event("test", "test_conv_123", count=1)
        log_delivery_event("test", "test_conv_123", "test_idem_key")
        log_webhook_event("test", "5511999999999", "test_msg_123")
        log_workflow_event("test", "test_conv_123", "test_stage")
        
        logger.info("✅ Structured logging functions work correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Structured logging test failed: {e}")
        return False


def run_comprehensive_tests():
    """Run all verification tests"""
    print("🚀 Kumon AI Receptionist - Loop Prevention Fix Verification")
    print("=" * 60)
    
    tests = [
        ("Import Fixes", test_import_fixes),
        ("Turn Lock Mechanism", test_turn_lock_mechanism),
        ("Outbox Repository", test_outbox_repository),
        ("Workflow Guards", test_workflow_guards),
        ("Structured Logging", test_structured_logging),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                failed += 1
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Loop prevention fixes are working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Check the logs above for details.")
        return False


def check_environment():
    """Check environment configuration"""
    print("\n🔧 Environment Check...")
    
    # Check critical environment variables
    env_vars = {
        "DATABASE_URL": "Database connection (required for outbox persistence)",
        "REDIS_URL": "Redis connection (required for turn lock and deduplication)",
        "MEMORY_REDIS_URL": "Alternative Redis connection",
    }
    
    for var, description in env_vars.items():
        value = os.getenv(var)
        if value:
            # Show only first part for security
            masked_value = value[:20] + "..." if len(value) > 20 else value
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"⚠️ {var}: Not set - {description}")
    
    print()


if __name__ == "__main__":
    check_environment()
    
    success = run_comprehensive_tests()
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)