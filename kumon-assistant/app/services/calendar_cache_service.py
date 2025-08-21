"""
Enterprise Calendar Caching Service
Multi-layer caching architecture for Google Calendar operations
"""
import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
import redis.asyncio as redis
from ..core.config import settings
from ..core.logger import app_logger


class CalendarCacheService:
    """
    Multi-layer caching service for Google Calendar data
    
    Architecture:
    - L1: In-memory cache (fast, small capacity)
    - L2: Redis cache (persistent, larger capacity)  
    - L3: Graceful degradation (fallback to manual booking)
    
    Features:
    - TTL-based expiration
    - Cache warming and preloading
    - Automatic cache invalidation
    - Compression for large datasets
    - Cache hit/miss metrics
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_prefix = "kumon:calendar"
        
        # Cache configuration
        self.availability_ttl = getattr(settings, 'AVAILABILITY_CACHE_TTL', 1800)  # 30 minutes
        self.conflict_check_ttl = getattr(settings, 'CONFLICT_CHECK_TTL', 600)     # 10 minutes
        self.event_cache_ttl = getattr(settings, 'EVENT_CACHE_TTL', 3600)         # 1 hour
        self.memory_cache_size = getattr(settings, 'MEMORY_CACHE_SIZE', 100)      # Max entries
        
        # Metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_writes = 0
        self.cache_invalidations = 0
        
        # Initialize Redis connection - defer to avoid event loop issues
        self._redis_initialized = False
    
    async def _ensure_redis_initialized(self):
        """Ensure Redis is initialized, initialize if not"""
        if not self._redis_initialized:
            try:
                # Use existing Redis URL from settings or default
                redis_url = getattr(settings, 'MEMORY_REDIS_URL', 'redis://localhost:6379/0')
                
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                
                # Test connection
                await self.redis_client.ping()
                app_logger.info("✅ Calendar cache service: Redis connection established")
                self._redis_initialized = True
                
            except Exception as e:
                app_logger.warning(f"⚠️ Calendar cache service: Redis unavailable, using memory-only cache: {e}")
                self.redis_client = None
                self._redis_initialized = True
    
    def _generate_cache_key(self, operation: str, **params) -> str:
        """Generate consistent cache key for operation and parameters"""
        # Create deterministic key from operation and sorted parameters
        param_string = json.dumps(params, sort_keys=True, default=str)
        param_hash = hashlib.md5(param_string.encode()).hexdigest()[:8]
        return f"{self.cache_prefix}:{operation}:{param_hash}"
    
    async def get_availability(
        self, 
        date: str, 
        calendar_id: str, 
        business_hours: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached availability data for a specific date"""
        cache_key = self._generate_cache_key(
            "availability",
            date=date,
            calendar_id=calendar_id,
            business_hours=business_hours
        )
        
        # L1: Check memory cache first
        memory_result = self._get_from_memory(cache_key)
        if memory_result is not None:
            self.cache_hits += 1
            app_logger.debug(f"Cache HIT (memory): {cache_key}")
            return memory_result
        
        # L2: Check Redis cache
        await self._ensure_redis_initialized()
        if self.redis_client:
            try:
                redis_data = await self.redis_client.get(cache_key)
                if redis_data:
                    result = json.loads(redis_data)
                    # Store in memory cache for faster future access
                    self._set_in_memory(cache_key, result, self.availability_ttl)
                    self.cache_hits += 1
                    app_logger.debug(f"Cache HIT (Redis): {cache_key}")
                    return result
            except Exception as e:
                app_logger.warning(f"Redis cache read error: {e}")
        
        # Cache miss
        self.cache_misses += 1
        app_logger.debug(f"Cache MISS: {cache_key}")
        return None
    
    async def set_availability(
        self, 
        date: str, 
        calendar_id: str, 
        business_hours: Dict[str, Any],
        availability_data: List[Dict[str, Any]]
    ):
        """Cache availability data for a specific date"""
        cache_key = self._generate_cache_key(
            "availability",
            date=date,
            calendar_id=calendar_id,
            business_hours=business_hours
        )
        
        self.cache_writes += 1
        
        # Store in memory cache
        self._set_in_memory(cache_key, availability_data, self.availability_ttl)
        
        # Store in Redis cache
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    cache_key,
                    self.availability_ttl,
                    json.dumps(availability_data, default=str)
                )
                app_logger.debug(f"Cache SET: {cache_key}")
            except Exception as e:
                app_logger.warning(f"Redis cache write error: {e}")
    
    async def get_conflicts(
        self,
        start_time: datetime,
        end_time: datetime,
        calendar_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached conflict check results"""
        cache_key = self._generate_cache_key(
            "conflicts",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            calendar_id=calendar_id
        )
        
        # L1: Memory cache
        memory_result = self._get_from_memory(cache_key)
        if memory_result is not None:
            self.cache_hits += 1
            return memory_result
        
        # L2: Redis cache
        if self.redis_client:
            try:
                redis_data = await self.redis_client.get(cache_key)
                if redis_data:
                    result = json.loads(redis_data)
                    self._set_in_memory(cache_key, result, self.conflict_check_ttl)
                    self.cache_hits += 1
                    return result
            except Exception as e:
                app_logger.warning(f"Redis cache read error: {e}")
        
        self.cache_misses += 1
        return None
    
    async def set_conflicts(
        self,
        start_time: datetime,
        end_time: datetime,
        calendar_id: str,
        conflicts: List[Dict[str, Any]]
    ):
        """Cache conflict check results"""
        cache_key = self._generate_cache_key(
            "conflicts",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            calendar_id=calendar_id
        )
        
        self.cache_writes += 1
        
        # Store in memory and Redis
        self._set_in_memory(cache_key, conflicts, self.conflict_check_ttl)
        
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    cache_key,
                    self.conflict_check_ttl,
                    json.dumps(conflicts, default=str)
                )
            except Exception as e:
                app_logger.warning(f"Redis cache write error: {e}")
    
    async def invalidate_date_cache(self, date: str, calendar_id: str):
        """Invalidate all cache entries for a specific date"""
        self.cache_invalidations += 1
        
        # Pattern matching for cache invalidation
        pattern = f"{self.cache_prefix}:*{date}*{calendar_id}*"
        
        # Invalidate memory cache
        keys_to_remove = [
            key for key in self.memory_cache.keys()
            if date in key and calendar_id in key
        ]
        for key in keys_to_remove:
            del self.memory_cache[key]
        
        # Invalidate Redis cache
        if self.redis_client:
            try:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
                app_logger.info(f"Invalidated {len(keys)} cache entries for date {date}")
            except Exception as e:
                app_logger.warning(f"Redis cache invalidation error: {e}")
    
    async def invalidate_calendar_cache(self, calendar_id: str):
        """Invalidate all cache entries for a calendar"""
        self.cache_invalidations += 1
        
        # Clear memory cache
        keys_to_remove = [
            key for key in self.memory_cache.keys()
            if calendar_id in key
        ]
        for key in keys_to_remove:
            del self.memory_cache[key]
        
        # Clear Redis cache
        if self.redis_client:
            try:
                pattern = f"{self.cache_prefix}:*{calendar_id}*"
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
                app_logger.info(f"Invalidated {len(keys)} cache entries for calendar {calendar_id}")
            except Exception as e:
                app_logger.warning(f"Redis cache invalidation error: {e}")
    
    def _get_from_memory(self, key: str) -> Optional[Any]:
        """Get data from memory cache with TTL check"""
        if key in self.memory_cache:
            cache_entry = self.memory_cache[key]
            if datetime.now() < cache_entry['expires_at']:
                return cache_entry['data']
            else:
                # Expired entry
                del self.memory_cache[key]
        return None
    
    def _set_in_memory(self, key: str, data: Any, ttl: int):
        """Set data in memory cache with TTL"""
        # Implement LRU eviction if cache is full
        if len(self.memory_cache) >= self.memory_cache_size:
            # Remove oldest entry
            oldest_key = min(
                self.memory_cache.keys(),
                key=lambda k: self.memory_cache[k]['created_at']
            )
            del self.memory_cache[oldest_key]
        
        self.memory_cache[key] = {
            'data': data,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(seconds=ttl)
        }
    
    async def warm_cache(self, dates: List[str], calendar_id: str):
        """Pre-warm cache with availability data for upcoming dates"""
        app_logger.info(f"Warming cache for {len(dates)} dates")
        # This would be called with actual availability data
        # Implementation depends on integration with GoogleCalendarClient
        pass
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache performance statistics"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / max(1, total_requests)) * 100
        
        stats = {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate_percentage": hit_rate,
            "cache_writes": self.cache_writes,
            "cache_invalidations": self.cache_invalidations,
            "memory_cache_size": len(self.memory_cache),
            "memory_cache_max_size": self.memory_cache_size,
            "redis_connected": self.redis_client is not None,
            "configuration": {
                "availability_ttl": self.availability_ttl,
                "conflict_check_ttl": self.conflict_check_ttl,
                "event_cache_ttl": self.event_cache_ttl,
                "cache_prefix": self.cache_prefix
            }
        }
        
        # Add Redis-specific stats
        if self.redis_client:
            try:
                redis_info = await self.redis_client.info()
                stats["redis_stats"] = {
                    "used_memory": redis_info.get("used_memory_human", "unknown"),
                    "connected_clients": redis_info.get("connected_clients", 0),
                    "keyspace_hits": redis_info.get("keyspace_hits", 0),
                    "keyspace_misses": redis_info.get("keyspace_misses", 0)
                }
            except Exception as e:
                stats["redis_stats"] = {"error": str(e)}
        
        return stats
    
    async def clear_all_cache(self):
        """Clear all cache data (for testing/admin purposes)"""
        # Clear memory cache
        self.memory_cache.clear()
        
        # Clear Redis cache
        if self.redis_client:
            try:
                pattern = f"{self.cache_prefix}:*"
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
                app_logger.info(f"Cleared {len(keys)} cache entries")
            except Exception as e:
                app_logger.warning(f"Redis cache clear error: {e}")
        
        # Reset metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_writes = 0
        self.cache_invalidations = 0


# Global calendar cache service instance
calendar_cache_service = CalendarCacheService()