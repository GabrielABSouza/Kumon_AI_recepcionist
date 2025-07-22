"""
LangChain integration for RAG pipeline using Qdrant and Sentence Transformers
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass

from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate, PromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import BaseMessage

from ..core.config import settings
from ..core.logger import app_logger
from .vector_store import vector_store, SearchResult, DocumentChunk
from .embedding_service import embedding_service


class LoggingCallbackHandler(BaseCallbackHandler):
    """Custom callback handler for logging LangChain operations"""
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        app_logger.info("LLM call started", extra={"prompt_count": len(prompts)})
    
    def on_llm_end(self, response, **kwargs) -> None:
        app_logger.info("LLM call completed")
    
    def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs) -> None:
        app_logger.error(f"LLM call failed: {str(error)}")


@dataclass
class RAGResponse:
    """Response from RAG pipeline"""
    answer: str
    sources: List[SearchResult]
    context_used: str
    confidence_score: float
    processing_time: float


class LangChainRAGService:
    """LangChain-powered RAG service with semantic search"""
    
    def __init__(self):
        self.llm = None
        self.retrieval_chain = None
        self._initialized = False
        self.callback_handler = LoggingCallbackHandler()
        
        # Prompt templates
        self.system_template = """Você é uma recepcionista virtual especializada do Kumon, sempre educada, prestativa e entusiasta da educação. 

Suas características:
- Use um tom profissional mas amigável
- Seja precisa e informativa
- Use emojis de forma moderada e apropriada
- Sempre procure ajudar o cliente a encontrar a melhor solução
- Se não souber uma informação específica, seja honesta e ofereça alternativas

Contexto disponível:
{context}

Baseie sua resposta no contexto fornecido acima. Se o contexto não contém informações suficientes para responder completamente à pergunta, indique isso claramente e sugira como o cliente pode obter mais informações.

Pergunta do cliente: {question}

