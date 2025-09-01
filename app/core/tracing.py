"""
LangSmith tracing configuration for Kumon Assistant
"""
import os
import logging
from typing import Any, Dict, Optional
from langsmith import Client
from langsmith.run_helpers import traceable
from langchain.callbacks.base import BaseCallbackHandler

from .config import settings

# Initialize LangSmith client
langsmith_client = Client() if settings.LANGSMITH_API_KEY else None

def setup_tracing() -> None:
    """Configure LangSmith tracing for the application"""
    if not settings.LANGSMITH_API_KEY:
        logging.warning("LANGSMITH_API_KEY not set. Tracing disabled.")
        return
    
    # Set environment variables for LangChain tracing
    os.environ["LANGCHAIN_TRACING_V2"] = str(settings.LANGCHAIN_TRACING_V2)
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    
    logging.info(f"LangSmith tracing enabled for project: {settings.LANGSMITH_PROJECT}")

class KumonTracingCallback(BaseCallbackHandler):
    """Custom callback handler for Kumon-specific tracing"""
    
    def __init__(self):
        super().__init__()
        self.conversation_id: Optional[str] = None
        self.phone_number: Optional[str] = None
    
    def set_conversation_context(self, conversation_id: str, phone_number: str):
        """Set conversation context for tracing"""
        self.conversation_id = conversation_id
        self.phone_number = phone_number
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: list[str], **kwargs) -> None:
        """Called when LLM starts"""
        metadata = {
            "conversation_id": self.conversation_id,
            "phone_number": self.phone_number,
            "prompt_count": len(prompts)
        }
        logging.info("LLM call started", extra=metadata)
    
    def on_llm_end(self, response, **kwargs) -> None:
        """Called when LLM ends"""
        metadata = {
            "conversation_id": self.conversation_id,
            "phone_number": self.phone_number,
            "response_length": len(str(response))
        }
        logging.info("LLM call completed", extra=metadata)
    
    def on_llm_error(self, error: Exception, **kwargs) -> None:
        """Called when LLM errors"""
        metadata = {
            "conversation_id": self.conversation_id,
            "phone_number": self.phone_number,
            "error": str(error)
        }
        logging.error("LLM call failed", extra=metadata)
    
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        """Called when chain starts"""
        metadata = {
            "conversation_id": self.conversation_id,
            "phone_number": self.phone_number,
            "chain_name": serialized.get("name", "Unknown")
        }
        logging.info("Chain started", extra=metadata)
    
    def on_chain_end(self, outputs: Dict[str, Any], **kwargs) -> None:
        """Called when chain ends"""
        metadata = {
            "conversation_id": self.conversation_id,
            "phone_number": self.phone_number,
            "output_keys": list(outputs.keys()) if outputs else []
        }
        logging.info("Chain completed", extra=metadata)

@traceable(name="kumon_conversation_flow")
def trace_conversation_flow(
    phone_number: str,
    message: str,
    stage: str,
    response: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Trace a complete conversation flow"""
    return {
        "phone_number": phone_number,
        "user_message": message,
        "conversation_stage": stage,
        "bot_response": response,
        "metadata": metadata or {}
    }

@traceable(name="kumon_validation_check")
def trace_validation_check(
    response_candidate: str,
    validation_result: Dict[str, Any],
    attempt_number: int
) -> Dict[str, Any]:
    """Trace response validation attempts"""
    return {
        "response_candidate": response_candidate,
        "is_valid": validation_result.get("is_valid", False),
        "validation_issues": validation_result.get("issues", []),
        "confidence": validation_result.get("confidence", 0.0),
        "attempt_number": attempt_number
    }

# Global callback instance
kumon_callback = KumonTracingCallback()

def get_tracing_callback() -> KumonTracingCallback:
    """Get the global tracing callback instance"""
    return kumon_callback