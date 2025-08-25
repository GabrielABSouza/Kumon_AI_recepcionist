"""
LangGraph LLM Adapter
Provides seamless integration between Production LLM Service and LangGraph workflows
Maintains backward compatibility while adding failover and cost monitoring
"""

import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional

# CRITICAL FIX: Remove import-time dependency injection - use lazy resolution instead
from langchain.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain.llms.base import BaseLLM
from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.messages import BaseMessage as CoreBaseMessage

from ..core.logger import app_logger


def _get_production_llm_service():
    """
    CRITICAL FIX: Lazy dependency resolution for production LLM service
    
    This prevents import-time circular dependencies by resolving the service
    at runtime through multiple fallback strategies.
    """
    try:
        # Strategy 1: Try optimized startup manager first (primary)
        from ..core.optimized_startup import optimized_startup_manager
        service = optimized_startup_manager.service_instances.get("llm_service")
        if service:
            app_logger.debug("LLM service resolved from optimized startup manager")
            return service
            
        # Strategy 2: Fallback to dependencies module
        from ..core import dependencies
        service = dependencies.llm_service
        if service:
            app_logger.debug("LLM service resolved from dependencies module")
            return service
            
        # Strategy 3: Manual service creation as last resort
        app_logger.warning("Creating emergency LLM service instance - startup may have failed")
        from ..services.production_llm_service import ProductionLLMService
        emergency_service = ProductionLLMService()
        
        # Try to initialize it synchronously (best effort)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                loop.run_until_complete(emergency_service.initialize())
                app_logger.info("Emergency LLM service initialized successfully")
                return emergency_service
            else:
                app_logger.warning("Cannot initialize emergency service in async context")
                return emergency_service  # Return uninitialized service
        except Exception as init_error:
            app_logger.error(f"Emergency LLM service initialization failed: {init_error}")
            return emergency_service  # Return uninitialized service anyway
            
    except Exception as e:
        app_logger.error(f"All LLM service resolution strategies failed: {e}")
        return None


