"""
Wave 6: Conversation-Specific Workflow Patterns
Specialized workflow patterns for WhatsApp conversation processing and AI responses
"""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..core.logger import app_logger
from ..core.state.models import CeciliaState
from .enhanced_workflow_patterns import (
    CachedNode,
    ConditionalNode,
    NodeResult,
    NodeStatus,
    ParallelNode,
    WorkflowContext,
    WorkflowNode,
    WorkflowPattern,
    WorkflowPriority,
)


@dataclass
class ConversationInput:
    """Input data structure for conversation workflows"""

    user_id: str
    unit_id: Optional[str]
    message_text: str
    message_type: str = "text"
    phone_number: str = ""
    context: Dict[str, Any] = None

    def __post_init__(self):
        if self.context is None:
            self.context = {}


@dataclass
class ConversationResult:
    """Result data structure for conversation workflows"""

    response_text: str
    response_type: str = "text"
    intent: Optional[str] = None
    confidence: float = 0.0
    context: Dict[str, Any] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.context is None:
            self.context = {}
        if self.metadata is None:
            self.metadata = {}


class MessagePreprocessingNode(WorkflowNode[ConversationInput, ConversationInput]):
    """Node for message preprocessing and sanitization"""

    def __init__(self):
        super().__init__(
            node_id="message_preprocessing",
            name="Message Preprocessing",
            description="Sanitize and preprocess incoming messages",
            timeout=10.0,
        )

    async def execute(
        self, input_data: ConversationInput, context: WorkflowContext
    ) -> ConversationInput:
        """Preprocess and sanitize message"""
        start_time = time.time()

        try:
            # Create processed input
            processed_input = ConversationInput(
                user_id=input_data.user_id,
                unit_id=input_data.unit_id,
                message_text=self._sanitize_message(input_data.message_text),
                message_type=input_data.message_type,
                phone_number=input_data.phone_number,
                context=input_data.context.copy(),
            )

            # Add preprocessing metadata
            processed_input.context["preprocessing"] = {
                "original_length": len(input_data.message_text),
                "processed_length": len(processed_input.message_text),
                "processing_time": time.time() - start_time,
                "sanitization_applied": True,
            }

            app_logger.debug(f"Message preprocessed for user {input_data.user_id}")
            return processed_input

        except Exception as e:
            app_logger.error(f"Message preprocessing failed: {e}")
            raise

    def _sanitize_message(self, message: str) -> str:
        """Sanitize message content"""
        if not message:
            return ""

        # Remove excessive whitespace
        sanitized = " ".join(message.split())

        # Limit message length (prevent DoS)
        max_length = 4000
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "..."

        # Remove potential script injections (basic)
        dangerous_patterns = ["<script", "javascript:", "data:", "vbscript:"]
        for pattern in dangerous_patterns:
            sanitized = sanitized.replace(pattern.lower(), "")
            sanitized = sanitized.replace(pattern.upper(), "")

        return sanitized


class IntentClassificationNode(CachedNode[ConversationInput, Dict[str, Any]]):
    """Cached node for intent classification"""

    def __init__(self):
        super().__init__(
            node_id="intent_classification",
            name="Intent Classification",
            description="Classify user intent from message",
            timeout=15.0,
            cache_ttl=300.0,  # 5 minutes cache
        )

    async def _execute_impl(
        self, input_data: ConversationInput, context: WorkflowContext
    ) -> Dict[str, Any]:
        """Execute intent classification"""
        try:
            # Get intent classifier service
            from ..core import dependencies

            intent_classifier = dependencies.intent_classifier

            if not intent_classifier:
                app_logger.warning("Intent classifier not available")
                return {"intent": "general", "confidence": 0.5, "fallback": True}

            # Classify intent
            classification_result = await intent_classifier.classify_intent(
                message=input_data.message_text, context=input_data.context
            )

            app_logger.debug(f"Intent classified: {classification_result.get('intent', 'unknown')}")
            return classification_result

        except Exception as e:
            app_logger.error(f"Intent classification failed: {e}")
            return {"intent": "general", "confidence": 0.0, "error": str(e)}


