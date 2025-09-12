"""
Minimal LangGraph flow: Entry → [Single Node] → End
Each node handles its intent and sends a response.
"""
import copy
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from app.core.delivery import send_text
from app.core.gemini_classifier import classifier
from app.core.llm import OpenAIClient
from app.core.nodes.greeting import greeting_node as simplified_greeting_node
from app.core.nodes.information import information_node as intelligent_information_node
from app.core.nodes.qualification import qualification_node
from app.core.routing.master_router import master_router_for_langgraph
from app.core.state_manager import get_conversation_state, save_conversation_state
from app.prompts.node_prompts import get_fallback_prompt, get_scheduling_prompt
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


async def greeting_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle greeting intent using simplified greeting node."""
    try:
        # Convert dict to CeciliaState for the simplified greeting node

        # Create a minimal CeciliaState with required fields
        cecil_state = {
            "phone": state.get("phone"),
            "instance": state.get("instance", "kumon_assistant"),
        }

        # Call the simplified greeting node
        result_state = await simplified_greeting_node(cecil_state)

        # Convert back to dict format expected by langgraph
        phone = state.get("phone")
        if phone:
            save_conversation_state(phone, {"greeting_sent": True})

        return {
            **state,
            "sent": "true",
            "response": result_state.get("last_bot_response", ""),
            "greeting_sent": True,
        }

    except Exception as e:
        print(f"GREETING|error|{str(e)}")
        # Fallback to simple response
        fallback_text = "Olá! Eu sou a Cecília do Kumon Vila A. Qual é o seu nome?"

        try:
            delivery_result = await send_text(
                state.get("phone", ""),
                fallback_text,
                state.get("instance", "kumon_assistant"),
            )
            phone = state.get("phone")
            if phone:
                save_conversation_state(phone, {"greeting_sent": True})

            return {
                **state,
                "sent": delivery_result.get("sent", "false"),
                "response": fallback_text,
                "greeting_sent": True,
                "error_reason": str(e),
            }
        except Exception as send_error:
            return {
                **state,
                "sent": "false",
                "response": fallback_text,
                "greeting_sent": True,
                "error_reason": f"{str(e)} | {str(send_error)}",
            }


async def qualification_node_wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    🔌 GRAPH WRAPPER: Nova arquitetura com NLU contextual integrado

    NOVA ARQUITETURA:
    - Executa GeminiClassifier contextual DENTRO do nó
    - Extrai entidades baseadas no contexto da conversa
    - Passa entidades para qualification_node para processamento
    """
    try:
        # 🧠 PASSO 1: Executar NLU contextual dentro do nó
        phone = state.get("phone")
        text = state.get("text", "")

        # Preparar contexto para classificação contextual
        conversation_context = None
        try:
            if phone:
                # Coletar contexto de conversa
                from app.core.state_manager import (
                    get_conversation_history,
                    get_conversation_state,
                )

                saved_state = get_conversation_state(phone)
                conversation_history = get_conversation_history(phone, limit=4)

                if saved_state or conversation_history:
                    conversation_context = {
                        "state": saved_state or {},
                        "history": conversation_history,
                    }
        except Exception as context_error:
            print(
                f"QUALIFICATION|context_error|error={str(context_error)}|phone={phone}"
            )
            # Continue with empty context

        # Executar GeminiClassifier contextual
        nlu_result = classifier.classify(text, context=conversation_context)
        nlu_entities = nlu_result.get("entities", {})

        print(f"🧠 QUALIFICATION NLU - entities extracted: {nlu_entities}")

        # Create simple dict state that qualification_node can process
        simple_state = {
            "text": text,
            "phone": phone,
            "phone_number": phone,  # For phone compatibility
            "collected_data": state.get("collected_data", {}),
            "current_stage": state.get("current_stage", "qualification"),
            "current_step": state.get("current_step", "parent_name_collection"),
            # 🎯 NOVA ARQUITETURA: Passa entidades do NLU contextual
            "nlu_entities": nlu_entities,
            "instance": state.get("instance", "kumon_assistant"),
        }

        # Call the refactored qualification_node with simple dict
        result_state = await qualification_node(simple_state)

        # Convert result back to LangGraph format
        dict_result = {
            **state,  # Preserve original LangGraph fields including nlu_entities
            "last_bot_response": result_state.get("last_bot_response", ""),
            "current_stage": result_state.get("current_stage", "qualification"),
            "current_step": result_state.get("current_step", "parent_name_collection"),
            "collected_data": result_state.get("collected_data", {}),
            "response": result_state.get("last_bot_response", ""),
            "sent": "true",  # Mark as processed
            # 🎯 FORÇA PRESERVAÇÃO: Garante que nlu_entities sejam mantidos
            "nlu_entities": state.get("nlu_entities", {}),
            "nlu_result": state.get("nlu_result", {}),
        }

        print(
            f"QUALIFICATION|wrapper_success|response_len={len(dict_result.get('response', ''))}"
        )
        return dict_result

    except Exception as e:
        print(f"QUALIFICATION|wrapper_error|error={str(e)}")

        # Fallback to simple response
        fallback_text = "Olá! Para começarmos, qual é o seu nome?"

        return {
            **state,
            "response": fallback_text,
            "last_bot_response": fallback_text,
            "sent": "true",
            "error_reason": str(e),
        }


