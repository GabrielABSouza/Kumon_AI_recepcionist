"""
Minimal LangGraph flow: Entry → [Single Node] → End
Each node handles its intent and sends a response.
"""
import asyncio
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from app.core.dedup import turn_controller
from app.core.delivery import send_text
from app.core.gemini_classifier import Intent, classifier
from app.core.llm import OpenAIClient
from app.core.state_manager import get_conversation_state, save_conversation_state
from app.prompts.node_prompts import (
    get_fallback_prompt,
    get_greeting_prompt,
    get_information_prompt,
    get_qualification_prompt,
    get_scheduling_prompt,
)

# Initialize OpenAI adapter (lazy initialization)
_openai_client = None


def get_openai_client():
    """Get or create OpenAI client instance."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClient()
    return _openai_client


def classify_intent(state: Dict[str, Any]) -> str:
    """Classify user intent and route to appropriate node with context awareness."""
    text = state.get("text", "")

    # Load saved state to check context
    phone = state.get("phone")
    saved_state = {}
    if phone:
        saved_state = get_conversation_state(phone)

    # Merge saved state for context
    full_state = {**saved_state, **state}
    has_parent_name = bool(full_state.get("parent_name"))

    # Use classifier for base intent
    intent, confidence = classifier.classify(text)

    # Context-aware routing adjustments
    if not has_parent_name:
        # If greeting intent or providing name, route to greeting
        import re

        name_patterns = [
            r"(?:meu nome é|me chamo|sou)\s+(?:o\s+|a\s+)?(\w+)",
            r"^(\w+)(?:\s*,|\s*\.|\s*$)",  # Just a name
        ]
        for pattern in name_patterns:
            if re.search(pattern, text.lower()):
                intent = Intent.GREETING  # Override to process name
                break

        # Initial contact should get name first
        if intent == Intent.GREETING:
            print(
                f"PIPELINE|classify_complete|intent=greeting|"
                f"confidence={confidence:.2f}|reason=need_name"
            )
            return "greeting_node"

    # Log classification
    print(
        f"PIPELINE|classify_complete|intent={intent.value}|"
        f"confidence={confidence:.2f}|has_name={has_parent_name}"
    )

    # Map intent to node name
    node_map = {
        Intent.GREETING: "greeting_node",
        Intent.QUALIFICATION: "qualification_node",
        Intent.INFORMATION: "information_node",
        Intent.SCHEDULING: "scheduling_node",
        Intent.FALLBACK: "fallback_node",
    }

    return node_map.get(intent, "fallback_node")


def greeting_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle greeting intent."""
    return _execute_node(state, "greeting", get_greeting_prompt)


def qualification_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle qualification intent."""
    return _execute_node(state, "qualification", get_qualification_prompt)


def information_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle information intent."""
    return _execute_node(state, "information", get_information_prompt)


def scheduling_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle scheduling intent."""
    return _execute_node(state, "scheduling", get_scheduling_prompt)


def fallback_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle fallback for unrecognized intents."""
    return _execute_node(state, "fallback", get_fallback_prompt)


def _execute_node(state: Dict[str, Any], node_name: str, prompt_func) -> Dict[str, Any]:
    """Execute a single node: generate response and send."""
    message_id = state.get("message_id")
    if not message_id:
        print(f"PIPELINE|node_error|name={node_name}|error=no_message_id")
        return {"sent": "false"}

    # Check if already replied
    if turn_controller.has_replied(message_id):
        print(f"PIPELINE|node_skip|name={node_name}|already_replied=true")
        return {"sent": "false"}

    print(f"PIPELINE|node_start|name={node_name}")

    # Load saved state
    phone = state.get("phone")
    if phone:
        saved_state = get_conversation_state(phone)
        if saved_state:
            # Merge saved state with current state (current state takes precedence)
            state = {**saved_state, **state}
            print(
                f"STATE|loaded|phone={phone[-4:]}|parent_name={state.get('parent_name')}"
            )

    try:
        # Get prompt for this node - pass full state for context
        user_text = state.get("text", "")

        # Enrich prompt with context if we have parent_name
        if state.get("parent_name") and node_name != "greeting":
            user_text = f"[Contexto: O nome do responsável é {state['parent_name']}] {user_text}"

        prompt = prompt_func(user_text)

        # Generate response with OpenAI adapter (async to sync bridge)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            reply_text = loop.run_until_complete(
                get_openai_client().chat(
                    model="gpt-3.5-turbo",
                    system_prompt=prompt["system"],
                    user_prompt=prompt["user"],
                    temperature=0.7,
                    max_tokens=300,
                )
            )
        finally:
            loop.close()

        # Send via Evolution API
        phone = state.get("phone")
        if not phone:
            print(f"PIPELINE|node_error|name={node_name}|error=no_phone")
            return {"sent": "false"}

        instance = state.get("instance", "recepcionistakumon")

        delivery_result = send_text(phone, reply_text, instance)
        sent_success = delivery_result.get("sent") == "true"

        if sent_success:
            # Mark as replied
            turn_controller.mark_replied(message_id)
            print(f"PIPELINE|node_sent|name={node_name}|chars={len(reply_text)}")

            # Extract entities from user message and save state
            import re

            user_text_lower = state.get("text", "").lower()

            # Extract parent name if present
            name_patterns = [
                r"(?:meu nome é|me chamo|sou)\s+(?:o\s+|a\s+)?(\w+)",
                r"(?:é\s+)?(\w+)(?:\s*,|\s*\.|\s*$)",  # Just the name as answer
            ]

            for pattern in name_patterns:
                match = re.search(pattern, user_text_lower)
                if match and node_name in ["greeting", "qualification"]:
                    extracted_name = match.group(1).title()
                    if len(extracted_name) > 2:  # Basic validation
                        state["parent_name"] = extracted_name
                        print(f"STATE|extracted|parent_name={extracted_name}")
                        break

            # Save updated state
            if phone:
                save_conversation_state(phone, state)

        return {
            "sent": delivery_result.get("sent", "false"),
            "response": reply_text,
            "error_reason": delivery_result.get("error_reason"),
        }

    except Exception as e:
        print(f"PIPELINE|node_error|name={node_name}|error={str(e)}")

        # Send fallback message
        fallback_text = (
            "Desculpe, estou com dificuldades técnicas. "
            "Por favor, entre em contato pelo telefone (11) 4745-2006."
        )
        phone = state.get("phone")
        if phone:  # Only send if we have a phone number
            instance = state.get("instance", "recepcionistakumon")
            delivery_result = send_text(phone, fallback_text, instance)
            if (
                message_id and delivery_result.get("sent") == "true"
            ):  # Only mark replied if we have message_id and sent
                turn_controller.mark_replied(message_id)
            return {
                "sent": delivery_result.get("sent", "false"),
                "response": fallback_text,
                "error_reason": delivery_result.get("error_reason"),
            }

        return {"sent": "false", "response": fallback_text, "error_reason": "no_phone"}


