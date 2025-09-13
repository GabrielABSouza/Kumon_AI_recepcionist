#!/usr/bin/env python3
"""
Redis debugging script for StateManager audit testing.
"""

import redis

# Connection details from CLAUDE.md
REDIS_URL = (
    "redis://default:kAcPDeAHtSeAFlqHrkXxgaHTAKbNdYFs@mainline.proxy.rlwy.net:56033"
)


def main():
    print("🔍 REDIS DEBUG: Connecting to production Redis...")
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

    # Test connection
    try:
        client.ping()
        print("✅ Redis connection successful!")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return

    # List all conversation keys before cleanup
    print("\n📋 Current conversation keys:")
    keys = client.keys("conversation:*")
    for key in keys:
        value = client.get(key)
        print(f"  {key}: {len(value) if value else 0} chars")

    # Clear all conversation data for clean testing
    print(f"\n🧹 Clearing {len(keys)} conversation keys...")
    if keys:
        deleted = client.delete(*keys)
        print(f"✅ Deleted {deleted} keys")
    else:
        print("ℹ️ No keys to delete")

    # Verify cleanup
    remaining_keys = client.keys("conversation:*")
    print(f"\n🔍 Verification: {len(remaining_keys)} conversation keys remaining")

    print("\n🎯 Redis is now clean and ready for STATE_AUDIT testing!")


if __name__ == "__main__":
    main()
