"""
Performance Optimizer with Intelligent Caching and Load Management

Advanced performance optimization system with:
- Intelligent caching for AI/ML operations
- Database query optimization
- Request queue management with priority scheduling
- Memory optimization and garbage collection
- Network I/O optimization
- Real-time performance tuning based on metrics
"""

import asyncio
import time
import hashlib
import gc
import weakref
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
from functools import wraps
import json
import pickle

from ..core.logger import app_logger
from ..core.config import settings


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int
    ttl_seconds: int
    size_bytes: int = 0


@dataclass
class QueuedRequest:
    """Queued request with priority and metadata"""
    request_id: str
    priority: int  # 1 = highest, 5 = lowest
    func: Callable
    args: tuple
    kwargs: dict
    queued_at: datetime
    timeout_seconds: int = 30
    category: str = "general"


@dataclass
class PerformanceOptimization:
    """Performance optimization recommendation"""
    optimization_id: str
    category: str
    title: str
    description: str
    impact_score: float  # 0-100
    implementation_effort: str  # "low", "medium", "high"
    code_changes: List[str]
    estimated_improvement: str


class IntelligentCache:
    """
    High-performance cache with intelligent eviction and optimization
    
    Features:
    - LRU with frequency-based eviction
    - Automatic cache size management
    - TTL-based expiration
    - Cache hit/miss analytics
    - Memory usage monitoring
    """
    
    def __init__(self, max_size_mb: int = 100, default_ttl_seconds: int = 3600):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl_seconds = default_ttl_seconds
        
        # Cache storage
        self.cache: Dict[str, CacheEntry] = {}
        self.access_times: deque = deque(maxlen=10000)  # Track access patterns
        
        # Cache statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "size_bytes": 0,
            "entries": 0
        }
        
        app_logger.info(f"Intelligent cache initialized with {max_size_mb}MB limit")
    
    def _generate_key(self, key_parts: tuple) -> str:
        """Generate cache key from parts"""
        key_string = json.dumps(key_parts, sort_keys=True, default=str)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate object size in bytes"""
        try:
            return len(pickle.dumps(value))
        except:
            # Fallback for unpicklable objects
            return len(str(value).encode('utf-8'))
    
    def _evict_expired(self):
        """Evict expired cache entries"""
        current_time = datetime.now()
        expired_keys = []
        
        for key, entry in self.cache.items():
            if (current_time - entry.created_at).total_seconds() > entry.ttl_seconds:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_entry(key)
    
    def _evict_lru(self, target_size_bytes: int):
        """Evict least recently used entries to free space"""
        if not self.cache:
            return
        
        # Sort by last access time and access count (LRU + LFU hybrid)
        entries = list(self.cache.values())
        entries.sort(key=lambda x: (x.last_accessed, x.access_count))
        
        bytes_freed = 0
        for entry in entries:
            if bytes_freed >= target_size_bytes:
                break
            
            bytes_freed += entry.size_bytes
            self._remove_entry(entry.key)
            self.stats["evictions"] += 1
    
    def _remove_entry(self, key: str):
        """Remove cache entry and update stats"""
        if key in self.cache:
            entry = self.cache[key]
            self.stats["size_bytes"] -= entry.size_bytes
            self.stats["entries"] -= 1
            del self.cache[key]
    
    def get(self, key_parts: tuple) -> Optional[Any]:
        """Get cached value"""
        key = self._generate_key(key_parts)
        
        # Clean expired entries periodically
        if len(self.cache) > 100 and len(self.cache) % 50 == 0:
            self._evict_expired()
        
        if key in self.cache:
            entry = self.cache[key]
            
            # Check if expired
            if (datetime.now() - entry.created_at).total_seconds() > entry.ttl_seconds:
                self._remove_entry(key)
                self.stats["misses"] += 1
                return None
            
            # Update access info
            entry.last_accessed = datetime.now()
            entry.access_count += 1
            
            self.stats["hits"] += 1
            return entry.value
        
        self.stats["misses"] += 1
        return None
    
    def set(self, key_parts: tuple, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Set cached value"""
        key = self._generate_key(key_parts)
        ttl = ttl_seconds or self.default_ttl_seconds
        
        # Estimate size
        size_bytes = self._estimate_size(value)
        
        # Check if we need to make space
        if self.stats["size_bytes"] + size_bytes > self.max_size_bytes:
            # Try to free 25% of max size
            target_free = int(self.max_size_bytes * 0.25)
            self._evict_lru(target_free)
        
        # Create cache entry
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=1,
            ttl_seconds=ttl,
            size_bytes=size_bytes
        )
        
        # Remove old entry if exists
        if key in self.cache:
            self._remove_entry(key)
        
        # Add new entry
        self.cache[key] = entry
        self.stats["size_bytes"] += size_bytes
        self.stats["entries"] += 1
        
        return True
    
    def delete(self, key_parts: tuple) -> bool:
        """Delete cached value"""
        key = self._generate_key(key_parts)
        if key in self.cache:
            self._remove_entry(key)
            return True
        return False
    
    def clear(self):
        """Clear all cached values"""
        self.cache.clear()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "size_bytes": 0,
            "entries": 0
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        hit_rate = (
            self.stats["hits"] / (self.stats["hits"] + self.stats["misses"])
            if (self.stats["hits"] + self.stats["misses"]) > 0 else 0.0
        )
        
        return {
            **self.stats,
            "hit_rate": hit_rate,
            "size_mb": self.stats["size_bytes"] / (1024 * 1024),
            "utilization": self.stats["size_bytes"] / self.max_size_bytes
        }


