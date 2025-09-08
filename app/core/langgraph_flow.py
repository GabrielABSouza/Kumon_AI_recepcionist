"""
Minimal LangGraph flow: Entry → [Single Node] → End
Each node handles its intent and sends a response.
"""
import os
from typing import Any, Dict

import openai
from langgraph.graph import END, StateGraph

from app.core.dedup import turn_controller
from app.core.delivery import send_text
from app.core.gemini_classifier import Intent, classifier
from app.prompts.node_prompts import (
    get_fallback_prompt,
    get_greeting_prompt,
    get_information_prompt,
    get_qualification_prompt,
    get_scheduling_prompt,
)

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")


def classify_intent(state: Dict[str, Any]) -> str:
    """Classify user intent and route to appropriate node."""
    text = state.get("text", "")
    intent, confidence = classifier.classify(text)

    # Log classification
    print(
        f"PIPELINE|classify_complete|intent={intent.value}|confidence={confidence:.2f}"
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
        return {"sent": False}

    # Check if already replied
    if turn_controller.has_replied(message_id):
        print(f"PIPELINE|node_skip|name={node_name}|already_replied=true")
        return {"sent": False}

    print(f"PIPELINE|node_start|name={node_name}")

    try:
        # Get prompt for this node
        user_text = state.get("text", "")
        prompt = prompt_func(user_text)

        # Generate response with OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ],
            max_tokens=300,
            temperature=0.7,
        )

        reply_text = response.choices[0].message.content.strip()

        # Send via Evolution API
        phone = state.get("phone")
        if not phone:
            print(f"PIPELINE|node_error|name={node_name}|error=no_phone")
            return {"sent": False}

        instance = state.get("instance", "recepcionistakumon")

        success = send_text(phone, reply_text, instance)

        if success:
            # Mark as replied
            turn_controller.mark_replied(message_id)
            print(f"PIPELINE|node_sent|name={node_name}|chars={len(reply_text)}")

        return {"sent": success, "response": reply_text}

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
            send_text(phone, fallback_text, instance)
            if message_id:  # Only mark replied if we have message_id
                turn_controller.mark_replied(message_id)

        return {"sent": True, "response": fallback_text}


def build_graph():
    """Build the minimal LangGraph flow."""
    # Create state graph
    graph = StateGraph(dict)

    # Add nodes
    graph.add_node("greeting_node", greeting_node)
    graph.add_node("qualification_node", qualification_node)
    graph.add_node("information_node", information_node)
    graph.add_node("scheduling_node", scheduling_node)
    graph.add_node("fallback_node", fallback_node)

    # Set conditional entry point based on classification
    graph.add_conditional_edges(
        "__start__",
        classify_intent,
        {
            "greeting_node": "greeting_node",
            "qualification_node": "qualification_node",
            "information_node": "information_node",
            "scheduling_node": "scheduling_node",
            "fallback_node": "fallback_node",
        },
    )

    # All nodes go to END
    graph.add_edge("greeting_node", END)
    graph.add_edge("qualification_node", END)
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
        print(f"PIPELINE|flow_complete|sent={result.get('sent', False)}")
        return result
    except Exception as e:
        print(f"PIPELINE|flow_error|error={str(e)}")
        return {"sent": False, "error": str(e)}
