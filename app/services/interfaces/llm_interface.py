"""
LLM Service Interface Standardization
Unified interface definitions for all LLM service implementations across the system
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from ...core.logger import app_logger


class LLMInterfaceType(Enum):
    """Types of LLM interfaces supported"""

    STREAMING = "streaming"
    COMPLETE = "complete"
    LANGCHAIN = "langchain"
    LANGGRAPH = "langgraph"


@dataclass
class StandardLLMRequest:
    """Standardized request format for all LLM interfaces"""

    messages: List[Dict[str, str]]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: bool = False
    context: Optional[Dict[str, Any]] = None
    workflow_stage: Optional[str] = None
    interface_type: LLMInterfaceType = LLMInterfaceType.COMPLETE
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class StandardLLMResponse:
    """Standardized response format for all LLM interfaces"""

    content: str
    interface_type: LLMInterfaceType
    model_used: str
    provider: str
    token_usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_langchain_format(self):
        """Convert to LangChain AIMessage format"""
        from langchain.schema import AIMessage

        return AIMessage(content=self.content)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "content": self.content,
            "interface_type": self.interface_type.value,
            "model_used": self.model_used,
            "provider": self.provider,
            "token_usage": self.token_usage,
            "finish_reason": self.finish_reason,
            "metadata": self.metadata,
        }


class StandardLLMInterface(ABC):
    """
    Abstract base class defining the standard interface for all LLM services.
    All LLM service implementations must conform to this interface.
    """

    @abstractmethod
    async def generate_response(self, request: StandardLLMRequest) -> StandardLLMResponse:
        """Generate a complete response (non-streaming)"""
        pass

    @abstractmethod
    async def generate_streamed_response(self, request: StandardLLMRequest) -> AsyncIterator[str]:
        """Generate a streaming response"""
        pass

    @abstractmethod
    async def ainvoke(self, messages: List[Any], **kwargs) -> Any:
        """LangChain/LangGraph compatibility method"""
        pass

    @abstractmethod
    def invoke(self, messages: List[Any], **kwargs) -> Any:
        """Synchronous LangChain compatibility method"""
        pass

    @abstractmethod
    async def astream(self, messages: List[Any], **kwargs) -> AsyncIterator[str]:
        """Async streaming for LangChain/LangGraph"""
        pass

    @abstractmethod
    async def get_health_status(self) -> Dict[str, Any]:
        """Get service health status"""
        pass

    @property
    @abstractmethod
    def interface_type(self) -> LLMInterfaceType:
        """Return the interface type"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name"""
        pass


class LLMInterfaceAdapter:
    """
    Universal adapter for converting between different LLM interface formats.
    Handles conversion between standard format and specific interface requirements.
    """

    @staticmethod
    def to_standard_request(
        messages: Union[List[Dict[str, str]], List[Any], str],
        interface_type: LLMInterfaceType,
        **kwargs,
    ) -> StandardLLMRequest:
        """Convert various input formats to StandardLLMRequest"""

        # Handle string input
        if isinstance(messages, str):
            formatted_messages = [{"role": "user", "content": messages}]

        # Handle LangChain messages
        elif isinstance(messages, list) and messages and hasattr(messages[0], "content"):
            formatted_messages = []
            for msg in messages:
                if hasattr(msg, "content"):
                    role = "user"  # default
                    if hasattr(msg, "__class__"):
                        class_name = msg.__class__.__name__
                        if "System" in class_name:
                            role = "system"
                        elif "Human" in class_name:
                            role = "user"
                        elif "AI" in class_name or "Assistant" in class_name:
                            role = "assistant"

                    formatted_messages.append({"role": role, "content": str(msg.content)})
                else:
                    formatted_messages.append({"role": "user", "content": str(msg)})

        # Handle dict format
        elif isinstance(messages, list) and messages and isinstance(messages[0], dict):
            formatted_messages = messages

        # Handle other formats
        else:
            formatted_messages = [{"role": "user", "content": str(messages)}]

        return StandardLLMRequest(
            messages=formatted_messages,
            max_tokens=kwargs.get("max_tokens"),
            temperature=kwargs.get("temperature"),
            stream=kwargs.get("stream", False),
            context=kwargs.get("context"),
            workflow_stage=kwargs.get("workflow_stage"),
            interface_type=interface_type,
            metadata=kwargs.get("metadata", {}),
        )

    @staticmethod
    def from_standard_response(
        response: StandardLLMResponse, target_interface: LLMInterfaceType
    ) -> Any:
        """Convert StandardLLMResponse to target interface format"""

        if target_interface == LLMInterfaceType.LANGCHAIN:
            return response.to_langchain_format()
        elif target_interface == LLMInterfaceType.LANGGRAPH:
            return response.to_langchain_format()  # LangGraph uses LangChain message format
        else:
            return response.to_dict()


