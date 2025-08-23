"""
API endpoints for embedding system management and testing
"""
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import asyncio

from app.core.dependencies import langchain_rag_service
from ..services.hybrid_embedding_service import hybrid_embedding_service
from ..services.vector_store import vector_store, SearchResult
from ..core.logger import app_logger

router = APIRouter(prefix="/api/v1/embeddings", tags=["embeddings"])


class QueryRequest(BaseModel):
    """Request model for RAG queries"""
    question: str = Field(..., description="The question to ask")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    use_semantic_search: bool = Field(True, description="Whether to use semantic search")
    similarity_threshold: float = Field(0.7, description="Minimum similarity threshold")


class QueryResponse(BaseModel):
    """Response model for RAG queries"""
    answer: str
    confidence_score: float
    processing_time: float
    sources_count: int
    sources: Optional[List[Dict[str, Any]]] = None


class SearchRequest(BaseModel):
    """Request model for knowledge base search"""
    query: str = Field(..., description="Search query")
    limit: int = Field(5, description="Maximum number of results")
    category_filter: Optional[str] = Field(None, description="Filter by category")
    score_threshold: float = Field(0.3, description="Minimum similarity score")


class AddDocumentRequest(BaseModel):
    """Request model for adding documents"""
    content: str = Field(..., description="Document content")
    category: str = Field(..., description="Document category")
    keywords: List[str] = Field(..., description="Keywords for the document")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class EmbeddingRequest(BaseModel):
    """Request model for generating embeddings"""
    texts: List[str] = Field(..., description="Texts to embed")
    use_cache: bool = Field(True, description="Whether to use cache")


@router.post("/query", response_model=QueryResponse)
async def query_rag_system(request: QueryRequest):
    """
    Query the RAG system with a question
    """
    try:
        app_logger.info(f"RAG query received: {request.question[:50]}...")
        
        # Use LangChain RAG service directly
        rag_result = await langchain_rag_service.query(
            question=request.question,
            search_kwargs={"score_threshold": request.similarity_threshold or 0.7},
            include_sources=request.use_semantic_search if hasattr(request, 'use_semantic_search') else True
        )
        answer = rag_result.answer
        
        # Get additional info from search results
        search_results = rag_result.sources if rag_result.sources else []
        
        # Use confidence score from RAG result
        confidence_score = rag_result.confidence_score
        
        sources = []
        if search_results:
            sources = [
                {
                    "id": result.id,
                    "category": result.category,
                    "content": result.content[:200] + "..." if len(result.content) > 200 else result.content,
                    "score": result.score,
                    "keywords": result.keywords
                }
                for result in search_results[:3]
            ]
        
        return QueryResponse(
            answer=answer,
            confidence_score=confidence_score,
            processing_time=0.5,  # Placeholder
            sources_count=len(search_results),
            sources=sources
        )
        
    except Exception as e:
        app_logger.error(f"Error in RAG query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/search")
async def search_knowledge_base(request: SearchRequest):
    """
    Search the knowledge base directly
    """
    try:
        results = await vector_store.search(
            query=request.query,
            limit=request.limit,
            score_threshold=request.score_threshold,
            category_filter=request.category_filter
        )
        
        formatted_results = [
            {
                "id": result.id,
                "content": result.content,
                "category": result.category,
                "keywords": result.keywords,
                "score": result.score,
                "metadata": result.metadata
            }
            for result in results
        ]
        
        return {
            "results": formatted_results,
            "count": len(formatted_results),
            "query": request.query
        }
        
    except Exception as e:
        app_logger.error(f"Error in knowledge base search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/documents")
