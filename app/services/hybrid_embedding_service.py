"""
Hybrid embedding service - uses local models by default, GCP as fallback
"""
from __future__ import annotations

import os
import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from ..core.config import settings
from ..core.logger import app_logger


class HybridEmbeddingService:
    """
    Hybrid embedding service that uses:
    1. Sentence Transformers (local, free) as primary
    2. GCP Vertex AI (cloud, paid) as fallback
    3. TF-IDF (lightweight) as last resort
    """
    
    def __init__(self):
        # Lazy initialization - defer heavy setup until needed
        self.primary_service = None
        self.fallback_service = None
        self.last_resort_service = None
        self.cache_dir: Optional[Path] = None
        self.use_gcp_embeddings = getattr(settings, 'USE_GCP_EMBEDDINGS', False)
        self._initialized = False
    
    def _ensure_initialized(self) -> None:
        """Lazy initialization of heavy resources"""
        if self._initialized:
            return
            
        # Skip heavy initialization during unit tests
        if os.getenv("UNIT_TESTING") == "1":
            app_logger.info("UNIT_TESTING=1: Skipping hybrid embedding service heavy initialization")
            self._initialized = True
            return
            
        app_logger.info(f"Hybrid Embedding service initialized - GCP enabled: {self.use_gcp_embeddings}")
        self.cache_dir = Path(settings.EMBEDDING_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._initialized = True
    
    async def initialize_model(self) -> None:
        """Initialize embedding services in order of preference"""
        self._ensure_initialized()
        if self.primary_service is not None:
            return
        
        # 1. Try to initialize Sentence Transformers (free)
        await self._initialize_sentence_transformers()
        
        # 2. Initialize GCP as fallback if enabled
        if self.use_gcp_embeddings:
            await self._initialize_gcp_service()
        
        # 3. Always have TF-IDF as last resort
        await self._initialize_tfidf_service()
        
        app_logger.info("Hybrid embedding service initialization completed")
    
    async def _initialize_sentence_transformers(self):
        """Initialize Sentence Transformers (primary, free)"""
        try:
            # Import only when needed to avoid dependency issues
            from sentence_transformers import SentenceTransformer
            import torch
            
            # Determine device
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
            
            # Load model
            model = SentenceTransformer(
                settings.EMBEDDING_MODEL_NAME,
                device=device,
                cache_folder=str(self.cache_dir / "models")
            )
            
            self.primary_service = SentenceTransformersWrapper(model, device)
            app_logger.info(f"✅ Sentence Transformers initialized (device: {device}) - FREE")
            
        except Exception as e:
            app_logger.warning(f"❌ Failed to initialize Sentence Transformers: {str(e)}")
            self.primary_service = None
    
    async def _initialize_gcp_service(self):
        """Initialize GCP Vertex AI (fallback, paid)"""
        try:
            from google.cloud import aiplatform
            
            # Initialize Vertex AI
            aiplatform.init(
                project=getattr(settings, 'GOOGLE_PROJECT_ID', ''),
                location=getattr(settings, 'GOOGLE_LOCATION', 'us-central1')
            )
            
            client = aiplatform.gapic.PredictionServiceClient()
            self.fallback_service = GCPEmbeddingWrapper(client, settings)
            app_logger.info("✅ GCP Vertex AI initialized - PAID ($0.025/1k chars)")
            
        except Exception as e:
            app_logger.warning(f"❌ Failed to initialize GCP service: {str(e)}")
            self.fallback_service = None
    
    async def _initialize_tfidf_service(self):
        """Initialize TF-IDF (last resort, free but lower quality)"""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            
            vectorizer = TfidfVectorizer(
                max_features=384,
                stop_words='english',
                ngram_range=(1, 2)
            )
            
            self.last_resort_service = TFIDFWrapper(vectorizer)
            app_logger.info("✅ TF-IDF initialized - FREE (last resort)")
            
        except Exception as e:
            app_logger.error(f"❌ Failed to initialize TF-IDF: {str(e)}")
            self.last_resort_service = None
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding using the best available service"""
        self._ensure_initialized()
        if not text or not text.strip():
            return [0.0] * 384
        
        # Check cache first
        cache_key = self._get_cache_key(text)
        cached_embedding = await self._get_cached_embedding(cache_key)
        if cached_embedding is not None:
            return cached_embedding
        
        embedding = None
        service_used = "none"
        
        # Try primary service (Sentence Transformers - FREE)
        if self.primary_service:
            try:
                embedding = await self.primary_service.embed_text(text)
                service_used = "sentence-transformers (FREE)"
            except Exception as e:
                app_logger.warning(f"Primary service failed: {str(e)}")
        
        # Try fallback service (GCP - PAID)
        if embedding is None and self.fallback_service:
            try:
                embedding = await self.fallback_service.embed_text(text)
                service_used = "gcp-vertex-ai (PAID)"
            except Exception as e:
                app_logger.warning(f"Fallback service failed: {str(e)}")
        
        # Try last resort (TF-IDF - FREE but lower quality)
        if embedding is None and self.last_resort_service:
            try:
                embedding = await self.last_resort_service.embed_text(text)
                service_used = "tfidf (FREE, lower quality)"
            except Exception as e:
                app_logger.error(f"Last resort service failed: {str(e)}")
        
        # Final fallback - zero vector
        if embedding is None:
            embedding = [0.0] * 384
            service_used = "zero-vector (fallback)"
        
        app_logger.debug(f"Embedding generated using: {service_used}")
        
        # Cache the result
        await self._cache_embedding(cache_key, embedding)
        return embedding
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        self._ensure_initialized()
        if not texts:
            return []
        
        # Process in batches for efficiency
        embeddings = []
        for text in texts:
            embedding = await self.embed_text(text)
            embeddings.append(embedding)
        
        return embeddings
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        return hashlib.md5(f"hybrid_embedding_{text}".encode()).hexdigest()
    
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
                    'timestamp': time.time()
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


# Wrapper classes for different services
class SentenceTransformersWrapper:
    """Wrapper for Sentence Transformers"""
    
    def __init__(self, model, device):
        self.model = model
        self.device = device
        self.executor = ThreadPoolExecutor(max_workers=2)
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding using Sentence Transformers"""
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            self.executor,
            lambda: self.model.encode([text], convert_to_numpy=True)[0].tolist()
        )
        return embedding


