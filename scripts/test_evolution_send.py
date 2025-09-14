#!/usr/bin/env python3
"""Test sending message via Evolution API"""
import asyncio
import os
import sys

# Add the app directory to the path
sys.path.append("/app")

from app.core.delivery import send_text


async def test_evolution_send():
    """Test sending message via Evolution API"""
    phone = os.getenv("TEST_PHONE", "+5511999999999")
    instance = os.getenv("EVOLUTION_INSTANCE", "cecilia_nova")

    print(f"📱 Sending test to: {phone} via instance: {instance}")

    result = await send_text(
        phone, "Teste de conectividade Evolution API (dev)", instance
    )

    print(f"📊 Result: {result}")
    return result.get("sent") == "true"


if __name__ == "__main__":
    success = asyncio.run(test_evolution_send())
    exit(0 if success else 1)
