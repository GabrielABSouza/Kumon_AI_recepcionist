"""
LangChain Adapter for ProductionLLMService
Makes ProductionLLMService compatible with LangChain's Runnable interface
"""

from typing import Any, Dict, List, Optional, Union

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseLLM
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import Generation, LLMResult
from langchain_core.runnables import Runnable

from ..core.logger import app_logger


class LangChainProductionLLMAdapter(BaseLLM):
    """
    Adapter that wraps ProductionLLMService to be compatible with 
    LangChain's Runnable interface.

    This allows our existing ProductionLLMService to work seamlessly 
    with LangChain chains while maintaining all existing functionality 
    including failover and cost monitoring.
    """

    def __init__(self, production_llm_service):
        super().__init__()
        self.production_llm_service = production_llm_service
        self._llm_type = "production_llm_service"

    @property
    def _llm_type(self) -> str:
        return "production_llm_service"

    async def _acall(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Async call implementation for LangChain compatibility"""
        try:
            # Convert LangChain messages to our format
            formatted_messages = []

            for msg in messages:
                if isinstance(msg, SystemMessage):
                    formatted_messages.append({
                        "role": "system", 
                        "content": msg.content
                    })
                elif isinstance(msg, HumanMessage):
                    formatted_messages.append({
                        "role": "user", 
                        "content": msg.content
                    })
                else:
                    # Handle other message types as user messages
                    formatted_messages.append({
                        "role": "user", 
                        "content": str(msg.content)
                    })

            # Call our ProductionLLMService
            response = await self.production_llm_service.generate_response(
                messages=formatted_messages, **kwargs
            )

            return response.content

        except Exception as e:
            app_logger.error(f"LangChain adapter error: {e}")
            raise

    def _call(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Synchronous call implementation (not recommended for production)"""
        import asyncio

        try:
            # Run async method in sync context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, can't use run_until_complete
                raise RuntimeError(
                    "Cannot run sync _call in async context. Use async methods."
                )
            else:
                return loop.run_until_complete(
                    self._acall(messages, stop, run_manager, **kwargs)
                )
        except Exception as e:
            app_logger.error(f"LangChain adapter sync call error: {e}")
            raise

    async def _agenerate(
        self,
        messages: List[List[BaseMessage]],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Generate method required by BaseLLM"""
        generations = []

        for message_list in messages:
            try:
                response = await self._acall(message_list, stop, run_manager, **kwargs)
                generations.append([Generation(text=response)])
            except Exception as e:
                app_logger.error(f"Generation error: {e}")
                generations.append([Generation(text="Error processing request")])

        return LLMResult(generations=generations)

    def _generate(
        self,
        messages: List[List[BaseMessage]],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Synchronous generate method"""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                raise RuntimeError(
                    "Cannot run sync _generate in async context. Use async methods."
                )
            else:
                return loop.run_until_complete(
                    self._agenerate(messages, stop, run_manager, **kwargs)
                )
        except Exception as e:
            app_logger.error(f"LangChain adapter sync generate error: {e}")
            raise

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Return identifying parameters"""
        return {
            "llm_type": self._llm_type,
            "production_service": True,
            "has_failover": True,
            "cost_monitoring": True,
        }


class LangChainRunnableAdapter(Runnable):
    """
    Direct Runnable adapter for cases where BaseLLM inheritance isn't needed.
    This provides a lighter-weight integration option.
    """

    def __init__(self, production_llm_service):
        super().__init__()
        self.production_llm_service = production_llm_service

    async def ainvoke(
        self,
        input: Union[str, Dict[str, Any], List[BaseMessage]],
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Async invoke implementation"""
        try:
            # Handle different input types
            if isinstance(input, str):
                # Simple string input
                messages = [{"role": "user", "content": input}]
            elif isinstance(input, dict):
                # Dictionary input (from LangChain chain)
                if "messages" in input:
                    # Handle messages from chain
                    messages = self._convert_langchain_messages(input["messages"])
                elif "question" in input and "context" in input:
                    # Handle Q&A format from retrieval chain
                    system_message = f"Context: {input['context']}"
                    user_message = input["question"]
                    messages = [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message},
                    ]
                else:
                    # Handle other dict formats
                    content = str(input)
                    messages = [{"role": "user", "content": content}]
            elif isinstance(input, list):
                # List of messages
                messages = self._convert_langchain_messages(input)
            else:
                # Fallback - convert to string
                messages = [{"role": "user", "content": str(input)}]

            # Call our ProductionLLMService
            response = await self.production_llm_service.generate_response(
                messages=messages, **kwargs
            )

            return response.content

        except Exception as e:
            app_logger.error(f"LangChain Runnable adapter error: {e}")
            raise

    def invoke(
        self,
        input: Union[str, Dict[str, Any], List[BaseMessage]],
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Synchronous invoke implementation"""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a new task if we're in an async context
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.ainvoke(input, config, **kwargs))
                    return future.result()
            else:
                return loop.run_until_complete(self.ainvoke(input, config, **kwargs))
        except Exception as e:
            app_logger.error(f"LangChain Runnable adapter sync invoke error: {e}")
            raise

    def _convert_langchain_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """Convert LangChain messages to our internal format"""
        formatted_messages = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                formatted_messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                formatted_messages.append({"role": "user", "content": msg.content})
            else:
                # Handle other message types as user messages
                formatted_messages.append({"role": "user", "content": str(msg.content)})

        return formatted_messages

    @property
    def InputType(self) -> type:
        return Union[str, Dict[str, Any], List[BaseMessage]]

    @property
    def OutputType(self) -> type:
        return str


def create_langchain_adapter(production_llm_service, adapter_type: str = "runnable"):
    """
    Factory function to create appropriate LangChain adapter

    Args:
        production_llm_service: Instance of ProductionLLMService
        adapter_type: "runnable" or "llm" - type of adapter to create

    Returns:
        Appropriate adapter instance
    """

    if adapter_type == "llm":
        return LangChainProductionLLMAdapter(production_llm_service)
    elif adapter_type == "runnable":
        return LangChainRunnableAdapter(production_llm_service)
    else:
        raise ValueError(
            f"Unknown adapter type: {adapter_type}. Use 'runnable' or 'llm'"
        )
