"""
Minimal LangGraph flow: Entry → [Single Node] → End
Each node handles its intent and sends a response.
"""
import asyncio
import copy
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from app.core.delivery import send_text
from app.core.gemini_classifier import Intent, classifier
from app.core.llm import OpenAIClient
from app.core.state_manager import (
    get_conversation_history,
    get_conversation_state,
    save_conversation_state,
)
from app.prompts.node_prompts import (
    get_blended_information_prompt,
    get_fallback_prompt,
    get_greeting_prompt,
    get_qualification_prompt,
    get_scheduling_prompt,
)
from app.utils.formatters import safe_phone_display

# Initialize OpenAI adapter (lazy initialization)
_openai_client = None

# Required qualification variables that must be collected
# Variáveis permanentes obrigatórias para qualificação (sem beneficiary_type que é temporária)
QUALIFICATION_REQUIRED_VARS = [
    "parent_name",
    "student_name",
    "student_age",
    "program_interests",
]

# Required scheduling variables that must be collected
SCHEDULING_REQUIRED_VARS = ["availability_preferences"]


def get_openai_client():
    """Get or create OpenAI client instance."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClient()
    return _openai_client


def classify_intent(state: Dict[str, Any]) -> str:
    """
    Business Logic Router: Check conversation state for continuation rules.

    This function implements the "Rules First" principle - it only checks
    business logic for conversation continuation, never does AI classification.

    Returns:
        str: Node name if a business rule applies (e.g., "qualification_node")
        None: If no business rules apply (defer to AI classification)
    """
    try:
        # Load saved state to check business context
        phone = state.get("phone")
        saved_state = {}
        if phone:
            saved_state = get_conversation_state(phone)

        # No saved state = new conversation = no business rules apply
        if not saved_state:
            return None
    except Exception:
        # If business logic fails, return None to defer to AI
        return None

    # Merge saved state for context
    full_state = {**saved_state, **state}
    has_parent_name = bool(full_state.get("parent_name"))

    # BUSINESS RULE 1: Post-greeting continuation
    # If we sent a greeting, the next message should be qualification
    if full_state.get("greeting_sent") and not has_parent_name:
        print(
            f"PIPELINE|classify_complete|intent=qualification|"
            f"confidence=1.0|reason=post_greeting_response"
        )
        return "qualification_node"

    # BUSINESS RULE 2: Qualification continuation
    # If we have partial qualification data, continue collecting
    missing_vars = [
        var
        for var in QUALIFICATION_REQUIRED_VARS
        if var not in saved_state or not saved_state[var]
    ]

    if has_parent_name and missing_vars:
        print(
            f"PIPELINE|classify_complete|intent=qualification|"
            f"confidence=1.0|reason=continue_qualification|missing={len(missing_vars)}"
        )
        return "qualification_node"

    # BUSINESS RULE 3: Qualification complete → Scheduling
    # If all qualification data is complete, proceed to scheduling
    if has_parent_name and not missing_vars:
        print(
            f"PIPELINE|classify_complete|intent=scheduling|"
            f"confidence=1.0|reason=qualification_complete"
        )
        return "scheduling_node"

    # No business rules apply - defer to AI classification
    return None


def master_router(state: Dict[str, Any]) -> str:
    """
    Master Router: Implements "Rules First, AI After" orchestration principle.

    This is the single entry point for all routing decisions. It follows the principle:
    1. Check business rules first (classify_intent)
    2. If no business rules apply, use AI classification (GeminiClassifier)

    This eliminates the responsibility duplication between business logic and AI.

    Returns:
        str: Node name to route to (e.g., "greeting_node", "qualification_node")
    """
    phone = safe_phone_display(state.get("phone"))
    text = state.get("text", "")

    print(f"PIPELINE|master_router_start|phone={phone}|text_len={len(text)}")

    try:
        # STEP 1: Rules First - Check business logic for conversation continuation
        business_decision = classify_intent(state)

        if business_decision is not None:
            # Business rule applied - use it directly
            print(
                f"PIPELINE|master_router_business_rule|decision={business_decision}|phone={phone}"
            )
            return business_decision

        # STEP 2: AI After - No business rules apply, use AI classification
        print(f"PIPELINE|master_router_ai_fallback|phone={phone}|text='{text[:50]}...'")

        # Prepare context for AI classification if available
        conversation_context = None
        try:
            if phone:
                # Collect conversation state
                saved_state = get_conversation_state(phone)
                # Collect conversation history
                conversation_history = get_conversation_history(phone, limit=4)

                if saved_state or conversation_history:
                    # Use new context format: {'state': {...}, 'history': [...]}
                    conversation_context = {
                        "state": saved_state or {},
                        "history": conversation_history,
                    }
        except Exception as context_error:
            print(
                f"PIPELINE|master_router_context_error|error={str(context_error)}|phone={phone}"
            )
            # Continue with empty context

        # Call AI classifier with context
        intent, confidence = classifier.classify(text, context=conversation_context)

        # Map AI intent to node names
        intent_to_node = {
            Intent.GREETING: "greeting_node",
            Intent.QUALIFICATION: "qualification_node",
            Intent.INFORMATION: "information_node",
            Intent.SCHEDULING: "scheduling_node",
            Intent.FALLBACK: "fallback_node",
        }

        ai_decision = intent_to_node.get(intent, "fallback_node")

        print(
            f"PIPELINE|master_router_ai_complete|decision={ai_decision}|intent={intent.value}|confidence={confidence:.2f}|phone={phone}"
        )

        return ai_decision

    except Exception as e:
        # Graceful fallback on any error
        print(f"PIPELINE|master_router_error|error={str(e)}|phone={phone}")
        print(f"PIPELINE|master_router_fallback|decision=fallback_node|phone={phone}")
        return "fallback_node"


def _get_next_qualification_question(state: Dict[str, Any]) -> str:
    """Determine the next qualification question based on missing data."""
    # Check which qualification variables are missing
    missing_vars = []
    for var in QUALIFICATION_REQUIRED_VARS:
        if not state.get(var):
            missing_vars.append(var)

    # If no variables missing, no qualification question needed
    if not missing_vars:
        return ""

    # Get first missing variable and generate appropriate question
    first_missing = missing_vars[0]
    parent_name = state.get("parent_name", "")

    # Personalize with parent name if available
    name_prefix = f"{parent_name}, " if parent_name else ""

    if first_missing == "parent_name":
        return "A propósito, qual é o seu nome?"
    elif first_missing == "student_name":
        return f"A propósito, {name_prefix}qual é o nome da criança para quem será o curso?"
    elif first_missing == "student_age":
        student_name = state.get("student_name", "")
        if student_name:
            return f"A propósito, {name_prefix}qual é a idade do {student_name}?"
        else:
            return f"A propósito, {name_prefix}qual é a idade da criança?"
    elif first_missing == "program_interests":
        return f"A propósito, {name_prefix}você tem interesse em algum programa específico? Matemática, Português ou ambos?"

    # Fallback
    return f"A propósito, {name_prefix}posso coletar mais algumas informações para personalizar nosso atendimento?"


def greeting_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle greeting intent and set flag for next turn routing."""
    result = _execute_node(state, "greeting", get_greeting_prompt)

    # Set flag to indicate greeting was sent (for next turn routing)
    result["greeting_sent"] = True

    return result


