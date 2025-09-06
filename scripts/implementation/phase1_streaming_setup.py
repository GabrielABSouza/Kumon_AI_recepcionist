#!/usr/bin/env python3
"""
FASE 1: Script de Implementação - Response Streaming
SuperClaude Framework Implementation Script
"""

import asyncio
import logging
from typing import AsyncIterator, Optional
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)


class StreamingImplementation:
    """
    Implementa streaming de respostas LLM para reduzir latência
    Target: First chunk <200ms
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.stream_config = {
            "model": "gpt-4-turbo",
            "stream": True,
            "max_tokens": 500,
            "temperature": 0.7,
            "stream_options": {"chunk_size": 50}
        }
    
    async def stream_response(
        self, 
        prompt: str,
        context: Optional[list] = None
    ) -> AsyncIterator[str]:
        """
        Stream LLM response chunk by chunk
        
        Args:
            prompt: User prompt
            context: Conversation context
            
        Yields:
            Response chunks as they arrive
        """
        messages = context or []
        messages.append({"role": "user", "content": prompt})
        
        try:
            # Start streaming
            start_time = asyncio.get_event_loop().time()
            first_chunk_time = None
            
            stream = await self.client.chat.completions.create(
                messages=messages,
                **self.stream_config
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    # Track first chunk latency
                    if first_chunk_time is None:
                        first_chunk_time = asyncio.get_event_loop().time()
                        latency = (first_chunk_time - start_time) * 1000
                        logger.info(f"First chunk latency: {latency:.2f}ms")
                        
                        # Alert if >200ms target
                        if latency > 200:
                            logger.warning(f"First chunk latency {latency:.2f}ms exceeds 200ms target")
                    
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield "Desculpe, houve um erro ao processar sua mensagem."
    
    async def test_streaming_performance(self):
        """Test streaming performance with sample prompts"""
        test_prompts = [
            "Olá, gostaria de saber sobre o método Kumon",
            "Quais são os horários de funcionamento?",
            "Como agendar uma entrevista?"
        ]
        
        results = []
        for prompt in test_prompts:
            chunks = []
            start = asyncio.get_event_loop().time()
            
            async for chunk in self.stream_response(prompt):
                chunks.append(chunk)
            
            total_time = (asyncio.get_event_loop().time() - start) * 1000
            results.append({
                "prompt": prompt[:30] + "...",
                "chunks": len(chunks),
                "total_time_ms": total_time,
                "response_preview": "".join(chunks[:3])
            })
        
        return results


async def main():
    """Execute streaming implementation and tests"""
    print("🚀 Iniciando implementação de Response Streaming...")
    
    impl = StreamingImplementation()
    
    # Test performance
    print("\n📊 Testando performance de streaming...")
    results = await impl.test_streaming_performance()
    
    print("\n✅ Resultados dos testes:")
    for result in results:
        print(f"\nPrompt: {result['prompt']}")
        print(f"Chunks: {result['chunks']}")
        print(f"Tempo total: {result['total_time_ms']:.2f}ms")
        print(f"Preview: {result['response_preview']}...")
    
    print("\n✅ Implementação de streaming concluída!")


if __name__ == "__main__":
    asyncio.run(main())