class ContextRetrievalNode(CachedNode[ConversationInput, Dict[str, Any]]):
    """Node for retrieving conversation context and relevant knowledge"""

    def __init__(self):
        super().__init__(
            node_id="context_retrieval",
            name="Context Retrieval",
            description="Retrieve conversation history and relevant knowledge",
            timeout=20.0,
            cache_ttl=180.0,  # 3 minutes cache
        )

    async def _execute_impl(
        self, input_data: ConversationInput, context: WorkflowContext
    ) -> Dict[str, Any]:
        """Retrieve conversation context"""
        try:
            context_data = {
                "conversation_history": [],
                "knowledge_base": [],
                "user_profile": {},
                "unit_context": {},
            }

            # Get conversation memory if available
            try:
                from ..services.conversation_memory_service import (
                    conversation_memory_service,
                )

                conversation_key = f"{input_data.user_id}_{input_data.unit_id or 'default'}"
                history = await conversation_memory_service.get_conversation_history(
                    conversation_key, limit=10
                )
                context_data["conversation_history"] = history or []

            except Exception as e:
                app_logger.warning(f"Failed to retrieve conversation history: {e}")

            # Get relevant knowledge from RAG if available
            try:
                from ..core import dependencies

                rag_service = dependencies.langchain_rag_service

                if rag_service:
                    knowledge_results = await rag_service.query(
                        query=input_data.message_text, max_results=3
                    )
                    context_data["knowledge_base"] = knowledge_results or []

            except Exception as e:
                app_logger.warning(f"Failed to retrieve knowledge base context: {e}")

            # Add unit-specific context if available
            if input_data.unit_id:
                context_data["unit_context"] = {
                    "unit_id": input_data.unit_id,
                    "context_retrieved": True,
                }

            app_logger.debug(f"Context retrieved for user {input_data.user_id}")
            return context_data

        except Exception as e:
            app_logger.error(f"Context retrieval failed: {e}")
            return {"conversation_history": [], "knowledge_base": [], "error": str(e)}