class LangGraphLLMAdapter:
    """
    Adapter to integrate Production LLM Service with LangGraph workflows

    This adapter:
    1. Converts LangChain message formats to our LLM service format
    2. Provides backward compatibility with existing workflow nodes
    3. Adds cost monitoring and failover capabilities
    4. Maintains the same interface as ChatOpenAI for easy replacement
    """

    def __init__(
        self, model: str = "gpt-4-turbo", temperature: float = 0.3, max_tokens: int = 500, **kwargs
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.kwargs = kwargs

        app_logger.info(
            "LangGraph LLM Adapter initialized",
            extra={"model": model, "temperature": temperature, "max_tokens": max_tokens},
        )

    def _convert_langchain_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """Convert LangChain messages to our service format"""
        converted = []

        for message in messages:
            if isinstance(message, SystemMessage):
                role = "system"
                content = message.content
            elif isinstance(message, HumanMessage):
                role = "user"
                content = message.content
            elif isinstance(message, AIMessage):
                role = "assistant"
                content = message.content
            else:
                # Generic handling for other message types
                role = getattr(message, "role", "user")
                content = str(message.content) if hasattr(message, "content") else str(message)

            converted.append({"role": role, "content": content})

        return converted

    def _extract_system_and_user_messages(self, messages: List[Dict[str, str]]) -> tuple:
        """Extract system prompt and user message from message list"""
        system_prompt = ""
        conversation_history = []
        current_user_message = ""

        for message in messages:
            if message["role"] == "system":
                system_prompt = message["content"]
            elif message["role"] == "user":
                current_user_message = message["content"]
            elif message["role"] == "assistant":
                conversation_history.append(message)

        # Add previous user messages to history if any
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        if len(user_messages) > 1:
            # Add previous user messages to conversation history
            for user_msg in user_messages[:-1]:
                conversation_history.append(user_msg)

        return system_prompt, current_user_message, conversation_history

    async def ainvoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:
        """Async invoke - compatible with LangChain's async pattern"""

        # Convert messages
        converted_messages = self._convert_langchain_messages(messages)
        system_prompt, user_message, conversation_history = self._extract_system_and_user_messages(
            converted_messages
        )

        # Use default prompts if system prompt is empty
        if not system_prompt.strip():
            system_prompt = """Você é Cecília, assistente virtual da unidade Kumon Vila A em Porto Alegre.
Suas características:
- Comunicação profissional, acolhedora e em português brasileiro
- Especialista em metodologia Kumon (matemática e português)
- Focada em agendamento de visitas e qualificação de leads
- Preços: R$ 375,00 por matéria + R$ 100,00 taxa de matrícula
- Atendimento: Segunda a sexta, 9h às 12h e 14h às 17h
- Contato para casos complexos: (51) 99692-1999"""

        # CRITICAL FIX: Use lazy dependency resolution
        production_llm_service = _get_production_llm_service()
        if not production_llm_service:
            app_logger.error("Production LLM service not available - returning emergency response")
            return AIMessage(content="Desculpe, houve um problema técnico. Para atendimento imediato, entre em contato: (51) 99692-1999")

        # Generate response using production service with standardized interface
        response_text = ""

        try:
            async for chunk in production_llm_service.generate_streamed_response_legacy(
                user_message=user_message,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
            ):
                response_text += chunk

        except Exception as e:
            app_logger.error(f"LangGraph LLM Adapter error: {e}")
            response_text = "Desculpe, houve um problema técnico. Para atendimento imediato, entre em contato: (51) 99692-1999"

        return AIMessage(content=response_text)

    async def astream(self, messages: List[BaseMessage], **kwargs) -> AsyncIterator[str]:
        """Async streaming - for streaming responses"""

        # Convert messages
        converted_messages = self._convert_langchain_messages(messages)
        system_prompt, user_message, conversation_history = self._extract_system_and_user_messages(
            converted_messages
        )

        # Use default prompts if system prompt is empty
        if not system_prompt.strip():
            system_prompt = """Você é Cecília, assistente virtual da unidade Kumon Vila A em Porto Alegre.
Suas características:
- Comunicação profissional, acolhedora e em português brasileiro
- Especialista em metodologia Kumon (matemática e português)
- Focada em agendamento de visitas e qualificação de leads
- Preços: R$ 375,00 por matéria + R$ 100,00 taxa de matrícula
- Atendimento: Segunda a sexta, 9h às 12h e 14h às 17h
- Contato para casos complexos: (51) 99692-1999"""

        # CRITICAL FIX: Use lazy dependency resolution
        production_llm_service = _get_production_llm_service()
        if not production_llm_service:
            app_logger.error("Production LLM service not available - returning emergency response")
            yield "Desculpe, houve um problema técnico. Para atendimento imediato, entre em contato: (51) 99692-1999"
            return

        # Stream response using production service
        try:
            async for chunk in production_llm_service.generate_streamed_response_legacy(
                user_message=user_message,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
            ):
                yield chunk

        except Exception as e:
            app_logger.error(f"LangGraph LLM Adapter streaming error: {e}")
            yield "Desculpe, houve um problema técnico. Para atendimento imediato, entre em contato: (51) 99692-1999"

    # Synchronous methods for backward compatibility
    def invoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:
        """Synchronous invoke - runs async method in event loop"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.ainvoke(messages, **kwargs))
        except RuntimeError:
            # If no event loop, create new one
            return asyncio.run(self.ainvoke(messages, **kwargs))

    # Compatibility properties and methods
    @property
    def _llm_type(self) -> str:
        """Return LLM type for compatibility"""
        return "production_llm_service"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Identifying parameters for the LLM"""
        return {"model": self.model, "temperature": self.temperature, "max_tokens": self.max_tokens}


class KumonLLMService:
    """
    Kumon-specific LLM service wrapper
    Provides business-context-aware responses with integrated cost monitoring
    LangChain Runnable compatible
    """

    def __init__(self):
        self.adapter = LangGraphLLMAdapter()
        self.business_context = {
            "unit_name": "Kumon Vila A",
            "location": "Porto Alegre",
            "phone": "(51) 99692-1999",
            "pricing": {"per_subject": "R$ 375,00", "enrollment_fee": "R$ 100,00"},
            "hours": {"weekdays": "9h às 12h e 14h às 17h", "weekend": "Fechado"},
            "subjects": ["Matemática", "Português"],
        }

    # LangChain Runnable interface compatibility
    async def ainvoke(self, messages, **kwargs) -> AIMessage:
        """LangChain async invoke compatibility - delegates to adapter"""
        return await self.adapter.ainvoke(messages, **kwargs)

    def invoke(self, messages, **kwargs) -> AIMessage:
        """LangChain sync invoke compatibility - delegates to adapter"""
        return self.adapter.invoke(messages, **kwargs)

    async def astream(self, messages, **kwargs) -> AsyncIterator[str]:
        """LangChain async streaming compatibility - delegates to adapter"""
        async for chunk in self.adapter.astream(messages, **kwargs):
            yield chunk

    async def generate_business_response(
        self, user_input: str, conversation_context: Dict[str, Any], workflow_stage: str = "general"
    ) -> str:
        """
        Generate business-context-aware response

        Args:
            user_input: User's message
            conversation_context: Current conversation context
            workflow_stage: Current stage of the workflow (greeting, qualification, etc.)
        """

        # Build system prompt based on workflow stage
        system_prompts = {
            "greeting": """Você é Cecília, assistente virtual da unidade Kumon Vila A em Porto Alegre.
Sua função é dar as boas-vindas e identificar o interesse do usuário (matemática, português, ou informações gerais).
Seja acolhedora, profissional e direta. Colete o nome e o interesse principal.""",
            "qualification": """Você é Cecília, assistente virtual da unidade Kumon Vila A.
Sua função é qualificar leads coletando informações essenciais:
- Nome do responsável, nome do aluno, idade/série
- Telefone e email para contato
- Interesse específico (matemática, português)
- Disponibilidade de horário
Preços: R$ 375,00 por matéria + R$ 100,00 taxa de matrícula.""",
            "scheduling": """Você é Cecília, assistente virtual da unidade Kumon Vila A.
Sua função é agendar visitas presenciais.
Horários disponíveis: Segunda a sexta, 9h às 12h e 14h às 17h.
Seja específica sobre datas e horários. Confirme todos os dados antes de finalizar.""",
            "general": """Você é Cecília, assistente virtual da unidade Kumon Vila A em Porto Alegre.
Responda perguntas sobre metodologia, preços, horários e agende visitas.
Preços: R$ 375,00 por matéria + R$ 100,00 taxa de matrícula.
Atendimento: Segunda a sexta, 9h às 12h e 14h às 17h.
Contato: (51) 99692-1999.""",
        }

        system_prompt = system_prompts.get(workflow_stage, system_prompts["general"])

        # Add business context to system prompt
        enhanced_system_prompt = f"""{system_prompt}

INFORMAÇÕES DA UNIDADE:
- Nome: Kumon Vila A
- Local: Porto Alegre
- Telefone: (51) 99692-1999
- Preços: R$ 375,00 por matéria + R$ 100,00 taxa de matrícula
- Horários: Segunda a sexta, 9h às 12h e 14h às 17h
- Matérias: Matemática e Português

CONTEXTO DA CONVERSA:
{conversation_context}

Seja sempre profissional, acolhedora e focada em agendar visitas presenciais."""

        # Build conversation history
        conversation_history = conversation_context.get("messages", [])

        # CRITICAL FIX: Use lazy dependency resolution
        production_llm_service = _get_production_llm_service()
        if not production_llm_service:
            app_logger.error("Production LLM service not available for business response")
            return f"Desculpe, estou enfrentando dificuldades técnicas. Para atendimento imediato, entre em contato: {self.business_context['phone']}"

        # Generate response
        response = ""
        try:
            async for chunk in production_llm_service.generate_streamed_response_legacy(
                user_message=user_input,
                system_prompt=enhanced_system_prompt,
                conversation_history=conversation_history,
                max_tokens=400,
                temperature=0.7,
                context={
                    "workflow_stage": workflow_stage,
                    "business_context": self.business_context,
                },
            ):
                response += chunk

        except Exception as e:
            app_logger.error(f"Kumon LLM Service error: {e}")
            response = f"Desculpe, estou enfrentando dificuldades técnicas. Para atendimento imediato, entre em contato: {self.business_context['phone']}"

        return response

    async def get_service_health(self) -> Dict[str, Any]:
        """Get health status of the LLM service"""
        # CRITICAL FIX: Use lazy dependency resolution
        production_llm_service = _get_production_llm_service()
        if not production_llm_service:
            return {"status": "unavailable", "error": "Production LLM service not available"}
        
        return await production_llm_service.get_health_status()


# Factory function for secure_conversation_workflow.py compatibility
def create_kumon_llm(
    model: str = "gpt-4-turbo", temperature: float = 0.7, **kwargs
) -> KumonLLMService:
    """
    Factory function to create KumonLLMService instances with proper encapsulation

    Args:
        model: OpenAI model name (default: gpt-4-turbo)
        temperature: Temperature for response generation (default: 0.7)
        **kwargs: Additional LLM parameters (max_tokens, etc.)

    Returns:
        KumonLLMService instance ready for LangChain integration

    Raises:
        ValueError: If invalid parameters provided
        RuntimeError: If service initialization fails
    """
    try:
        # Validate kwargs to prevent runtime errors
        allowed_params = {"max_tokens", "top_p", "frequency_penalty", "presence_penalty", "stop"}
        validated_kwargs = {k: v for k, v in kwargs.items() if k in allowed_params}

        if len(validated_kwargs) < len(kwargs):
            filtered_params = set(kwargs.keys()) - allowed_params
            app_logger.warning(f"Filtered invalid parameters: {filtered_params}")

        # Use proper constructor pattern with validated parameters
        service = KumonLLMService()
        service.adapter = LangGraphLLMAdapter(
            model=model, temperature=temperature, **validated_kwargs
        )

        app_logger.info(
            "KumonLLMService created successfully",
            extra={
                "model": model,
                "temperature": temperature,
                "additional_params": list(validated_kwargs.keys()),
            },
        )

        return service

    except Exception as e:
        app_logger.error(
            "Failed to create KumonLLMService",
            extra={"error": str(e), "model": model, "temperature": temperature},
        )
        raise RuntimeError(f"KumonLLMService initialization failed: {str(e)}") from e


# Global instances removed, will be initialized on startup
