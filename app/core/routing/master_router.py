"""
Master Router: Implements Flexible Intent Prioritization.

🔍 PERFORMANCE INSTRUMENTED VERSION
Measures timing for each critical operation to identify bottlenecks.

New Architecture: Prioritizes explicit user intent over rigid continuation rules.
Hierarchy:
1. Get AI analysis first (always)
2. Honor explicit interruption intents (information, scheduling, help)
3. Apply continuation rules only if no explicit intent
4. Use AI classification for new flows
"""
import time
from typing import Any, Dict

from app.core.gemini_classifier import classifier
from app.core.state_manager import get_conversation_history, get_conversation_state
from app.utils.formatters import safe_phone_display


def map_intent_to_node(intent: str) -> str:
    """Map intent string to corresponding node name."""
    intent_to_node = {
        "greeting": "greeting_node",
        "qualification": "qualification_node",
        "information": "information_node",
        "scheduling": "scheduling_node",
        "fallback": "fallback_node",
        "help": "fallback_node",  # Help routes to fallback for now
    }
    return intent_to_node.get(intent, "fallback_node")


def check_for_continuation_rule(state: Dict[str, Any]) -> str:
    """
    Check if there's a continuation rule that should override AI intent.

    Priority 2: Continuation rules for flows in progress.
    Only applies if no explicit interruption intent was detected.

    Returns:
        str: Node name to continue to, or None if no continuation needed
    """
    # REGRA 1: Post-greeting response - coletou greeting, agora precisa coletar nome
    if state.get("greeting_sent") and not state.get("parent_name"):
        print("ROUTER|continuation_rule|post_greeting|collect_parent_name")
        return "qualification_node"

    # Required qualification variables that must be collected
    QUALIFICATION_REQUIRED_VARS = [
        "parent_name",
        "student_name",
        "student_age",
        "program_interests",
    ]

    # REGRA 2: Check if qualification is incomplete and should continue
    if state.get("parent_name"):  # User has started qualification
        missing_vars = []
        for var in QUALIFICATION_REQUIRED_VARS:
            if var not in state or not state[var]:
                missing_vars.append(var)

        if missing_vars:
            qualification_attempts = state.get("qualification_attempts", 0)
            # Continue qualification if not at escape hatch limit
            if qualification_attempts < 4:
                print(
                    f"ROUTER|continuation_rule|qualification|missing={len(missing_vars)}|"
                    f"attempts={qualification_attempts}"
                )
                return "qualification_node"

    # Check if scheduling is incomplete and should continue
    SCHEDULING_REQUIRED_VARS = ["availability_preferences"]
    for var in SCHEDULING_REQUIRED_VARS:
        if var not in state or not state[var]:
            # Only continue scheduling if qualification is complete
            missing_qualification = []
            for qual_var in QUALIFICATION_REQUIRED_VARS:
                if qual_var not in state or not state[qual_var]:
                    missing_qualification.append(qual_var)

            if not missing_qualification:  # Qualification complete, can do scheduling
                print(f"ROUTER|continuation_rule|scheduling|missing={var}")
                return "scheduling_node"

    return None