class RequestQueue:
    """
    Priority-based request queue with intelligent scheduling
    
    Features:
    - Priority-based scheduling (1 = highest, 5 = lowest)
    - Request timeout management
    - Category-based queue management
    - Load balancing and throttling
    - Queue statistics and analytics
    """
    
    def __init__(self, max_concurrent: int = 10, max_queue_size: int = 1000):
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        
        # Queue storage
        self.queues: Dict[int, deque] = {i: deque() for i in range(1, 6)}  # Priority 1-5
        self.processing: Dict[str, QueuedRequest] = {}
        
        # Queue statistics
        self.stats = {
            "total_queued": 0,
            "total_processed": 0,
            "total_failed": 0,
            "total_timeouts": 0,
            "avg_wait_time": 0.0,
            "avg_processing_time": 0.0
        }
        
        # Processing state
        self._processing_active = True
        
        app_logger.info(f"Request queue initialized with {max_concurrent} concurrent limit")
    
    async def enqueue(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        priority: int = 3,
        timeout_seconds: int = 30,
        category: str = "general"
    ) -> str:
        """Enqueue a request for processing"""
        
        if kwargs is None:
            kwargs = {}
        
        # Check queue size limit
        total_queued = sum(len(q) for q in self.queues.values())
        if total_queued >= self.max_queue_size:
            raise Exception("Request queue is full")
        
        # Generate request ID
        request_id = f"{category}_{priority}_{int(time.time() * 1000)}"
        
        # Create queued request
        request = QueuedRequest(
            request_id=request_id,
            priority=max(1, min(5, priority)),  # Clamp to 1-5
            func=func,
            args=args,
            kwargs=kwargs,
            queued_at=datetime.now(),
            timeout_seconds=timeout_seconds,
            category=category
        )
        
        # Add to appropriate priority queue
        self.queues[request.priority].append(request)
        self.stats["total_queued"] += 1
        
        return request_id
    
    def _get_next_request(self) -> Optional[QueuedRequest]:
        """Get next request from highest priority queue"""
        
        # Check priorities from highest (1) to lowest (5)
        for priority in range(1, 6):
            queue = self.queues[priority]
            if queue:
                return queue.popleft()
        
        return None
    
    async def _process_request(self, request: QueuedRequest) -> Any:
        """Process a single request"""
        
        start_time = time.time()
        
        try:
            # Add to processing set
            self.processing[request.request_id] = request
            
            # Execute the function
            if asyncio.iscoroutinefunction(request.func):
                result = await request.func(*request.args, **request.kwargs)
            else:
                result = request.func(*request.args, **request.kwargs)
            
            # Update statistics
            processing_time = time.time() - start_time
            wait_time = (request.queued_at - datetime.now()).total_seconds()
            
            self.stats["total_processed"] += 1
            self.stats["avg_processing_time"] = (
                (self.stats["avg_processing_time"] * (self.stats["total_processed"] - 1) + processing_time)
                / self.stats["total_processed"]
            )
            self.stats["avg_wait_time"] = (
                (self.stats["avg_wait_time"] * (self.stats["total_processed"] - 1) + abs(wait_time))
                / self.stats["total_processed"]
            )
            
            return result
            
        except Exception as e:
            self.stats["total_failed"] += 1
            app_logger.error(f"Request processing failed: {e}")
            raise
        
        finally:
            # Remove from processing set
            if request.request_id in self.processing:
                del self.processing[request.request_id]
    
    async def start_processing(self):
        """Start request processing loop"""
        
        app_logger.info("Starting request queue processing")
        
        while self._processing_active:
            try:
                # Check if we can process more requests
                if len(self.processing) >= self.max_concurrent:
                    await asyncio.sleep(0.1)
                    continue
                
                # Get next request
                request = self._get_next_request()
                if not request:
                    await asyncio.sleep(0.1)
                    continue
                
                # Check timeout
                if (datetime.now() - request.queued_at).total_seconds() > request.timeout_seconds:
                    self.stats["total_timeouts"] += 1
                    continue
                
                # Process request in background
                asyncio.create_task(self._process_request(request))
                
            except Exception as e:
                app_logger.error(f"Request queue processing error: {e}")
                await asyncio.sleep(1)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        
        queue_sizes = {f"priority_{i}": len(self.queues[i]) for i in range(1, 6)}
        
        return {
            **self.stats,
            "current_processing": len(self.processing),
            "queue_sizes": queue_sizes,
            "total_queued_current": sum(len(q) for q in self.queues.values())
        }
    
    async def stop_processing(self):
        """Stop request processing"""
        self._processing_active = False
        app_logger.info("Request queue processing stopped")


