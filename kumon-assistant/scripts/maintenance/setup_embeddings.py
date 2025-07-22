#!/usr/bin/env python3
"""
Setup script for the embedding system
"""
import asyncio
import sys
import json
from pathlib import Path
import time

# Add the parent directory to the path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.enhanced_rag_engine import enhanced_rag_engine
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store
from app.services.langchain_rag import langchain_rag_service
from app.core.logger import app_logger


async def test_embedding_service():
    """Test the embedding service"""
    print("🔧 Testing Embedding Service...")
    
    try:
        # Test single embedding
        test_text = "Como funciona o método Kumon?"
        embedding = await embedding_service.embed_text(test_text)
        
        print(f"✅ Single embedding test passed - Shape: {embedding.shape}")
        
        # Test batch embeddings
        test_texts = [
            "Qual a idade mínima para começar no Kumon?",
            "Quanto custa o curso de matemática?",
            "Como funciona a metodologia de ensino?"
        ]
        embeddings = await embedding_service.embed_texts(test_texts)
        
        print(f"✅ Batch embedding test passed - Generated {len(embeddings)} embeddings")
        
        # Test similarity
        similarity = embedding_service.cosine_similarity(embedding, embeddings[0])
        print(f"✅ Similarity calculation test passed - Score: {similarity:.3f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Embedding service test failed: {str(e)}")
        return False


async def test_vector_store():
    """Test the vector store"""
    print("\n🗄️ Testing Vector Store...")
    
    try:
        # Initialize vector store
        await vector_store.initialize()
        print("✅ Vector store initialized")
        
        # Get collection info
        info = await vector_store.get_collection_info()
        print(f"✅ Collection info retrieved: {info.get('points_count', 0)} points")
        
        # Test search (should work even with empty collection)
        results = await vector_store.search("teste", limit=1, score_threshold=0.1)
        print(f"✅ Search test passed - Found {len(results)} results")
        
        return True
        
    except Exception as e:
        print(f"❌ Vector store test failed: {str(e)}")
        return False


async def load_knowledge_base():
    """Load the knowledge base"""
    print("\n📚 Loading Knowledge Base...")
    
    try:
        # Initialize enhanced RAG engine (this will load the knowledge base)
        await enhanced_rag_engine.initialize()
        print("✅ Enhanced RAG engine initialized")
        
        # Get stats
        stats = await enhanced_rag_engine.get_system_stats()
        vector_info = stats.get("vector_store_info", {})
        
        print(f"✅ Knowledge base loaded with {vector_info.get('points_count', 0)} documents")
        
        return True
        
    except Exception as e:
        print(f"❌ Knowledge base loading failed: {str(e)}")
        return False


async def test_semantic_search():
    """Test semantic search functionality"""
    print("\n🔍 Testing Semantic Search...")
    
    try:
        # Test questions
        test_questions = [
            "Como funciona o método Kumon?",
            "Qual a idade mínima para começar?",
            "Quanto custa?",
            "Quais disciplinas vocês oferecem?"
        ]
        
        for question in test_questions:
            print(f"\n📝 Testing: {question}")
            
            # Test vector search
            results = await vector_store.search(question, limit=3, score_threshold=0.5)
            print(f"   🔍 Vector search: {len(results)} results")
            
            if results:
                best_result = results[0]
                print(f"   ⭐ Best match: {best_result.category} (score: {best_result.score:.3f})")
            
            # Test enhanced RAG
            answer = await enhanced_rag_engine.answer_question(question)
            print(f"   🤖 RAG answer: {answer[:100]}...")
        
        print("\n✅ Semantic search tests completed")
        return True
        
    except Exception as e:
        print(f"❌ Semantic search test failed: {str(e)}")
        return False


async def benchmark_performance():
    """Benchmark the system performance"""
    print("\n⚡ Performance Benchmark...")
    
    try:
        test_questions = [
            "Como funciona o método Kumon?",
            "Qual a idade mínima?",
            "Quanto custa o curso?",
            "Quais disciplinas oferece?",
            "Como agendar uma aula?"
        ]
        
        # Warm up
        await enhanced_rag_engine.answer_question("teste")
        
        # Benchmark
        start_time = time.time()
        
        for question in test_questions:
            q_start = time.time()
            await enhanced_rag_engine.answer_question(question)
            q_time = time.time() - q_start
            print(f"   ⏱️ {question[:30]}... - {q_time:.2f}s")
        
        total_time = time.time() - start_time
        avg_time = total_time / len(test_questions)
        
        print(f"\n✅ Benchmark completed:")
        print(f"   📊 Total time: {total_time:.2f}s")
        print(f"   📊 Average per question: {avg_time:.2f}s")
        print(f"   📊 Questions per minute: {60 / avg_time:.1f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance benchmark failed: {str(e)}")
        return False


async def main():
    """Main setup and test function"""
    print("🚀 Setting up Embedding System for Kumon Assistant")
    print("=" * 60)
    
    # Run tests
    tests = [
        ("Embedding Service", test_embedding_service),
        ("Vector Store", test_vector_store),
        ("Knowledge Base Loading", load_knowledge_base),
        ("Semantic Search", test_semantic_search),
        ("Performance Benchmark", benchmark_performance)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'=' * 20} {test_name} {'=' * 20}")
        try:
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 SETUP SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} - {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All systems ready! The embedding system is fully operational.")
        
        # Show usage example
        print("\n" + "=" * 60)
        print("💡 USAGE EXAMPLE")
        print("=" * 60)
        print("""
# Using the enhanced RAG engine:
from app.services.enhanced_rag_engine import enhanced_rag_engine

# Initialize
await enhanced_rag_engine.initialize()

# Ask questions
answer = await enhanced_rag_engine.answer_question("Como funciona o método Kumon?")
print(answer)

# Search knowledge base
results = await enhanced_rag_engine.search_knowledge_base("matemática")
for result in results:
    print(f"{result.category}: {result.content}")
        """)
    else:
        print(f"\n⚠️ {total - passed} tests failed. Please check the errors above.")
        return 1
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⏹️ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Setup failed with unexpected error: {str(e)}")
        sys.exit(1) 