def qualification_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle qualification intent with attempt tracking."""
    # CRITICAL: Increment attempt counter here (where state changes are preserved)
    state = copy.deepcopy(state)  # Deep copy to prevent state corruption
    state["qualification_attempts"] = state.get("qualification_attempts", 0) + 1

    print(
        f"QUALIFICATION|node_enter|attempts={state['qualification_attempts']}|phone={safe_phone_display(state.get('phone'))}"
    )

    # LOCAL EXTRACTION: Check if parent_name is missing and extract from user message
    phone = state.get("phone")
    if phone:
        # Load current state from Redis
        saved_state = get_conversation_state(phone)

        # Check if parent_name is missing
        if not saved_state.get("parent_name"):
            user_text = state.get("text", "")
            if user_text:
                # Extract parent_name from user message using regex patterns
                import re

                parent_name_patterns = [
                    r"meu nome é (\w+)",
                    r"me chamo (\w+)",
                    r"sou (\w+)",
                    r"eu sou (\w+)",
                    r"^(?!(?:Olá|olá|Oi|oi|Bom|bom|Boa|boa|Hey|hey|Eai|eai|E aí|e aí)$)(\w+)$",  # Single word response excluding greetings
                ]

                extracted_name = None
                for pattern in parent_name_patterns:
                    match = re.search(pattern, user_text.lower())
                    if match:
                        extracted_name = match.group(1).capitalize()
                        break

                if extracted_name:
                    # Save extracted parent_name to Redis state
                    updated_state = {**saved_state, "parent_name": extracted_name}
                    save_conversation_state(phone, updated_state)
                    print(
                        f"STATE|extracted|phone={safe_phone_display(phone)}|parent_name={extracted_name}"
                    )

    return _execute_node(state, "qualification", get_qualification_prompt)


def information_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle information intent with contextual qualification awareness."""
    return _execute_blended_node(state, "information", get_blended_information_prompt)


