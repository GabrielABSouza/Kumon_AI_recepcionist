"""
Enhanced RAG engine combining semantic search with LangChain and traditional approaches
"""
import json
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
import time

from ..core.config import settings
from ..core.logger import app_logger
from .langchain_rag import langchain_rag_service, RAGResponse
from .vector_store import vector_store, SearchResult
from .embedding_service import embedding_service


class EnhancedRAGEngine:
    """
    Enhanced RAG engine that combines semantic search with traditional approaches
    """
    
    def __init__(self):
        self._initialized = False
        self._fallback_enabled = True
        self.knowledge_base_loaded = False
    
    async def initialize(self) -> None:
        """Initialize the enhanced RAG engine"""
        if self._initialized:
            return
        
        try:
            app_logger.info("Initializing Enhanced RAG Engine...")
            
            # Initialize all components
            await langchain_rag_service.initialize()
            
            # Load knowledge base if not already loaded
            if not self.knowledge_base_loaded:
                await self._load_knowledge_base()
            
            self._initialized = True
            app_logger.info("Enhanced RAG Engine initialized successfully")
            
        except Exception as e:
            app_logger.error(f"Failed to initialize Enhanced RAG Engine: {str(e)}")
            raise
    
    async def _load_knowledge_base(self) -> None:
        """Load few-shot examples into the vector store"""
        try:
            # Get the path to the JSON file
            current_dir = Path(__file__).parent.parent
            json_file = current_dir / "data" / "few_shot_examples.json"
            
            if not json_file.exists():
                app_logger.warning(f"Few-shot examples file not found: {json_file}")
                return
            
            app_logger.info(f"Loading knowledge base from: {json_file}")
            
            with open(json_file, 'r', encoding='utf-8') as f:
                examples_data = json.load(f)
            
            examples_count = len(examples_data.get('examples', []))
            app_logger.info(f"Found {examples_count} examples in JSON file")
            
            # Load examples into vector store
            success = await langchain_rag_service.load_few_shot_examples(examples_data)
            
            if success:
                self.knowledge_base_loaded = True
                app_logger.info(f"Successfully loaded {examples_count} examples into knowledge base")
                
                # Verify the vector store has data
                collection_info = await vector_store.get_collection_info()
                app_logger.info(f"Vector store now contains {collection_info.get('points_count', 0)} documents")
            else:
                app_logger.error("Failed to load knowledge base - langchain_rag_service.load_few_shot_examples returned False")
                
        except Exception as e:
            app_logger.error(f"Error loading knowledge base: {str(e)}", exc_info=True)
    
    async def answer_question(
        self, 
        question: str, 
        context: Optional[Dict[str, Any]] = None,
        use_semantic_search: bool = True,
        similarity_threshold: float = 0.7
    ) -> str:
        """
        Answer user question using enhanced semantic search approach
        
        Args:
            question: User's question
            context: Additional context (unit info, etc.)
            use_semantic_search: Whether to use semantic search (True) or fallback to keyword matching
            similarity_threshold: Minimum similarity score for semantic search results
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            app_logger.info(
                f"Processing question with enhanced RAG",
                extra={
                    "question_preview": question[:50],
                    "use_semantic_search": use_semantic_search,
                    "similarity_threshold": similarity_threshold
                }
            )
            
            # Check if it's a greeting first
            greeting_response = self._handle_greeting(question, context)
            if greeting_response:
                return greeting_response
            
            if use_semantic_search:
                # Use semantic search approach
                response = await self._semantic_search_answer(
                    question, 
                    context, 
                    similarity_threshold
                )
                
                # If semantic search found good results, return them
                if response.confidence_score >= similarity_threshold:
                    return self._format_final_answer(response, context)
                else:
                    app_logger.info(
                        f"Semantic search confidence too low ({response.confidence_score:.2f}), "
                        f"trying fallback approach"
                    )
            
            # Fallback to keyword-based approach if semantic search fails or is disabled
            if self._fallback_enabled:
                fallback_answer = await self._fallback_answer(question, context)
                return fallback_answer
            else:
                return self._get_default_response()
            
        except Exception as e:
            app_logger.error(f"Error in enhanced RAG answer_question: {str(e)}")
            return self._get_error_response()
    
    def _handle_greeting(self, question: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Handle greeting messages before going to semantic search"""
        
        # Common greetings in Portuguese
        greetings = [
            "oi", "olá", "bom dia", "boa tarde", "boa noite", 
            "hello", "hi", "hey", "e aí", "opa", "oii"
        ]
        
        question_lower = question.lower().strip()
        
        # Check if it's a greeting
        if any(greeting in question_lower for greeting in greetings):
            app_logger.info(f"Detected greeting: {question}")
            
            # Get business name from context or use default
            business_name = context.get("username", "Kumon") if context else "Kumon"
            
            greeting_response = f"Olá! Bem-vindo ao {business_name}! 👋\n\n"
            greeting_response += (
                "Como posso ajudá-lo hoje? Posso:\n"
                "📅 Agendar uma aula experimental\n"
                "❓ Responder suas dúvidas sobre o método Kumon\n"
                "📍 Fornecer informações sobre nossos serviços\n"
                "💰 Falar sobre valores e condições\n\n"
                "O que você gostaria de saber? 😊"
            )
            
            return greeting_response
            
        return None
    
    async def _semantic_search_answer(
        self, 
        question: str, 
        context: Optional[Dict[str, Any]], 
        similarity_threshold: float
    ) -> RAGResponse:
        """Generate answer using semantic search and LangChain"""
        try:
            # Configure search parameters
            search_kwargs = {
                "score_threshold": similarity_threshold,
                "limit": 3
            }
            
            # Add category filter if we can infer it from context
            if context and context.get("category"):
                search_kwargs["category_filter"] = context["category"]
            
            # Query the LangChain RAG service
            response = await langchain_rag_service.query(
                question=question,
                search_kwargs=search_kwargs,
                include_sources=True
            )
            
            app_logger.info(
                f"Semantic search completed",
                extra={
                    "confidence_score": response.confidence_score,
                    "sources_count": len(response.sources),
                    "processing_time": response.processing_time
                }
            )
            
            return response
            
        except Exception as e:
            app_logger.error(f"Error in semantic search: {str(e)}")
            # Return empty response to trigger fallback
            return RAGResponse(
                answer="",
                sources=[],
                context_used="",
                confidence_score=0.0,
                processing_time=0.0
            )
    
    async def _fallback_answer(
        self, 
        question: str, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Fallback to keyword-based matching (similar to original RAG engine)"""
        try:
            # For now, we'll use a simple approach
            # In a full implementation, you might want to keep the original FewShotExample logic
            app_logger.info("Using fallback keyword-based approach")
            
            # Try to find relevant documents using lower threshold
            search_results = await vector_store.search(
                query=question,
                limit=3,
                score_threshold=0.3  # Lower threshold for fallback
            )
            
            if search_results:
                # Use the best result as a simple fallback
                best_result = search_results[0]
                
                # If it's a few-shot example, try to extract the answer
                if (best_result.metadata.get("type") == "few_shot_example" and 
                    best_result.metadata.get("answer")):
                    return best_result.metadata["answer"]
                else:
                    return best_result.content
            
            return self._get_default_response()
            
        except Exception as e:
            app_logger.error(f"Error in fallback approach: {str(e)}")
            return self._get_error_response()
    
    def _format_final_answer(
        self, 
        response: RAGResponse, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Format the final answer with context information"""
        answer = response.answer
        
        # Add context-specific information if available
        if context:
            # Add unit-specific info if available
            if context.get("phone"):
                if "telefone" not in answer.lower() and "contato" not in answer.lower():
                    if context.get("username"):
                        answer += f"\n\n📞 Para mais informações, entre em contato com a unidade {context['username']}: {context['phone']}"
                    else:
                        answer += f"\n\n📞 Para mais informações: {context['phone']}"
            
            # Add address if available and relevant
            if context.get("address") and ("endereço" in response.context_used.lower() or "local" in response.context_used.lower()):
                answer += f"\n\n📍 Endereço: {context['address']}"
            
            # Add operating hours if relevant
            if context.get("operating_hours") and ("horário" in response.context_used.lower() or "funciona" in response.context_used.lower()):
                answer += f"\n\n⏰ Horário de funcionamento: {context['operating_hours']}"
        
        return answer
    
    def _get_default_response(self) -> str:
        """Get default response when no specific information is found"""
        return (
            "Obrigada pela sua pergunta! Para uma resposta mais precisa e personalizada, "
            "recomendo que entre em contato diretamente com nossa unidade. "
            "Teremos prazer em ajudá-lo! 😊📞"
        )
    
    def _get_error_response(self) -> str:
        """Get error response when something goes wrong"""
        return (
            "Desculpe, não consegui processar sua pergunta no momento. "
            "Você poderia reformular ou entrar em contato pelo telefone para "
            "atendimento direto? 📞"
        )
    
    async def add_knowledge_document(
        self, 
        content: str, 
        category: str, 
        keywords: List[str], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add a new knowledge document to the system"""
        try:
            if not self._initialized:
                await self.initialize()
            
            document = {
                "id": f"doc_{int(time.time() * 1000)}",  # Timestamp-based ID
                "content": content,
                "category": category,
                "keywords": keywords,
                "metadata": metadata or {}
            }
            
            success = await langchain_rag_service.add_knowledge_base_documents([document])
            
            if success:
                app_logger.info(f"Added new knowledge document: {category}")
            
            return success
            
        except Exception as e:
            app_logger.error(f"Error adding knowledge document: {str(e)}")
            return False
    
    async def search_knowledge_base(
        self, 
        query: str, 
        limit: int = 5, 
        category_filter: Optional[str] = None
    ) -> List[SearchResult]:
        """Search the knowledge base directly"""
        try:
            if not self._initialized:
                await self.initialize()
            
            results = await vector_store.search(
                query=query,
                limit=limit,
                score_threshold=0.3,
                category_filter=category_filter
            )
            
            return results
            
        except Exception as e:
            app_logger.error(f"Error searching knowledge base: {str(e)}")
            return []
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        try:
            base_stats = await langchain_rag_service.get_system_stats()
            
            enhanced_stats = {
                **base_stats,
                "enhanced_rag_initialized": self._initialized,
                "knowledge_base_loaded": self.knowledge_base_loaded,
                "fallback_enabled": self._fallback_enabled
            }
            
            return enhanced_stats
            
        except Exception as e:
            app_logger.error(f"Error getting system stats: {str(e)}")
            return {"error": str(e)}
    
    async def reload_knowledge_base(self) -> bool:
        """Reload the knowledge base from file"""
        try:
            # Clear existing knowledge base
            await langchain_rag_service.clear_knowledge_base()
            
            # Reload from file
            self.knowledge_base_loaded = False
            await self._load_knowledge_base()
            
            app_logger.info("Knowledge base reloaded successfully")
            return self.knowledge_base_loaded
            
        except Exception as e:
            app_logger.error(f"Error reloading knowledge base: {str(e)}")
            return False
    
    def enable_fallback(self, enabled: bool = True) -> None:
        """Enable or disable fallback to keyword-based search"""
        self._fallback_enabled = enabled
        app_logger.info(f"Fallback approach {'enabled' if enabled else 'disabled'}")


# Global instance
enhanced_rag_engine = EnhancedRAGEngine() 