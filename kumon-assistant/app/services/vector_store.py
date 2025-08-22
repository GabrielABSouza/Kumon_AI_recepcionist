"""
Vector store service using Qdrant for semantic search and retrieval
"""
import asyncio
import uuid
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
import numpy as np

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    VectorParams, Distance, PointStruct, Filter, 
    FieldCondition, MatchValue, SearchRequest, Record, UpdateResult
)

from ..core.config import settings
from ..core.logger import app_logger
from .embedding_service import embedding_service


@dataclass
class DocumentChunk:
    """Represents a document chunk for vector storage"""
    id: int
    content: str
    category: str
    keywords: List[str]
    metadata: Dict[str, Any]
    embedding: Optional[np.ndarray] = None


@dataclass
class SearchResult:
    """Represents a search result from vector store"""
    id: str
    content: str
    category: str
    keywords: List[str]
    metadata: Dict[str, Any]
    score: float


class VectorStore:
    """Vector store service using Qdrant for semantic search"""
    
    def __init__(self):
        self.client: Optional[QdrantClient] = None
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.embedding_dim = settings.EMBEDDING_DIMENSION
        self._initialized = False
        self._fallback_mode = False
        self._fallback_store = None
    
    async def initialize(self) -> None:
        """Initialize the vector store connection and collection"""
        if self._initialized:
            return
        
        try:
            # Initialize Qdrant client with timeout
            if settings.QDRANT_API_KEY:
                self.client = QdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY,
                    timeout=60  # 60 second timeout for Railway (same as PostgreSQL)
                )
            else:
                self.client = QdrantClient(
                    url=settings.QDRANT_URL,
                    timeout=60  # 60 second timeout for Railway (same as PostgreSQL)
                )
            
            # Ensure collection exists
            await self._ensure_collection_exists()
            
            self._initialized = True
            app_logger.info(f"Vector store initialized with collection: {self.collection_name}")
            
        except Exception as e:
            app_logger.error(f"Failed to initialize vector store: {str(e)}")
            
            # Activate fallback mode
            app_logger.warning("🚨 Activating vector store fallback mode - using local knowledge base")
            from ..core.robust_fallbacks import robust_fallback_manager
            robust_fallback_manager.activate_fallback("vector", f"Qdrant initialization failed: {e}")
            
            # Set fallback mode
            self._fallback_mode = True
            self._fallback_store = robust_fallback_manager.vector_store
            
            app_logger.info("✅ Vector store fallback mode activated successfully")
    
    async def _ensure_collection_exists(self) -> None:
        """Ensure the collection exists, create if it doesn't"""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                app_logger.info(f"Creating collection: {self.collection_name}")
                
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_dim,
                        distance=Distance.COSINE
                    )
                )
                
                app_logger.info(f"Collection {self.collection_name} created successfully")
            else:
                app_logger.info(f"Collection {self.collection_name} already exists")
                
        except Exception as e:
            app_logger.error(f"Error ensuring collection exists: {str(e)}")
            raise
    
    async def add_documents(self, documents: List[DocumentChunk]) -> bool:
        """Add documents to the vector store"""
        if not self._initialized:
            await self.initialize()
        
        if not documents:
            return True
        
        try:
            # Generate embeddings for documents that don't have them
            texts_to_embed = []
            for doc in documents:
                if doc.embedding is None:
                    texts_to_embed.append(doc.content)
            
            if texts_to_embed:
                app_logger.info(f"Generating embeddings for {len(texts_to_embed)} documents")
                embeddings = await embedding_service.embed_texts(texts_to_embed)
                
                # Assign embeddings back to documents
                embedding_idx = 0
                for doc in documents:
                    if doc.embedding is None:
                        doc.embedding = embeddings[embedding_idx]
                        embedding_idx += 1
            
            # Prepare points for Qdrant
            points = []
            for doc in documents:
                if doc.embedding is not None:
                    app_logger.info(f"Creating PointStruct with ID: {doc.id} (type: {type(doc.id)})")
                    
                    point = PointStruct(
                        id=doc.id,  # DocumentChunk.id is now guaranteed to be int
                        vector=doc.embedding.tolist(),
                        payload={
                            "content": doc.content,
                            "category": doc.category,
                            "keywords": doc.keywords,
                            "metadata": doc.metadata
                        }
                    )
                    
                    app_logger.info(f"PointStruct created successfully with ID: {point.id}")
                    points.append(point)
            
            # Upload points to Qdrant
            if points:
                result = self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                
                app_logger.info(
                    f"Successfully added {len(points)} documents to vector store. "
                    f"Operation status: {result.status}"
                )
                
                return result.status == models.UpdateStatus.COMPLETED
            
            return True
            
        except Exception as e:
            app_logger.error(f"Error adding documents to vector store: {str(e)}")
            return False
    
    async def search(
        self, 
        query: str, 
        limit: int = 5, 
        score_threshold: float = 0.7,
        category_filter: Optional[str] = None,
        keyword_filter: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """Search for similar documents in the vector store"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Generate query embedding
            query_embedding = await embedding_service.embed_text(query)
            
            # Build filter conditions
            filter_conditions = []
            
            if category_filter:
                filter_conditions.append(
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=category_filter)
                    )
                )
            
            if keyword_filter:
                # Create OR condition for keywords
                for keyword in keyword_filter:
                    filter_conditions.append(
                        FieldCondition(
                            key="keywords",
                            match=MatchValue(value=keyword)
                        )
                    )
            
            # Create filter if conditions exist
            search_filter = None
            if filter_conditions:
                if len(filter_conditions) == 1:
                    search_filter = Filter(must=[filter_conditions[0]])
                else:
                    search_filter = Filter(should=filter_conditions)
            
            # Perform search
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding.tolist(),
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold
            )
            
            # Convert results to SearchResult objects
            results = []
            for result in search_results:
                search_result = SearchResult(
                    id=str(result.id),
                    content=result.payload.get("content", ""),
                    category=result.payload.get("category", ""),
                    keywords=result.payload.get("keywords", []),
                    metadata=result.payload.get("metadata", {}),
                    score=result.score
                )
                results.append(search_result)
            
            app_logger.info(
                f"Vector search returned {len(results)} results for query",
                extra={
                    "query_preview": query[:50],
                    "score_threshold": score_threshold,
                    "category_filter": category_filter
                }
            )
            
            return results
            
        except Exception as e:
            app_logger.error(f"Error searching vector store: {str(e)}")
            
            # If in fallback mode or if search fails, use fallback
            if getattr(self, '_fallback_mode', False) and hasattr(self, '_fallback_store'):
                app_logger.warning(f"Using fallback vector search for query: {query[:50]}")
                fallback_results = await self._fallback_store.search(query, limit)
                
                # Convert fallback results to SearchResult format
                results = []
                for result in fallback_results:
                    search_result = SearchResult(
                        id=result.get("id", "fallback"),
                        content=result.get("text", ""),
                        category=result.get("metadata", {}).get("category", "fallback"),
                        keywords=result.get("metadata", {}).get("keywords", []),
                        metadata=result.get("metadata", {}),
                        score=result.get("score", 0.5)
                    )
                    results.append(search_result)
                
                return results
            
            return []
    
    async def delete_documents(self, document_ids: List[str]) -> bool:
        """Delete documents from the vector store"""
        if not self._initialized:
            await self.initialize()
        
        try:
            result = self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=document_ids
                )
            )
            
            app_logger.info(f"Deleted {len(document_ids)} documents from vector store")
            return result.status == models.UpdateStatus.COMPLETED
            
        except Exception as e:
            app_logger.error(f"Error deleting documents from vector store: {str(e)}")
            return False
    
    async def update_document(self, document: DocumentChunk) -> bool:
        """Update a single document in the vector store"""
        return await self.add_documents([document])
    
    async def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection"""
        if not self._initialized:
            await self.initialize()
        
        try:
            collection_info = self.client.get_collection(self.collection_name)
            
            return {
                "name": collection_info.config.name,
                "vector_size": collection_info.config.params.vectors.size,
                "distance": collection_info.config.params.vectors.distance.value,
                "points_count": collection_info.points_count,
                "status": collection_info.status.value
            }
            
        except Exception as e:
            app_logger.error(f"Error getting collection info: {str(e)}")
            return {}
    
    async def clear_collection(self) -> bool:
        """Clear all documents from the collection"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Delete the collection and recreate it
            self.client.delete_collection(self.collection_name)
            await self._ensure_collection_exists()
            
            app_logger.info(f"Cleared collection: {self.collection_name}")
            return True
            
        except Exception as e:
            app_logger.error(f"Error clearing collection: {str(e)}")
            return False
    
    async def similarity_search_with_score(
        self, 
        query: str, 
        k: int = 4
    ) -> List[Tuple[SearchResult, float]]:
        """Search for similar documents and return with scores"""
        results = await self.search(query, limit=k, score_threshold=0.0)
        return [(result, result.score) for result in results]
    
    async def get_document_by_id(self, document_id: str) -> Optional[SearchResult]:
        """Retrieve a specific document by ID"""
        if not self._initialized:
            await self.initialize()
        
        try:
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[document_id]
            )
            
            if result:
                point = result[0]
                return SearchResult(
                    id=str(point.id),
                    content=point.payload.get("content", ""),
                    category=point.payload.get("category", ""),
                    keywords=point.payload.get("keywords", []),
                    metadata=point.payload.get("metadata", {}),
                    score=1.0  # Perfect match since it's exact retrieval
                )
            
            return None
            
        except Exception as e:
            app_logger.error(f"Error retrieving document by ID: {str(e)}")
            return None
    
    async def bulk_update_embeddings(self) -> bool:
        """Update embeddings for all documents in the collection"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # This would typically be used when changing embedding models
            # For now, we'll just log that it's not implemented
            app_logger.warning("Bulk embedding update not implemented yet")
            return False
            
        except Exception as e:
            app_logger.error(f"Error in bulk embedding update: {str(e)}")
            return False


# Global instance
vector_store = VectorStore() 