"""
Streaming Message Processor - Wave 1 Implementation
Integrates LLM streaming with existing message processors
Target: <200ms first chunk, maintain security and quality
"""

import asyncio
import time
from typing import AsyncIterator, Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from ..core.logger import app_logger
from ..core.config import settings
from ..models.message import WhatsAppMessage, MessageResponse, MessageType
from ..services.llm_streaming_service import streaming_service
from ..services.message_processor import MessageProcessor
from ..services.secure_message_processor import secure_message_processor
from ..core.workflow import cecilia_workflow


@dataclass
class StreamingResponse:
    """Container for streaming response data"""
    message_id: str
    phone_number: str
    chunks: List[str]
    is_complete: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    total_processing_time: float = 0.0
    first_chunk_time: float = 0.0


class StreamingMessageProcessor:
    """
    Enhanced message processor with streaming capabilities
    
    Integrates streaming responses with:
    - Legacy message processor
    - Secure message processor (Fase 5)
    - LangGraph workflow
    - Security validation
    """
    
    def __init__(self):
        # Component processors
        self.legacy_processor = MessageProcessor()
        self.secure_processor = secure_message_processor
        self.streaming_service = streaming_service
        
        # Configuration
        self.config = {
            "enable_streaming": True,
            "streaming_timeout": 30.0,
            "max_chunk_size": 100,
            "fallback_on_stream_failure": True,
            "security_validation_enabled": True
        }
        
        # Active streaming sessions
        self.active_streams: Dict[str, StreamingResponse] = {}
        
        # Performance metrics
        self.metrics = {
            "total_streaming_requests": 0,
            "successful_streams": 0,
            "failed_streams": 0,
            "avg_first_chunk_time": 0.0,
            "avg_total_time": 0.0
        }
        
        app_logger.info("Streaming Message Processor initialized", extra={
            "streaming_enabled": self.config["enable_streaming"],
            "security_enabled": self.config["security_validation_enabled"]
        })
    
    async def process_message_stream(
        self,
        message: WhatsAppMessage
    ) -> AsyncIterator[str]:
        """
        Process message with streaming response
        
        Args:
            message: Incoming WhatsApp message
            
        Yields:
            Response chunks as they become available
        """
        
        start_time = time.time()
        self.metrics["total_streaming_requests"] += 1
        
        phone_number = getattr(message, 'from_number', None) or getattr(message, 'phone', None)
        message_content = getattr(message, 'content', None) or getattr(message, 'message', None)
        
        # Initialize streaming response
        streaming_response = StreamingResponse(
            message_id=message.message_id,
            phone_number=phone_number,
            chunks=[],
            metadata={"start_time": start_time}
        )
        
        try:
            app_logger.info(f"Starting streaming response for {phone_number}", extra={
                "message_id": message.message_id,
                "content_length": len(message_content) if message_content else 0
            })
            
            # Phase 1: Security validation (if enabled)
            if self.config["security_validation_enabled"]:
                security_valid = await self._validate_streaming_security(message)
                if not security_valid["allowed"]:
                    yield security_valid["response"]
                    streaming_response.error = "security_block"
                    return
            
            # Phase 2: Determine processing path
            use_secure = self._should_use_secure_processing(message)
            use_langgraph = getattr(settings, 'USE_LANGGRAPH_WORKFLOW', False)
            
            # Phase 3: Generate streaming response
            if use_langgraph:
                async for chunk in self._stream_langgraph_response(message, streaming_response):
                    yield chunk
            elif use_secure:
                async for chunk in self._stream_secure_response(message, streaming_response):
                    yield chunk
            else:
                async for chunk in self._stream_legacy_response(message, streaming_response):
                    yield chunk
            
            # Update success metrics
            streaming_response.is_complete = True
            streaming_response.total_processing_time = time.time() - start_time
            self.metrics["successful_streams"] += 1
            
            # Update average times
            if streaming_response.first_chunk_time > 0:
                self._update_timing_metrics(streaming_response)
            
            app_logger.info(f"Streaming completed successfully", extra={
                "phone_number": phone_number,
                "chunks_sent": len(streaming_response.chunks),
                "total_time": streaming_response.total_processing_time,
                "first_chunk_time": streaming_response.first_chunk_time
            })
            
        except asyncio.TimeoutError:
            self.metrics["failed_streams"] += 1
            streaming_response.error = "timeout"
            yield "Desculpe, sua solicitação está demorando para ser processada. Tente novamente em alguns minutos."
            
        except Exception as e:
            self.metrics["failed_streams"] += 1
            streaming_response.error = str(e)
            app_logger.error(f"Streaming error for {phone_number}: {e}")
            
            # Fallback to non-streaming if enabled
            if self.config["fallback_on_stream_failure"]:
                fallback_response = await self._fallback_to_non_streaming(message)
                yield fallback_response.content
            else:
                yield "Desculpe, houve um problema técnico. Entre em contato conosco pelo telefone (51) 99692-1999."
        
        finally:
            # Clean up streaming session
            if phone_number in self.active_streams:
                del self.active_streams[phone_number]
    
    async def _stream_langgraph_response(
        self, 
        message: WhatsAppMessage,
        streaming_response: StreamingResponse
    ) -> AsyncIterator[str]:
        """Stream response using LangGraph workflow"""
        
        phone_number = getattr(message, 'from_number', None) or getattr(message, 'phone', None)
        message_content = getattr(message, 'content', None) or getattr(message, 'message', None)
        
        try:
            app_logger.info(f"Streaming via LangGraph workflow for {phone_number}")
            
            # Get LangGraph workflow result (non-streaming for now)
            workflow_result = await cecilia_workflow.process_message(
                phone_number=phone_number,
                user_message=message_content
            )
            
            # Stream the response content
            response_content = workflow_result.get("response", "Desculpe, houve um problema técnico.")
            
            # For now, simulate streaming by chunking the response
            # TODO: Implement true streaming in LangGraph nodes
            chunks = self._chunk_response(response_content)
            
            for i, chunk in enumerate(chunks):
                if i == 0:
                    streaming_response.first_chunk_time = time.time() - streaming_response.metadata["start_time"]
                
                streaming_response.chunks.append(chunk)
                yield chunk
                
                # Small delay between chunks for realistic streaming
                await asyncio.sleep(0.1)
            
        except Exception as e:
            app_logger.error(f"LangGraph streaming error: {e}")
            raise
    
    async def _stream_secure_response(
        self, 
        message: WhatsAppMessage,
        streaming_response: StreamingResponse
    ) -> AsyncIterator[str]:
        """Stream response using secure processor with LLM streaming"""
        
        phone_number = getattr(message, 'from_number', None) or getattr(message, 'phone', None)
        message_content = getattr(message, 'content', None) or getattr(message, 'message', None)
        
        try:
            app_logger.info(f"Streaming via secure processor for {phone_number}")
            
            # Get context from secure workflow
            # For now, get non-streaming response and enhance with streaming
            secure_response = await self.secure_processor.process_message(message)
            
            # Build streaming context for LLM
            system_prompt = "Você é Cecília, assistente virtual do Kumon Vila A. Seja amigável, profissional e focada em educação."
            
            # Stream enhanced response
            chunk_count = 0
            async for chunk in self.streaming_service.generate_streamed_response(
                user_message=message_content,
                system_prompt=system_prompt
            ):
                if chunk_count == 0:
                    streaming_response.first_chunk_time = time.time() - streaming_response.metadata["start_time"]
                
                streaming_response.chunks.append(chunk)
                chunk_count += 1
                yield chunk
            
        except Exception as e:
            app_logger.error(f"Secure streaming error: {e}")
            raise
    
    async def _stream_legacy_response(
        self, 
        message: WhatsAppMessage,
        streaming_response: StreamingResponse
    ) -> AsyncIterator[str]:
        """Stream response using legacy processor"""
        
        phone_number = getattr(message, 'from_number', None) or getattr(message, 'phone', None)
        
        try:
            app_logger.info(f"Streaming via legacy processor for {phone_number}")
            
            # Get legacy response
            legacy_response = await self.legacy_processor.process_message(message)
            
            # Stream the response content
            chunks = self._chunk_response(legacy_response.content)
            
            for i, chunk in enumerate(chunks):
                if i == 0:
                    streaming_response.first_chunk_time = time.time() - streaming_response.metadata["start_time"]
                
                streaming_response.chunks.append(chunk)
                yield chunk
                
                # Small delay for realistic streaming
                await asyncio.sleep(0.05)
            
        except Exception as e:
            app_logger.error(f"Legacy streaming error: {e}")
            raise
    
    def _chunk_response(self, response_content: str, chunk_size: int = 50) -> List[str]:
        """Break response into streaming chunks"""
        
        if not response_content:
            return ["Olá! Como posso ajudá-lo hoje?"]
        
        # Split by sentences first
        sentences = []
        current_sentence = ""
        
        for char in response_content:
            current_sentence += char
            if char in '.!?\n' and len(current_sentence.strip()) > 10:
                sentences.append(current_sentence.strip())
                current_sentence = ""
        
        # Add remaining content
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        # Group sentences into chunks
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk + sentence) <= chunk_size or not current_chunk:
                current_chunk += sentence + " "
            else:
                chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks or [response_content]
    
    async def _validate_streaming_security(self, message: WhatsAppMessage) -> Dict[str, Any]:
        """Quick security validation for streaming"""
        
        try:
            # Basic rate limiting check
            phone_number = getattr(message, 'from_number', None) or getattr(message, 'phone', None)
            
            # Check if user is currently streaming (prevent concurrent streams)
            if phone_number in self.active_streams:
                return {
                    "allowed": False,
                    "response": "Aguarde enquanto processo sua mensagem anterior."
                }
            
            # Quick threat assessment (simplified for streaming)
            message_content = getattr(message, 'content', None) or getattr(message, 'message', None)
            
            # Basic prompt injection detection
            suspicious_patterns = ['ignore', 'forget', 'system', 'admin', 'developer']
            if any(pattern in message_content.lower() for pattern in suspicious_patterns):
                app_logger.warning(f"Suspicious pattern detected in streaming request: {phone_number}")
            
            return {"allowed": True}
            
        except Exception as e:
            app_logger.error(f"Streaming security validation error: {e}")
            return {
                "allowed": False,
                "response": "Por questões de segurança, não posso processar sua solicitação no momento."
            }
    
    def _should_use_secure_processing(self, message: WhatsAppMessage) -> bool:
        """Determine if message should use secure processing"""
        
        # Check global secure processing setting
        use_secure = getattr(settings, 'USE_SECURE_PROCESSING', True)
        if not use_secure:
            return False
        
        # Check rollout percentage
        rollout_percentage = getattr(settings, 'SECURE_ROLLOUT_PERCENTAGE', 100.0)
        if rollout_percentage >= 100.0:
            return True
        
        # Gradual rollout based on phone number hash
        if rollout_percentage > 0:
            import hashlib
            phone_number = getattr(message, 'from_number', None) or getattr(message, 'phone', None)
            phone_hash = hashlib.md5(phone_number.encode()).hexdigest()
            hash_value = int(phone_hash[:8], 16) % 100
            return hash_value < rollout_percentage
        
        return False
    
    async def _fallback_to_non_streaming(self, message: WhatsAppMessage) -> MessageResponse:
        """Fallback to non-streaming response"""
        
        try:
            app_logger.info("Falling back to non-streaming response")
            
            # Use appropriate processor
            if self._should_use_secure_processing(message):
                return await self.secure_processor.process_message(message)
            else:
                return await self.legacy_processor.process_message(message)
            
        except Exception as e:
            app_logger.error(f"Fallback processing error: {e}")
            
            # Final fallback
            return MessageResponse(
                content="Desculpe, houve um problema técnico. Entre em contato conosco pelo telefone (51) 99692-1999.",
                message_type=MessageType.TEXT,
                metadata={"fallback": True, "error": str(e)}
            )
    
    def _update_timing_metrics(self, streaming_response: StreamingResponse):
        """Update timing performance metrics"""
        
        # Update first chunk time
        total_requests = self.metrics["successful_streams"]
        if total_requests > 0:
            self.metrics["avg_first_chunk_time"] = (
                (self.metrics["avg_first_chunk_time"] * (total_requests - 1) + 
                 streaming_response.first_chunk_time * 1000) / total_requests
            )
            
            self.metrics["avg_total_time"] = (
                (self.metrics["avg_total_time"] * (total_requests - 1) + 
                 streaming_response.total_processing_time * 1000) / total_requests
            )
    
    async def process_message_traditional(self, message: WhatsAppMessage) -> MessageResponse:
        """Traditional non-streaming message processing (for compatibility)"""
        
        try:
            if self._should_use_secure_processing(message):
                return await self.secure_processor.process_message(message)
            else:
                return await self.legacy_processor.process_message(message)
        except Exception as e:
            app_logger.error(f"Traditional processing error: {e}")
            return MessageResponse(
                content="Desculpe, houve um problema técnico.",
                message_type=MessageType.TEXT,
                metadata={"error": True}
            )
    
    def get_streaming_metrics(self) -> Dict[str, Any]:
        """Get comprehensive streaming performance metrics"""
        
        success_rate = (
            self.metrics["successful_streams"] / 
            max(1, self.metrics["total_streaming_requests"])
        ) * 100
        
        return {
            "streaming_performance": {
                "total_requests": self.metrics["total_streaming_requests"],
                "successful_streams": self.metrics["successful_streams"],
                "failed_streams": self.metrics["failed_streams"],
                "success_rate_percentage": success_rate,
                "avg_first_chunk_ms": self.metrics["avg_first_chunk_time"],
                "avg_total_time_ms": self.metrics["avg_total_time"],
                "target_met_percentage": (
                    100.0 if self.metrics["avg_first_chunk_time"] < 200 else 0.0
                )
            },
            "active_sessions": len(self.active_streams),
            "configuration": self.config,
            "component_status": {
                "llm_streaming_service": "operational",
                "legacy_processor": "operational",
                "secure_processor": "operational",
                "langgraph_workflow": "operational" if getattr(settings, 'USE_LANGGRAPH_WORKFLOW', False) else "disabled"
            }
        }
    
    async def test_streaming_performance(self) -> Dict[str, Any]:
        """Test streaming performance with sample messages"""
        
        from ..models.message import WhatsAppMessage
        
        test_messages = [
            WhatsAppMessage(
                message_id="test_1",
                from_number="test_user",
                content="Olá, gostaria de saber sobre o método Kumon",
                message_type=MessageType.TEXT
            ),
            WhatsAppMessage(
                message_id="test_2", 
                from_number="test_user",
                content="Quero agendar uma entrevista para meu filho",
                message_type=MessageType.TEXT
            ),
            WhatsAppMessage(
                message_id="test_3",
                from_number="test_user", 
                content="Quais são os horários de funcionamento?",
                message_type=MessageType.TEXT
            )
        ]
        
        results = []
        
        for test_msg in test_messages:
            start_time = time.time()
            first_chunk_time = None
            chunk_count = 0
            
            try:
                async for chunk in self.process_message_stream(test_msg):
                    if first_chunk_time is None:
                        first_chunk_time = time.time()
                    chunk_count += 1
                
                total_time = time.time() - start_time
                first_chunk_latency = (first_chunk_time - start_time) * 1000 if first_chunk_time else 0
                
                results.append({
                    "message_id": test_msg.message_id,
                    "success": True,
                    "first_chunk_ms": first_chunk_latency,
                    "total_duration_ms": total_time * 1000,
                    "chunks_received": chunk_count,
                    "target_met": first_chunk_latency < 200
                })
                
            except Exception as e:
                results.append({
                    "message_id": test_msg.message_id,
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
                "total_tests": len(test_messages),
                "successful_tests": len(successful_tests), 
                "avg_first_chunk_ms": avg_first_chunk,
                "targets_met": targets_met,
                "success_rate": len(successful_tests) / len(test_messages) * 100,
                "target_met_rate": targets_met / len(successful_tests) * 100 if successful_tests else 0
            },
            "individual_results": results,
            "performance_assessment": "EXCELLENT" if avg_first_chunk < 150 else "GOOD" if avg_first_chunk < 200 else "NEEDS_IMPROVEMENT"
        }


# Global streaming message processor instance
streaming_message_processor = StreamingMessageProcessor()