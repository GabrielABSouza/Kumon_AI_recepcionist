"""
Cache package compatibility layer
Provides backward compatibility for cache imports
"""

# Re-export from core cache manager for compatibility
from ..core.cache_manager import get_redis

__all__ = ["get_redis"]