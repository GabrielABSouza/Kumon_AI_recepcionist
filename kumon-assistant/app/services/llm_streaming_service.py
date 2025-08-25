"""
LLM Streaming Service for Real-time Response Delivery
Wave 1 Implementation - Response Streaming
Target: <200ms first chunk latency
"""

import asyncio
import time
from typing import AsyncIterator, Optional, Dict, Any, List
from openai import AsyncOpenAI
import logging
from dataclasses import dataclass

from ..core.config import settings
from ..core.logger import app_logger


@dataclass
class StreamingMetrics:
    """Metrics for streaming performance tracking"""
    start_time: float
    first_chunk_time: Optional[float] = None
    total_chunks: int = 0
    total_characters: int = 0
    completion_time: Optional[float] = None
    
    @property
    def first_chunk_latency_ms(self) -> float:
        """First chunk latency in milliseconds"""
        if self.first_chunk_time:
            return (self.first_chunk_time - self.start_time) * 1000
        return 0.0
    
    @property
    def total_duration_ms(self) -> float:
        """Total completion time in milliseconds"""
        if self.completion_time:
            return (self.completion_time - self.start_time) * 1000
        return 0.0


class StreamingBuffer:
    """Smart buffer for managing streaming chunks"""
    
    def __init__(self, target_chunk_size: int = 50):
        self.buffer = ""
        self.target_chunk_size = target_chunk_size
        self.sentences_buffer = []
        
    def add_content(self, content: str) -> List[str]:
        """Add content and return ready chunks"""
        self.buffer += content
        chunks = []
        
        # Check for sentence boundaries
        while True:
            # Look for sentence endings
            sentence_endings = ['. ', '! ', '? ', '.\n', '!\n', '?\n']
            earliest_end = float('inf')
            ending_found = None
            
            for ending in sentence_endings:
                pos = self.buffer.find(ending)
                if pos != -1 and pos < earliest_end:
                    earliest_end = pos
                    ending_found = ending
            
            # If we found a sentence ending or buffer is getting large
            if ending_found and earliest_end < float('inf'):
                chunk = self.buffer[:earliest_end + len(ending_found)]
                self.buffer = self.buffer[earliest_end + len(ending_found):]
                if chunk.strip():
                    chunks.append(chunk.strip())
            elif len(self.buffer) > self.target_chunk_size * 2:
                # Force chunk if buffer is too large
                chunk = self.buffer[:self.target_chunk_size]
                self.buffer = self.buffer[self.target_chunk_size:]
                if chunk.strip():
                    chunks.append(chunk.strip())
            else:
                break
        
        return chunks
    
    def flush(self) -> str:
        """Get remaining content in buffer"""
        content = self.buffer
        self.buffer = ""
        return content.strip()


