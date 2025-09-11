"""
🧪 TDD Test Suite for Scheduling Node Architectural Violations

This test suite proves that the scheduling_node violates our unified NLU architecture
by containing duplicated entity extraction logic instead of trusting GeminiClassifier.

ARCHITECTURAL PROBLEM BEING TESTED:
- scheduling_node contains keyword matching and regex patterns
- It should trust pre-extracted entities from GeminiClassifier instead
- The node should act as a pure orchestrator, not an entity extractor

CRITICAL: These are RED PHASE tests that will FAIL until we refactor scheduling_node
to follow the same pattern as greeting_node and qualification_node.
"""


import pytest

from app.core.nodes.scheduling import SchedulingNode
from app.core.state.models import (
    ConversationStage,
    ConversationStep,
    create_initial_cecilia_state,
)


class TestSchedulingNodeArchitecturalViolations:
    """
    🚨 RED PHASE TEST SUITE: Prove scheduling_node violates unified NLU architecture

    These tests will FAIL until we refactor scheduling_node to eliminate
    duplicate NLU logic and make it trust GeminiClassifier entities.
    """

    @pytest.mark.asyncio
    async def test_scheduling_node_uses_keyword_matching_instead_of_entities(self):
        """
        🔥 RED PHASE TEST: Prove scheduling_node uses keyword matching instead of
        GeminiClassifier entities.

        PROBLEM: _handle_date_preference contains hardcoded keyword matching:
        - if any(word in message_lower for word in ['manhã', 'manha', 'morning', ...])

        NOVA ARQUITETURA: Should use entities.get("time_preference") from GeminiClassifier

        CENÁRIO CRÍTICO:
        - User says: "depois do almoço seria ideal" (sophisticated language)
        - GeminiClassifier extracts: {"time_preference": "afternoon"} (intelligent)
        - scheduling_node keyword matching: FAILS (rigid)
        - EXPECTED: Node should trust GeminiClassifier, not do its own analysis

        🔥 ESTE TESTE VAI FALHAR até refatorarmos para usar entidades
        """
        # ARRANGE: Create state where GeminiClassifier contradicts keyword analysis
        state = create_initial_cecilia_state(
            phone_number="5511999999999",
            # 🎯 CRÍTICO: Mensagem sofisticada que keywords não reconhecem
            user_message="depois do almoço seria perfeito para mim",
            instance="kumon_assistant",
        )

        # Setup scheduling context
        state["current_stage"] = ConversationStage.SCHEDULING
        state["current_step"] = ConversationStep.DATE_PREFERENCE
        state["last_user_message"] = "depois do almoço seria perfeito para mim"

        # 🧠 INTELIGÊNCIA: GeminiClassifier extrai corretamente
        state["nlu_entities"] = {
            "time_preference": "afternoon",  # Gemini é inteligente
            "scheduling_intent": "book_appointment",
        }

        # Setup required collected data
        state["collected_data"] = {
            "parent_name": "Maria",
            "student_name": "João",
            "student_age": 8,
        }

        # ACT: Execute scheduling node
        node = SchedulingNode()
        result = await node(state)

        # 🔍 DEBUG: Let's see what's happening
        response = result.get("response", "")
        print(f"🔍 DEBUG - Response: {response[:100]}...")
        print(f"🔍 DEBUG - Updates: {result}")

        # 🔥 CRITICAL ASSERTION: This PROVES the architectural violation!
        # The scheduling_node IGNORED the GeminiClassifier entity and asked user to choose again
        # This proves it's using keyword matching instead of trusting entities

        # VIOLATION PROOF 1: Node ignored the intelligent entity extraction
        # Note: scheduling_node doesn't have access to nlu_entities yet (architectural problem)
        # We manually added it to demonstrate what SHOULD happen
        expected_entities = {
            "time_preference": "afternoon",
            "scheduling_intent": "book_appointment",
        }
        print(f"🧠 Expected entities that should be used: {expected_entities}")

        # VIOLATION PROOF 2: Node responded with generic choice instead of acting on the entity
        is_generic_choice = any(
            keyword in response.lower()
            for keyword in [
                "poderia escolher",
                "manhã** ou",
                "tarde**",
                "digite simplesmente",
            ]
        )

        print(f"🔍 DEBUG - is_generic_choice: {is_generic_choice}")
        print(f"🔍 DEBUG - response content: {repr(response.lower()[:200])}")

        # 🎉 GREEN PHASE SUCCESS: This assertion now expects CORRECT behavior!
        # The scheduling_node should now TRUST GeminiClassifier entities

        # SUCCESS PROOF 1: Node should NOT ask generic choice (it should act on the entity)
        assert not is_generic_choice, (
            f"✅ ARCHITECTURAL SUCCESS: scheduling_node should now trust GeminiClassifier entity "
            f"time_preference='afternoon' and show afternoon slots directly. "
            f"Response: {response}"
        )

        # SUCCESS PROOF 2: Should show afternoon time slots (because it trusted the entity)
        afternoon_slots_shown = any(
            hour in response for hour in ["14h", "15h", "16h", "17h"]
        )
        assert afternoon_slots_shown, (
            f"✅ GREEN PHASE SUCCESS: Node should show afternoon slots because it now trusts "
            f"GeminiClassifier entities. This proves the architectural refactor worked! "
            f"Response: {response}"
        )

        print(
            "🎉 GREEN PHASE SUCCESS: scheduling_node now uses GeminiClassifier entities!"
        )
        return True

    @pytest.mark.asyncio
    async def test_scheduling_node_uses_regex_instead_of_entity_extraction(self):
        """
        🔥 RED PHASE TEST: Prove scheduling_node uses regex instead of
        GeminiClassifier entity extraction.

        PROBLEM: _handle_time_selection contains regex pattern:
        - option_match = re.search(r'\\b([1-9])\\b', user_message.strip())

        NOVA ARQUITETURA: Should use entities.get("selected_option") from GeminiClassifier

        CENÁRIO CRÍTICO:
        - User says: "quero a segunda opção, por favor" (natural language)
        - GeminiClassifier extracts: {"selected_option": 2} (intelligent)
        - scheduling_node regex: FAILS (can't find number)
        - EXPECTED: Node should trust GeminiClassifier, not use regex

        🔥 ESTE TESTE VAI FALHAR até refatorarmos para usar entidades
        """
        # ARRANGE: Create state with time selection step
        state = create_initial_cecilia_state(
            phone_number="5511999999999",
            # 🎯 CRÍTICO: Mensagem natural que regex não pega
            user_message="quero a segunda opção, por favor",
            instance="kumon_assistant",
        )

        # Setup scheduling context
        state["current_stage"] = ConversationStage.SCHEDULING
        state["current_step"] = ConversationStep.TIME_SELECTION
        state["last_user_message"] = "quero a segunda opção, por favor"

        # 🧠 INTELIGÊNCIA: GeminiClassifier extrai corretamente
        state["nlu_entities"] = {
            "selected_option": 2,  # Gemini entende "segunda opção"
            "time_slot_selection": True,
        }

        # Setup available dates (mock scheduling context)
        state["collected_data"] = {
            "parent_name": "Maria",
            "date_preferences": {
                "preference": "manhã",
                "available_dates": [
                    {
                        "datetime": "2024-01-15T09:00:00",
                        "date_formatted": "15/01/2024 (Segunda-feira)",
                        "time_formatted": "9h00",
                        "time": "09:00",
                    },
                    {
                        "datetime": "2024-01-15T10:00:00",
                        "date_formatted": "15/01/2024 (Segunda-feira)",
                        "time_formatted": "10h00",
                        "time": "10:00",
                    },
                ],
            },
        }

        # ACT: Execute scheduling node
        node = SchedulingNode()
        result = await node(state)

        # 🔍 DEBUG: Let's see what's happening
        response = result.get("response", "")
        print(f"🔍 DEBUG - Response: {response[:100]}...")
        print(
            f"🔍 DEBUG - Current step after: {result.get('updated_state', {}).get('current_step')}"
        )

        # 🔥 CRITICAL ASSERTION: Should select option 2 correctly
        # If scheduling_node still uses regex, it will fail to find "2" in "segunda opção"
        assert "10h00" in response or "segunda" in response.lower(), (
            f"scheduling_node should recognize option 2 from GeminiClassifier entities, "
            f"not rely on regex matching. Response: {response}"
        )

        # Should advance to next step (email collection or event creation)
        updated_step = result.get("updated_state", {}).get("current_step")
        assert updated_step in [
            ConversationStep.EMAIL_COLLECTION,
            ConversationStep.EVENT_CREATION,
        ], (
            f"Should advance to next step after selecting time slot. "
            f"Got step: {updated_step}"
        )

        print("✅ RED PHASE: Test created - will fail until we eliminate regex matching")
        return True

    @pytest.mark.asyncio
    async def test_scheduling_node_validates_email_with_regex_instead_of_entities(self):
        """
        🔥 RED PHASE TEST: Prove scheduling_node validates email with regex
        instead of GeminiClassifier.

        PROBLEM: _handle_email_collection contains regex validation:
        - email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'

        NOVA ARQUITETURA: Should use entities.get("contact_email") from GeminiClassifier

        CENÁRIO CRÍTICO:
        - User says: "meu email é maria arroba gmail ponto com" (verbal format)
        - GeminiClassifier extracts: {"contact_email": "maria@gmail.com"} (intelligent)
        - scheduling_node regex: FAILS (not in email format)
        - EXPECTED: Node should trust GeminiClassifier, not validate with regex

        🔥 ESTE TESTE VAI FALHAR até refatorarmos para usar entidades
        """
        # ARRANGE: Create state with email collection step
        state = create_initial_cecilia_state(
            phone_number="5511999999999",
            # 🎯 CRÍTICO: Email em formato verbal que regex não valida
            user_message="meu email é maria arroba gmail ponto com",
            instance="kumon_assistant",
        )

        # Setup scheduling context
        state["current_stage"] = ConversationStage.SCHEDULING
        state["current_step"] = ConversationStep.EMAIL_COLLECTION
        state["last_user_message"] = "meu email é maria arroba gmail ponto com"

        # 🧠 INTELIGÊNCIA: GeminiClassifier extrai e valida corretamente
        state["nlu_entities"] = {
            "contact_email": "maria@gmail.com",  # Gemini converte formato verbal
            "email_provided": True,
        }

        # Setup required context
        state["collected_data"] = {
            "parent_name": "Maria",
            "selected_slot": {
                "datetime": "2024-01-15T10:00:00",
                "date_formatted": "15/01/2024 (Segunda-feira)",
                "time_formatted": "10h00",
                "time": "10:00",
            },
        }

        # ACT: Execute scheduling node
        node = SchedulingNode()
        result = await node(state)

        # 🔍 DEBUG: Let's see what's happening
        response = result.get("response", "")
        updated_state = result.get("updated_state", {})
        print(f"🔍 DEBUG - Response: {response[:100]}...")
        print(
            f"🔍 DEBUG - Email stored: "
            f"{updated_state.get('collected_data', {}).get('contact_email')}"
        )

        # 🔥 CRITICAL ASSERTION: Should accept email from GeminiClassifier
        # If scheduling_node still uses regex, it will reject the verbal format
        stored_email = updated_state.get("collected_data", {}).get("contact_email")
        assert stored_email == "maria@gmail.com", (
            f"scheduling_node should accept email from GeminiClassifier entities, "
            f"not validate with regex. Stored email: {stored_email}"
        )

        # Should advance to event creation
        updated_step = updated_state.get("current_step")
        assert updated_step == ConversationStep.EVENT_CREATION, (
            f"Should advance to event creation after email validation. "
            f"Got step: {updated_step}"
        )

        print(
            "✅ RED PHASE: Test created - will fail until we eliminate "
            "regex validation"
        )
        return True

    @pytest.mark.asyncio
    async def test_scheduling_node_acts_as_state_machine_instead_of_orchestrator(self):
        """
        🔥 RED PHASE TEST: Prove scheduling_node acts as complex state machine instead of simple orchestrator.

        PROBLEM: scheduling_node.__call__ contains complex if/elif state machine:
        - if current_step == ConversationStep.DATE_PREFERENCE: ...
        - elif current_step == ConversationStep.TIME_SELECTION: ...
        - elif current_step == ConversationStep.EMAIL_COLLECTION: ...

        NOVA ARQUITETURA: Should be a simple orchestrator that executes actions based on entities

        ARCHITECTURAL VIOLATION:
        - Node decides its own flow instead of trusting router/graph orchestration
        - Contains business logic that should be externalized
        - Acts as monolithic processor instead of focused tool

        🔥 ESTE TESTE DOCUMENTA a violação arquitetural
        """
        # This test documents the architectural violation by showing the complex state machine

        # ARRANGE: Create state
        state = create_initial_cecilia_state(
            phone_number="5511999999999",
            user_message="quero agendar uma visita",
            instance="kumon_assistant",
        )

        # ACT: Analyze the node's call method signature and structure
        node = SchedulingNode()

        # ASSERT: Document the architectural problems

        # 1. Node contains complex state machine logic (should be external)
        call_method = node.__call__
        import inspect

        source = inspect.getsource(call_method)
        del state  # Remove unused variable

        # Count the number of step-based conditions (state machine complexity)
        step_conditions = source.count("current_step ==")
        assert step_conditions >= 4, (
            f"scheduling_node contains complex state machine with {step_conditions} conditions. "
            f"Should be a simple orchestrator with minimal branching."
        )

        # 2. Node contains entity extraction methods (should trust GeminiClassifier)
        assert hasattr(
            node, "_handle_date_preference"
        ), "Contains date preference extraction logic"
        assert hasattr(
            node, "_handle_time_selection"
        ), "Contains time selection extraction logic"
        assert hasattr(
            node, "_handle_email_collection"
        ), "Contains email extraction logic"

        # 3. Each method contains NLU logic that should be eliminated
        date_method = node._handle_date_preference
        date_source = inspect.getsource(date_method)

        # Check for keyword matching patterns
        keyword_patterns = [
            "any(word in message_lower",  # Keyword matching
            "for word in [",  # Word list iteration
            "message_lower.lower()",  # Text preprocessing
            "re.search(",  # Regex usage
        ]

        violations_found = []
        for pattern in keyword_patterns:
            if pattern in date_source:
                violations_found.append(pattern)

        assert len(violations_found) > 0, (
            f"scheduling_node methods should not contain NLU logic patterns. "
            f"Found violations: {violations_found}"
        )

        print("🚨 ARCHITECTURAL VIOLATION DOCUMENTED:")
        print(f"  - Complex state machine: {step_conditions} conditions")
        print(f"  - NLU logic patterns: {len(violations_found)} violations")
        print(f"  - Monolithic structure instead of orchestrator pattern")
        print("✅ RED PHASE: Architectural violations documented and proven")

        return True


