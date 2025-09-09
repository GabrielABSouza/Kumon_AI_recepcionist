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
from app.core.state_manager import get_conversation_state, save_conversation_state
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

    # INTELLIGENT ENTRY POINT: Check if conversation is in progress
    # If we have partial qualification data, continue from where we left off
    if saved_state:
        missing_vars = [
            var
            for var in QUALIFICATION_REQUIRED_VARS
            if var not in saved_state or not saved_state[var]
        ]

        # If we have some data but not all, continue qualification
        if has_parent_name and missing_vars:
            print(
                f"PIPELINE|classify_complete|intent=qualification|"
                f"confidence=1.0|reason=continue_qualification|missing={len(missing_vars)}"
            )
            return "qualification_node"

        # If all qualification data is complete, proceed to next stage
        if has_parent_name and not missing_vars:
            print(
                f"PIPELINE|classify_complete|intent=scheduling|"
                f"confidence=1.0|reason=qualification_complete"
            )
            return "scheduling_node"

    # Use classifier with contextual information for intelligent classification
    context = {
        "conversation_history": _get_conversation_history(phone),
        **full_state,  # Include all state variables for context
    }
    intent, confidence = classifier.classify(text, context=context)

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


def _get_conversation_history(phone: str) -> list:
    """Get recent conversation history for context."""
    if not phone:
        return []

    try:
        # This is a placeholder - in a real system you'd query message history from Redis/DB
        # For now, return empty list since we don't have message persistence
        # TODO: Implement actual conversation history retrieval
        return []
    except Exception as e:
        print(f"Error retrieving conversation history: {e}")
        return []


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
    """Handle greeting intent."""
    return _execute_node(state, "greeting", get_greeting_prompt)