class InterfaceValidationError(Exception):
    """Raised when interface validation fails"""

    pass


class InterfaceValidator:
    """Validates interface implementations against the standard"""

    @staticmethod
    def validate_request(request: StandardLLMRequest) -> bool:
        """Validate that request conforms to standard format"""
        try:
            # Validate required fields
            if not isinstance(request.messages, list):
                raise InterfaceValidationError("messages must be a list")

            if not request.messages:
                raise InterfaceValidationError("messages cannot be empty")

            # Validate message format
            for i, msg in enumerate(request.messages):
                if not isinstance(msg, dict):
                    raise InterfaceValidationError(f"Message {i} must be a dictionary")

                if "role" not in msg or "content" not in msg:
                    raise InterfaceValidationError(
                        f"Message {i} must have 'role' and 'content' fields"
                    )

                if msg["role"] not in ["system", "user", "assistant"]:
                    raise InterfaceValidationError(f"Message {i} has invalid role: {msg['role']}")

            # Validate optional fields
            if request.max_tokens is not None and (
                not isinstance(request.max_tokens, int) or request.max_tokens <= 0
            ):
                raise InterfaceValidationError("max_tokens must be a positive integer")

            if request.temperature is not None and (
                not isinstance(request.temperature, (int, float))
                or not 0 <= request.temperature <= 2
            ):
                raise InterfaceValidationError("temperature must be between 0 and 2")

            return True

        except InterfaceValidationError:
            raise
        except Exception as e:
            raise InterfaceValidationError(f"Request validation error: {str(e)}")

    @staticmethod
    def validate_response(response: StandardLLMResponse) -> bool:
        """Validate that response conforms to standard format"""
        try:
            # Validate required fields
            if not isinstance(response.content, str):
                raise InterfaceValidationError("content must be a string")

            if not isinstance(response.interface_type, LLMInterfaceType):
                raise InterfaceValidationError("interface_type must be LLMInterfaceType enum")

            if not isinstance(response.model_used, str) or not response.model_used:
                raise InterfaceValidationError("model_used must be a non-empty string")

            if not isinstance(response.provider, str) or not response.provider:
                raise InterfaceValidationError("provider must be a non-empty string")

            return True

        except InterfaceValidationError:
            raise
        except Exception as e:
            raise InterfaceValidationError(f"Response validation error: {str(e)}")

    @staticmethod
    async def validate_interface_implementation(service: StandardLLMInterface) -> Dict[str, Any]:
        """Validate that a service properly implements the standard interface"""

        validation_results = {
            "interface_compliant": True,
            "errors": [],
            "warnings": [],
            "test_results": {},
        }

        try:
            # Test basic request/response
            test_request = StandardLLMRequest(
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=50,
                temperature=0.7,
                interface_type=service.interface_type,
            )

            # Test generate_response
            try:
                response = await service.generate_response(test_request)
                InterfaceValidator.validate_response(response)
                validation_results["test_results"]["generate_response"] = "PASS"
            except Exception as e:
                validation_results["errors"].append(f"generate_response failed: {str(e)}")
                validation_results["test_results"]["generate_response"] = "FAIL"
                validation_results["interface_compliant"] = False

            # Test health status
            try:
                health = await service.get_health_status()
                if not isinstance(health, dict):
                    raise ValueError("health_status must return dict")
                validation_results["test_results"]["health_status"] = "PASS"
            except Exception as e:
                validation_results["errors"].append(f"get_health_status failed: {str(e)}")
                validation_results["test_results"]["health_status"] = "FAIL"
                validation_results["interface_compliant"] = False

            # Test properties
            try:
                interface_type = service.interface_type
                model_name = service.model_name
                provider_name = service.provider_name

                if not isinstance(interface_type, LLMInterfaceType):
                    raise ValueError("interface_type must be LLMInterfaceType")
                if not isinstance(model_name, str) or not model_name:
                    raise ValueError("model_name must be non-empty string")
                if not isinstance(provider_name, str) or not provider_name:
                    raise ValueError("provider_name must be non-empty string")

                validation_results["test_results"]["properties"] = "PASS"
            except Exception as e:
                validation_results["errors"].append(f"Properties validation failed: {str(e)}")
                validation_results["test_results"]["properties"] = "FAIL"
                validation_results["interface_compliant"] = False

        except Exception as e:
            validation_results["errors"].append(f"Interface validation failed: {str(e)}")
            validation_results["interface_compliant"] = False

        return validation_results