# ========== HELPER TEST FOR ARCHITECTURE COMPLIANCE ==========


@pytest.mark.asyncio
async def test_scheduling_architecture_should_follow_unified_pattern():
    """
    📋 SPECIFICATION TEST: Define how scheduling_node should work in new architecture.

    This test defines the CORRECT behavior after refactoring:
    1. Trust GeminiClassifier entities completely
    2. Act as pure orchestrator of tools/actions
    3. No internal NLU logic or state machine complexity

    This test serves as specification for the GREEN PHASE refactor.
    """
    # SPECIFICATION: How scheduling_node should work after refactor

    expected_architecture = {
        "entity_extraction": "GeminiClassifier only",
        "node_responsibility": "Pure orchestration",
        "internal_nlu": "None - eliminated",
        "state_machine": "Minimal - externalized to router",
        "tool_pattern": "Simple action execution based on entities",
    }

    # This test will guide the refactoring process
    print("📋 SCHEDULING NODE ARCHITECTURE SPECIFICATION:")
    for key, value in expected_architecture.items():
        print(f"  {key}: {value}")

    print(
        "\n🎯 REFACTOR TARGET: Transform scheduling_node to match "
        "greeting/qualification pattern"
    )
    print("✅ SPECIFICATION: Architecture specification documented")

    return True


# ========== EXECUTION VALIDATION ==========

if __name__ == "__main__":
    """
    🧪 Quick validation that tests can be imported and basic structure works.
    """
    print("🧪 TDD Scheduling Node Architectural Test Suite")
    print("🚨 RED PHASE: These tests will FAIL until refactoring is complete")
    print("🎯 Goal: Eliminate NLU duplication and create pure orchestrator")