class LLMStreamingService:
    """
    High-performance LLM streaming service
    Optimized for WhatsApp response delivery
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=30.0,
            max_retries=2
        )
        
        # Optimized streaming configuration
        self.stream_config = {
            "model": getattr(settings, 'OPENAI_MODEL', 'gpt-4-turbo'),
            "stream": True,
            "max_tokens": 500,
            "temperature": 0.7,
            "presence_penalty": 0.1,
            "frequency_penalty": 0.1,
            "top_p": 0.95
        }
        
        # Performance tracking
        self.metrics_history = []
        
        app_logger.info("LLM Streaming Service initialized", extra={
            "model": self.stream_config["model"],
            "max_tokens": self.stream_config["max_tokens"]
        })
    
    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[str]:
        """
        Stream LLM response chunk by chunk
        
        Args:
            messages: OpenAI format messages
            context: Additional context for optimization
            
        Yields:
            Response chunks as they become available
        """
        metrics = StreamingMetrics(start_time=time.time())
        buffer = StreamingBuffer(target_chunk_size=50)
        
        try:
            app_logger.info("Starting streaming request", extra={
                "message_count": len(messages),
                "context_keys": list(context.keys()) if context else []
            })
            
            # Create streaming request
            stream = await self.client.chat.completions.create(
                messages=messages,
                **self.stream_config
            )
            
            # Process streaming chunks
            async for chunk in stream:
                current_time = time.time()
                
                # Track first chunk
                if metrics.first_chunk_time is None:
                    metrics.first_chunk_time = current_time
                    first_chunk_latency = metrics.first_chunk_latency_ms
                    
                    app_logger.info(f"First chunk received", extra={
                        "latency_ms": first_chunk_latency,
                        "target_met": first_chunk_latency < 200
                    })
                    
                    # Alert if target not met
                    if first_chunk_latency > 200:
                        app_logger.warning(f"First chunk latency {first_chunk_latency:.2f}ms exceeds 200ms target")
                
                # Extract content
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    metrics.total_characters += len(content)
                    
                    # Buffer and yield ready chunks
                    ready_chunks = buffer.add_content(content)
                    for ready_chunk in ready_chunks:
                        metrics.total_chunks += 1
                        yield ready_chunk
            
            # Yield any remaining content
            remaining = buffer.flush()
            if remaining:
                metrics.total_chunks += 1
                yield remaining
            
            # Final metrics
            metrics.completion_time = time.time()
            
            # Log performance metrics
            app_logger.info("Streaming completed", extra={
                "first_chunk_ms": metrics.first_chunk_latency_ms,
                "total_duration_ms": metrics.total_duration_ms,
                "total_chunks": metrics.total_chunks,
                "total_characters": metrics.total_characters,
                "avg_chunk_size": metrics.total_characters / max(metrics.total_chunks, 1)
            })
            
            # Store metrics for analysis
            self.metrics_history.append(metrics)
            
            # Keep only last 100 metrics
            if len(self.metrics_history) > 100:
                self.metrics_history = self.metrics_history[-100:]
                
        except Exception as e:
            app_logger.error(f"Streaming error: {e}", extra={
                "elapsed_ms": (time.time() - metrics.start_time) * 1000
            })
            
            # Yield fallback response
            yield "Desculpe, houve um problema técnico. Como posso ajudá-lo?"
    
    async def generate_streamed_response(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncIterator[str]:
        """
        Generate streamed response from user message
        
        Args:
            user_message: User's message
            system_prompt: System prompt for context
            conversation_history: Previous conversation context
            
        Yields:
            Response chunks
        """
        
        # Build messages array
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history (last 5 messages to stay within context)
        if conversation_history:
            messages.extend(conversation_history[-5:])
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Stream response
        async for chunk in self.stream_response(messages):
            yield chunk
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        recent_metrics = self.metrics_history[-10:]  # Last 10 requests
        
        first_chunk_latencies = [m.first_chunk_latency_ms for m in recent_metrics if m.first_chunk_time]
        total_durations = [m.total_duration_ms for m in recent_metrics if m.completion_time]
        
        return {
            "requests_tracked": len(self.metrics_history),
            "recent_requests": len(recent_metrics),
            "avg_first_chunk_ms": sum(first_chunk_latencies) / len(first_chunk_latencies) if first_chunk_latencies else 0,
            "avg_total_duration_ms": sum(total_durations) / len(total_durations) if total_durations else 0,
            "target_met_percentage": (
                len([l for l in first_chunk_latencies if l < 200]) / len(first_chunk_latencies) * 100
                if first_chunk_latencies else 0
            ),
            "max_first_chunk_ms": max(first_chunk_latencies) if first_chunk_latencies else 0,
            "min_first_chunk_ms": min(first_chunk_latencies) if first_chunk_latencies else 0
        }
    
    async def test_streaming_performance(self) -> Dict[str, Any]:
        """Test streaming performance with sample queries"""
        
        test_cases = [
            {
                "name": "greeting",
                "system": "Você é Cecília, assistente do Kumon Vila A. Seja amigável e profissional.",
                "user": "Olá, gostaria de saber sobre o método Kumon"
            },
            {
                "name": "scheduling",
                "system": "Você é Cecília, assistente do Kumon Vila A. Ajude com agendamentos.",
                "user": "Quero agendar uma entrevista para meu filho"
            },
            {
                "name": "information",
                "system": "Você é Cecília, assistente do Kumon Vila A. Forneça informações precisas.",
                "user": "Quais são os horários de funcionamento?"
            }
        ]
        
        results = []
        
        for test_case in test_cases:
            chunks = []
            start_time = time.time()
            first_chunk_time = None
            
            try:
                async for chunk in self.generate_streamed_response(
                    test_case["user"],
                    test_case["system"]
                ):
                    if first_chunk_time is None:
                        first_chunk_time = time.time()
                    chunks.append(chunk)
                
                total_time = time.time() - start_time
                first_chunk_latency = (first_chunk_time - start_time) * 1000 if first_chunk_time else 0
                
                results.append({
                    "test_case": test_case["name"],
                    "success": True,
                    "first_chunk_ms": first_chunk_latency,
                    "total_duration_ms": total_time * 1000,
                    "chunks_count": len(chunks),
                    "total_response_length": sum(len(chunk) for chunk in chunks),
                    "target_met": first_chunk_latency < 200
                })
                
            except Exception as e:
                results.append({
                    "test_case": test_case["name"],
                    "success": False,
                    "error": str(e),
                    "target_met": False
                })
        
        # Calculate summary
        successful_tests = [r for r in results if r["success"]]
        avg_first_chunk = sum(r["first_chunk_ms"] for r in successful_tests) / len(successful_tests) if successful_tests else 0
        targets_met = sum(1 for r in successful_tests if r["target_met"])
        
        return {
            "test_summary": {
                "total_tests": len(test_cases),
                "successful_tests": len(successful_tests),
                "avg_first_chunk_ms": avg_first_chunk,
                "targets_met": targets_met,
                "success_rate": len(successful_tests) / len(test_cases) * 100,
                "target_met_rate": targets_met / len(successful_tests) * 100 if successful_tests else 0
            },
            "individual_results": results,
            "performance_assessment": "EXCELLENT" if avg_first_chunk < 150 else "GOOD" if avg_first_chunk < 200 else "NEEDS_IMPROVEMENT"
        }


# Global streaming service instance
streaming_service = LLMStreamingService()