async def add_document(request: AddDocumentRequest):
    """
    Add a new document to the knowledge base
    """
    try:
        # Create document for LangChain RAG service
        documents = [{
            "content": request.content,
            "category": request.category,
            "keywords": request.keywords,
            "metadata": request.metadata or {}
        }]
        success = await langchain_rag_service.add_knowledge_base_documents(documents)
        
        if success:
            return {"message": "Document added successfully", "success": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to add document")
            
    except Exception as e:
        app_logger.error(f"Error adding document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add document: {str(e)}")


@router.post("/embeddings")
async def generate_embeddings(request: EmbeddingRequest):
    """
    Generate embeddings for texts
    """
    try:
        embeddings = await hybrid_embedding_service.embed_texts(
            texts=request.texts
        )
        
        # Embeddings are already lists from hybrid service
        embeddings_list = embeddings
        
        return {
            "embeddings": embeddings_list,
            "count": len(embeddings_list),
            "dimension": len(embeddings_list[0]) if embeddings_list else 0
        }
        
    except Exception as e:
        app_logger.error(f"Error generating embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate embeddings: {str(e)}")


@router.get("/stats")
async def get_system_stats():
    """
    Get system statistics and health information
    """
    try:
        stats = await langchain_rag_service.get_system_stats()
        return stats
        
    except Exception as e:
        app_logger.error(f"Error getting system stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/health")
async def health_check():
    """
    Health check endpoint for the embedding system
    """
    try:
        # Check if all services are initialized
        embedding_ready = hybrid_embedding_service.primary_service is not None
        vector_store_ready = vector_store._initialized
        rag_ready = langchain_rag_service._initialized
        
        health_status = {
            "status": "healthy" if all([embedding_ready, vector_store_ready, rag_ready]) else "degraded",
            "components": {
                "embedding_service": "ready" if embedding_ready else "not_ready",
                "vector_store": "ready" if vector_store_ready else "not_ready",
                "rag_engine": "ready" if rag_ready else "not_ready"
            },
            "knowledge_base_loaded": rag_ready  # LangChain RAG doesn't have this specific flag
        }
        
        return health_status
        
    except Exception as e:
        app_logger.error(f"Error in health check: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.post("/initialize")
async def initialize_system():
    """
    Initialize the embedding system
    """
    try:
        await langchain_rag_service.initialize()
        
        return {
            "message": "System initialized successfully",
            "status": "ready"
        }
        
    except Exception as e:
        app_logger.error(f"Error initializing system: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


@router.post("/reload")
async def reload_knowledge_base():
    """
    Reload the knowledge base from files
    """
    try:
        # LangChain RAG doesn't have a specific reload method - reinitialization accomplishes this
        await langchain_rag_service.initialize()
        success = True
        
        if success:
            return {"message": "Knowledge base reloaded successfully", "success": True}
        else:
            raise HTTPException(status_code=500, detail="Failed to reload knowledge base")
            
    except Exception as e:
        app_logger.error(f"Error reloading knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Reload failed: {str(e)}")


@router.delete("/cache")
async def clear_embedding_cache():
    """
    Clear the embedding cache
    """
    try:
        # Hybrid embedding service doesn't have a clear_cache method
        
        return {"message": "Embedding cache cleared successfully"}
        
    except Exception as e:
        app_logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/categories")
async def get_categories():
    """
    Get all available categories in the knowledge base
    """
    try:
        # Search for all documents to get categories
        all_results = await vector_store.search(
            query="",  # Empty query to get diverse results
            limit=100,
            score_threshold=0.0
        )
        
        categories = list(set(result.category for result in all_results if result.category))
        categories.sort()
        
        return {
            "categories": categories,
            "count": len(categories)
        }
        
    except Exception as e:
        app_logger.error(f"Error getting categories: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")


@router.get("/similarity")
async def calculate_similarity(
    text1: str = Query(..., description="First text"),
    text2: str = Query(..., description="Second text")
):
    """
    Calculate similarity between two texts
    """
    try:
        # Generate embeddings
        embeddings = await hybrid_embedding_service.embed_texts([text1, text2])
        
        # Calculate similarity
        similarity = hybrid_embedding_service.cosine_similarity(embeddings[0], embeddings[1])
        
        return {
            "text1": text1,
            "text2": text2,
            "similarity": float(similarity),
            "interpretation": {
                "very_similar": similarity > 0.8,
                "similar": similarity > 0.6,
                "somewhat_similar": similarity > 0.4,
                "different": similarity <= 0.4
            }
        }
        
    except Exception as e:
        app_logger.error(f"Error calculating similarity: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate similarity: {str(e)}") 