def scheduling_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle scheduling intent."""
    return _execute_node(state, "scheduling", get_scheduling_prompt)


def fallback_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle fallback for unrecognized intents."""
    return _execute_node(state, "fallback", get_fallback_prompt)


def _execute_blended_node(
    state: Dict[str, Any], node_name: str, prompt_func
) -> Dict[str, Any]:
    """Execute a blended node that combines informative response with qualification question."""
    message_id = state.get("message_id")
    if not message_id:
        print(f"PIPELINE|node_error|name={node_name}|error=no_message_id")
        return {"sent": "false"}

    # Load conversation state for context
    phone = state.get("phone")
    saved_state = {}
    if phone:
        saved_state = get_conversation_state(phone)

    # Merge state for complete context
    full_state = {**saved_state, **state}

    # Determine next qualification question based on missing variables
    next_qualification_question = _get_next_qualification_question(full_state)

    print(f"PIPELINE|node_start|name={node_name}")

    try:
        # Build blended prompt with information request + next qualification question
        prompt = prompt_func(
            state.get("text", ""), full_state, next_qualification_question
        )

        # Generate response
        client = get_openai_client()
        response_text = client.chat(prompt["system"], prompt["user"])

        # Send message
        result = send_text(
            instance=state.get("instance", ""),
            number=state.get("phone", ""),
            text=response_text,
        )

        # Save updated state (if any new data was collected)
        if phone:
            save_conversation_state(phone, full_state)

        return {
            **state,
            "sent": result.get("sent", "false"),
            "response": response_text,
            "error_reason": result.get("error_reason"),
        }

    except Exception as e:
        print(f"PIPELINE|node_error|name={node_name}|error={str(e)}")
        # Fallback message
        fallback_text = "Desculpe, estou com dificuldades técnicas. Por favor, entre em contato pelo telefone (11) 4745-2006."

        try:
            result = send_text(
                instance=state.get("instance", ""),
                number=state.get("phone", ""),
                text=fallback_text,
            )
            return {
                **state,
                "sent": result.get("sent", "false"),
                "response": fallback_text,
                "error_reason": str(e),
            }
        except Exception as send_error:
            print(f"DELIVERY|error|{send_error}")
            return {
                **state,
                "sent": "false",
                "response": fallback_text,
                "error_reason": f"{str(e)} | {str(send_error)}",
            }