class ResponseGenerationNode(
    WorkflowNode[Tuple[ConversationInput, Dict, Dict], ConversationResult]
):
    """Node for generating AI responses based on intent and context"""

    def __init__(self):
        super().__init__(
            node_id="response_generation",
            name="Response Generation",
            description="Generate AI response using LLM service",
            timeout=30.0,
            retries=2,
        )

    async def execute(
        self, input_data: Tuple[ConversationInput, Dict, Dict], context: WorkflowContext
    ) -> ConversationResult:
        """Generate AI response"""
        conversation_input, intent_data, context_data = input_data

        try:
            # Get LLM service
            from ..core import dependencies

            llm_service = dependencies.llm_service

            if not llm_service:
                raise RuntimeError("LLM service not available")

            # Prepare messages for LLM
            messages = self._prepare_llm_messages(conversation_input, intent_data, context_data)

            # Generate response
            llm_response = await llm_service.generate_response(
                messages=messages,
                context={
                    "user_id": conversation_input.user_id,
                    "unit_id": conversation_input.unit_id,
                    "intent": intent_data.get("intent", "general"),
                    "confidence": intent_data.get("confidence", 0.0),
                },
            )

            # Create conversation result
            result = ConversationResult(
                response_text=llm_response.content,
                response_type="text",
                intent=intent_data.get("intent"),
                confidence=intent_data.get("confidence", 0.0),
                context={
                    "llm_response": {
                        "model": getattr(llm_response, "model", "unknown"),
                        "tokens_used": getattr(llm_response, "tokens_used", 0),
                        "processing_time": getattr(llm_response, "processing_time", 0.0),
                    }
                },
                metadata={
                    "generation_timestamp": time.time(),
                    "workflow_context": context.metadata,
                },
            )

            app_logger.info(f"Response generated for user {conversation_input.user_id}")
            return result

        except Exception as e:
            app_logger.error(f"Response generation failed: {e}")

            # Return fallback response
            return ConversationResult(
                response_text="Desculpe, estou tendo dificuldades para processar sua mensagem no momento. Tente novamente em alguns instantes.",
                response_type="text",
                intent=intent_data.get("intent", "error"),
                confidence=0.0,
                metadata={"error": str(e), "fallback": True},
            )

    def _prepare_llm_messages(
        self,
        conversation_input: ConversationInput,
        intent_data: Dict[str, Any],
        context_data: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Prepare messages for LLM service"""
        messages = []

        # System message with context
        system_content = self._build_system_message(intent_data, context_data)
        messages.append({"role": "system", "content": system_content})

        # Add conversation history
        for hist_msg in context_data.get("conversation_history", []):
            if isinstance(hist_msg, dict):
                messages.append(
                    {"role": hist_msg.get("role", "user"), "content": hist_msg.get("content", "")}
                )

        # Current user message
        messages.append({"role": "user", "content": conversation_input.message_text})

        return messages

    def _build_system_message(self, intent_data: Dict, context_data: Dict) -> str:
        """Build system message with context"""
        system_parts = [
            "Você é Cecília, a recepcionista virtual do Kumon.",
            "Responda de forma educada, prestativa e profissional.",
        ]

        # Add intent-specific instructions
        intent = intent_data.get("intent", "general")
        if intent == "scheduling":
            system_parts.append(
                "O usuário quer agendar uma aula ou atividade. Ajude com informações sobre horários e disponibilidade."
            )
        elif intent == "information":
            system_parts.append(
                "O usuário está pedindo informações sobre o Kumon. Forneça informações precisas e úteis."
            )
        elif intent == "support":
            system_parts.append(
                "O usuário precisa de suporte. Seja empático e tente resolver a questão."
            )

        # Add knowledge base context if available
        knowledge_items = context_data.get("knowledge_base", [])
        if knowledge_items:
            system_parts.append("\nInformações relevantes:")
            for item in knowledge_items[:3]:  # Limit to 3 most relevant
                if isinstance(item, dict) and "content" in item:
                    system_parts.append(f"- {item['content']}")

        return "\n".join(system_parts)


class ResponsePostprocessingNode(WorkflowNode[ConversationResult, ConversationResult]):
    """Node for post-processing generated responses"""

    def __init__(self):
        super().__init__(
            node_id="response_postprocessing",
            name="Response Postprocessing",
            description="Post-process and enhance generated responses",
            timeout=5.0,
        )

    async def execute(
        self, input_data: ConversationResult, context: WorkflowContext
    ) -> ConversationResult:
        """Post-process response"""
        try:
            # Create enhanced result
            enhanced_result = ConversationResult(
                response_text=self._enhance_response_text(input_data.response_text),
                response_type=input_data.response_type,
                intent=input_data.intent,
                confidence=input_data.confidence,
                context=input_data.context.copy(),
                metadata=input_data.metadata.copy(),
            )

            # Add postprocessing metadata
            enhanced_result.metadata["postprocessing"] = {
                "enhanced": True,
                "processing_timestamp": time.time(),
                "original_length": len(input_data.response_text),
                "enhanced_length": len(enhanced_result.response_text),
            }

            return enhanced_result

        except Exception as e:
            app_logger.error(f"Response postprocessing failed: {e}")
            return input_data  # Return original if postprocessing fails

    def _enhance_response_text(self, response_text: str) -> str:
        """Enhance response text with formatting and improvements"""
        if not response_text:
            return response_text

        enhanced = response_text.strip()

        # Ensure proper punctuation
        if enhanced and not enhanced.endswith((".", "!", "?")):
            enhanced += "."

        # Add friendly closing if response is informational
        if len(enhanced) > 100 and enhanced.lower().startswith(("o kumon", "nossos", "oferecemos")):
            if not any(
                phrase in enhanced.lower()
                for phrase in ["posso ajudar", "mais informações", "dúvida"]
            ):
                enhanced += "\n\nPosso ajudá-lo com mais alguma coisa?"

        return enhanced


class ConversationMemoryNode(
    WorkflowNode[Tuple[ConversationInput, ConversationResult], Dict[str, Any]]
):
    """Node for storing conversation in memory"""

    def __init__(self):
        super().__init__(
            node_id="conversation_memory",
            name="Conversation Memory",
            description="Store conversation in memory service",
            timeout=10.0,
        )

    async def execute(
        self, input_data: Tuple[ConversationInput, ConversationResult], context: WorkflowContext
    ) -> Dict[str, Any]:
        """Store conversation in memory"""
        conversation_input, conversation_result = input_data

        try:
            # Get memory service
            from ..services.conversation_memory_service import (
                conversation_memory_service,
            )

            conversation_key = (
                f"{conversation_input.user_id}_{conversation_input.unit_id or 'default'}"
            )

            # Store user message
            await conversation_memory_service.add_message(
                conversation_key=conversation_key,
                role="user",
                content=conversation_input.message_text,
                metadata={
                    "phone_number": conversation_input.phone_number,
                    "message_type": conversation_input.message_type,
                    "timestamp": time.time(),
                },
            )

            # Store assistant response
            await conversation_memory_service.add_message(
                conversation_key=conversation_key,
                role="assistant",
                content=conversation_result.response_text,
                metadata={
                    "intent": conversation_result.intent,
                    "confidence": conversation_result.confidence,
                    "response_type": conversation_result.response_type,
                    "timestamp": time.time(),
                },
            )

            return {"stored": True, "conversation_key": conversation_key, "messages_stored": 2}

        except Exception as e:
            app_logger.warning(f"Failed to store conversation in memory: {e}")
            return {"stored": False, "error": str(e)}


# Conversation Workflow Patterns


def create_basic_conversation_pattern() -> WorkflowPattern:
    """Create basic conversation processing workflow pattern"""
    pattern = WorkflowPattern(
        pattern_id="basic_conversation",
        name="Basic Conversation Processing",
        description="Standard workflow for processing WhatsApp messages",
    )

    # Add nodes
    pattern.add_node(MessagePreprocessingNode())
    pattern.add_node(IntentClassificationNode(), dependencies=["message_preprocessing"])
    pattern.add_node(ContextRetrievalNode(), dependencies=["message_preprocessing"])
    pattern.add_node(
        ResponseGenerationNode(), dependencies=["intent_classification", "context_retrieval"]
    )
    pattern.add_node(ResponsePostprocessingNode(), dependencies=["response_generation"])
    pattern.add_node(ConversationMemoryNode(), dependencies=["response_postprocessing"])

    return pattern


def create_high_priority_conversation_pattern() -> WorkflowPattern:
    """Create high-priority conversation pattern with parallel processing"""
    pattern = WorkflowPattern(
        pattern_id="high_priority_conversation",
        name="High Priority Conversation Processing",
        description="Optimized workflow for urgent conversations with parallel processing",
    )

    # Add nodes with parallel processing
    pattern.add_node(MessagePreprocessingNode())

    # Parallel intent classification and context retrieval
    intent_node = IntentClassificationNode()
    context_node = ContextRetrievalNode()
    pattern.add_node(intent_node, dependencies=["message_preprocessing"])
    pattern.add_node(context_node, dependencies=["message_preprocessing"])

    pattern.add_node(
        ResponseGenerationNode(), dependencies=["intent_classification", "context_retrieval"]
    )

    # Parallel postprocessing and memory storage
    postprocess_node = ResponsePostprocessingNode()
    memory_node = ConversationMemoryNode()
    pattern.add_node(postprocess_node, dependencies=["response_generation"])
    pattern.add_node(memory_node, dependencies=["response_generation"])

    return pattern


def create_fallback_conversation_pattern() -> WorkflowPattern:
    """Create fallback conversation pattern for when services are unavailable"""
    pattern = WorkflowPattern(
        pattern_id="fallback_conversation",
        name="Fallback Conversation Processing",
        description="Minimal workflow when core services are unavailable",
    )

    # Simple pattern with basic nodes only
    pattern.add_node(MessagePreprocessingNode())

    # Conditional response based on service availability
    async def service_available_condition(input_data, context):
        from ..core import dependencies

        return dependencies.llm_service is not None

    # Simple fallback response node
    class FallbackResponseNode(WorkflowNode[ConversationInput, ConversationResult]):
        def __init__(self):
            super().__init__(
                node_id="fallback_response",
                name="Fallback Response",
                description="Generate simple fallback response",
            )

        async def execute(
            self, input_data: ConversationInput, context: WorkflowContext
        ) -> ConversationResult:
            return ConversationResult(
                response_text="Olá! Obrigada por entrar em contato. Estou passando por uma manutenção no momento. Tente novamente em alguns minutos ou entre em contato diretamente com nossa unidade.",
                response_type="text",
                intent="fallback",
                confidence=1.0,
                metadata={"fallback": True},
            )

    # Full response generation or fallback
    full_response_node = ResponseGenerationNode()
    fallback_response_node = FallbackResponseNode()

    conditional_node = ConditionalNode(
        node_id="response_choice",
        name="Response Choice",
        condition_func=service_available_condition,
        true_node=full_response_node,
        false_node=fallback_response_node,
    )

    pattern.add_node(conditional_node, dependencies=["message_preprocessing"])

    return pattern