async def information_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle information intent using intelligent node with few-shot learning."""
    try:
        # Import and convert state to CeciliaState
        from app.core.state.models import (
            CeciliaState,
            ConversationStage,
            ConversationStep,
        )

        # Load conversation state for proper context
        phone = state.get("phone")
        saved_state = {}
        if phone:
            saved_state = get_conversation_state(phone)

        # Create CeciliaState object with proper conversion
        cecil_state = CeciliaState(
            phone_number=phone or "",
            last_user_message=state.get("text", ""),
            current_stage=ConversationStage.INFORMATION_GATHERING,
            current_step=ConversationStep.PROGRAM_DETAILS,
            conversation_metrics={"message_count": 0, "failed_attempts": 0},
            collected_data=saved_state or {},
        )

        # CRITICAL: Pass nlu_entities from master_router to the information_node
        cecil_state["nlu_entities"] = state.get("nlu_entities", {})
        cecil_state["text"] = state.get("text", "")
        cecil_state["phone"] = phone
        cecil_state["instance"] = state.get("instance", "kumon_assistant")

        # Call the intelligent information node
        result = await intelligent_information_node(cecil_state)

        # Convert back to dict format expected by langgraph
        if isinstance(result, dict):
            return {**state, **result}
        else:
            # Handle CeciliaState result
            return {
                **state,
                "sent": "true",
                "response": getattr(result, "last_bot_response", ""),
            }

    except Exception as e:
        print(f"PIPELINE|information_node_error|{str(e)}")
        # Fallback to simple response
        fallback_text = (
            "Desculpe, estou com dificuldades técnicas. Como posso ajudá-lo?"
        )

        try:
            delivery_result = send_text(
                state.get("phone", ""),
                fallback_text,
                state.get("instance", "recepcionistakumon"),
            )
            return {
                **state,
                "sent": delivery_result.get("sent", "false"),
                "response": fallback_text,
                "error_reason": str(e),
            }
        except Exception as send_error:
            return {
                **state,
                "sent": "false",
                "response": fallback_text,
                "error_reason": f"{str(e)} | {str(send_error)}",
            }


async def scheduling_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle scheduling intent."""
    return await _execute_node(state, "scheduling", get_scheduling_prompt)


async def fallback_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle fallback for unrecognized intents."""
    return await _execute_node(state, "fallback", get_fallback_prompt)


async def _execute_node(
    state: Dict[str, Any], node_name: str, prompt_func
) -> Dict[str, Any]:
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
                f"QUALIFICATION|node_exec|attempts={qualification_attempts}|"
                f"missing={len(missing_vars)}"
            )
            prompt = prompt_func(
                user_text, redis_state=state, attempts=qualification_attempts
            )
        else:
            prompt = prompt_func(user_text)

        # Generate response with OpenAI adapter (direct async usage)
        # FIXED: Use existing event loop instead of creating new one
        reply_text = await get_openai_client().chat(
            model="gpt-3.5-turbo",
            system_prompt=prompt["system"],
            user_prompt=prompt["user"],
            temperature=0.7,
            max_tokens=300,
        )

        # Send via Evolution API
        phone = state.get("phone")
        if not phone:
            print(f"PIPELINE|node_error|name={node_name}|error=no_phone")
            return {"sent": "false"}

        instance = state.get("instance", "recepcionistakumon")

        # FIXED: send_text is already synchronous and imported at module level
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

            # CRITICAL FIX: Remove automatic state saving from _execute_node
            # Only specific nodes (like qualification_node) should save state
            # This prevents contamination from Redis data in new conversations

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


def route_from_greeting(state: Dict[str, Any]) -> str:  # noqa: U100
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
        f"QUALIFICATION|route_check|attempts={qualification_attempts}|"
        f"phone={safe_phone_display(state.get('phone'))}"
    )

    # Check if all required variables are collected
    missing_vars = []
    for var in QUALIFICATION_REQUIRED_VARS:
        if var not in state or not state[var]:
            missing_vars.append(var)

    if not missing_vars:
        # All data collected - proceed to scheduling
        print("QUALIFICATION|complete|all_data_collected|next=scheduling")
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
        f"QUALIFICATION|stop_and_wait|missing_vars={missing_vars}|"
        f"attempts={qualification_attempts}"
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
        print("INFORMATION|qualification_complete|next=scheduling")
        return "scheduling_node"

    # If user has qualification context (parent_name) but incomplete data
    if state.get("parent_name") and missing_qualification_vars:
        attempts = state.get("qualification_attempts", 0)

        # If user hasn't hit the escape hatch limit, continue qualification
        if attempts < 4:
            print(
                f"INFORMATION|continue_qualification|"
                f"missing={len(missing_qualification_vars)}|attempts={attempts}"
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
    print("INFORMATION|no_qualification_context|end=true")
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
    graph.add_node("qualification_node", qualification_node_wrapper)
    graph.add_node("information_node", information_node)
    graph.add_node("scheduling_node", scheduling_node)
    graph.add_node("fallback_node", fallback_node)

    # Set conditional entry point using SAFE sync wrapper for LangGraph 0.0.26
    # Uses thread pool executor to avoid "Event loop is closed" errors
    graph.set_conditional_entry_point(
        master_router_for_langgraph,  # Safe sync wrapper that doesn't conflict with Uvicorn
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


async def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the workflow with the given state asynchronously."""
    print(f"PIPELINE|flow_start|message_id={state.get('message_id')}")

    try:
        result = await workflow.ainvoke(state)
        print(f"PIPELINE|flow_complete|sent={result.get('sent', 'false')}")
        return result
    except Exception as e:
        print(f"PIPELINE|flow_error|error={str(e)}")
        return {"sent": "false", "error": str(e)}
