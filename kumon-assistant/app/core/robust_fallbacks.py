"""
ROBUST FALLBACK SYSTEM: When external services are unavailable
Prevents total system failure when PostgreSQL, Redis, or Qdrant are down
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class InMemoryConversationStore:
    """
    In-memory fallback for conversation storage when PostgreSQL is unavailable
    """
    
    def __init__(self):
        self.conversations: Dict[str, Dict[str, Any]] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.max_conversations = 1000  # Memory limit
        self.created_at = datetime.now(timezone.utc)
        
    async def create_session(self, phone_number: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create fallback session"""
        session_id = f"fallback_{phone_number}_{int(datetime.now().timestamp())}"
        
        session = {
            "session_id": session_id,
            "phone_number": phone_number,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "is_fallback": True,
            "fallback_reason": "PostgreSQL unavailable"
        }
        
        self.sessions[session_id] = session
        logger.warning(f"Created fallback session for {phone_number}: {session_id}")
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get fallback session"""
        return self.sessions.get(session_id)
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update fallback session"""
        if session_id in self.sessions:
            self.sessions[session_id].update(updates)
            self.sessions[session_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            return True
        return False
    
    async def add_message_to_session(self, session_id: str, message: Dict[str, Any]) -> bool:
        """Add message to fallback session"""
        if session_id in self.sessions:
            if "messages" not in self.sessions[session_id]:
                self.sessions[session_id]["messages"] = []
            
            self.sessions[session_id]["messages"].append({
                **message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "is_fallback": True
            })
            
            # Limit message history in memory
            if len(self.sessions[session_id]["messages"]) > 50:
                self.sessions[session_id]["messages"] = self.sessions[session_id]["messages"][-50:]
            
            return True
        return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Fallback health check"""
        return {
            "status": "healthy", 
            "type": "in_memory_fallback",
            "sessions": len(self.sessions),
            "conversations": len(self.conversations),
            "uptime_seconds": (datetime.now(timezone.utc) - self.created_at).total_seconds()
        }
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old fallback sessions"""
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        
        old_sessions = []
        for session_id, session in self.sessions.items():
            created_timestamp = datetime.fromisoformat(session["created_at"].replace('Z', '+00:00')).timestamp()
            if created_timestamp < cutoff:
                old_sessions.append(session_id)
        
        for session_id in old_sessions:
            del self.sessions[session_id]
        
        if old_sessions:
            logger.info(f"Cleaned up {len(old_sessions)} old fallback sessions")

class InMemoryCacheStore:
    """
    In-memory fallback for caching when Redis is unavailable
    """
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_entries = 10000  # Memory limit
        self.created_at = datetime.now(timezone.utc)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get from fallback cache"""
        if key in self.cache:
            entry = self.cache[key]
            
            # Check TTL
            if entry.get("expires_at"):
                expires_timestamp = datetime.fromisoformat(entry["expires_at"]).timestamp()
                if datetime.now(timezone.utc).timestamp() > expires_timestamp:
                    del self.cache[key]
                    return None
            
            return entry["value"]
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set in fallback cache"""
        # Memory management
        if len(self.cache) >= self.max_entries:
            # Remove oldest 10% of entries
            oldest_keys = sorted(
                self.cache.keys(),
                key=lambda k: self.cache[k].get("created_at", ""),
            )[:self.max_entries // 10]
            
            for old_key in oldest_keys:
                del self.cache[old_key]
        
        expires_at = datetime.now(timezone.utc).timestamp() + ttl
        
        self.cache[key] = {
            "value": value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
            "ttl": ttl,
            "is_fallback": True
        }
        
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete from fallback cache"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def cleanup_expired(self):
        """Clean up expired cache entries"""
        now = datetime.now(timezone.utc).timestamp()
        expired_keys = []
        
        for key, entry in self.cache.items():
            if entry.get("expires_at"):
                expires_timestamp = datetime.fromisoformat(entry["expires_at"]).timestamp()
                if now > expires_timestamp:
                    expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

class LocalVectorStore:
    """
    Local file-based fallback for vector search when Qdrant is unavailable
    """
    
    def __init__(self):
        self.data_dir = Path("./fallback_data/vectors")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_file = self.data_dir / "knowledge_base.json"
        self.knowledge_base = self._load_knowledge_base()
    
    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        """Load local knowledge base"""
        if self.knowledge_file.exists():
            try:
                with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"Loaded {len(data)} entries from local knowledge base")
                return data
            except Exception as e:
                logger.error(f"Error loading knowledge base: {e}")
        
        # Return default knowledge base
        return self._get_default_knowledge_base()
    
    def _get_default_knowledge_base(self) -> List[Dict[str, Any]]:
        """Default knowledge base when Qdrant is unavailable"""
        return [
            {
                "id": "programs_math",
                "text": "O programa de Matemática do Kumon desenvolve o cálculo mental e o raciocínio lógico. Valor: R$ 375,00 por mês.",
                "metadata": {"category": "programs", "subject": "mathematics", "price": 375.0}
            },
            {
                "id": "programs_portuguese", 
                "text": "O programa de Português do Kumon desenvolve a leitura, interpretação de texto e escrita. Valor: R$ 375,00 por mês.",
                "metadata": {"category": "programs", "subject": "portuguese", "price": 375.0}
            },
            {
                "id": "enrollment_fee",
                "text": "Taxa de matrícula única: R$ 100,00. Esta taxa é cobrada apenas no primeiro mês.",
                "metadata": {"category": "pricing", "type": "enrollment_fee", "price": 100.0}
            },
            {
                "id": "business_hours",
                "text": "Horário de funcionamento: Segunda a Sexta, das 8h às 12h e das 14h às 18h.",
                "metadata": {"category": "business_info", "type": "hours"}
            },
            {
                "id": "location",
                "text": "Localização: Rua Amoreira, 571. Salas 6 e 7. Jardim das Laranjeiras. Telefone: (51) 99692-1999",
                "metadata": {"category": "business_info", "type": "location"}
            },
            {
                "id": "methodology",
                "text": "A metodologia Kumon é individualizada e permite que cada aluno avance no seu próprio ritmo, desenvolvendo autonomia nos estudos.",
                "metadata": {"category": "methodology", "type": "approach"}
            }
        ]
    
    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Simple text search in local knowledge base"""
        query_lower = query.lower()
        results = []
        
        for entry in self.knowledge_base:
            text_lower = entry["text"].lower()
            
            # Simple scoring based on word matches
            query_words = set(query_lower.split())
            text_words = set(text_lower.split())
            
            matches = len(query_words.intersection(text_words))
            
            if matches > 0:
                score = matches / len(query_words)  # Simple relevance score
                results.append({
                    **entry,
                    "score": score,
                    "is_fallback": True,
                    "fallback_reason": "Qdrant unavailable"
                })
        
        # Sort by score and limit results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    def save_knowledge_base(self):
        """Save current knowledge base to file"""
        try:
            with open(self.knowledge_file, 'w', encoding='utf-8') as f:
                json.dump(self.knowledge_base, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.knowledge_base)} entries to local knowledge base")
        except Exception as e:
            logger.error(f"Error saving knowledge base: {e}")

class RobustFallbackManager:
    """
    Manages all fallback systems
    """
    
    def __init__(self):
        self.memory_store = InMemoryConversationStore()
        self.cache_store = InMemoryCacheStore() 
        self.vector_store = LocalVectorStore()
        self.fallback_active = {
            "memory": False,
            "cache": False, 
            "vector": False
        }
        
        # Start cleanup task
        asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of fallback stores"""
        while True:
            try:
                await asyncio.sleep(1800)  # 30 minutes
                
                self.memory_store.cleanup_old_sessions()
                self.cache_store.cleanup_expired()
                
                logger.info("Completed periodic fallback cleanup")
                
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    def activate_fallback(self, service_type: str, reason: str = "Service unavailable"):
        """Activate fallback for a service type"""
        if service_type in self.fallback_active:
            self.fallback_active[service_type] = True
            logger.warning(f"🚨 Activated {service_type} fallback: {reason}")
    
    def deactivate_fallback(self, service_type: str):
        """Deactivate fallback for a service type"""
        if service_type in self.fallback_active:
            self.fallback_active[service_type] = False
            logger.info(f"✅ Deactivated {service_type} fallback - service recovered")
    
    def get_fallback_status(self) -> Dict[str, Any]:
        """Get status of all fallback systems"""
        return {
            "fallback_active": self.fallback_active,
            "memory_store_sessions": len(self.memory_store.sessions),
            "cache_store_entries": len(self.cache_store.cache),
            "vector_store_entries": len(self.vector_store.knowledge_base),
            "uptime": (datetime.now(timezone.utc) - self.memory_store.created_at).total_seconds()
        }

# Global instance
robust_fallback_manager = RobustFallbackManager()