class GCPEmbeddingWrapper:
    """Wrapper for GCP Vertex AI"""
    
    def __init__(self, client, settings):
        self.client = client
        self.project_id = getattr(settings, 'GOOGLE_PROJECT_ID', '')
        self.location = getattr(settings, 'GOOGLE_LOCATION', 'us-central1')
        self.model_name = "textembedding-gecko@003"
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding using GCP Vertex AI with Gemini"""
        try:
            from google.cloud import aiplatform
            from google.protobuf import json_format
            from google.protobuf.struct_pb2 import Value
            
            # Prepare the request
            endpoint = f"projects/{self.project_id}/locations/{self.location}/publishers/google/models/textembedding-gecko@003"
            
            # Create the instance
            instance_dict = {
                "content": text,
                "task_type": "RETRIEVAL_QUERY"
            }
            
            instance = json_format.ParseDict(instance_dict, Value())
            
            # Make the prediction request
            response = self.client.predict(
                endpoint=endpoint,
                instances=[instance],
                parameters=json_format.ParseDict({}, Value())
            )
            
            # Extract embedding from response
            if response.predictions:
                prediction = response.predictions[0]
                embedding_values = prediction.get("embeddings", {}).get("values", [])
                
                if embedding_values:
                    return list(embedding_values)
            
            # If no valid response, raise error to trigger fallback
            raise Exception("No embedding returned from Vertex AI")
            
        except Exception as e:
            app_logger.error(f"GCP Vertex AI embedding failed: {str(e)}")
            raise


class TFIDFWrapper:
    """Wrapper for TF-IDF embeddings"""
    
    def __init__(self, vectorizer):
        self.vectorizer = vectorizer
        self.fitted = False
        self.fallback_texts = [
            "Kumon é um método de ensino",
            "Matemática e português para crianças",
            "Desenvolvimento de habilidades acadêmicas"
        ]
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding using TF-IDF"""
        try:
            if not self.fitted:
                # Fit with some basic texts
                self.vectorizer.fit(self.fallback_texts + [text])
                self.fitted = True
            
            # Transform text to TF-IDF vector
            tfidf_matrix = self.vectorizer.transform([text])
            dense_embedding = tfidf_matrix.toarray()[0].tolist()
            
            # Pad or truncate to 384 dimensions
            if len(dense_embedding) < 384:
                dense_embedding.extend([0.0] * (384 - len(dense_embedding)))
            else:
                dense_embedding = dense_embedding[:384]
            
            return dense_embedding
            
        except Exception as e:
            # Hash-based embedding as absolute fallback
            embedding = []
            for i in range(384):
                hash_val = hash(f"{text}_{i}") % 1000000
                embedding.append(hash_val / 1000000.0 - 0.5)
            return embedding


# ========== LAZY SINGLETON PATTERN ==========

_hybrid_embedding_service: Optional[HybridEmbeddingService] = None

def get_hybrid_embedding_service() -> HybridEmbeddingService:
    """Get hybrid embedding service singleton with lazy initialization"""
    global _hybrid_embedding_service
    if _hybrid_embedding_service is None:
        _hybrid_embedding_service = HybridEmbeddingService()
    return _hybrid_embedding_service

# Legacy compatibility
hybrid_embedding_service = get_hybrid_embedding_service() 