def _execute_node(state: Dict[str, Any], node_name: str, prompt_func) -> Dict[str, Any]:
    """Execute a single node: generate response and send."""
    message_id = state.get("message_id")
    if not message_id:
        print(f"PIPELINE|node_error|name={node_name}|error=no_message_id")
        return {"sent": "false"}

    # REMOVED: turn_controller check moved to webhook level
    # Individual nodes no longer need to check if already replied
    # The webhook entry point handles all deduplication logic

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

        # Pass state to qualification prompt for dynamic prompting with attempt tracking
        if node_name == "qualification":
            # Enhanced qualification with attempt awareness
            qualification_attempts = state.get("qualification_attempts", 0)
            missing_vars = [
                var
                for var in QUALIFICATION_REQUIRED_VARS
                if var not in state or not state[var]
            ]

            print(
                f"QUALIFICATION|node_exec|attempts={qualification_attempts}|missing={len(missing_vars)}"
            )
            prompt = prompt_func(
                user_text, redis_state=state, attempts=qualification_attempts
            )
        else:
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
            # REMOVED: mark_replied moved to workflow level (not per node)
            # Only the final workflow completion should mark as replied
            print(f"PIPELINE|node_sent|name={node_name}|chars={len(reply_text)}")

            # REMOVED: Global entity extraction logic moved to qualification_node
            # Entity extraction should be contextual and localized to specific nodes
            # that need specific information, not a global process that runs for all messages

            # REMOVED: All global entity extraction logic moved to qualification_node
            # Each node should handle its own specific extraction needs locally

            # Save updated state
            if phone:
                save_conversation_state(phone, state)

        # CRITICAL FIX: Return the complete state with metadata
        # This ensures state propagation between nodes in LangGraph
        # USE THE MODIFIED STATE (not original) to preserve qualification_attempts increment
        result_state = copy.deepcopy(
            state
        )  # Deep copy the MODIFIED state (with incremented attempts)
        result_state.update(
            {
                "sent": delivery_result.get("sent", "false"),
                "response": reply_text,
                "error_reason": delivery_result.get("error_reason"),
            }
        )
        return result_state

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
            # REMOVED: mark_replied logic moved to workflow level
            # Error handling no longer marks individual nodes as replied
            # CRITICAL FIX: Return complete state even in error cases
            # USE THE MODIFIED STATE to preserve qualification_attempts increment
            result_state = copy.deepcopy(
                state
            )  # Deep copy modified state with incremented attempts
            result_state.update(
                {
                    "sent": delivery_result.get("sent", "false"),
                    "response": fallback_text,
                    "error_reason": delivery_result.get("error_reason"),
                }
            )
            return result_state

        # CRITICAL FIX: Return complete state even when no phone
        # USE THE MODIFIED STATE to preserve qualification_attempts increment
        result_state = copy.deepcopy(
            state
        )  # Deep copy modified state with incremented attempts
        result_state.update(
            {"sent": "false", "response": fallback_text, "error_reason": "no_phone"}
        )
        return result_state


def route_from_greeting(state: Dict[str, Any]) -> str:
    """
    Greeting always ends the current turn to wait for user response.
    The next turn will be routed by Gemini classifier based on context.
    """
    # End the current turn after greeting (turn-based conversation)
    return END


def route_from_qualification(state: Dict[str, Any]) -> str:
    """
    Decide para onde ir após o nó de qualificação.
    Implementa state machine com proteção contra loops infinitos.
    """
    # Read current attempt count (updated by qualification_node)
    qualification_attempts = state.get("qualification_attempts", 0)

    print(
        f"QUALIFICATION|route_check|attempts={qualification_attempts}|phone={safe_phone_display(state.get('phone'))}"
    )

    # Check if all required variables are collected
    missing_vars = []
    for var in QUALIFICATION_REQUIRED_VARS:
        if var not in state or not state[var]:
            missing_vars.append(var)

    if not missing_vars:
        # All data collected - proceed to scheduling
        print(f"QUALIFICATION|complete|all_data_collected|next=scheduling")
        return "scheduling_node"

    # INFINITE LOOP PREVENTION: After 4 failed attempts, route to information_node
    # This provides escape hatch and allows user to get general info instead
    if qualification_attempts >= 4:
        print(
            f"QUALIFICATION|max_attempts_reached|missing_vars={missing_vars}|next=information"
        )
        # Log the incomplete qualification for human follow-up
        return "information_node"

    # Data still missing - STOP AND WAIT for user response (conversational behavior)
    # The qualification question has been asked, now we wait for user input
    print(
        f"QUALIFICATION|stop_and_wait|missing_vars={missing_vars}|attempts={qualification_attempts}"
    )
    return END


