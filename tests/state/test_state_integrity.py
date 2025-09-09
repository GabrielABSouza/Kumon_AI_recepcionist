"""
Test State Integrity - Regression tests for state corruption bugs.

This test addresses the ROOT CAUSE identified in the bug analysis:
- Phone field corruption (phone=nown) caused by unsafe state mutations
- Deep copy vs shallow copy issues causing state corruption between nodes
- Unsafe string slicing without validation
"""

import copy

import pytest

from app.core.langgraph_flow import build_graph
from app.utils.formatters import safe_phone_display


class TestStateIntegrity:
    """Test suite to prevent state corruption between LangGraph nodes."""

    def test_state_corruption_prevention(self):
        """
        CRITICAL REGRESSION TEST: Prevents the phone=nown corruption bug.

        This test should FAIL before the fix and PASS after the tactical fix.

        Background:
        The bug occurs when state mutations between nodes corrupt critical fields,
        specifically when phone field becomes corrupted and string slicing of
        'unknown'[-4:] produces 'nown', causing infinite loops.

        Root Cause: Shallow copy (state.copy()) + direct mutations + unsafe slicing
        """
        # STEP 1: Set up initial state that matches real-world scenario
        initial_state = {
            "phone": "5511999999999",  # Real Brazilian phone format
            "parent_name": "Gabriel",  # User provided name
            "message_id": "test_corruption_msg_123",
            "last_user_message": "oi, meu nome é Gabriel",
            "intent": "greeting",
            "confidence": 0.95,
        }

        # STEP 2: Create graph instance (same as production)
        graph = build_graph()

        # STEP 3: Execute multiple times to catch intermittent corruption
        for iteration in range(3):
            print(f"\n=== ITERATION {iteration + 1} - Testing state integrity ===")

            # Use deep copy to ensure each iteration starts fresh
            test_state = copy.deepcopy(initial_state)

            try:
                # STEP 4: Execute the graph (this is where corruption happens)
                result_state = graph.invoke(test_state)

                # STEP 5: CRITICAL ASSERTIONS - These should catch the phone=nown bug

                # ASSERTION 1: Phone field must be preserved exactly
                assert result_state.get("phone") == "5511999999999", (
                    f"CRITICAL BUG: Phone corrupted! "
                    f"Expected: 5511999999999, Got: {result_state.get('phone')} "
                    f"(Iteration {iteration + 1})"
                )

                # ASSERTION 2: The infamous 'nown' corruption must never appear
                result_str = str(result_state)
                assert "nown" not in result_str, (
                    f"CRITICAL BUG: 'nown' corruption detected in state! "
                    f"This indicates unsafe string slicing of 'unknown'[-4:] "
                    f"State: {result_state} (Iteration {iteration + 1})"
                )

                # ASSERTION 3: All critical keys must be preserved
                critical_keys = ["phone", "parent_name", "message_id"]
                for key in critical_keys:
                    assert key in result_state, (
                        f"CRITICAL BUG: Key '{key}' lost during state processing! "
                        f"Available keys: {list(result_state.keys())} "
                        f"(Iteration {iteration + 1})"
                    )

                # ASSERTION 4: Phone must be valid string (not None/corrupted)
                phone_value = result_state.get("phone")
                assert isinstance(phone_value, str), (
                    f"CRITICAL BUG: Phone is not a string! "
                    f"Type: {type(phone_value)}, Value: {phone_value} "
                    f"(Iteration {iteration + 1})"
                )

                assert len(phone_value) >= 10, (
                    f"CRITICAL BUG: Phone too short! "
                    f"Length: {len(phone_value)}, Value: {phone_value} "
                    f"(Iteration {iteration + 1})"
                )

                print(f"✅ Iteration {iteration + 1}: State integrity maintained")
                print(f"   Phone: {result_state.get('phone')}")
                print(f"   Parent: {result_state.get('parent_name')}")

            except Exception as e:
                pytest.fail(
                    f"CRITICAL BUG: Graph execution failed with state corruption! "
                    f"Error: {str(e)} "
                    f"Initial state: {test_state} "
                    f"(Iteration {iteration + 1})"
                )

        print("\n🎯 SUCCESS: All iterations completed without state corruption!")

    def test_concurrent_state_isolation(self):
        """
        Test that concurrent processing doesn't cause cross-contamination.

        This test ensures that multiple states processed simultaneously
        don't interfere with each other through shared references.
        """
        # Different phone numbers to detect cross-contamination
        states = [
            {
                "phone": "5511111111111",
                "parent_name": "João",
                "message_id": "msg_joao_001",
                "last_user_message": "oi, sou o João",
            },
            {
                "phone": "5522222222222",
                "parent_name": "Maria",
                "message_id": "msg_maria_002",
                "last_user_message": "olá, meu nome é Maria",
            },
            {
                "phone": "5533333333333",
                "parent_name": "Pedro",
                "message_id": "msg_pedro_003",
                "last_user_message": "oi, me chamo Pedro",
            },
        ]

        graph = build_graph()

        # Process each state
        results = []
        for i, state in enumerate(states):
            print(
                f"\nProcessing state {i+1}: {state['parent_name']} ({state['phone']})"
            )

            # Deep copy to prevent contamination from test setup
            test_state = copy.deepcopy(state)
            result = graph.invoke(test_state)
            results.append(result)

            # Immediate validation
            expected_phone = states[i]["phone"]
            expected_name = states[i]["parent_name"]

            assert result["phone"] == expected_phone, (
                f"State contamination detected! "
                f"Expected phone: {expected_phone}, Got: {result['phone']} "
                f"for user: {expected_name}"
            )

            assert result["parent_name"] == expected_name, (
                f"Name contamination detected! "
                f"Expected: {expected_name}, Got: {result['parent_name']}"
            )

        # Final cross-validation: ensure no state leaked between processes
        for i, result in enumerate(results):
            original_state = states[i]

            assert (
                result["phone"] == original_state["phone"]
            ), f"Final validation failed! Phone mismatch for state {i+1}"
            assert (
                result["parent_name"] == original_state["parent_name"]
            ), f"Final validation failed! Name mismatch for state {i+1}"

        print("\n🎯 SUCCESS: No cross-contamination detected across states!")

    def test_phone_display_formatting_safety(self):
        """
        Test that phone display formatting doesn't cause corruption.

        This specifically tests the code path that was generating 'nown':
        state.get('phone', 'unknown')[-4:]
        """
        test_cases = [
            # Valid cases
            ("5511999999999", "9999"),  # Normal case
            ("11987654321", "4321"),  # Another normal case
            # Edge cases that were causing corruption
            ("", "unknown"),  # Empty string
            (None, "unknown"),  # None value
            ("abc", "unknown"),  # Invalid phone
            ("123", "unknown"),  # Too short
        ]

        for phone_input, expected_display in test_cases:
            print(f"\nTesting phone input: {repr(phone_input)}")

            # This simulates the exact scenario in route_from_qualification
            state = {"phone": phone_input} if phone_input is not None else {}

            # Test both old (unsafe) and new (safe) approaches
            try:
                # OLD APPROACH: This is the problematic line that was causing corruption
                old_result = state.get("phone", "unknown")[-4:]
                print(f"  Old slice result: {repr(old_result)}")

                # NEW APPROACH: Using our safe function
                safe_result = safe_phone_display(state.get("phone"))
                print(f"  Safe function result: {repr(safe_result)}")

                # CRITICAL TEST: Ensure our safe function never produces 'nown'
                assert (
                    safe_result != "nown"
                ), f"CRITICAL BUG: safe_phone_display produced 'nown'! Input: {repr(phone_input)}"

                # CRITICAL TEST: For valid phones, safe function should return last 4 digits
                if (
                    phone_input
                    and isinstance(phone_input, str)
                    and len(phone_input) >= 4
                    and phone_input.isdigit()
                ):
                    assert (
                        safe_result == expected_display
                    ), f"Valid phone should show last 4 digits. Got: {safe_result}, Expected: {expected_display}"
                else:
                    # For invalid inputs, safe function should return 'unknown'
                    assert (
                        safe_result == "unknown"
                    ), f"Invalid phone should return 'unknown'. Got: {safe_result}"

                # VERIFICATION: Show that old code still produces the bug (for awareness)
                if old_result == "nown":
                    print(
                        f"  ⚠️  Old code still vulnerable: {repr(phone_input)} -> 'nown'"
                    )
                    print(
                        f"  ✅ Safe function fixed it: {repr(phone_input)} -> '{safe_result}'"
                    )

            except (TypeError, IndexError) as e:
                pytest.fail(
                    f"UNSAFE SLICING: Error processing phone {repr(phone_input)}: {e}"
                )