class InterfaceBridge:
    """
    Bridge pattern for seamless integration between different LLM interfaces.
    Provides automatic conversion and compatibility layer.
    """

    def __init__(self, service: StandardLLMInterface):
        self.service = service

    async def bridge_call(
        self,
        method_name: str,
        args: tuple,
        kwargs: dict,
        source_interface: LLMInterfaceType,
        target_interface: LLMInterfaceType,
    ) -> Any:
        """Bridge a call between different interface types"""

        try:
            # Convert arguments to standard format
            if method_name in ["generate_response", "ainvoke", "invoke"]:
                messages = args[0] if args else kwargs.get("messages", [])
                standard_request = LLMInterfaceAdapter.to_standard_request(
                    messages, source_interface, **kwargs
                )

                # Call the standardized method
                if method_name in ["generate_response", "ainvoke", "invoke"]:
                    response = await self.service.generate_response(standard_request)

                    # Convert response to target format
                    return LLMInterfaceAdapter.from_standard_response(response, target_interface)

            elif method_name in ["generate_streamed_response", "astream"]:
                messages = args[0] if args else kwargs.get("messages", [])
                standard_request = LLMInterfaceAdapter.to_standard_request(
                    messages, source_interface, **kwargs
                )
                standard_request.stream = True

                # Return async generator function, not yield directly
                return self.service.generate_streamed_response(standard_request)

            else:
                raise ValueError(f"Unsupported method: {method_name}")

        except Exception as e:
            app_logger.error(f"Interface bridge error: {e}")
            raise


# Utility functions for interface standardization


def create_standard_request(
    user_message: str,
    system_prompt: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    **kwargs,
) -> StandardLLMRequest:
    """Utility function to create a standard request from common parameters"""

    messages = []

    # Add system prompt if provided
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Add conversation history if provided
    if conversation_history:
        messages.extend(conversation_history)

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    return StandardLLMRequest(
        messages=messages,
        max_tokens=kwargs.get("max_tokens"),
        temperature=kwargs.get("temperature"),
        context=kwargs.get("context"),
        workflow_stage=kwargs.get("workflow_stage"),
        interface_type=kwargs.get("interface_type", LLMInterfaceType.COMPLETE),
        metadata=kwargs.get("metadata", {}),
    )


def wrap_legacy_service(legacy_service, interface_type: LLMInterfaceType) -> StandardLLMInterface:
    """Wrap a legacy service to conform to the standard interface"""

    class LegacyServiceWrapper(StandardLLMInterface):
        def __init__(self, service, iface_type):
            self.service = service
            self._interface_type = iface_type

        async def generate_response(self, request: StandardLLMRequest) -> StandardLLMResponse:
            # Implementation depends on legacy service interface
            if hasattr(self.service, "generate_response"):
                response = await self.service.generate_response(
                    request.messages, max_tokens=request.max_tokens, temperature=request.temperature
                )
                return StandardLLMResponse(
                    content=response.content,
                    interface_type=self._interface_type,
                    model_used=getattr(response, "model", "unknown"),
                    provider=getattr(response, "provider", "unknown"),
                    token_usage=getattr(response, "usage", None),
                    finish_reason=getattr(response, "finish_reason", None),
                )
            else:
                raise NotImplementedError("Legacy service doesn't support generate_response")

        async def generate_streamed_response(
            self, request: StandardLLMRequest
        ) -> AsyncIterator[str]:
            if hasattr(self.service, "generate_streamed_response"):
                system_prompt = ""
                user_message = ""
                conversation_history = []

                for msg in request.messages:
                    if msg["role"] == "system":
                        system_prompt = msg["content"]
                    elif msg["role"] == "user":
                        user_message = msg["content"]
                    elif msg["role"] == "assistant":
                        conversation_history.append(msg)

                async for chunk in self.service.generate_streamed_response(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    conversation_history=conversation_history,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                ):
                    yield chunk
            else:
                raise NotImplementedError("Legacy service doesn't support streaming")

        async def ainvoke(self, messages: List[Any], **kwargs) -> Any:
            request = LLMInterfaceAdapter.to_standard_request(
                messages, self._interface_type, **kwargs
            )
            response = await self.generate_response(request)
            return response.to_langchain_format()

        def invoke(self, messages: List[Any], **kwargs) -> Any:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.ainvoke(messages, **kwargs))

        async def astream(self, messages: List[Any], **kwargs) -> AsyncIterator[str]:
            request = LLMInterfaceAdapter.to_standard_request(
                messages, self._interface_type, stream=True, **kwargs
            )
            async for chunk in self.generate_streamed_response(request):
                yield chunk

        async def get_health_status(self) -> Dict[str, Any]:
            if hasattr(self.service, "get_health_status"):
                return await self.service.get_health_status()
            else:
                return {"status": "unknown", "service": "legacy_wrapped"}

        @property
        def interface_type(self) -> LLMInterfaceType:
            return self._interface_type

        @property
        def model_name(self) -> str:
            return getattr(self.service, "model", "unknown")

        @property
        def provider_name(self) -> str:
            return getattr(self.service, "provider_name", "legacy")

    return LegacyServiceWrapper(legacy_service, interface_type)
