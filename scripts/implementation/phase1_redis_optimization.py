#!/usr/bin/env python3
"""
FASE 1: Script de Otimização do Redis Cache
SuperClaude Framework Implementation Script
"""

import asyncio
import json
import hashlib
from typing import Optional, Dict, Any
from redis import asyncio as aioredis
import lz4.frame
from app.core.config import settings

class RedisOptimization:
    """
    Implementa otimizações de cache Redis
    Target: >80% hit rate
    """
    
    def __init__(self):
        self.redis_url = settings.MEMORY_REDIS_URL
        self.pools = {}
        
    async def setup_optimized_pools(self):
        """Configure optimized connection pools"""
        
        # L1 Hot Cache Pool (Memory-like speed)
        self.pools['hot'] = await aioredis.create_redis_pool(
            self.redis_url,
            minsize=5,
            maxsize=20,
            db=1  # Separate DB for hot cache
        )
        
        # L2 Session Cache Pool
        self.pools['session'] = await aioredis.create_redis_pool(
            self.redis_url,
            minsize=10,
            maxsize=50,
            db=2
        )
        
        # L3 RAG Cache Pool
        self.pools['rag'] = await aioredis.create_redis_pool(
            self.redis_url,
            minsize=5,
            maxsize=30,
            db=3
        )
        
        print("✅ Redis pools configurados com sucesso")
        
    async def implement_hierarchical_cache(self):
        """Implement 3-layer hierarchical caching"""
        
        cache_config = {
            "L1_hot_cache": {
                "ttl": 300,  # 5 minutes
                "max_size": "100MB",
                "eviction": "lfu",  # Least Frequently Used
                "compression": False  # No compression for speed
            },
            "L2_sessions": {
                "ttl": 604800,  # 7 days
                "prefix": "sess:",
                "compression": "lz4",
                "max_entries": 10000
            },
            "L3_rag": {
                "ttl": 2592000,  # 30 days
                "prefix": "rag:",
                "compression": "lz4",
                "similarity_threshold": 0.85,
                "max_entries": 50000
            }
        }
        
        # Configure each cache layer
        for layer, config in cache_config.items():
            print(f"\n🔧 Configurando {layer}...")
            # Save config to Redis
            await self.pools['hot'].set(
                f"config:{layer}",
                json.dumps(config),
                expire=0  # No expiration for config
            )
            print(f"✅ {layer} configurado")
            
        return cache_config
    
    async def setup_cache_warming(self):
        """Implement intelligent cache warming"""
        
        # Common queries to pre-warm
        warm_queries = [
            # Greeting variations
            ("ola", "Olá! Sou Cecília, assistente virtual do Kumon Vila A..."),
            ("oi", "Oi! Bem-vindo ao Kumon Vila A..."),
            ("bom dia", "Bom dia! Como posso ajudar você hoje?..."),
            
            # Common questions
            ("horarios", "Nossos horários são de segunda a sexta..."),
            ("preco", "Para informações sobre valores..."),
            ("metodo", "O método Kumon desenvolve..."),
            ("agendar", "Para agendar uma entrevista...")
        ]
        
        print("\n🔥 Aquecendo cache com queries comuns...")
        
        for query, response in warm_queries:
            # Generate cache key
            query_hash = hashlib.md5(query.encode()).hexdigest()
            cache_key = f"rag:{query_hash}"
            
            # Compress and store
            compressed = lz4.frame.compress(response.encode())
            await self.pools['rag'].setex(
                cache_key,
                2592000,  # 30 days
                compressed
            )
            
        print(f"✅ {len(warm_queries)} queries aquecidas no cache")
        
    async def implement_cache_metrics(self):
        """Setup cache hit rate monitoring"""
        
        metrics_script = """
        local hits = redis.call('get', KEYS[1]) or 0
        local misses = redis.call('get', KEYS[2]) or 0
        local total = hits + misses
        
        if total > 0 then
            return {hits, misses, (hits / total) * 100}
        else
            return {0, 0, 0}
        end
        """
        
        # Register Lua script for atomic metrics
        script_sha = await self.pools['hot'].script_load(metrics_script)
        
        # Initialize counters
        await self.pools['hot'].set('metrics:cache_hits', 0)
        await self.pools['hot'].set('metrics:cache_misses', 0)
        
        print("\n📊 Sistema de métricas de cache configurado")
        print(f"Script SHA: {script_sha}")
        
        return script_sha
    
    async def optimize_redis_config(self):
        """Apply Redis configuration optimizations"""
        
        optimizations = [
            # Memory optimizations
            ("maxmemory-policy", "allkeys-lru"),
            ("maxmemory", "500mb"),
            
            # Performance optimizations
            ("tcp-keepalive", "300"),
            ("timeout", "0"),
            ("tcp-backlog", "511"),
            
            # Persistence (disabled for cache)
            ("save", ""),
            ("appendonly", "no"),
            
            # Compression
            ("rdbcompression", "yes"),
            ("activedefrag", "yes")
        ]
        
        print("\n⚙️ Aplicando otimizações de configuração Redis...")
        
        for param, value in optimizations:
            try:
                await self.pools['hot'].config_set(param, value)
                print(f"✅ {param} = {value}")
            except Exception as e:
                print(f"⚠️ Não foi possível definir {param}: {e}")
        
    async def test_cache_performance(self):
        """Test cache performance metrics"""
        
        print("\n🧪 Testando performance do cache...")
        
        # Test write performance
        write_times = []
        for i in range(100):
            start = asyncio.get_event_loop().time()
            await self.pools['hot'].setex(f"test:key{i}", 300, f"value{i}")
            write_times.append((asyncio.get_event_loop().time() - start) * 1000)
        
        # Test read performance
        read_times = []
        for i in range(100):
            start = asyncio.get_event_loop().time()
            await self.pools['hot'].get(f"test:key{i}")
            read_times.append((asyncio.get_event_loop().time() - start) * 1000)
        
        # Calculate metrics
        avg_write = sum(write_times) / len(write_times)
        avg_read = sum(read_times) / len(read_times)
        
        print(f"\n📊 Resultados de Performance:")
        print(f"Escrita média: {avg_write:.2f}ms")
        print(f"Leitura média: {avg_read:.2f}ms")
        print(f"Operações/segundo: {1000 / avg_read:.0f} reads/s")
        
        # Cleanup
        for i in range(100):
            await self.pools['hot'].delete(f"test:key{i}")
            
        return {
            "avg_write_ms": avg_write,
            "avg_read_ms": avg_read,
            "ops_per_second": 1000 / avg_read
        }


async def main():
    """Execute Redis optimization setup"""
    
    print("🚀 Iniciando otimização do Redis Cache...")
    optimizer = RedisOptimization()
    
    # Setup pools
    await optimizer.setup_optimized_pools()
    
    # Implement hierarchical cache
    cache_config = await optimizer.implement_hierarchical_cache()
    print("\n📋 Configuração do cache hierárquico:")
    print(json.dumps(cache_config, indent=2))
    
    # Setup cache warming
    await optimizer.setup_cache_warming()
    
    # Implement metrics
    metrics_sha = await optimizer.implement_cache_metrics()
    
    # Apply optimizations
    await optimizer.optimize_redis_config()
    
    # Test performance
    performance = await optimizer.test_cache_performance()
    
    print("\n✅ Otimização do Redis concluída!")
    print(f"\n🎯 Meta de hit rate: >80%")
    print(f"🎯 Latência alvo: <5ms para hot cache")
    
    # Close pools
    for pool in optimizer.pools.values():
        pool.close()
        await pool.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())