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

# Required qualification variables that must be collected
QUALIFICATION_REQUIRED_VARS = [
    "parent_name",
    "preferred_name",
    "child_name",
    "child_age",
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

            # Extract child name and relationship context
            child_name_patterns = [
                r"(?:(?:meu|minha)\s+)?(?:filho|filha|criança|menino|menina|neto|neta|"
                r"sobrinho|sobrinha)\s+(?:se chama|é o|é a|é)\s+"
                r"([a-záàâãéêíóôõúç]+)",
                r"(?:o nome (?:dele|dela|da criança) é|chama)\s+"
                r"([a-záàâãéêíóôõúç]+)",
                r"(?:se )?chama\s+([a-záàâãéêíóôõúç]+)(?=\s+e\s+tem|\s*,|\s*$)",
            ]
            for pattern in child_name_patterns:
                match = re.search(pattern, user_text_lower)
                if (
                    match
                    and node_name == "qualification"
                    and not state.get("child_name")
                ):
                    extracted_child = match.group(1).strip().title()
                    if len(extracted_child) >= 2 and not extracted_child.lower() in [
                        "tem",
                        "anos",
                        "ele",
                        "ela",
                    ]:
                        state["child_name"] = extracted_child
                        print(f"STATE|extracted|child_name={extracted_child}")
                        break

            # Extract child age
            age_patterns = [
                r"(?:tem|possui|está com|idade|anos?)\s*(\d{1,2})\s*anos?",
                r"(\d{1,2})\s*anos?(?:\s+de idade)?",
            ]
            for pattern in age_patterns:
                match = re.search(pattern, user_text_lower)
                if (
                    match
                    and node_name == "qualification"
                    and not state.get("child_age")
                ):
                    age = int(match.group(1))
                    if 3 <= age <= 18:  # Kumon age range validation
                        state["child_age"] = age
                        print(f"STATE|extracted|child_age={age}")
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


def route_from_greeting(_state: Dict[str, Any]) -> str:
    """
    Greeting always transitions to qualification_node.
    The qualification_node is responsible for collecting all required data.
    """
    # Greeting node always transitions to qualification
    return "qualification_node"


def route_from_qualification(state: Dict[str, Any]) -> str:
    """
    Decide para onde ir após o nó de qualificação.
    Verifica se todas as variáveis necessárias foram coletadas.
    """
    # Itera pela lista de variáveis obrigatórias
    for var in QUALIFICATION_REQUIRED_VARS:
        # Se qualquer variável estiver faltando no estado, continua no loop
        if var not in state or not state[var]:
            return "qualification_node"

    # Se todas as variáveis foram coletadas, avança para o próximo passo
    return "scheduling_node"


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

    # Scheduling can loop or end based on collected availability preferences
    graph.add_conditional_edges(
        "scheduling_node",
        route_from_scheduling,
        {
            "scheduling_node": "scheduling_node",
            END: END,
        },
    )

    # Information and fallback go directly to END
    graph.add_edge("information_node", END)
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
