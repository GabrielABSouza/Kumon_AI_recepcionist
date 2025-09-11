"""
🔌 GRAPH WIRING TEST: Proves that LangGraph calls the correct qualification_node implementation

This test is designed to FAIL initially, proving that the graph is calling
the wrong qualification_node function (inline version instead of the refactored file).
"""

from unittest.mock import patch

import pytest

from app.core.langgraph_flow import build_graph


class TestGraphWiring:
    """
    🧪 TDD Test to prove graph wiring failure and then validate the fix.
    """

    @pytest.mark.asyncio
    async def test_graph_calls_the_correct_qualification_node_implementation(self):
        """
        🚨 RED PHASE TEST: Prove that graph calls WRONG qualification_node

        This test will FAIL initially because:
        1. We mock the CORRECT qualification_node from app.core.nodes.qualification
        2. We execute a workflow that should route to qualification_node
        3. We assert that our mock was called
        4. FAILURE: The inline version is called instead, so our mock is never called

        After the fix, this test will PASS, proving the wiring is correct.
        """
        print("🧪 TESTING: Graph wiring to correct qualification_node")

        # Build the workflow graph
        workflow = build_graph()

        # Create state that should route to qualification_node
        state = {
            "phone": "5511999999999",
            "text": "olá gostaria de saber sobre o kumon",  # This should trigger qualification flow
            "instance": "kumon_assistant",
            # Force qualification routing by setting stage
            "current_stage": "qualification",
            "collected_data": {},
        }

        # 🎯 CRITICAL: Mock the CORRECT qualification_node in both locations
        with patch(
            "app.core.nodes.qualification.qualification_node"
        ) as mock_correct_node, patch(
            "app.core.langgraph_flow.qualification_node", mock_correct_node
        ):
            # Configure the mock to return a proper response
            mock_correct_node.return_value = {
                **state,
                "last_bot_response": "Olá! Para começarmos, qual é o seu nome?",
                "current_stage": "qualification",
                "current_step": "parent_name_collection",
            }

            try:
                # Execute the workflow - this should call qualification_node
                result = await workflow.ainvoke(state)

                # 🚨 ASSERTION THAT SHOULD FAIL INITIALLY:
                # The correct qualification_node should have been called
                mock_correct_node.assert_called_once()

                print("✅ SUCCESS: Graph correctly calls refactored qualification_node!")

                # Validate the result structure
                assert "last_bot_response" in result
                assert result["last_bot_response"] is not None

                print(f"✅ Response generated: {result['last_bot_response'][:50]}...")

            except AssertionError as e:
                # This is EXPECTED to fail initially
                print(f"🚨 EXPECTED FAILURE: {str(e)}")
                print(
                    "🔍 DIAGNOSIS: Graph is calling inline qualification_node, not the refactored version"
                )
                print("🎯 SOLUTION: Need to fix graph wiring in langgraph_flow.py")
                raise AssertionError(
                    "GRAPH WIRING FAILURE: LangGraph is calling the wrong qualification_node implementation. "
                    "Expected: app.core.nodes.qualification.qualification_node (refactored version). "
                    "Actual: inline qualification_node in langgraph_flow.py. "
                    "Fix: Import correct function and remove inline version."
                ) from e

        print("🎯 Graph wiring test completed - ready for fix!")

    @pytest.mark.asyncio
    async def test_inline_qualification_node_should_not_exist_after_fix(self):
        """
        🔍 VERIFICATION TEST: After fix, inline qualification_node should not exist

        This test ensures that the inline function was properly removed.
        """
        import inspect

        from app.core import langgraph_flow

        # Get all functions in the langgraph_flow module
        module_functions = [
            name
            for name, obj in inspect.getmembers(langgraph_flow)
            if inspect.isfunction(obj) and obj.__module__ == langgraph_flow.__name__
        ]

        # The inline qualification_node should NOT exist after the fix
        inline_functions_that_should_not_exist = [
            func for func in module_functions if func == "qualification_node"
        ]

        assert (
            len(inline_functions_that_should_not_exist) == 0
        ), f"Found inline qualification_node functions that should have been removed: {inline_functions_that_should_not_exist}"

        print(
            "✅ VERIFICATION: No inline qualification_node found - clean architecture!"
        )
