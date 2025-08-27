"""
LangGraph Workflow Graph for Kumon Assistant

This module constructs the main conversation workflow graph using LangGraph,
integrating all nodes, edges, and state management for the complete conversation flow.
"""

from typing import Any, Dict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from ..core.config import settings
from ..core.logger import app_logger
from .edges import (
    route_from_fallback,
    route_from_greeting,
    route_from_information,
    route_from_scheduling,
    should_end_conversation,
    smart_route_conversation,
)
from .nodes import (
    entry_point_node,
    fallback_node,
    greeting_node,
    information_node,
    scheduling_node,
)
from .states import (
    ConversationState,
    ConversationStep,
    WorkflowStage,
    create_initial_state,
)


class KumonWorkflow:
    """
    Main Kumon Assistant Workflow using LangGraph

    This class encapsulates the complete conversation workflow, providing
    a clean interface for processing user messages and managing conversation state.
    """

    def __init__(self):
        """Initialize the workflow graph and components"""
        self.memory = MemorySaver() if settings.MEMORY_ENABLE_SYSTEM else None
        self.graph = self._build_graph()

        # Configuration
        self.config = {
            "configurable": {"thread_id": "default"}  # Will be overridden per conversation
        }

        app_logger.info("KumonWorkflow initialized successfully")

    def _build_graph(self) -> StateGraph:
        """
        Build the complete LangGraph workflow

        Returns:
            StateGraph: Configured workflow graph ready for execution
        """
        app_logger.info("Building LangGraph workflow...")

        # Create the state graph
        workflow = StateGraph(ConversationState)

        # Add nodes
        workflow.add_node("entry_point", entry_point_node)
        workflow.add_node("greeting", greeting_node)
        workflow.add_node("information", information_node)
        workflow.add_node("scheduling", scheduling_node)
        workflow.add_node("fallback", fallback_node)
        workflow.add_node("human_handoff", self._human_handoff_node)
        workflow.add_node("completed", self._completion_node)

        # Set entry point to the new intelligent router
        workflow.set_entry_point("entry_point")

        # Add the primary routing edge from the entry point
        workflow.add_conditional_edges(
            "entry_point",
            smart_route_conversation,
            {
                "information": "information",
                "scheduling": "scheduling",
                "fallback": "fallback",
                "greeting": "greeting",
                "completed": "completed",
                "human_handoff": "human_handoff",
            },
        )

        # Phase 4: Add smart routing as primary routing mechanism
        workflow.add_conditional_edges(
            "greeting",
            smart_route_conversation,
            {
                "information": "information",
                "scheduling": "scheduling",
                "fallback": "fallback",
                "greeting": "greeting",  # Stay in greeting
                "completed": "completed",
                "human_handoff": "human_handoff",
            },
        )

        # Add conditional edges from information with smart routing
        workflow.add_conditional_edges(
            "information",
            smart_route_conversation,
            {
                "scheduling": "scheduling",
                "information": "information",  # Stay in information
                "greeting": "greeting",  # Back to greeting
                "fallback": "fallback",
                "completed": "completed",
                "human_handoff": "human_handoff",
            },
        )

        # Add conditional edges from scheduling with smart routing
        workflow.add_conditional_edges(
            "scheduling",
            smart_route_conversation,
            {
                "completed": "completed",
                "fallback": "fallback",
                "scheduling": "scheduling",  # Stay in scheduling
                "information": "information",
                "human_handoff": "human_handoff",
            },
        )

        # Add conditional edges from fallback with smart routing
        workflow.add_conditional_edges(
            "fallback",
            smart_route_conversation,
            {
                "greeting": "greeting",
                "information": "information",
                "scheduling": "scheduling",
                "human_handoff": "human_handoff",
                "completed": "completed",
                "fallback": "fallback",  # Stay in fallback
            },
        )

        # Terminal nodes
        workflow.add_edge("human_handoff", END)
        workflow.add_edge("completed", END)

        app_logger.info("LangGraph workflow built successfully")
        return workflow.compile(checkpointer=self.memory)

    async def _human_handoff_node(self, state: ConversationState) -> ConversationState:
        """
        Handle human handoff scenarios

        Args:
            state: Current conversation state

        Returns:
            ConversationState: Updated state for human handoff
        """
        app_logger.info(f"Human handoff initiated for {state['phone_number']}")

        # Use LangSmith prompt for consistent handoff message
        try:
            from ..prompts.manager import prompt_manager

            response = await prompt_manager.get_prompt("kumon:fallback:handoff:explicit_request")
        except Exception as e:
            app_logger.error(f"Failed to get handoff prompt: {e}")
            response = """Vou conectá-lo com nossa equipe para um atendimento personalizado! 👥

📞 **Entre em contato:**
• WhatsApp: **(51) 99692-1999**
• Horário: Segunda a Sexta, 8h às 18h

Nossa equipe terá todo prazer em ajudá-lo! 😊"""

        return {
            **state,
            "ai_response": response,
            "requires_human": True,
            "conversation_ended": True,
            "stage": WorkflowStage.COMPLETED,
            "step": ConversationStep.CONVERSATION_ENDED,
            "validation_passed": True,
            "prompt_used": "kumon:fallback:handoff:explicit_request",
        }

    async def _completion_node(self, state: ConversationState) -> ConversationState:
        """
        Handle conversation completion

        Args:
            state: Current conversation state

        Returns:
            ConversationState: Final state for completed conversation
        """
        app_logger.info(f"Conversation completed for {state['phone_number']}")

        # Log completion metrics
        metrics = state["metrics"]
        app_logger.info(
            f"Conversation metrics for {state['phone_number']}: "
            f"messages={metrics.message_count}, "
            f"clarifications={metrics.clarification_attempts}, "
            f"confusions={metrics.consecutive_confusion}"
        )

        return {
            **state,
            "conversation_ended": True,
            "stage": WorkflowStage.COMPLETED,
            "step": ConversationStep.CONVERSATION_ENDED,
        }

    async def process_message(
        self, phone_number: str, user_message: str, existing_state: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Process a user message through the workflow

        Args:
            phone_number: User's phone number identifier
            user_message: User's input message
            existing_state: Optional existing conversation state

        Returns:
            Dict containing the response and updated state
        """
        try:
            app_logger.info(f"Processing message from {phone_number}: {user_message[:50]}...")

            # Create or update conversation state
            if existing_state:
                # Update existing state with new message
                state = {
                    **existing_state,
                    "user_message": user_message,
                    "retry_count": 0,
                    "last_error": None,
                }

                # Add message to history
                state["messages"].append(
                    {
                        "role": "user",
                        "content": user_message,
                        "timestamp": state["metrics"].last_activity.isoformat(),
                    }
                )

            else:
                # Create initial state for new conversation
                state = create_initial_state(phone_number, user_message)

            # Set thread ID for this conversation
            config = {**self.config, "configurable": {"thread_id": phone_number}}

            # Process through workflow
            result = await self.graph.ainvoke(state, config)

            # Add AI response to message history
            if result.get("ai_response"):
                result["messages"].append(
                    {
                        "role": "assistant",
                        "content": result["ai_response"],
                        "timestamp": result["metrics"].last_activity.isoformat(),
                    }
                )

            app_logger.info(
                f"Message processed for {phone_number}. "
                f"Stage: {result['stage'].value}, "
                f"Response: {result.get('ai_response', 'No response')[:50]}..."
            )

            return {
                "response": result.get("ai_response", "Desculpe, tive um problema técnico."),
                "state": result,
                "requires_human": result.get("requires_human", False),
                "conversation_ended": result.get("conversation_ended", False),
                "validation_passed": result.get("validation_passed", False),
            }

        except Exception as e:
            app_logger.error(f"Error processing message for {phone_number}: {e}")

            # Return error response with fallback
            return {
                "response": "Desculpe, tive um problema técnico. Vou conectá-lo com nossa equipe! 📞 WhatsApp: (51) 99692-1999",
                "state": (
                    state
                    if "state" in locals()
                    else create_initial_state(phone_number, user_message)
                ),
                "requires_human": True,
                "conversation_ended": True,
                "validation_passed": False,
                "error": str(e),
            }

    async def get_workflow_status(self) -> Dict[str, Any]:
        """
        Get current workflow status and statistics

        Returns:
            Dict containing workflow statistics and health info
        """
        try:
            from ..prompts.manager import prompt_manager

            prompt_stats = await prompt_manager.get_prompt_stats()

            return {
                "workflow_ready": True,
                "langsmith_integration": prompt_stats["langsmith_enabled"],
                "memory_enabled": self.memory is not None,
                "cached_prompts": prompt_stats["cached_prompts"],
                "fallback_templates": prompt_stats["fallback_templates"],
                "graph_compiled": self.graph is not None,
            }

        except Exception as e:
            app_logger.error(f"Error getting workflow status: {e}")
            return {"workflow_ready": False, "error": str(e)}


# Global workflow instance
kumon_workflow = KumonWorkflow()


async def create_conversation_graph() -> StateGraph:
    """
    Legacy function for backward compatibility

    Returns:
        StateGraph: The main workflow graph
    """
    return kumon_workflow.graph


# Convenience function for direct message processing
async def process_conversation_message(
    phone_number: str, user_message: str, existing_state: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Process a conversation message directly

    Args:
        phone_number: User's phone number
        user_message: User's message
        existing_state: Optional existing state

    Returns:
        Processing result with response and updated state
    """
    return await kumon_workflow.process_message(phone_number, user_message, existing_state)
