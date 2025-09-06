"""
Core Cache Manager - Redis client management and connection pooling
Provides centralized Redis access for the application
"""

import os
import logging
import redis
from typing import Optional
from .config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    """Redis connection manager with automatic failover"""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connected = False
    
    @property
    def client(self) -> Optional[redis.Redis]:
        """Get Redis client, initialize if needed"""
        if not self._client:
            self._initialize()
        return self._client
    
    def _initialize(self):
        """Initialize Redis connection"""
        try:
            # Try to get Redis URL from various environment variables
            redis_url = (
                os.getenv("REDIS_URL") or
                os.getenv("MEMORY_REDIS_URL") or  
                os.getenv("REDISCLOUD_URL") or
                "redis://localhost:6379"
            )
            
            logger.info(f"CACHE_INIT|source=app.core.cache_manager|connecting_to_redis")
            logger.info(f"Connecting to Redis: {redis_url[:20]}...")
            
            # Create Redis client with connection pooling
            self._client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
            
            # Test connection
            self._client.ping()
            self._connected = True
            
            logger.info("✅ Redis connection established")
            
        except Exception as e:
            logger.warning(f"❌ Redis connection failed: {e}")
            self._client = None
            self._connected = False
    
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        if not self._client:
            return False
        try:
            self._client.ping()
            return True
        except:
            self._connected = False
            return False
    
    def reconnect(self):
        """Force reconnection to Redis"""
        if self._client:
            try:
                self._client.close()
            except:
                pass
        self._client = None
        self._connected = False
        self._initialize()


# Global Redis manager instance
redis_cache = RedisManager()


def get_redis() -> Optional[redis.Redis]:
    """
    Get Redis client instance
    
    Returns:
        Optional[redis.Redis]: Redis client or None if unavailable
    """
    return redis_cache.client


# Legacy compatibility
def get_cache_client():
    """Legacy function for backward compatibility"""
    return get_redis()