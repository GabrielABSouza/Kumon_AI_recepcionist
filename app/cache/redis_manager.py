"""
Redis Manager Compatibility Shim
Provides backward compatibility for app.cache.redis_manager imports
"""

import logging
from ..core.cache_manager import redis_cache as _core_redis_cache, get_redis

logger = logging.getLogger(__name__)

# Log the compatibility shim usage for observability
logger.info("CACHE_INIT|source=app.cache.redis_manager(shim)|redirecting_to_core")

# Export the core redis_cache instance with compatibility wrapper
redis_cache = _core_redis_cache

# Export common functions for compatibility
def get_redis_client():
    """Compatibility function for legacy get_redis_client calls"""
    logger.debug("CACHE_SHIM|get_redis_client|redirecting_to_core")
    return get_redis()

def close_redis_client():
    """Compatibility function for legacy close_redis_client calls"""
    logger.debug("CACHE_SHIM|close_redis_client|delegating_to_core")
    if redis_cache.client:
        try:
            redis_cache.client.close()
        except Exception as e:
            logger.error(f"CACHE_SHIM|close_error|{e}")

class CacheManager:
    """Compatibility class for legacy CacheManager usage"""
    
    def __init__(self):
        logger.debug("CACHE_SHIM|CacheManager|init|redirecting_to_core")
        self._redis_cache = redis_cache
    
    @property
    def client(self):
        return self._redis_cache.client
    
    def get_client(self):
        return get_redis_client()
    
    def is_connected(self):
        return self._redis_cache.is_connected()

__all__ = ["redis_cache", "CacheManager", "get_redis_client", "close_redis_client"]