#!/usr/bin/env python3
"""Test Evolution API connectivity"""
import asyncio
import os

import httpx


async def test_evolution_connectivity():
    """Test Evolution API connectivity"""
    url = os.getenv("EVOLUTION_API_URL", "").rstrip("/")

    if not url:
        print("❌ EVOLUTION_API_URL not defined")
        return False

    print(f"🌐 Target URL: {url}")

    try:
        timeout = httpx.Timeout(5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{url}/")

        print(f"✅ HTTP {response.status_code}: Connection successful")
        return response.status_code < 400

    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_evolution_connectivity())
    exit(0 if success else 1)
