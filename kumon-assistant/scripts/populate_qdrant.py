#!/usr/bin/env python3
"""
Script para popular a base de conhecimento do Kumon no Qdrant Cloud
Usa os dados de app/data/few_shot_examples.json
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.core.config import settings
from app.core.logger import app_logger
from app.services.embedding_service import EmbeddingService


async def load_knowledge_from_json():
    """Load knowledge from few_shot_examples.json"""
    json_path = Path(__file__).parent.parent / "app" / "data" / "few_shot_examples.json"
    
    app_logger.info(f"Loading knowledge from {json_path}")
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    knowledge_entries = []
    
    for i, example in enumerate(data.get("examples", [])):
        # Create a comprehensive content string
        content_parts = [
            f"Pergunta: {example.get('question', '')}",
            f"Resposta: {example.get('answer', '')}",
        ]
        
        # Add keywords for better search
        if example.get("keywords"):
            keywords = ", ".join(example.get("keywords", []))
            content_parts.append(f"Palavras-chave: {keywords}")
        
        content = "\n".join(content_parts)
        
        entry = {
            "id": f"kumon_faq_{i+1}",
            "content": content,
            "metadata": {
                "category": example.get("category", "general"),
                "question": example.get("question", ""),
                "answer": example.get("answer", ""),
                "keywords": example.get("keywords", []),
                "source": "few_shot_examples"
            }
        }
        knowledge_entries.append(entry)
    
    app_logger.info(f"Loaded {len(knowledge_entries)} knowledge entries")
    return knowledge_entries


async def populate_qdrant():
    """Populate Qdrant Cloud with Kumon knowledge"""
    
    app_logger.info("🚀 Starting Qdrant population process...")
    
    # Verify environment variables
    if not settings.QDRANT_URL:
        app_logger.error("❌ QDRANT_URL not configured")
        return False
    
    app_logger.info(f"📍 Connecting to Qdrant at: {settings.QDRANT_URL}")
    
    # Load knowledge data
    knowledge_entries = await load_knowledge_from_json()
    
    if not knowledge_entries:
        app_logger.error("❌ No knowledge entries to populate")
        return False
    
    # Initialize embedding service
    app_logger.info("🔄 Initializing embedding service...")
    embedding_service = EmbeddingService()
    await embedding_service.initialize_model()
    
    # Connect to Qdrant
    try:
        client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            timeout=30,
        )
        
        # Check if collection exists
        collection_name = settings.QDRANT_COLLECTION_NAME
        collections = client.get_collections()
        exists = any(col.name == collection_name for col in collections.collections)
        
        if not exists:
            app_logger.info(f"📦 Creating collection '{collection_name}'...")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=384,  # Model dimension for paraphrase-multilingual-MiniLM-L12-v2
                    distance=Distance.COSINE
                )
            )
            app_logger.info(f"✅ Collection '{collection_name}' created")
        else:
            app_logger.info(f"📦 Collection '{collection_name}' already exists")
            
            # Check if collection is empty
            collection_info = client.get_collection(collection_name)
            if collection_info.points_count > 0:
                app_logger.info(f"🗑️ Clearing existing {collection_info.points_count} points...")
                client.delete_collection(collection_name=collection_name)
                app_logger.info("🗑️ Existing collection deleted")
                
                # Recreate collection
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=384,
                        distance=Distance.COSINE
                    )
                )
                app_logger.info("✅ Collection recreated")
            else:
                app_logger.info("📦 Collection is empty, proceeding with population")
        
        # Generate embeddings and create points
        app_logger.info("🔄 Generating embeddings...")
        points = []
        
        for i, entry in enumerate(knowledge_entries):
            app_logger.info(f"Processing {i+1}/{len(knowledge_entries)}: {entry['id']}")
            
            # Generate embedding
            embedding = await embedding_service.embed_text(entry['content'])
            
            # Create point
            point = PointStruct(
                id=i,
                vector=embedding,
                payload={
                    "content": entry['content'],
                    "doc_id": entry['id'],
                    **entry['metadata']
                }
            )
            points.append(point)
        
        # Upload to Qdrant
        app_logger.info(f"📤 Uploading {len(points)} points to Qdrant...")
        
        batch_size = 100  # Upload in batches
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            client.upsert(
                collection_name=collection_name,
                points=batch
            )
            app_logger.info(f"  Uploaded batch {i//batch_size + 1}/{(len(points) + batch_size - 1)//batch_size}")
        
        # Verify upload
        collection_info = client.get_collection(collection_name)
        app_logger.info(f"✅ Success! Collection now has {collection_info.points_count} points")
        
        # Test search
        app_logger.info("🔍 Testing search...")
        test_query = "Como funciona o método Kumon?"
        test_embedding = await embedding_service.embed_text(test_query)
        
        search_results = client.search(
            collection_name=collection_name,
            query_vector=test_embedding,
            limit=3
        )
        
        app_logger.info(f"Test query: '{test_query}'")
        for i, result in enumerate(search_results):
            app_logger.info(f"  Result {i+1} (score: {result.score:.3f}): {result.payload.get('doc_id', 'unknown')}")
        
        return True
        
    except Exception as e:
        app_logger.error(f"❌ Error connecting to Qdrant: {e}")
        return False


async def main():
    """Main execution"""
    success = await populate_qdrant()
    
    if success:
        app_logger.info("🎉 Qdrant population completed successfully!")
    else:
        app_logger.error("❌ Qdrant population failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())