def route_from_information(state: Dict[str, Any]) -> str:
    """
    Context-aware routing from information_node.

    Intelligence: Instead of always ending conversation,
    check if user has incomplete qualification and offer to continue.
    """
    # Check if user has incomplete qualification context
    missing_qualification_vars = []
    for var in QUALIFICATION_REQUIRED_VARS:
        if var not in state or not state[var]:
            missing_qualification_vars.append(var)

    # If qualification is complete, can proceed to scheduling
    if not missing_qualification_vars:
        print(f"INFORMATION|qualification_complete|next=scheduling")
        return "scheduling_node"

    # If user has qualification context (parent_name) but incomplete data
    if state.get("parent_name") and missing_qualification_vars:
        attempts = state.get("qualification_attempts", 0)

        # If user hasn't hit the escape hatch limit, continue qualification
        if attempts < 4:
            print(
                f"INFORMATION|continue_qualification|missing={len(missing_qualification_vars)}|attempts={attempts}"
            )
            return "qualification_node"
        else:
            # User hit escape hatch but might want to continue
            # For now, end conversation, but could offer options here
            print(
                f"INFORMATION|post_escape_hatch|missing={len(missing_qualification_vars)}|end=true"
            )
            return END

    # No qualification context - end conversation
    print(f"INFORMATION|no_qualification_context|end=true")
    return END


def route_from_scheduling(state: Dict[str, Any]) -> str:
    """
    Decide para onde ir após o nó de agendamento.
    Verifica se as preferências de horário foram coletadas.
    """
    # Verifica se as preferências de disponibilidade foram coletadas
    for var in SCHEDULING_REQUIRED_VARS:
        if var not in state or not state[var]:
            return "scheduling_node"

    # Se todas as informações de agendamento foram coletadas, finaliza
    return END


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

    # Set conditional entry point using master router (Rules First, AI After)
    # For langgraph 0.0.26, we need to use set_conditional_entry_point
    graph.set_conditional_entry_point(
        master_router,
        {
            "greeting_node": "greeting_node",
            "qualification_node": "qualification_node",
            "information_node": "information_node",
            "scheduling_node": "scheduling_node",
            "fallback_node": "fallback_node",
        },
    )

    # Add conditional transitions
    # Greeting ends the flow (turn-based conversation)
    graph.add_conditional_edges(
        "greeting_node",
        route_from_greeting,
        {
            END: END,  # Greeting always ends the current turn
        },
    )

    # Qualification can loop, go to scheduling, or escape to information
    graph.add_conditional_edges(
        "qualification_node",
        route_from_qualification,
        {
            "qualification_node": "qualification_node",
            "scheduling_node": "scheduling_node",
            "information_node": "information_node",  # CRITICAL: Add escape hatch
            END: END,
        },
    )

    # Scheduling can loop or end based on collected availability preferences
    graph.add_conditional_edges(
        "scheduling_node",
        route_from_scheduling,
        {
            "scheduling_node": "scheduling_node",
            END: END,
        },
    )

    # Information node should be context-aware, not always end
    graph.add_conditional_edges(
        "information_node",
        route_from_information,  # New function - will be created
        {
            "qualification_node": "qualification_node",  # Continue qualification if incomplete
            "scheduling_node": "scheduling_node",  # Go to scheduling if qualification complete
            END: END,  # End if no context to continue
        },
    )

    # Fallback still goes directly to END
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
