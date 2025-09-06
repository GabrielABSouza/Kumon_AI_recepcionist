# app/cache.py
"""
Compatibility shim for cache module access
Provides backward compatibility for imports from app.cache
"""

from app.core.cache_manager import get_redis

__all__ = ["get_redis"]

# For legacy code compatibility
def get_cache_client():
    """Legacy function name compatibility"""
    return get_redis()