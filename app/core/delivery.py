"""
Simple delivery service using Evolution API.
Sends text messages to WhatsApp.
"""
import os
import requests
from typing import Optional


def send_text(phone: str, text: str, instance: str = "recepcionistakumon") -> bool:
    """
    Send text message via Evolution API.
    Returns True if successful, False otherwise.
    """
    try:
        # Get Evolution API config from environment
        api_url = os.getenv("EVOLUTION_API_URL", "https://evo.whatlead.com.br")
        api_key = os.getenv("EVOLUTION_API_KEY")
        
        if not api_key:
            print("DELIVERY|error|missing_api_key")
            return False
        
        # Clean phone number (remove non-digits)
        clean_phone = ''.join(filter(str.isdigit, phone))
        
        # Ensure Brazilian format
        if not clean_phone.startswith("55"):
            clean_phone = "55" + clean_phone
        
        # Build request
        url = f"{api_url}/message/sendText/{instance}"
        headers = {
            "apikey": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "number": clean_phone,
            "text": text
        }
        
        # Send request
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 200:
            print(f"DELIVERY|sent|phone=****{clean_phone[-4:]}|chars={len(text)}")
            return True
        else:
            print(f"DELIVERY|error|status={response.status_code}")
            return False
            
    except Exception as e:
        print(f"DELIVERY|error|exception={str(e)}")
        return False