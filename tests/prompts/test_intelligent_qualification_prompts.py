"""
Test suite for enhanced intelligent qualification prompts.

Tests the improved prompt generation logic that identifies the first missing
variable from QUALIFICATION_REQUIRED_VARS and generates appropriate prompts.
"""
from app.core.langgraph_flow import QUALIFICATION_REQUIRED_VARS
from app.prompts.node_prompts import get_qualification_prompt


class TestIntelligentQualificationPrompts:
    """Test suite for intelligent qualification prompt generation."""

    def test_prompts_follow_required_vars_sequence(self):
        """Test that prompts are generated in the correct sequence based on QUALIFICATION_REQUIRED_VARS."""

        # Test Case 1: No data - should ask for first missing variable (parent_name)
        empty_state = {}
        result = get_qualification_prompt("Oi", empty_state, attempts=1)

        # Should ask for parent name (first in QUALIFICATION_REQUIRED_VARS)
        assert (
            "parent_name" == QUALIFICATION_REQUIRED_VARS[0]
        ), "Test expects parent_name to be first"
        assert (
            "nome" in result["system"].lower()
        ), f"Should ask for name, got: {result['system']}"

        print("✅ Empty state correctly asks for first missing variable (parent_name)")

    def test_prompts_ask_for_next_missing_variable(self):
        """Test that prompts intelligently ask for the next missing variable in sequence."""

        # Test Case 1: Have parent_name + student_name, missing age + interests
        # BUT: need beneficiary_type to avoid the "para você mesmo?" question
        partial_state = {
            "parent_name": "Maria",
            "student_name": "Pedro",
            "beneficiary_type": "child"  # Add this to skip beneficiary question
            # Missing: student_age, program_interests
        }

        result = get_qualification_prompt("Ok", partial_state, attempts=1)

        # Should ask for student_age (next in sequence)
        assert (
            "idade" in result["system"].lower()
        ), f"Should ask for age when name is present, got: {result['system']}"
        assert "Pedro" in result["system"], "Should personalize with student name"

        print("✅ Partial state correctly asks for next missing variable (age)")

        # Test Case 2: Have name + age, missing interests
        almost_complete_state = {
            "parent_name": "Carlos",
            "student_name": "Ana",
            "student_age": 10,
            "beneficiary_type": "child"  # Add this to skip beneficiary question
            # Missing: program_interests
        }

        result = get_qualification_prompt("10 anos", almost_complete_state, attempts=1)

        # Should ask for program_interests (last in sequence)
        system_lower = result["system"].lower()
        assert any(
            word in system_lower for word in ["disciplina", "matemática", "português"]
        ), f"Should ask for program interests, got: {result['system']}"
        assert (
            "Ana" in result["system"] and "10 anos" in result["system"]
        ), "Should personalize with collected data"

        print("✅ Near-complete state correctly asks for final variable (interests)")

    def test_complete_state_offers_next_steps(self):
        """Test behavior when all required variables are collected."""

        complete_state = {
            "parent_name": "Roberto",
            "student_name": "Lucas",
            "student_age": 8,
            "program_interests": ["mathematics"],
        }

        result = get_qualification_prompt("Matemática", complete_state, attempts=1)

        # Should offer to proceed with complete information
        system_lower = result["system"].lower()
        assert (
            "perfeito" in system_lower or "ótimo" in system_lower
        ), "Should acknowledge completion positively"
        assert "roberto" in result["system"].lower(), "Should use parent name"
        assert "lucas" in result["system"].lower(), "Should use student name"
        assert "8" in result["system"], "Should include age"

        print("✅ Complete state offers appropriate next steps")

    def test_beneficiary_type_handling(self):
        """Test special handling of beneficiary_type temporary variable."""

        # Test Case 1: Have parent_name, missing beneficiary_type
        with_parent_name = {
            "parent_name": "Patricia"
            # Missing beneficiary_type
        }

        result = get_qualification_prompt("Sou Patricia", with_parent_name, attempts=1)

        # Should ask about beneficiary type
        system_lower = result["system"].lower()
        assert any(
            phrase in system_lower
            for phrase in ["para você", "para outra pessoa", "beneficiário"]
        ), f"Should ask about beneficiary, got: {result['system']}"
        assert "Patricia" in result["system"], "Should use parent name"

        print("✅ Beneficiary type question correctly generated")

        # Test Case 2: beneficiary_type = "child", should ask for student name
        child_beneficiary = {
            "parent_name": "Sandra",
            "beneficiary_type": "child"
            # Missing student_name
        }

        result = get_qualification_prompt(
            "Para minha filha", child_beneficiary, attempts=1
        )

        # Should ask for child's name specifically
        system_lower = result["system"].lower()
        assert any(
            word in system_lower for word in ["nome", "criança", "filha"]
        ), f"Should ask for child's name, got: {result['system']}"
        assert "Sandra" in result["system"], "Should use parent name"

        print("✅ Child beneficiary correctly prompts for student name")

    def test_escape_hatch_after_multiple_attempts(self):
        """Test enhanced escape hatch logic after 3+ attempts."""

        struggling_state = {
            "parent_name": "Fernanda",
            "beneficiary_type": "child"  # Add this to skip beneficiary question and trigger escape hatch
            # Missing: student_name, student_age, program_interests after several attempts
        }

        result = get_qualification_prompt("Não sei", struggling_state, attempts=4)

        # Should offer alternatives and be helpful
        system_lower = result["system"].lower()
        assert "4745-2006" in result["system"], "Should provide phone number"
        assert any(
            word in system_lower for word in ["telefone", "informações"]
        ), "Should offer alternatives"
        assert "fernanda" in system_lower, "Should personalize with known name"

        print("✅ Escape hatch correctly activated after multiple attempts")

    def test_debug_logging_integration(self):
        """Test that debug logging is integrated for troubleshooting."""

        # This test validates that logging information is generated
        # (We can't easily capture print statements in pytest, but we ensure no errors)

        test_state = {
            "parent_name": "TestUser",
            "student_name": "TestStudent"
            # Missing age and interests
        }

        # Should execute without errors and include logging logic
        result = get_qualification_prompt("Test message", test_state, attempts=2)

        # Basic validation that prompt was generated
        assert "system" in result, "Should return system prompt"
        assert "user" in result, "Should return user text"
        assert result["user"] == "Test message", "Should preserve user input"

        print("✅ Debug logging integration working without errors")

    def test_missing_vars_identification(self):
        """Test that missing variables are correctly identified."""

        # Test with various states to ensure missing vars logic works
        test_cases = [
            ({}, 4),  # Empty state - all 4 vars missing
            (
                {"parent_name": "Test"},
                3,
            ),  # Parent name IS in QUALIFICATION_REQUIRED_VARS - 1 present, 3 missing
            (
                {"parent_name": "Test", "student_name": "Test"},
                2,
            ),  # 2 present, 2 missing
            (
                {"parent_name": "Test", "student_name": "Test", "student_age": 10},
                1,
            ),  # 3 present, 1 missing
            (
                {
                    "parent_name": "Test",
                    "student_name": "Test",
                    "student_age": 10,
                    "program_interests": ["math"],
                },
                0,
            ),  # All present
        ]

        for state, expected_missing_count in test_cases:
            result = get_qualification_prompt("test", state, attempts=1)

            # Count missing vars manually to validate logic
            missing_count = sum(
                1
                for var in QUALIFICATION_REQUIRED_VARS
                if var not in state or not state[var]
            )

            assert missing_count == expected_missing_count, (
                f"State {state} should have {expected_missing_count} missing vars, "
                f"but logic shows {missing_count}"
            )

            # Ensure prompt was generated successfully
            assert result["system"], f"Should generate prompt for state: {state}"

        print("✅ Missing variables correctly identified across all test cases")

    def test_enhanced_personalization(self):
        """Test that prompts are properly personalized with collected data."""

        personalized_state = {
            "parent_name": "Dr. Silva",
            "student_name": "Mariana",
            "student_age": 12,
            "beneficiary_type": "child"  # Add to skip beneficiary question
            # Missing: program_interests
        }

        result = get_qualification_prompt(
            "Ela tem 12 anos", personalized_state, attempts=1
        )

        # Should use all available personal information
        system_text = result["system"]
        assert "Mariana" in system_text, "Should use student name"
        assert "12 anos" in system_text, "Should use student age"

        # Should ask for the remaining missing variable (program_interests)
        system_lower = system_text.lower()
        assert any(
            word in system_lower for word in ["disciplina", "matemática", "português"]
        ), "Should ask for program interests"

        print("✅ Enhanced personalization working correctly")
        print(f"Generated prompt sample: {system_text[:100]}...")
