"""
GCP-optimized embedding service using Vertex AI instead of local ML models
"""
import asyncio
import hashlib
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np

from google.cloud import aiplatform
from google.oauth2 import service_account
import httpx

from ..core.config import settings
from ..core.logger import app_logger


class GCPEmbeddingService:
    """Optimized embedding service using GCP Vertex AI"""
    
    def __init__(self):
        self.project_id = settings.GOOGLE_PROJECT_ID
        self.location = getattr(settings, 'GOOGLE_LOCATION', 'us-central1')
        self.model_name = "textembedding-gecko@003"  # GCP's multilingual model
        self.client = None
        self.cache_dir = Path(settings.EMBEDDING_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        app_logger.info("GCP Embedding service initialized - using Vertex AI")
    
    async def initialize_model(self) -> None:
        """Initialize the Vertex AI client"""
        if self.client is not None:
            return
        
        try:
            # Initialize Vertex AI
            aiplatform.init(
                project=self.project_id,
                location=self.location
            )
            
            self.client = aiplatform.gapic.PredictionServiceClient()
            app_logger.info("Vertex AI client initialized successfully")
            
        except Exception as e:
            app_logger.error(f"Failed to initialize Vertex AI client: {str(e)}")
            # Fallback to lightweight local embeddings if GCP fails
            await self._initialize_fallback()
    
    async def _initialize_fallback(self):
        """Fallback to lightweight local embeddings"""
        try:
            # Use a much lighter model for fallback
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.fallback_vectorizer = TfidfVectorizer(
                max_features=384,  # Same dimension as sentence-transformers
                stop_words='english',
                ngram_range=(1, 2)
            )
            app_logger.warning("Using TF-IDF fallback for embeddings")
        except ImportError:
            app_logger.error("No fallback available for embeddings")
            raise
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        if not text or not text.strip():
            return [0.0] * 384
        
        # Check cache first
        cache_key = self._get_cache_key(text)
        cached_embedding = await self._get_cached_embedding(cache_key)
        if cached_embedding is not None:
            return cached_embedding
        
        try:
            # Use Vertex AI for embeddings
            embedding = await self._get_vertex_embedding(text)
            
            # Cache the result
            await self._cache_embedding(cache_key, embedding)
            return embedding
            
        except Exception as e:
            app_logger.error(f"Vertex AI embedding failed: {str(e)}")
            # Use fallback
            return await self._get_fallback_embedding(text)
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        if not texts:
            return []
        
        # Process in batches for efficiency
        batch_size = 50  # Vertex AI batch limit
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await asyncio.gather(*[
                self.embed_text(text) for text in batch
            ])
            embeddings.extend(batch_embeddings)
        
        return embeddings
    
    async def _get_vertex_embedding(self, text: str) -> List[float]:
        """Get embedding from Vertex AI"""
        if not self.client:
            await self.initialize_model()
        
        endpoint = f"projects/{self.project_id}/locations/{self.location}/publishers/google/models/{self.model_name}"
        
        instance = {
            "content": text,
            "task_type": "RETRIEVAL_QUERY"  # Optimized for search
        }
        
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.client.predict(
                endpoint=endpoint,
                instances=[instance]
            )
        )
        
        # Extract embedding from response
        embedding = response.predictions[0]["embeddings"]["values"]
        return embedding
    
    async def _get_fallback_embedding(self, text: str) -> List[float]:
        """Generate fallback embedding using TF-IDF"""
        try:
            if not hasattr(self, 'fallback_vectorizer'):
                # Quick TF-IDF based embedding
                words = text.lower().split()
                # Simple hash-based embedding (very lightweight)
                embedding = []
                for i in range(384):
                    hash_val = hash(f"{text}_{i}") % 1000000
                    embedding.append(hash_val / 1000000.0 - 0.5)
                return embedding
            
            # Use TF-IDF if available
            tfidf_matrix = self.fallback_vectorizer.fit_transform([text])
            dense_embedding = tfidf_matrix.toarray()[0].tolist()
            
            # Pad or truncate to 384 dimensions
            if len(dense_embedding) < 384:
                dense_embedding.extend([0.0] * (384 - len(dense_embedding)))
            else:
                dense_embedding = dense_embedding[:384]
            
            return dense_embedding
            
        except Exception as e:
            app_logger.error(f"Fallback embedding failed: {str(e)}")
            # Return zero vector as last resort
            return [0.0] * 384
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        return hashlib.md5(f"gcp_embedding_{text}".encode()).hexdigest()
    
    async def _get_cached_embedding(self, cache_key: str) -> Optional[List[float]]:
        """Get embedding from cache"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                return data.get('embedding')
            except Exception as e:
                app_logger.warning(f"Cache read error: {str(e)}")
        
        return None
    
    async def _cache_embedding(self, cache_key: str, embedding: List[float]) -> None:
        """Cache embedding to disk"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    'embedding': embedding,
                    'timestamp': asyncio.get_event_loop().time()
                }, f)
        except Exception as e:
            app_logger.warning(f"Cache write error: {str(e)}")
    
    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        if not a or not b:
            return 0.0
        
        try:
            a_np = np.array(a)
            b_np = np.array(b)
            
            dot_product = np.dot(a_np, b_np)
            norm_a = np.linalg.norm(a_np)
            norm_b = np.linalg.norm(b_np)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            return float(dot_product / (norm_a * norm_b))
            
        except Exception:
            return 0.0


# Global instance
gcp_embedding_service = GCPEmbeddingService() 