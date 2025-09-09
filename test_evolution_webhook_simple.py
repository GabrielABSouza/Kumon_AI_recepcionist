#!/usr/bin/env python3
"""
Simple test for Evolution webhook normalization.
Tests that the webhook always returns sent as string, not boolean.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test the normalizer directly
from app.utils.webhook_normalizer import normalize_webhook_payload

def test_normalizer():
    """Test normalizer function directly"""
    print("=" * 60)
    print("Testing webhook normalizer...")
    
    # Test 1: Boolean False -> string "false"
    test1 = {"sent": False, "message_id": "MSG1", "confidence": 0.9, "entities": {}}
    result1 = normalize_webhook_payload(test1)
    assert result1["sent"] == "false", f"Expected 'false', got {result1['sent']}"
    assert isinstance(result1["sent"], str), f"Expected str, got {type(result1['sent'])}"
    print("✅ Boolean False -> string 'false'")
    
    # Test 2: Boolean True -> string "true"
    test2 = {"sent": True, "message_id": "MSG2", "confidence": 0.9, "entities": {}}
    result2 = normalize_webhook_payload(test2)
    assert result2["sent"] == "true", f"Expected 'true', got {result2['sent']}"
    assert isinstance(result2["sent"], str), f"Expected str, got {type(result2['sent'])}"
    print("✅ Boolean True -> string 'true'")
    
    # Test 3: String remains string
    test3 = {"sent": "false", "message_id": "MSG3", "confidence": 0.9, "entities": {}}
    result3 = normalize_webhook_payload(test3)
    assert result3["sent"] == "false"
    print("✅ String 'false' remains string 'false'")
    
    # Test 4: Invalid types default to "false"
    test4 = {"sent": None, "message_id": "MSG4", "confidence": 0.9, "entities": {}}
    result4 = normalize_webhook_payload(test4)
    assert result4["sent"] == "false"
    print("✅ None -> string 'false'")
    
    print("\nAll normalizer tests passed! ✅")


def test_evolution_endpoint():
    """Test the actual Evolution endpoint"""
    print("\n" + "=" * 60)
    print("Testing Evolution webhook endpoint...")
    
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # Prepare a test webhook payload
        webhook_data = {
            "event": "messages.upsert",
            "instance": "test",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "TEST123"
                },
                "message": {"conversation": "Test message"},
                "messageType": "conversation",
                "messageTimestamp": 1704800000
            }
        }
        
        # Make request to Evolution webhook (no prefix, just /webhook)
        response = client.post(
            "/webhook",
            json=webhook_data
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")
            
            # Check sent field type
            if "sent" in data:
                sent_value = data["sent"]
                sent_type = type(sent_value).__name__
                
                if sent_type == "str" and sent_value in ["true", "false"]:
                    print(f"✅ 'sent' field is correctly typed as string: '{sent_value}'")
                else:
                    print(f"❌ 'sent' field has wrong type: {sent_type} = {sent_value}")
                    return False
            else:
                print("⚠️ No 'sent' field in response")
                
            return True
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Starting Evolution webhook normalization tests...")
    
    # Test normalizer directly
    test_normalizer()
    
    # Test actual endpoint
    success = test_evolution_endpoint()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests completed successfully!")
    else:
        print("⚠️ Some tests failed or couldn't run")