# test_redis.py
import asyncio
import os

import redis.asyncio as redis


async def main():
    url = os.getenv("REDIS_URL")
    client = redis.from_url(url)

    await client.set("ping", "pong")
    value = await client.get("ping")
    print("Redis test:", value)


if __name__ == "__main__":
    asyncio.run(main())