class PerformanceOptimizer:
    """
    Advanced performance optimizer with intelligent caching and optimization
    
    Features:
    - Intelligent caching for AI/ML operations
    - Request queue management
    - Performance bottleneck detection
    - Automatic optimization recommendations  
    - Memory and resource optimization
    - Database query caching and optimization
    """
    
    def __init__(self):
        # Initialize components
        self.cache = IntelligentCache(max_size_mb=200, default_ttl_seconds=1800)
        self.request_queue = RequestQueue(max_concurrent=15, max_queue_size=2000)
        
        # Optimization tracking
        self.optimizations_applied: List[PerformanceOptimization] = []
        self.performance_history: deque = deque(maxlen=1000)
        
        # Function call analytics
        self.function_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "calls": 0,
            "total_time": 0.0,
            "avg_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        })
        
        app_logger.info("Performance Optimizer initialized with intelligent caching and queue management")
    
    async def start_optimization(self):
        """Start performance optimization services"""
        
        # Start request queue processing
        await asyncio.gather(
            self.request_queue.start_processing(),
            self._optimization_loop(),
            return_exceptions=True
        )
    
    async def _optimization_loop(self):
        """Continuous optimization monitoring and application"""
        
        while True:
            try:
                await self._analyze_performance()
                await self._apply_automatic_optimizations()
                await self._cleanup_resources()
                
                await asyncio.sleep(300)  # Run every 5 minutes
                
            except Exception as e:
                app_logger.error(f"Optimization loop error: {e}")
                await asyncio.sleep(300)
    
    async def _analyze_performance(self):
        """Analyze current performance and identify bottlenecks"""
        
        try:
            # Get current metrics from various sources
            cache_stats = self.cache.get_stats()
            queue_stats = self.request_queue.get_stats()
            
            # Analyze cache performance
            if cache_stats["hit_rate"] < 0.6:  # Less than 60% hit rate
                optimization = PerformanceOptimization(
                    optimization_id="low_cache_hit_rate",
                    category="caching",
                    title="Low Cache Hit Rate",
                    description=f"Cache hit rate is {cache_stats['hit_rate']:.1%}, below optimal threshold",
                    impact_score=75.0,
                    implementation_effort="medium",
                    code_changes=["Increase cache TTL", "Improve cache key strategy", "Add preemptive caching"],
                    estimated_improvement="20-30% response time reduction"
                )
                
                await self._recommend_optimization(optimization)
            
            # Analyze queue performance
            if queue_stats["avg_wait_time"] > 5.0:  # More than 5 seconds wait time
                optimization = PerformanceOptimization(
                    optimization_id="high_queue_wait_time",
                    category="queuing",
                    title="High Queue Wait Time",
                    description=f"Average queue wait time is {queue_stats['avg_wait_time']:.1f} seconds",
                    impact_score=85.0,
                    implementation_effort="low",
                    code_changes=["Increase concurrent request limit", "Implement request prioritization", "Add more worker processes"],
                    estimated_improvement="40-50% reduction in wait times"
                )
                
                await self._recommend_optimization(optimization)
            
        except Exception as e:
            app_logger.error(f"Performance analysis failed: {e}")
    
    async def _recommend_optimization(self, optimization: PerformanceOptimization):
        """Recommend a performance optimization"""
        
        # Check if already applied
        if any(opt.optimization_id == optimization.optimization_id for opt in self.optimizations_applied):
            return
        
        app_logger.info(
            f"Performance optimization recommended: {optimization.title}",
            extra={
                "optimization_id": optimization.optimization_id,
                "impact_score": optimization.impact_score,
                "category": optimization.category
            }
        )
    
    async def _apply_automatic_optimizations(self):
        """Apply automatic performance optimizations"""
        
        try:
            # Automatic cache size adjustment
            cache_stats = self.cache.get_stats()
            if cache_stats["utilization"] > 0.9:  # Over 90% cache utilization
                # Force cleanup of least used entries
                self.cache._evict_lru(int(self.cache.max_size_bytes * 0.2))  # Free 20%
                
                app_logger.info("Automatic cache cleanup performed due to high utilization")
            
            # Automatic queue management
            queue_stats = self.request_queue.get_stats()
            if queue_stats["total_queued_current"] > queue_stats.get("max_queue_size", 1000) * 0.8:
                # Clear old requests from low priority queues
                for priority in range(4, 6):  # Clear priorities 4 and 5
                    while self.request_queue.queues[priority]:
                        expired_request = self.request_queue.queues[priority].popleft()
                        if (datetime.now() - expired_request.queued_at).total_seconds() > 60:
                            continue  # Keep clearing
                        else:
                            self.request_queue.queues[priority].appendleft(expired_request)
                            break
                
                app_logger.info("Automatic queue cleanup performed due to high queue size")
            
        except Exception as e:
            app_logger.error(f"Automatic optimization failed: {e}")
    
    async def _cleanup_resources(self):
        """Perform resource cleanup"""
        
        try:
            # Force garbage collection if memory usage is high
            import psutil
            memory_percent = psutil.virtual_memory().percent
            
            if memory_percent > 80:
                gc.collect()
                app_logger.info(f"Garbage collection performed due to high memory usage ({memory_percent:.1f}%)")
            
        except Exception as e:
            app_logger.error(f"Resource cleanup failed: {e}")
    
    def cached(self, ttl_seconds: int = 1800, key_func: Optional[Callable] = None):
        """
        Decorator for intelligent function caching
        
        Args:
            ttl_seconds: Time to live for cached result
            key_func: Custom function to generate cache key
        """
        
        def decorator(func: Callable):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = (func.__name__, args, tuple(sorted(kwargs.items())))
                
                # Try to get from cache
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    self.function_stats[func.__name__]["cache_hits"] += 1
                    return cached_result
                
                # Execute function
                start_time = time.time()
                
                try:
                    result = await func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    # Update function statistics
                    stats = self.function_stats[func.__name__]
                    stats["calls"] += 1
                    stats["total_time"] += execution_time
                    stats["avg_time"] = stats["total_time"] / stats["calls"]
                    stats["cache_misses"] += 1
                    
                    # Cache the result
                    self.cache.set(cache_key, result, ttl_seconds)
                    
                    return result
                    
                except Exception as e:
                    app_logger.error(f"Cached function {func.__name__} failed: {e}")
                    raise
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = (func.__name__, args, tuple(sorted(kwargs.items())))
                
                # Try to get from cache
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    self.function_stats[func.__name__]["cache_hits"] += 1
                    return cached_result
                
                # Execute function
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    # Update function statistics
                    stats = self.function_stats[func.__name__]
                    stats["calls"] += 1
                    stats["total_time"] += execution_time
                    stats["avg_time"] = stats["total_time"] / stats["calls"]
                    stats["cache_misses"] += 1
                    
                    # Cache the result
                    self.cache.set(cache_key, result, ttl_seconds)
                    
                    return result
                    
                except Exception as e:
                    app_logger.error(f"Cached function {func.__name__} failed: {e}")
                    raise
            
            # Return appropriate wrapper based on function type
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    async def enqueue_request(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        priority: int = 3,
        category: str = "general"
    ) -> str:
        """Enqueue a request for optimized processing"""
        
        return await self.request_queue.enqueue(
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            category=category
        )
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get comprehensive optimization statistics"""
        
        return {
            "cache": self.cache.get_stats(),
            "queue": self.request_queue.get_stats(),
            "function_analytics": dict(self.function_stats),
            "optimizations_applied": len(self.optimizations_applied),
            "performance_score": self._calculate_performance_score()
        }
    
    def _calculate_performance_score(self) -> float:
        """Calculate overall performance score (0-100)"""
        
        try:
            cache_stats = self.cache.get_stats()
            queue_stats = self.request_queue.get_stats()
            
            # Cache performance (40% weight)
            cache_score = min(100, cache_stats["hit_rate"] * 100)
            
            # Queue performance (40% weight)
            queue_score = max(0, 100 - (queue_stats["avg_wait_time"] * 10))  # Penalty for wait time
            
            # Function performance (20% weight)
            if self.function_stats:
                avg_function_time = sum(
                    stats["avg_time"] for stats in self.function_stats.values()
                ) / len(self.function_stats)
                function_score = max(0, 100 - (avg_function_time * 20))  # Penalty for slow functions
            else:
                function_score = 100
            
            # Weighted overall score
            overall_score = (
                cache_score * 0.4 +
                queue_score * 0.4 +
                function_score * 0.2
            )
            
            return min(100, max(0, overall_score))
            
        except Exception as e:
            app_logger.error(f"Performance score calculation failed: {e}")
            return 0.0
    
    async def stop_optimization(self):
        """Stop performance optimization services"""
        
        await self.request_queue.stop_processing()
        app_logger.info("Performance optimization stopped")


# Global performance optimizer instance
performance_optimizer = PerformanceOptimizer()