def route_from_greeting(state: Dict[str, Any]) -> str:
    """Determine next node after greeting based on collected data."""
    # Check if we have parent name
    if state.get("parent_name"):
        # If name collected and user expressed interest, go to qualification
        text = state.get("text", "").lower()
        if any(
            word in text
            for word in ["matrícula", "matricular", "filho", "filha", "interesse"]
        ):
            return "qualification_node"
        # Otherwise end for now
        return END
    else:
        # Stay in greeting to collect name
        return "greeting_node"


def route_from_qualification(state: Dict[str, Any]) -> str:
    """Determine next node after qualification based on collected data."""
    # Check if we have required qualification data
    has_child_name = bool(state.get("child_name"))
    has_child_age = bool(state.get("child_age"))
    has_subject = bool(state.get("subject_interest"))

    if has_child_name and has_child_age and has_subject:
        # All data collected, can move to scheduling if requested
        text = state.get("text", "").lower()
        if any(word in text for word in ["agendar", "visitar", "conhecer"]):
            return "scheduling_node"
        return END
    else:
        # Stay in qualification to collect missing data
        return "qualification_node"


def build_graph():
    """Build the minimal LangGraph flow with conditional transitions."""
    # Create state graph
    graph = StateGraph(dict)

    # Add nodes
    graph.add_node("greeting_node", greeting_node)
    graph.add_node("qualification_node", qualification_node)
    graph.add_node("information_node", information_node)
    graph.add_node("scheduling_node", scheduling_node)
    graph.add_node("fallback_node", fallback_node)

    # Set conditional entry point based on classification
    # For langgraph 0.0.26, we need to use set_conditional_entry_point
    graph.set_conditional_entry_point(
        classify_intent,
        {
            "greeting_node": "greeting_node",
            "qualification_node": "qualification_node",
            "information_node": "information_node",
            "scheduling_node": "scheduling_node",
            "fallback_node": "fallback_node",
        },
    )

    # Add conditional transitions
    # Greeting can loop or go to qualification
    graph.add_conditional_edges(
        "greeting_node",
        route_from_greeting,
        {
            "greeting_node": "greeting_node",
            "qualification_node": "qualification_node",
            END: END,
        },
    )

    # Qualification can loop or go to scheduling
    graph.add_conditional_edges(
        "qualification_node",
        route_from_qualification,
        {
            "qualification_node": "qualification_node",
            "scheduling_node": "scheduling_node",
            END: END,
        },
    )

    # Information and scheduling go to END for now
    graph.add_edge("information_node", END)
    graph.add_edge("scheduling_node", END)
    graph.add_edge("fallback_node", END)

    return graph.compile()


# Global compiled graph
workflow = build_graph()


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the workflow with the given state."""
    print(f"PIPELINE|flow_start|message_id={state.get('message_id')}")

    try:
        result = workflow.invoke(state)
        print(f"PIPELINE|flow_complete|sent={result.get('sent', 'false')}")
        return result
    except Exception as e:
        print(f"PIPELINE|flow_error|error={str(e)}")
        return {"sent": "false", "error": str(e)}
