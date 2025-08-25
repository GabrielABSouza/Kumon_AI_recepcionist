"""
Cache Manager - Wave 2 Implementation
Central cache management with intelligent caching strategies
"""

import hashlib
import json
import time
from typing import Any, Optional, Dict, List, Callable
from functools import wraps
from datetime import datetime

from ..core.logger import app_logger
from ..core.config import settings
from .enhanced_cache_service import enhanced_cache_service


class CacheManager:
    """
    Central cache manager with intelligent caching strategies
    
    Provides high-level caching operations for:
    - Conversation state
    - RAG responses
    - User profiles
    - Intent classifications
    - API responses
    """
    
    def __init__(self):
        self.cache_service = enhanced_cache_service
        self.cache_patterns = {
            "conversation": {"category": "conversation", "ttl": 604800},  # 7 days
            "rag": {"category": "rag", "ttl": 2592000},  # 30 days
            "user_profile": {"category": "user", "ttl": 2592000},  # 30 days
            "intent": {"category": "rag", "ttl": 86400},  # 1 day
            "api_response": {"category": "default", "ttl": 3600},  # 1 hour
            "session": {"category": "session", "ttl": 604800}  # 7 days
        }
        
        app_logger.info("Cache Manager initialized")
    
    async def initialize(self):
        """Initialize cache service"""
        await self.cache_service.initialize()
        app_logger.info("Cache Manager ready")
    
    # ==================== CONVERSATION CACHING ====================
    
    async def get_conversation_state(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Get conversation state from cache"""
        cache_key = f"conversation_state:{phone_number}"
        return await self.cache_service.get(cache_key, "conversation")
    
    async def set_conversation_state(self, phone_number: str, state: Dict[str, Any]) -> bool:
        """Cache conversation state"""
        cache_key = f"conversation_state:{phone_number}"
        return await self.cache_service.set(
            cache_key, 
            state, 
            "conversation",
            self.cache_patterns["conversation"]["ttl"]
        )
    
    async def get_conversation_history(self, phone_number: str) -> Optional[List[Dict[str, Any]]]:
        """Get conversation history from cache"""
        cache_key = f"conversation_history:{phone_number}"
        return await self.cache_service.get(cache_key, "conversation")
    
    async def set_conversation_history(self, phone_number: str, history: List[Dict[str, Any]]) -> bool:
        """Cache conversation history"""
        cache_key = f"conversation_history:{phone_number}"
        return await self.cache_service.set(
            cache_key,
            history,
            "conversation",
            self.cache_patterns["conversation"]["ttl"]
        )
    
    # ==================== RAG CACHING ====================
    
    async def get_rag_response(self, query: str, context: Optional[str] = None) -> Optional[str]:
        """Get RAG response from cache"""
        cache_key = self._generate_rag_key(query, context)
        return await self.cache_service.get(cache_key, "rag")
    
    async def set_rag_response(self, query: str, response: str, context: Optional[str] = None) -> bool:
        """Cache RAG response"""
        cache_key = self._generate_rag_key(query, context)
        return await self.cache_service.set(
            cache_key,
            response,
            "rag",
            self.cache_patterns["rag"]["ttl"]
        )
    
    def _generate_rag_key(self, query: str, context: Optional[str] = None) -> str:
        """Generate cache key for RAG responses"""
        # Normalize query
        normalized_query = query.lower().strip()
        
        # Include context in key if provided
        key_data = normalized_query
        if context:
            key_data += f"|{context}"
        
        # Generate hash
        return f"rag:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    # ==================== USER PROFILE CACHING ====================
    
    async def get_user_profile(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Get user profile from cache"""
        cache_key = f"user_profile:{phone_number}"
        return await self.cache_service.get(cache_key, "user")
    
    async def set_user_profile(self, phone_number: str, profile: Dict[str, Any]) -> bool:
        """Cache user profile"""
        cache_key = f"user_profile:{phone_number}"
        return await self.cache_service.set(
            cache_key,
            profile,
            "user",
            self.cache_patterns["user_profile"]["ttl"]
        )
    
    async def update_user_profile(self, phone_number: str, updates: Dict[str, Any]) -> bool:
        """Update user profile in cache"""
        existing_profile = await self.get_user_profile(phone_number) or {}
        existing_profile.update(updates)
        return await self.set_user_profile(phone_number, existing_profile)
    
    # ==================== INTENT CACHING ====================
    
    async def get_intent_classification(self, message: str) -> Optional[Dict[str, Any]]:
        """Get intent classification from cache"""
        cache_key = self._generate_intent_key(message)
        return await self.cache_service.get(cache_key, "rag")
    
    async def set_intent_classification(self, message: str, intent_result: Dict[str, Any]) -> bool:
        """Cache intent classification"""
        cache_key = self._generate_intent_key(message)
        return await self.cache_service.set(
            cache_key,
            intent_result,
            "rag",
            self.cache_patterns["intent"]["ttl"]
        )
    
    def _generate_intent_key(self, message: str) -> str:
        """Generate cache key for intent classification"""
        normalized = message.lower().strip()
        return f"intent:{hashlib.md5(normalized.encode()).hexdigest()}"
    
    # ==================== SESSION CACHING ====================
    
    async def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data from cache"""
        cache_key = f"session:{session_id}"
        return await self.cache_service.get(cache_key, "session")
    
    async def set_session_data(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Cache session data"""
        cache_key = f"session:{session_id}"
        return await self.cache_service.set(
            cache_key,
            data,
            "session",
            self.cache_patterns["session"]["ttl"]
        )
    
    # ==================== CACHE DECORATORS ====================
    
    def cached(
        self,
        cache_type: str = "default",
        ttl: Optional[int] = None,
        key_generator: Optional[Callable] = None
    ):
        """
        Decorator for caching function results
        
        Args:
            cache_type: Type of cache (conversation, rag, user, intent, etc.)
            ttl: Time to live in seconds
            key_generator: Custom key generation function
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                if key_generator:
                    cache_key = key_generator(*args, **kwargs)
                else:
                    cache_key = self._generate_function_key(func.__name__, args, kwargs)
                
                # Try to get from cache
                cached_result = await self.cache_service.get(
                    cache_key,
                    self.cache_patterns.get(cache_type, {}).get("category", "default")
                )
                
                if cached_result is not None:
                    app_logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                    return cached_result
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Cache result
                cache_ttl = ttl or self.cache_patterns.get(cache_type, {}).get("ttl", 3600)
                await self.cache_service.set(
                    cache_key,
                    result,
                    self.cache_patterns.get(cache_type, {}).get("category", "default"),
                    cache_ttl
                )
                
                app_logger.debug(f"Cache miss for {func.__name__}: {cache_key}")
                return result
                
            return wrapper
        return decorator
    
    def _generate_function_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate cache key for function call"""
        key_data = {
            "function": func_name,
            "args": str(args),
            "kwargs": sorted(kwargs.items())
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return f"func:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    # ==================== CACHE WARMING ====================
    
    async def warm_common_patterns(self):
        """Warm cache with common usage patterns"""
        try:
            # Common conversation starters
            common_starters = [
                "olá",
                "oi", 
                "bom dia",
                "boa tarde",
                "boa noite",
                "gostaria de informações",
                "quero saber sobre o kumon"
            ]
            
            # Pre-classify common intents
            for starter in common_starters:
                intent_key = self._generate_intent_key(starter)
                # This would typically call the actual intent classifier
                # For now, we'll cache a basic greeting intent
                await self.cache_service.set(
                    intent_key,
                    {
                        "intent": "greeting",
                        "confidence": 0.95,
                        "cached": True
                    },
                    "rag",
                    self.cache_patterns["intent"]["ttl"]
                )
            
            # Common RAG responses
            common_qa = [
                ("horários de funcionamento", "Nossos horários são de segunda a sexta, das 8h às 18h."),
                ("endereço kumon", "Estamos na Rua Amoreira, 571. Salas 6 e 7. Jardim das Laranjeiras."),
                ("telefone contato", "Nosso telefone é (51) 99692-1999."),
                ("método kumon", "O método Kumon desenvolve o aprendizado autodidático."),
                ("disciplinas oferecidas", "Oferecemos Matemática, Português e Inglês."),
            ]
            
            for query, response in common_qa:
                await self.set_rag_response(query, response)
            
            app_logger.info(f"Cache warmed with {len(common_starters)} intents and {len(common_qa)} RAG responses")
            
        except Exception as e:
            app_logger.error(f"Cache warming error: {e}")
    
    # ==================== CACHE INVALIDATION ====================
    
    async def invalidate_user_cache(self, phone_number: str):
        """Invalidate all cache entries for a user"""
        try:
            patterns = [
                f"conversation_state:{phone_number}",
                f"conversation_history:{phone_number}",
                f"user_profile:{phone_number}"
            ]
            
            for pattern in patterns:
                await self.cache_service.invalidate(pattern, "conversation")
            
            app_logger.info(f"Cache invalidated for user {phone_number}")
            
        except Exception as e:
            app_logger.error(f"Cache invalidation error: {e}")
    
    async def invalidate_pattern(self, pattern: str, cache_type: str = "default"):
        """Invalidate cache entries matching pattern"""
        try:
            category = self.cache_patterns.get(cache_type, {}).get("category", "default")
            await self.cache_service.invalidate(pattern, category)
            
        except Exception as e:
            app_logger.error(f"Pattern invalidation error: {e}")
    
    # ==================== METRICS AND MONITORING ====================
    
    def get_cache_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics"""
        return self.cache_service.get_metrics()
    
    async def health_check(self) -> Dict[str, Any]:
        """Cache health check"""
        return await self.cache_service.health_check()
    
    async def test_cache_performance(self) -> Dict[str, Any]:
        """Test cache performance"""
        test_cases = [
            ("conversation", "test_conversation_key", {"test": "conversation_data"}),
            ("rag", "test_rag_query", "Test RAG response"),
            ("user", "test_user_profile", {"name": "Test User", "age": 25}),
            ("intent", "test_intent_message", {"intent": "test", "confidence": 0.9})
        ]
        
        results = []
        
        for cache_type, key, value in test_cases:
            start_time = time.time()
            
            # Test set operation
            set_success = await self.cache_service.set(
                key,
                value,
                self.cache_patterns[cache_type]["category"],
                60  # 1 minute TTL for test
            )
            set_time = (time.time() - start_time) * 1000
            
            # Test get operation
            start_time = time.time()
            retrieved_value = await self.cache_service.get(
                key,
                self.cache_patterns[cache_type]["category"]
            )
            get_time = (time.time() - start_time) * 1000
            
            # Test data integrity
            data_integrity = retrieved_value == value
            
            results.append({
                "cache_type": cache_type,
                "set_time_ms": set_time,
                "get_time_ms": get_time,
                "set_success": set_success,
                "get_success": retrieved_value is not None,
                "data_integrity": data_integrity
            })
            
            # Cleanup
            await self.cache_service.invalidate(key, self.cache_patterns[cache_type]["category"])
        
        # Calculate averages
        avg_set_time = sum(r["set_time_ms"] for r in results) / len(results)
        avg_get_time = sum(r["get_time_ms"] for r in results) / len(results)
        success_rate = sum(1 for r in results if r["set_success"] and r["get_success"]) / len(results) * 100
        
        return {
            "test_summary": {
                "total_tests": len(test_cases),
                "avg_set_time_ms": avg_set_time,
                "avg_get_time_ms": avg_get_time,
                "success_rate_percentage": success_rate,
                "data_integrity_passed": all(r["data_integrity"] for r in results)
            },
            "individual_results": results,
            "performance_assessment": "EXCELLENT" if avg_get_time < 5 else "GOOD" if avg_get_time < 10 else "NEEDS_IMPROVEMENT"
        }
    
    async def cleanup(self):
        """Cleanup cache manager"""
        await self.cache_service.cleanup()


# Global cache manager instance
cache_manager = CacheManager()