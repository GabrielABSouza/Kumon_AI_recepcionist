"""
Embedding service using Sentence Transformers for semantic search
"""
import os
import asyncio
import hashlib
import pickle
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from sentence_transformers import SentenceTransformer
import torch

from ..core.config import settings
from ..core.logger import app_logger


class EmbeddingService:
    """Service for generating and managing embeddings using Sentence Transformers"""
    
    def __init__(self):
        self.model: Optional[SentenceTransformer] = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.cache_dir = Path(settings.EMBEDDING_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.device = self._get_device()
        
        app_logger.info(f"Embedding service initialized with device: {self.device}")
    
    def _get_device(self) -> str:
        """Determine the best device to use for embeddings"""
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():  # Mac M1/M2
            return "mps"
        else:
            return "cpu"
    
    async def initialize_model(self) -> None:
        """Initialize the sentence transformer model asynchronously"""
        if self.model is not None:
            return
        
        try:
            app_logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL_NAME}")
            
            # Load model in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                self.executor,
                self._load_model
            )
            
            app_logger.info(
                f"Embedding model loaded successfully. "
                f"Model dimension: {self.model.get_sentence_embedding_dimension()}, "
                f"Device: {self.device}"
            )
            
        except Exception as e:
            app_logger.error(f"Failed to load embedding model: {str(e)}")
            raise
    
    def _load_model(self) -> SentenceTransformer:
        """Load the sentence transformer model (runs in thread pool)"""
        model = SentenceTransformer(
            settings.EMBEDDING_MODEL_NAME,
            device=self.device,
            cache_folder=str(self.cache_dir / "models")
        )
        return model
    
    async def embed_text(self, text: str, use_cache: bool = True) -> np.ndarray:
        """Generate embedding for a single text"""
        if not text or not text.strip():
            return np.zeros(settings.EMBEDDING_DIMENSION)
        
        # Check cache first
        if use_cache:
            cached_embedding = self._get_cached_embedding(text)
            if cached_embedding is not None:
                return cached_embedding
        
        # Generate embedding
        embedding = await self.embed_texts([text], use_cache=use_cache)
        return embedding[0] if embedding else np.zeros(settings.EMBEDDING_DIMENSION)
    
    async def embed_texts(self, texts: List[str], use_cache: bool = True) -> List[np.ndarray]:
        """Generate embeddings for multiple texts"""
        if not texts:
            return []
        
        # Ensure model is loaded
        await self.initialize_model()
        
        # Filter out empty texts and create mapping
        valid_texts = [(i, text.strip()) for i, text in enumerate(texts) if text and text.strip()]
        if not valid_texts:
            return [np.zeros(settings.EMBEDDING_DIMENSION) for _ in texts]
        
        # Check cache for valid texts
        embeddings_map = {}
        texts_to_embed = []
        
        if use_cache:
            for i, text in valid_texts:
                cached = self._get_cached_embedding(text)
                if cached is not None:
                    embeddings_map[i] = cached
                else:
                    texts_to_embed.append((i, text))
        else:
            texts_to_embed = valid_texts
        
        # Generate embeddings for uncached texts
        if texts_to_embed:
            try:
                app_logger.info(f"Generating embeddings for {len(texts_to_embed)} texts")
                
                # Extract just the text strings
                text_strings = [text for _, text in texts_to_embed]
                
                # Generate embeddings in thread pool
                loop = asyncio.get_event_loop()
                raw_embeddings = await loop.run_in_executor(
                    self.executor,
                    self._generate_embeddings,
                    text_strings
                )
                
                # Map back to original indices and cache
                for (original_idx, text), embedding in zip(texts_to_embed, raw_embeddings):
                    embeddings_map[original_idx] = embedding
                    if use_cache:
                        self._cache_embedding(text, embedding)
                
                app_logger.info(f"Successfully generated {len(raw_embeddings)} embeddings")
                
            except Exception as e:
                app_logger.error(f"Error generating embeddings: {str(e)}")
                # Return zero embeddings for failed texts
                for i, _ in texts_to_embed:
                    embeddings_map[i] = np.zeros(settings.EMBEDDING_DIMENSION)
        
        # Build final result maintaining original order
        result = []
        for i, text in enumerate(texts):
            if i in embeddings_map:
                result.append(embeddings_map[i])
            else:
                result.append(np.zeros(settings.EMBEDDING_DIMENSION))
        
        return result
    
    def _generate_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings using the model (runs in thread pool)"""
        try:
            # Process in batches to manage memory
            all_embeddings = []
            batch_size = settings.EMBEDDING_BATCH_SIZE
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_embeddings = self.model.encode(
                    batch,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False
                )
                all_embeddings.extend(batch_embeddings)
            
            return all_embeddings
            
        except Exception as e:
            app_logger.error(f"Error in embedding generation: {str(e)}")
            return [np.zeros(settings.EMBEDDING_DIMENSION) for _ in texts]
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        model_hash = hashlib.md5(settings.EMBEDDING_MODEL_NAME.encode()).hexdigest()[:8]
        return f"{model_hash}_{text_hash}"
    
    def _get_cached_embedding(self, text: str) -> Optional[np.ndarray]:
        """Retrieve cached embedding if available"""
        try:
            cache_key = self._get_cache_key(text)
            cache_file = self.cache_dir / f"{cache_key}.pkl"
            
            if cache_file.exists():
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            app_logger.warning(f"Error reading cached embedding: {str(e)}")
        
        return None
    
    def _cache_embedding(self, text: str, embedding: np.ndarray) -> None:
        """Cache embedding to disk"""
        try:
            cache_key = self._get_cache_key(text)
            cache_file = self.cache_dir / f"{cache_key}.pkl"
            
            with open(cache_file, 'wb') as f:
                pickle.dump(embedding, f)
        except Exception as e:
            app_logger.warning(f"Error caching embedding: {str(e)}")
    
    def cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings"""
        try:
            # Normalize embeddings
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return np.dot(embedding1, embedding2) / (norm1 * norm2)
        except Exception:
            return 0.0
    
    def find_most_similar(
        self, 
        query_embedding: np.ndarray, 
        candidate_embeddings: List[np.ndarray], 
        top_k: int = 5
    ) -> List[tuple]:
        """Find most similar embeddings to query"""
        similarities = []
        
        for i, candidate in enumerate(candidate_embeddings):
            similarity = self.cosine_similarity(query_embedding, candidate)
            similarities.append((i, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    async def get_embedding_stats(self) -> Dict[str, Any]:
        """Get statistics about the embedding service"""
        cache_files = list(self.cache_dir.glob("*.pkl"))
        
        stats = {
            "model_name": settings.EMBEDDING_MODEL_NAME,
            "embedding_dimension": settings.EMBEDDING_DIMENSION,
            "device": self.device,
            "cached_embeddings": len(cache_files),
            "cache_size_mb": sum(f.stat().st_size for f in cache_files) / (1024 * 1024),
            "model_loaded": self.model is not None
        }
        
        if self.model:
            stats["model_dimension"] = self.model.get_sentence_embedding_dimension()
        
        return stats
    
    def clear_cache(self) -> None:
        """Clear the embedding cache"""
        try:
            cache_files = list(self.cache_dir.glob("*.pkl"))
            for cache_file in cache_files:
                cache_file.unlink()
            app_logger.info(f"Cleared {len(cache_files)} cached embeddings")
        except Exception as e:
            app_logger.error(f"Error clearing cache: {str(e)}")


# Global instance
embedding_service = EmbeddingService() 