def qualification_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle qualification intent with attempt tracking."""
    # CRITICAL: Increment attempt counter here (where state changes are preserved)
    state = copy.deepcopy(state)  # Deep copy to prevent state corruption
    state["qualification_attempts"] = state.get("qualification_attempts", 0) + 1

    print(
        f"QUALIFICATION|node_enter|attempts={state['qualification_attempts']}|phone={safe_phone_display(state.get('phone'))}"
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

            # Extract entities from user message and save state
            import re

            user_text = state.get("text", "")
            user_text_lower = user_text.lower()

            # Extract parent name (responsible person)
            parent_name_patterns = [
                r"(?:meu nome é|me chamo|sou)\s+(?:o\s+|a\s+)?([a-záàâãéêíóôõúç]+(?:\s+[a-záàâãéêíóôõúç]+)*)",
            ]
            # Only try simple name pattern if it's a direct answer (short text)
            if len(user_text.strip()) <= 20 and not any(
                word in user_text_lower
                for word in ["tem", "anos", "interesse", "matemática", "português"]
            ):
                parent_name_patterns.append(
                    r"^([a-záàâãéêíóôõúç]+(?:\s+[a-záàâãéêíóôõúç]+)*)$"
                )

            for pattern in parent_name_patterns:
                match = re.search(pattern, user_text_lower)
                if (
                    match
                    and node_name in ["greeting", "qualification"]
                    and not state.get("parent_name")
                ):
                    extracted_name = match.group(1).strip().title()
                    if len(extracted_name) >= 3 and not extracted_name.lower() in [
                        "sim",
                        "não",
                        "talvez",
                    ]:
                        state["parent_name"] = extracted_name
                        # If no preferred name set, use parent_name as default
                        if not state.get("preferred_name"):
                            state["preferred_name"] = extracted_name
                        print(f"STATE|extracted|parent_name={extracted_name}")
                        break

            # Extract preferred name (different from parent name)
            preferred_name_patterns = [
                r"(?:me chame|prefiro|pode me chamar)\s+(?:de\s+)?(\w+(?:\s+\w+)?)",
                r"(?:sou|é)\s+(?:o\s+|a\s+)?(\w+)(?:\s*,|\s*mas|\s*porém)",
            ]
            for pattern in preferred_name_patterns:
                match = re.search(pattern, user_text_lower)
                if match and node_name in ["greeting", "qualification"]:
                    extracted_preferred = match.group(1).strip().title()
                    if len(extracted_preferred) > 2:
                        state["preferred_name"] = extracted_preferred
                        print(f"STATE|extracted|preferred_name={extracted_preferred}")
                        break

            # Extract beneficiary_type (self or child)
            beneficiary_patterns = [
                r"(?:para mim|para eu|para mim mesmo|para mim mesma|meu|eu mesmo|eu mesma)",
                r"(?:para (?:o\s+|a\s+)?(?:meu|minha)\s+(?:filho|filha|criança|neto|neta|sobrinho|sobrinha))",
                r"(?:para outra pessoa|para (?:outro|outra)|para (?:ele|ela))",
            ]

            for i, pattern in enumerate(beneficiary_patterns):
                if (
                    re.search(pattern, user_text_lower)
                    and node_name == "qualification"
                    and not state.get("beneficiary_type")
                ):
                    if i == 0:  # self patterns
                        state["beneficiary_type"] = "self"
                        # Auto-fill student_name with parent_name when beneficiary is self
                        if state.get("parent_name"):
                            state["student_name"] = state["parent_name"]
                            print(
                                f"STATE|extracted|student_name={state['parent_name']} (auto-filled)"
                            )
                        print("STATE|extracted|beneficiary_type=self")
                    else:  # child/other patterns
                        state["beneficiary_type"] = "child"
                        print("STATE|extracted|beneficiary_type=child")
                    break

            # Extract student name (child/person name when beneficiary_type=child)
            student_name_patterns = [
                r"(?:(?:meu|minha)\s+)?(?:filho|filha|criança|menino|menina|neto|neta|"
                r"sobrinho|sobrinha)\s+(?:se chama|é o|é a|é)\s+"
                r"([a-záàâãéêíóôõúç]+)",
                r"(?:o nome (?:dele|dela|da criança) é|chama)\s+"
                r"([a-záàâãéêíóôõúç]+)",
                r"(?:se )?chama\s+([a-záàâãéêíóôõúç]+)(?=\s+e\s+tem|\s*,|\s*$)",
            ]
            for pattern in student_name_patterns:
                match = re.search(pattern, user_text_lower)
                if (
                    match
                    and node_name == "qualification"
                    and not state.get("student_name")
                ):
                    extracted_student = match.group(1).strip().title()
                    if len(
                        extracted_student
                    ) >= 2 and not extracted_student.lower() in [
                        "tem",
                        "anos",
                        "ele",
                        "ela",
                    ]:
                        state["student_name"] = extracted_student
                        print(f"STATE|extracted|student_name={extracted_student}")
                        break

            # Extract student age
            age_patterns = [
                r"(?:tem|possui|está com|idade|anos?)\s*(\d{1,2})\s*anos?",
                r"(\d{1,2})\s*anos?(?:\s+de idade)?",
            ]
            for pattern in age_patterns:
                match = re.search(pattern, user_text_lower)
                if (
                    match
                    and node_name == "qualification"
                    and not state.get("student_age")
                ):
                    age = int(match.group(1))
                    if 3 <= age <= 18:  # Kumon age range validation
                        state["student_age"] = age
                        print(f"STATE|extracted|student_age={age}")
                        break

            # Extract program interests (subjects)
            program_interests = []
            interest_patterns = [
                r"(?:matemática|math|mat)",
                r"(?:português|portugues|port|lingua portuguesa)",
                r"(?:inglês|ingles|english|eng)",
                r"(?:ambas|ambos|os dois|duas matérias|todas)",
            ]

            for i, pattern in enumerate(interest_patterns):
                if re.search(pattern, user_text_lower):
                    if i == 0:  # matemática
                        program_interests.append("mathematics")
                    elif i == 1:  # português
                        program_interests.append("portuguese")
                    elif i == 2:  # inglês
                        program_interests.append("english")
                    elif i == 3:  # ambas/todas
                        program_interests.extend(["mathematics", "portuguese"])

            if (
                program_interests
                and node_name == "qualification"
                and not state.get("program_interests")
            ):
                # Remove duplicates and save as JSON
                unique_interests = list(set(program_interests))
                state["program_interests"] = unique_interests
                print(f"STATE|extracted|program_interests={unique_interests}")

            # Extract availability preferences for scheduling
            availability_patterns = [
                r"(?:manhã|matutino|de manhã)",
                r"(?:tarde|vespertino|à tarde)",
                r"(?:noite|noturno|à noite)",
                r"(?:segunda|terça|quarta|quinta|sexta|sábado|domingo)",
                r"(?:dias da semana|final de semana|fins de semana)",
            ]

            availability_prefs = []
            for pattern in availability_patterns:
                if re.search(pattern, user_text_lower):
                    availability_prefs.append(pattern)

            if (
                availability_prefs
                and node_name == "scheduling"
                and not state.get("availability_preferences")
            ):
                state["availability_preferences"] = {
                    "preferred_times": availability_prefs
                }
                print(f"STATE|extracted|availability_preferences={availability_prefs}")

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
    Greeting always transitions to qualification_node.
    The qualification_node is responsible for collecting all required data.
    """
    # Greeting node always transitions to qualification
    return "qualification_node"


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
    # Greeting always goes to qualification
    graph.add_conditional_edges(
        "greeting_node",
        route_from_greeting,
        {
            "qualification_node": "qualification_node",
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