Resposta:"""

        self.qa_template = ChatPromptTemplate.from_messages([
            ("system", self.system_template),
            ("human", "{question}")
        ])
    
    async def initialize(self) -> None:
        """Initialize the LangChain RAG service"""
        if self._initialized:
            return
        
        try:
            # Initialize dependencies
            await vector_store.initialize()
            await embedding_service.initialize_model()
            
            # Initialize OpenAI LLM
            self.llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                temperature=0.3,
                max_tokens=500,
                callbacks=[self.callback_handler]
            )
            
            # Create retrieval chain
            self._create_retrieval_chain()
            
            self._initialized = True
            app_logger.info("LangChain RAG service initialized successfully")
            
        except Exception as e:
            app_logger.error(f"Failed to initialize LangChain RAG service: {str(e)}")
            raise
    
    def _create_retrieval_chain(self) -> None:
        """Create the retrieval chain pipeline"""
        try:
            # Create the chain
            self.retrieval_chain = (
                {
                    "context": RunnablePassthrough() | self._format_context,
                    "question": RunnablePassthrough()
                }
                | self.qa_template
                | self.llm
                | StrOutputParser()
            )
            
            app_logger.info("Retrieval chain created successfully")
            
        except Exception as e:
            app_logger.error(f"Error creating retrieval chain: {str(e)}")
            raise
    
    async def _format_context(self, input_data: Dict[str, Any]) -> str:
        """Format context from search results"""
        if isinstance(input_data, dict) and "context" in input_data:
            search_results = input_data["context"]
        else:
            # If it's just the question, we need to search first
            question = input_data.get("question", "") if isinstance(input_data, dict) else str(input_data)
            search_results = await vector_store.search(
                query=question,
                limit=3,
                score_threshold=0.7
            )
        
        if not search_results:
            return "Nenhum contexto específico encontrado."
        
        formatted_context = "Informações relevantes:\n\n"
        for i, result in enumerate(search_results, 1):
            formatted_context += f"{i}. Categoria: {result.category}\n"
            formatted_context += f"   Conteúdo: {result.content}\n"
            if result.keywords:
                formatted_context += f"   Palavras-chave: {', '.join(result.keywords)}\n"
            formatted_context += f"   Relevância: {result.score:.2f}\n\n"
        
        return formatted_context
    
    async def query(
        self, 
        question: str, 
        search_kwargs: Optional[Dict[str, Any]] = None,
        include_sources: bool = True
    ) -> RAGResponse:
        """Query the RAG system with a question"""
        if not self._initialized:
            await self.initialize()
        
        import time
        start_time = time.time()
        
        try:
            # Set default search parameters
            search_params = {
                "limit": 3,
                "score_threshold": 0.7,
                **( search_kwargs or {})
            }
            
            # Retrieve relevant documents
            app_logger.info(f"Searching for relevant documents for query: {question[:50]}...")
            search_results = await vector_store.search(
                query=question,
                **search_params
            )
            
            if not search_results:
                app_logger.warning("No relevant documents found for query")
                return RAGResponse(
                    answer="Desculpe, não encontrei informações específicas sobre sua pergunta. "
                           "Você poderia reformular ou entrar em contato pelo telefone para "
                           "atendimento personalizado? 📞",
                    sources=[],
                    context_used="",
                    confidence_score=0.0,
                    processing_time=time.time() - start_time
                )
            
            # Format context
            context = await self._format_context({"context": search_results})
            
            # Generate answer using the chain
            app_logger.info(f"Generating answer using {len(search_results)} relevant documents")
            
            answer = await self.retrieval_chain.ainvoke({
                "question": question,
                "context": context
            })
            
            # Calculate confidence score based on search results
            confidence_score = self._calculate_confidence_score(search_results)
            
            processing_time = time.time() - start_time
            
            app_logger.info(
                f"RAG query completed successfully",
                extra={
                    "processing_time": processing_time,
                    "sources_count": len(search_results),
                    "confidence_score": confidence_score
                }
            )
            
            return RAGResponse(
                answer=answer,
                sources=search_results if include_sources else [],
                context_used=context,
                confidence_score=confidence_score,
                processing_time=processing_time
            )
            
        except Exception as e:
            app_logger.error(f"Error in RAG query: {str(e)}")
            return RAGResponse(
                answer="Desculpe, ocorreu um erro ao processar sua pergunta. "
                       "Tente novamente ou entre em contato pelo telefone. 📞",
                sources=[],
                context_used="",
                confidence_score=0.0,
                processing_time=time.time() - start_time
            )
    
    def _calculate_confidence_score(self, search_results: List[SearchResult]) -> float:
        """Calculate confidence score based on search results"""
        if not search_results:
            return 0.0
        
        # Use the highest similarity score as base confidence
        max_score = max(result.score for result in search_results)
        
        # Adjust based on number of results and their consistency
        result_count_factor = min(len(search_results) / 3.0, 1.0)  # Normalize to 3 results
        
        # Check if multiple results are from the same category (consistency)
        categories = [result.category for result in search_results]
        category_consistency = len(set(categories)) / len(categories) if categories else 1.0
        consistency_factor = 1.0 - (category_consistency - 1.0) * 0.2  # Slight boost for consistency
        
        confidence = max_score * result_count_factor * consistency_factor
        return min(confidence, 1.0)
    
    async def add_knowledge_base_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Add documents to the knowledge base"""
        try:
            doc_chunks = []
            
            for i, doc in enumerate(documents):
                chunk = DocumentChunk(
                    id=doc.get("id", f"doc_{i}"),
                    content=doc.get("content", ""),
                    category=doc.get("category", "general"),
                    keywords=doc.get("keywords", []),
                    metadata=doc.get("metadata", {})
                )
                doc_chunks.append(chunk)
            
            success = await vector_store.add_documents(doc_chunks)
            
            if success:
                app_logger.info(f"Successfully added {len(doc_chunks)} documents to knowledge base")
            else:
                app_logger.error("Failed to add documents to knowledge base")
            
            return success
            
        except Exception as e:
            app_logger.error(f"Error adding documents to knowledge base: {str(e)}")
            return False
    
    async def load_few_shot_examples(self, examples_data: Dict[str, Any]) -> bool:
        """Load few-shot examples into the vector store"""
        try:
            if not self._initialized:
                await self.initialize()
            
            documents = []
            for example in examples_data.get("examples", []):
                # Create document from question-answer pair
                content = f"Pergunta: {example.get('question', '')}\nResposta: {example.get('answer', '')}"
                
                doc = {
                    "id": f"example_{len(documents)}",
                    "content": content,
                    "category": example.get("category", "general"),
                    "keywords": example.get("keywords", []),
                    "metadata": {
                        "type": "few_shot_example",
                        "question": example.get("question", ""),
                        "answer": example.get("answer", "")
                    }
                }
                documents.append(doc)
            
            success = await self.add_knowledge_base_documents(documents)
            
            if success:
                app_logger.info(f"Successfully loaded {len(documents)} few-shot examples into vector store")
            
            return success
            
        except Exception as e:
            app_logger.error(f"Error loading few-shot examples: {str(e)}")
            return False
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        stats = {
            "initialized": self._initialized,
            "embedding_stats": await embedding_service.get_embedding_stats(),
            "vector_store_info": await vector_store.get_collection_info()
        }
        
        return stats
    
    async def clear_knowledge_base(self) -> bool:
        """Clear the entire knowledge base"""
        try:
            success = await vector_store.clear_collection()
            if success:
                app_logger.info("Knowledge base cleared successfully")
            return success
        except Exception as e:
            app_logger.error(f"Error clearing knowledge base: {str(e)}")
            return False


# Global instance
langchain_rag_service = LangChainRAGService() 