async def master_router(state: Dict[str, Any]) -> str:
    """
    Master Router: Implements Flexible Intent Prioritization.

    🔍 PERFORMANCE INSTRUMENTED VERSION
    Measures timing for each critical operation to identify bottlenecks.

    New Architecture: Prioritizes explicit user intent over rigid continuation rules.
    Hierarchy:
    1. Get AI analysis first (always)
    2. Honor explicit interruption intents (information, scheduling, help)
    3. Apply continuation rules only if no explicit intent
    4. Use AI classification for new flows

    Returns:
        str: Node name to route to (e.g., "greeting_node", "qualification_node")
    """
    # 🚀 PERFORMANCE AUDIT: Start total timing
    total_start_time = time.perf_counter()

    phone = safe_phone_display(state.get("phone"))
    text = state.get("text", "")

    print(f"PIPELINE|master_router_start|phone={phone}|text_len={len(text)}")
    print(f"PERF_AUDIT|Master Router Start|phone={phone}")

    try:
        # 🔍 PERFORMANCE AUDIT: Measure State & History Loading
        db_start_time = time.perf_counter()

        # Prepare context for AI classification
        conversation_context = None
        try:
            if phone:
                # Collect conversation state
                saved_state = get_conversation_state(phone)
                # Collect conversation history
                conversation_history = get_conversation_history(phone, limit=4)

                if saved_state or conversation_history:
                    # Use new context format: {'state': {...}, 'history': [...]}
                    # Context is loaded here but used by individual nodes as needed
                    conversation_context = {
                        "state": saved_state or {},
                        "history": conversation_history,
                    }
                    # Merge saved state into current state for continuation rules
                    if saved_state:
                        # Current state takes precedence over saved state
                        for key, value in saved_state.items():
                            if key not in state:
                                state[key] = value
        except Exception as context_error:
            print(
                f"PIPELINE|master_router_context_error|error={str(context_error)}|"
                f"phone={phone}"
            )
            # Continue with empty context

        db_duration = (time.perf_counter() - db_start_time) * 1000
        print(
            f"PERF_AUDIT|Load State & History|duration_ms={db_duration:.2f}|phone={phone}"
        )

        # 🤖 PERFORMANCE AUDIT: Measure Gemini Classifier Call
        gemini_start_time = time.perf_counter()

        # STEP A: AI analysis with FULL CONTEXT (not basic only!)
        # 🎯 FIXED: Use conversation_context para análise contextual completa
        nlu_result = await classifier.classify(text, context=conversation_context)

        gemini_duration = (time.perf_counter() - gemini_start_time) * 1000
        print(
            f"PERF_AUDIT|Gemini Full Classification|"
            f"duration_ms={gemini_duration:.2f}|phone={phone}"
        )

        # 🧠 PERFORMANCE AUDIT: Measure Decision Logic
        rules_start_time = time.perf_counter()

        # Extract intent and add NLU result to state for nodes to use
        primary_intent = nlu_result.get("primary_intent", "fallback")
        confidence = nlu_result.get("confidence", 0.0)

        # Add NLU result to state for nodes to access
        state["nlu_result"] = nlu_result
        state["nlu_entities"] = nlu_result.get("entities", {})

        print(
            f"PIPELINE|full_context_routing|intent={primary_intent}|"
            f"confidence={confidence:.2f}|entities={len(nlu_result.get('entities', {}))}|phone={phone}"
        )

        # STEP B: Priority 1 - Honor Explicit Interruption Intents
        interrupt_intents = ["information", "scheduling", "help"]
        if primary_intent in interrupt_intents:
            decision = map_intent_to_node(primary_intent)
            print(
                f"PIPELINE|priority_1_interruption|decision={decision}|intent={primary_intent}|"
                f"confidence={confidence:.2f}|phone={phone}"
            )
            rules_duration = (time.perf_counter() - rules_start_time) * 1000
            print(
                f"PERF_AUDIT|Business Rules & Decision|"
                f"duration_ms={rules_duration:.2f}|phone={phone}"
            )

            # 📊 PERFORMANCE AUDIT: Total Master Router Time
            total_duration = (time.perf_counter() - total_start_time) * 1000
            print(
                f"PERF_AUDIT|Master Router Total|duration_ms={total_duration:.2f}|"
                f"decision={decision}|phone={phone}"
            )
            return decision

        # STEP C: Priority 2 - Apply Continuation Rules
        continuation_node = check_for_continuation_rule(state)
        if continuation_node:
            print(
                f"PIPELINE|priority_2_continuation|decision={continuation_node}|"
                f"intent={primary_intent}|confidence={confidence:.2f}|phone={phone}"
            )
            rules_duration = (time.perf_counter() - rules_start_time) * 1000
            print(
                f"PERF_AUDIT|Business Rules & Decision|"
                f"duration_ms={rules_duration:.2f}|phone={phone}"
            )

            # 📊 PERFORMANCE AUDIT: Total Master Router Time
            total_duration = (time.perf_counter() - total_start_time) * 1000
            print(
                f"PERF_AUDIT|Master Router Total|duration_ms={total_duration:.2f}|"
                f"decision={continuation_node}|phone={phone}"
            )
            return continuation_node

        # STEP D: Priority 3 - Use AI Classification for New Flows
        decision = map_intent_to_node(primary_intent)
        print(
            f"PIPELINE|priority_3_new_flow|decision={decision}|"
            f"intent={primary_intent}|confidence={confidence:.2f}|phone={phone}"
        )

        rules_duration = (time.perf_counter() - rules_start_time) * 1000
        print(
            f"PERF_AUDIT|Business Rules & Decision|"
            f"duration_ms={rules_duration:.2f}|phone={phone}"
        )

        # 📊 PERFORMANCE AUDIT: Total Master Router Time
        total_duration = (time.perf_counter() - total_start_time) * 1000
        print(
            f"PERF_AUDIT|Master Router Total|duration_ms={total_duration:.2f}|"
            f"decision={decision}|phone={phone}"
        )

        return decision

    except Exception as e:
        # Graceful fallback on any error
        total_duration = (time.perf_counter() - total_start_time) * 1000
        print(f"PIPELINE|master_router_error|error={str(e)}|phone={phone}")
        print(f"PIPELINE|master_router_fallback|decision=fallback_node|phone={phone}")
        print(
            f"PERF_AUDIT|Master Router Total|duration_ms={total_duration:.2f}|"
            f"decision=fallback_node|error=true|phone={phone}"
        )
        return "fallback_node"
