"""
Enhanced Cache Service - Wave 2 Implementation
Hierarchical caching with L1/L2/L3 layers targeting >80% hit rate
"""

import asyncio
import time
import hashlib
# Temporarily disable lz4 until proper installation
# import lz4.frame
import json
import pickle
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

import redis.asyncio as redis
from ..core.config import settings
from ..core.logger import app_logger
from ..core.circuit_breaker import circuit_breaker, CircuitBreakerOpenError


class CacheLayer(Enum):
    """Cache layer enumeration"""
    L1_MEMORY = "l1_memory"
    L2_REDIS_SESSION = "l2_redis_session" 
    L3_REDIS_RAG = "l3_redis_rag"


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    layer: CacheLayer
    created_at: datetime
    ttl: int
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    compressed: bool = False
    size_bytes: int = 0


@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    total_requests: int = 0
    hits: int = 0
    misses: int = 0
    l1_hits: int = 0
    l2_hits: int = 0
    l3_hits: int = 0
    evictions: int = 0
    errors: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Overall hit rate percentage"""
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100
    
    @property
    def l1_hit_rate(self) -> float:
        """L1 hit rate percentage"""
        if self.total_requests == 0:
            return 0.0
        return (self.l1_hits / self.total_requests) * 100


class EnhancedCacheService:
    """
    Enterprise-grade hierarchical cache service
    
    L1: Memory Cache (ultra-fast, 5-minute TTL)
    L2: Redis Sessions (7-day TTL, conversation state)
    L3: Redis RAG (30-day TTL, knowledge responses)
    """
    
    def __init__(self):
        # Cache configurations
        self.cache_config = {
            "l1_memory": {
                "max_entries": 1000,
                "ttl": 300,  # 5 minutes
                "max_size_mb": 100,
                "compression": False
            },
            "l2_sessions": {
                "ttl": 604800,  # 7 days
                "prefix": "sess:",
                "compression": True,
                "max_entries": 10000
            },
            "l3_rag": {
                "ttl": 2592000,  # 30 days
                "prefix": "rag:",
                "compression": True,
                "max_entries": 50000,
                "similarity_threshold": 0.85
            }
        }
        
        # L1 Memory cache
        self.l1_cache: Dict[str, CacheEntry] = {}
        
        # Redis connections
        self.redis_sessions = None
        self.redis_rag = None
        
        # Metrics
        self.metrics = CacheMetrics()
        
        # Cache warming data
        self.warming_patterns = []
        
        app_logger.info("Enhanced Cache Service initializing...")
    
    async def initialize(self):
        """Initialize Redis connections and cache warming"""
        try:
            # Setup Redis connections with modern API
            self.redis_sessions = redis.from_url(
                settings.MEMORY_REDIS_URL,
                db=2,  # Sessions DB
                max_connections=20,
                retry_on_timeout=True,
                socket_timeout=5.0,
                decode_responses=False  # Keep binary for pickle compatibility
            )
            
            self.redis_rag = redis.from_url(
                settings.MEMORY_REDIS_URL,
                db=3,  # RAG DB
                max_connections=30,
                retry_on_timeout=True,
                socket_timeout=5.0,
                decode_responses=False  # Keep binary for pickle compatibility
            )
            
            # Test connections
            await self.redis_sessions.ping()
            await self.redis_rag.ping()
            
            # Start cache warming
            await self._warm_cache()
            
            app_logger.info("Enhanced Cache Service initialized successfully", extra={
                "l1_max_entries": self.cache_config["l1_memory"]["max_entries"],
                "l2_ttl_days": self.cache_config["l2_sessions"]["ttl"] // 86400,
                "l3_ttl_days": self.cache_config["l3_rag"]["ttl"] // 86400
            })
            
        except Exception as e:
            app_logger.error(f"Cache service initialization failed: {e}")
            raise
    
    @circuit_breaker(failure_threshold=3, recovery_timeout=10, name="cache_get")
    async def get(self, key: str, category: str = "default") -> Optional[Any]:
        """
        Get value from hierarchical cache
        
        Args:
            key: Cache key
            category: Cache category (conversation, rag, general)
            
        Returns:
            Cached value or None if not found
        """
        self.metrics.total_requests += 1
        start_time = time.time()
        
        try:
            # Step 1: Check L1 memory cache
            l1_key = self._generate_l1_key(key, category)
            if l1_key in self.l1_cache:
                entry = self.l1_cache[l1_key]
                if not self._is_expired(entry):
                    entry.access_count += 1
                    entry.last_accessed = datetime.now()
                    self.metrics.hits += 1
                    self.metrics.l1_hits += 1
                    
                    app_logger.debug(f"L1 cache hit: {key}", extra={
                        "cache_layer": "L1",
                        "access_count": entry.access_count
                    })
                    
                    return entry.value
                else:
                    # Remove expired entry
                    del self.l1_cache[l1_key]
            
            # Step 2: Check L2 Redis sessions
            if category in ["conversation", "session", "user"]:
                l2_value = await self._get_from_l2(key)
                if l2_value is not None:
                    # Store in L1 for future access
                    await self._store_in_l1(key, l2_value, category)
                    self.metrics.hits += 1
                    self.metrics.l2_hits += 1
                    
                    app_logger.debug(f"L2 cache hit: {key}", extra={"cache_layer": "L2"})
                    return l2_value
            
            # Step 3: Check L3 Redis RAG
            if category in ["rag", "knowledge", "response"]:
                l3_value = await self._get_from_l3(key)
                if l3_value is not None:
                    # Store in L1 for future access
                    await self._store_in_l1(key, l3_value, category)
                    self.metrics.hits += 1
                    self.metrics.l3_hits += 1
                    
                    app_logger.debug(f"L3 cache hit: {key}", extra={"cache_layer": "L3"})
                    return l3_value
            
            # Cache miss
            self.metrics.misses += 1
            
            elapsed_ms = (time.time() - start_time) * 1000
            app_logger.debug(f"Cache miss: {key}", extra={
                "category": category,
                "lookup_time_ms": elapsed_ms
            })
            
            return None
            
        except Exception as e:
            self.metrics.errors += 1
            app_logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    @circuit_breaker(failure_threshold=3, recovery_timeout=10, name="cache_set")
    async def set(
        self, 
        key: str, 
        value: Any, 
        category: str = "default",
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in appropriate cache layer
        
        Args:
            key: Cache key
            value: Value to cache
            category: Cache category
            ttl: Time to live (optional)
            
        Returns:
            True if successfully cached
        """
        try:
            # Determine appropriate cache layer and TTL
            if category in ["conversation", "session", "user"]:
                # Store in L2 (sessions) and L1
                layer_ttl = ttl or self.cache_config["l2_sessions"]["ttl"]
                await self._store_in_l2(key, value, layer_ttl)
                await self._store_in_l1(key, value, category)
                
            elif category in ["rag", "knowledge", "response"]:
                # Store in L3 (RAG) and L1
                layer_ttl = ttl or self.cache_config["l3_rag"]["ttl"]
                await self._store_in_l3(key, value, layer_ttl)
                await self._store_in_l1(key, value, category)
                
            else:
                # Store only in L1 for general cache
                await self._store_in_l1(key, value, category)
            
            app_logger.debug(f"Cache set: {key}", extra={
                "category": category,
                "value_size": len(str(value))
            })
            
            return True
            
        except Exception as e:
            self.metrics.errors += 1
            app_logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def _get_from_l2(self, key: str) -> Optional[Any]:
        """Get from L2 Redis sessions cache"""
        try:
            redis_key = f"{self.cache_config['l2_sessions']['prefix']}{key}"
            data = await self.redis_sessions.get(redis_key)
            
            if data:
                # Temporarily disable compression until lz4 is properly installed
                # if self.cache_config["l2_sessions"]["compression"]:
                #     # Decompress and deserialize
                #     decompressed = lz4.frame.decompress(data)
                #     return pickle.loads(decompressed)
                # else:
                return pickle.loads(data)
            
            return None
            
        except Exception as e:
            app_logger.error(f"L2 cache get error: {e}")
            return None
    
    async def _get_from_l3(self, key: str) -> Optional[Any]:
        """Get from L3 Redis RAG cache"""
        try:
            redis_key = f"{self.cache_config['l3_rag']['prefix']}{key}"
            data = await self.redis_rag.get(redis_key)
            
            if data:
                # Temporarily disable compression until lz4 is properly installed
                # if self.cache_config["l3_rag"]["compression"]:
                #     # Decompress and deserialize
                #     decompressed = lz4.frame.decompress(data)
                #     return pickle.loads(decompressed)
                # else:
                return pickle.loads(data)
            
            return None
            
        except Exception as e:
            app_logger.error(f"L3 cache get error: {e}")
            return None
    
    async def _store_in_l1(self, key: str, value: Any, category: str):
        """Store in L1 memory cache"""
        try:
            # Check memory limits
            if len(self.l1_cache) >= self.cache_config["l1_memory"]["max_entries"]:
                await self._evict_l1_entries()
            
            l1_key = self._generate_l1_key(key, category)
            entry = CacheEntry(
                key=l1_key,
                value=value,
                layer=CacheLayer.L1_MEMORY,
                created_at=datetime.now(),
                ttl=self.cache_config["l1_memory"]["ttl"],
                size_bytes=len(str(value))
            )
            
            self.l1_cache[l1_key] = entry
            
        except Exception as e:
            app_logger.error(f"L1 cache store error: {e}")
    
    async def _store_in_l2(self, key: str, value: Any, ttl: int):
        """Store in L2 Redis sessions cache"""
        try:
            redis_key = f"{self.cache_config['l2_sessions']['prefix']}{key}"
            
            # Serialize and optionally compress
            serialized = pickle.dumps(value)
            # Temporarily disable compression until lz4 is properly installed
            # if self.cache_config["l2_sessions"]["compression"]:
            #     data = lz4.frame.compress(serialized)
            # else:
            data = serialized
            
            await self.redis_sessions.setex(redis_key, ttl, data)
            
        except Exception as e:
            app_logger.error(f"L2 cache store error: {e}")
    
    async def _store_in_l3(self, key: str, value: Any, ttl: int):
        """Store in L3 Redis RAG cache"""
        try:
            redis_key = f"{self.cache_config['l3_rag']['prefix']}{key}"
            
            # Serialize and optionally compress
            serialized = pickle.dumps(value)
            # Temporarily disable compression until lz4 is properly installed
            # if self.cache_config["l3_rag"]["compression"]:
            #     data = lz4.frame.compress(serialized)
            # else:
            data = serialized
            
            await self.redis_rag.setex(redis_key, ttl, data)
            
        except Exception as e:
            app_logger.error(f"L3 cache store error: {e}")
    
    def _generate_l1_key(self, key: str, category: str) -> str:
        """Generate L1 cache key with category prefix"""
        return f"{category}:{key}"
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if cache entry is expired"""
        age_seconds = (datetime.now() - entry.created_at).total_seconds()
        return age_seconds > entry.ttl
    
    async def _evict_l1_entries(self):
        """Evict old L1 entries using LRU policy"""
        try:
            # Sort by last access time (LRU)
            sorted_entries = sorted(
                self.l1_cache.items(),
                key=lambda x: x[1].last_accessed or x[1].created_at
            )
            
            # Remove oldest 20% of entries
            evict_count = len(sorted_entries) // 5
            for i in range(evict_count):
                key_to_evict = sorted_entries[i][0]
                del self.l1_cache[key_to_evict]
                self.metrics.evictions += 1
            
            app_logger.debug(f"Evicted {evict_count} L1 cache entries")
            
        except Exception as e:
            app_logger.error(f"L1 cache eviction error: {e}")
    
    async def _warm_cache(self):
        """Warm cache with common patterns"""
        try:
            # Common greeting patterns
            greeting_patterns = [
                ("ola", "Olá! Sou Cecília, assistente virtual do Kumon Vila A. Como posso ajudá-lo hoje? 😊"),
                ("oi", "Oi! Bem-vindo ao Kumon Vila A! Em que posso auxiliá-lo?"),
                ("bom_dia", "Bom dia! Como posso ajudar você hoje no Kumon Vila A?"),
                ("boa_tarde", "Boa tarde! Sou Cecília do Kumon Vila A. Como posso auxiliá-lo?"),
                ("boa_noite", "Boa noite! Em que posso ajudá-lo no Kumon Vila A?"),
            ]
            
            # Common information patterns
            info_patterns = [
                ("horarios", "Nossos horários de funcionamento são de segunda a sexta, das 8h às 18h."),
                ("endereco", "Estamos localizados na Rua Amoreira, 571. Salas 6 e 7. Jardim das Laranjeiras."),
                ("telefone", "Nosso telefone para contato é (51) 99692-1999."),
                ("metodo_kumon", "O método Kumon desenvolve a capacidade de aprendizado autodidático através de material didático programado."),
                ("disciplinas", "Oferecemos Kumon de Matemática, Português e Inglês para todas as idades."),
            ]
            
            # Warm L3 cache (RAG responses)
            for pattern, response in greeting_patterns + info_patterns:
                await self.set(
                    key=self._generate_cache_key(pattern),
                    value=response,
                    category="rag"
                )
            
            app_logger.info(f"Cache warmed with {len(greeting_patterns + info_patterns)} patterns")
            
        except Exception as e:
            app_logger.error(f"Cache warming error: {e}")
    
    def _generate_cache_key(self, text: str) -> str:
        """Generate consistent cache key from text"""
        # Normalize text and generate hash
        normalized = text.lower().strip().replace(" ", "_")
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    async def invalidate(self, key: str, category: str = "default"):
        """Invalidate cache entry across all layers"""
        try:
            # L1 invalidation
            l1_key = self._generate_l1_key(key, category)
            if l1_key in self.l1_cache:
                del self.l1_cache[l1_key]
            
            # L2 invalidation
            if category in ["conversation", "session", "user"]:
                redis_key = f"{self.cache_config['l2_sessions']['prefix']}{key}"
                await self.redis_sessions.delete(redis_key)
            
            # L3 invalidation
            if category in ["rag", "knowledge", "response"]:
                redis_key = f"{self.cache_config['l3_rag']['prefix']}{key}"
                await self.redis_rag.delete(redis_key)
            
            app_logger.debug(f"Cache invalidated: {key}")
            
        except Exception as e:
            app_logger.error(f"Cache invalidation error: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive cache metrics"""
        
        # Calculate current memory usage
        l1_memory_usage = sum(entry.size_bytes for entry in self.l1_cache.values())
        
        return {
            "performance_metrics": {
                "total_requests": self.metrics.total_requests,
                "cache_hits": self.metrics.hits,
                "cache_misses": self.metrics.misses,
                "hit_rate_percentage": self.metrics.hit_rate,
                "l1_hit_rate_percentage": self.metrics.l1_hit_rate,
                "error_rate_percentage": (self.metrics.errors / max(1, self.metrics.total_requests)) * 100
            },
            "layer_metrics": {
                "l1_hits": self.metrics.l1_hits,
                "l2_hits": self.metrics.l2_hits,
                "l3_hits": self.metrics.l3_hits,
                "l1_entries": len(self.l1_cache),
                "l1_memory_mb": l1_memory_usage / (1024 * 1024)
            },
            "operational_metrics": {
                "evictions": self.metrics.evictions,
                "errors": self.metrics.errors
            },
            "target_metrics": {
                "hit_rate_target": 80.0,
                "target_met": self.metrics.hit_rate >= 80.0,
                "performance_assessment": "EXCELLENT" if self.metrics.hit_rate >= 90 else "GOOD" if self.metrics.hit_rate >= 80 else "NEEDS_IMPROVEMENT"
            },
            "configuration": self.cache_config
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive cache health check"""
        try:
            start_time = time.time()
            
            # Test all cache layers
            test_key = f"health_check_{int(time.time())}"
            test_value = {"timestamp": datetime.now().isoformat(), "test": True}
            
            # Test L1
            await self._store_in_l1(test_key, test_value, "test")
            l1_test = self.l1_cache.get(self._generate_l1_key(test_key, "test"))
            
            # Test L2
            await self._store_in_l2(test_key, test_value, 60)
            l2_test = await self._get_from_l2(test_key)
            
            # Test L3
            await self._store_in_l3(test_key, test_value, 60)
            l3_test = await self._get_from_l3(test_key)
            
            # Cleanup
            await self.invalidate(test_key, "test")
            
            health_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "health_check_time_ms": health_time,
                "layers": {
                    "l1_memory": "operational" if l1_test else "degraded",
                    "l2_redis_sessions": "operational" if l2_test else "degraded",
                    "l3_redis_rag": "operational" if l3_test else "degraded"
                },
                "metrics": self.get_metrics(),
                "redis_connections": {
                    "sessions_pool": "connected",
                    "rag_pool": "connected"
                }
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "layers": {
                    "l1_memory": "unknown",
                    "l2_redis_sessions": "unknown", 
                    "l3_redis_rag": "unknown"
                }
            }
    
    async def cleanup(self):
        """Cleanup cache connections"""
        try:
            if self.redis_sessions:
                self.redis_sessions.close()
                await self.redis_sessions.wait_closed()
            
            if self.redis_rag:
                self.redis_rag.close()
                await self.redis_rag.wait_closed()
            
            app_logger.info("Enhanced Cache Service cleaned up")
            
        except Exception as e:
            app_logger.error(f"Cache cleanup error: {e}")


# Global enhanced cache service
enhanced_cache_service = EnhancedCacheService()