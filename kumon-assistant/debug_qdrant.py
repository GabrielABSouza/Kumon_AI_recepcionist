#!/usr/bin/env python3
"""
Debug script to test Qdrant connectivity from Railway environment
"""

import asyncio
import httpx
import time
import os
from qdrant_client import QdrantClient

async def test_qdrant_connection():
    """Test Qdrant connection with detailed debugging"""
    
    qdrant_url = os.getenv("QDRANT_URL", "https://qdrant-production.up.railway.app")
    print(f"🔍 Testing connection to: {qdrant_url}")
    
    # Test 1: Simple HTTP request
    print("\n=== Test 1: HTTP Health Check ===")
    try:
        start_time = time.time()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{qdrant_url}/health")
            elapsed = time.time() - start_time
            print(f"✅ HTTP Health Check: {response.status_code} in {elapsed:.2f}s")
            print(f"Response: {response.json()}")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ HTTP Health Check failed after {elapsed:.2f}s: {e}")
    
    # Test 2: Qdrant client connection
    print("\n=== Test 2: Qdrant Client Connection ===")
    try:
        start_time = time.time()
        client = QdrantClient(url=qdrant_url, timeout=30)
        info = client.get_cluster_info()
        elapsed = time.time() - start_time
        print(f"✅ Qdrant Client: Connected in {elapsed:.2f}s")
        print(f"Cluster info: {info}")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Qdrant Client failed after {elapsed:.2f}s: {e}")
    
    # Test 3: Collection operations
    print("\n=== Test 3: Collection Operations ===")
    try:
        start_time = time.time()
        client = QdrantClient(url=qdrant_url, timeout=30)
        collections = client.get_collections()
        elapsed = time.time() - start_time
        print(f"✅ Collections listed in {elapsed:.2f}s")
        print(f"Collections: {collections}")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Collection operations failed after {elapsed:.2f}s: {e}")

if __name__ == "__main__":
    asyncio.run(test_qdrant_connection())