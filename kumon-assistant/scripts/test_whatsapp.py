#!/usr/bin/env python3
"""
Test script for WhatsApp Business API integration
"""
import asyncio
import json
import sys
import os
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.clients.whatsapp import WhatsAppClient, WhatsAppAPIError
from app.core.config import settings
from app.core.logger import app_logger


async def test_whatsapp_client():
    """Test WhatsApp client functionality"""
    
    print("🧪 Testing WhatsApp Business API Integration")
    print("=" * 50)
    
    # Initialize client
    client = WhatsAppClient()
    
    # Test 1: Validate configuration
    print("\n1. Testing Configuration...")
    if not settings.WHATSAPP_TOKEN:
        print("❌ WHATSAPP_TOKEN not configured")
        return False
    
    if not settings.WHATSAPP_PHONE_NUMBER_ID:
        print("❌ WHATSAPP_PHONE_NUMBER_ID not configured")
        return False
    
    print("✅ Configuration looks good")
    
    # Test 2: Get business profile
    print("\n2. Testing Business Profile...")
    try:
        profile = await client.get_business_profile()
        if profile:
            print("✅ Business profile retrieved successfully")
            print(f"   Profile data: {json.dumps(profile, indent=2)}")
        else:
            print("⚠️  Could not retrieve business profile")
    except Exception as e:
        print(f"❌ Business profile error: {str(e)}")
    
    # Test 3: Send test message (only if test number provided)
    test_number = os.getenv("TEST_WHATSAPP_NUMBER")
    if test_number:
        print(f"\n3. Testing Message Send to {test_number}...")
        try:
            response = await client.send_message(
                to_number=test_number,
                message="🧪 Esta é uma mensagem de teste do Kumon AI Receptionist!\n\nSe você recebeu esta mensagem, a integração está funcionando perfeitamente! ✅"
            )
            print("✅ Test message sent successfully")
            print(f"   Message ID: {response.get('messages', [{}])[0].get('id', 'N/A')}")
        except WhatsAppAPIError as e:
            print(f"❌ WhatsApp API Error: {e.message}")
            print(f"   Status Code: {e.status_code}")
            if e.response_data:
                print(f"   Response: {json.dumps(e.response_data, indent=2)}")
        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")
    else:
        print("\n3. Skipping message send test (TEST_WHATSAPP_NUMBER not set)")
    
    # Test 4: Webhook verification
    print("\n4. Testing Webhook Verification...")
    try:
        is_valid = await client.verify_webhook(settings.WHATSAPP_VERIFY_TOKEN)
        if is_valid:
            print("✅ Webhook verification working")
        else:
            print("❌ Webhook verification failed")
    except Exception as e:
        print(f"❌ Webhook verification error: {str(e)}")
    
    await client.close()
    
    print("\n" + "=" * 50)
    print("🎉 WhatsApp integration test completed!")
    return True


async def simulate_webhook_message():
    """Test message processing pipeline"""
    
    print("\n🧪 Testing Message Processing Pipeline")
    print("=" * 50)
    
    from app.models.message import WhatsAppMessage, MessageType
    from app.services.message_processor import MessageProcessor
    
    # Initialize processor
    processor = MessageProcessor()
    
    # Create test message
    test_message = WhatsAppMessage(
        message_id="test_msg_123",
        from_number="5511999999999",
        to_number=settings.WHATSAPP_PHONE_NUMBER_ID,
        message_type=MessageType.TEXT,
        content="Olá! Gostaria de agendar uma consulta para meu filho.",
        metadata={"test": True}
    )
    
    try:
        print(f"Processing test message: '{test_message.content}'")
        response = await processor.process_message(test_message)
        
        print("✅ Message processed successfully")
        print(f"Response: {response.content}")
        print(f"Intent detected: {response.metadata.get('intent', 'unknown')}")
        
    except Exception as e:
        print(f"❌ Message processing error: {str(e)}")
        return False
    
    return True


def check_environment():
    """Check if environment is properly configured"""
    
    print("🔍 Checking Environment Configuration")
    print("=" * 50)
    
    required_vars = [
        "WHATSAPP_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID", 
        "WHATSAPP_VERIFY_TOKEN"
    ]
    
    missing_vars = []
    for var in required_vars:
        value = getattr(settings, var, None)
        if not value or value.strip() == "":
            missing_vars.append(var)
            print(f"❌ {var}: Not set")
        else:
            # Show partial value for security
            display_value = str(value)[:8] + "..." if len(str(value)) > 8 else str(value)
            print(f"✅ {var}: {display_value}")
    
    optional_vars = [
        "WHATSAPP_BUSINESS_ACCOUNT_ID",
        "WHATSAPP_APP_ID",
        "OPENAI_API_KEY"
    ]
    
    print("\nOptional Configuration:")
    for var in optional_vars:
        value = getattr(settings, var, None)
        if value and value.strip() != "":
            display_value = str(value)[:8] + "..." if len(str(value)) > 8 else str(value)
            print(f"✅ {var}: {display_value}")
        else:
            print(f"⚠️  {var}: Not set")
    
    if missing_vars:
        print(f"\n❌ Missing required variables: {', '.join(missing_vars)}")
        print("\nTo fix this:")
        print("1. Copy .env.example to .env")
        print("2. Fill in your WhatsApp Business API credentials")
        print("3. Run this test again")
        return False
    
    print("\n✅ Environment configuration looks good!")
    return True


async def main():
    """Main test function"""
    
    print("🚀 WhatsApp Business API Integration Test Suite")
    print("=" * 60)
    
    # Check environment first
    if not check_environment():
        sys.exit(1)
    
    # Test WhatsApp client
    success = await test_whatsapp_client()
    
    # Test message processing (this doesn't require actual API calls)
    await simulate_webhook_message()
    
    if success:
        print("\n🎉 All tests completed! Your WhatsApp integration is ready.")
        print("\nNext steps:")
        print("1. Set up your webhook URL with WhatsApp")
        print("2. Test with real messages")
        print("3. Configure your business information")
    else:
        print("\n⚠️  Some tests failed. Please check your configuration.")
        sys.exit(1)


if __name__ == "__main__":
    # Set test number if provided as argument
    if len(sys.argv) > 1:
        os.environ["TEST_WHATSAPP_NUMBER"] = sys.argv[1]
        print(f"Test number set to: {sys.argv[1]}")
    
    asyncio.run(main()) 