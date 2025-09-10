"""
Tests for prompt utility functions including few-shot example loading.
"""
import json
import tempfile
from unittest.mock import patch

from app.utils.prompt_utils import load_few_shot_examples


class TestPromptUtils:
    """Test suite for prompt utility functions."""

    def test_loads_few_shot_examples_from_json(self):
        """
        🚨 RED PHASE TDD TEST: load_few_shot_examples should load JSON examples correctly.

        This test will FAIL with current implementation because load_few_shot_examples
        function doesn't exist yet and the JSON file structure isn't defined.

        Scenario: Load few-shot examples from JSON file for prompt enhancement.
        Expected: Function returns list of dictionaries with input/output examples.
        Current Bug: Function doesn't exist, will get import error.
        """
        # ARRANGE: Create test JSON data with few-shot examples
        test_examples = [
            {
                "user_question": "Qual o valor da mensalidade?",
                "next_qualification_question": "O Kumon é para você mesmo ou para outra pessoa?",
                "ideal_response": "A mensalidade do Kumon varia de acordo com a disciplina escolhida. Para Matemática ou Português individual, o valor é R$ 180,00 por mês. Se optar pelo programa combinado (Matemática + Português), o investimento é R$ 320,00 mensais.\n\nPara personalizar ainda mais nossa conversa, posso saber se o Kumon é para você mesmo ou para outra pessoa?",
            },
            {
                "user_question": "Vocês atendem crianças pequenas?",
                "next_qualification_question": "Qual é o nome da criança?",
                "ideal_response": "Sim! O método Kumon é ideal para crianças pequenas. Atendemos a partir dos 3 anos de idade, sempre respeitando o ritmo individual de cada criança. O material é desenvolvido especialmente para essa faixa etária.\n\nPara eu te ajudar melhor, qual é o nome da criança?",
            },
            {
                "user_question": "Como funciona o método?",
                "next_qualification_question": None,
                "ideal_response": "O método Kumon é baseado no aprendizado individualizado. Cada aluno avança no seu próprio ritmo, desenvolvendo autonomia e autoconfiança. O material é sequencial e permite que a criança evolua gradualmente, sempre consolidando o conhecimento antes de avançar.",
            },
        ]

        # Create temporary JSON file with test data
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            json.dump(test_examples, temp_file, ensure_ascii=False, indent=2)
            temp_file_path = temp_file.name

        try:
            # Mock the file path to use our test file
            with patch("app.utils.prompt_utils.FEW_SHOT_EXAMPLES_PATH", temp_file_path):
                # ACT: Call load_few_shot_examples function
                # 🚨 THIS WILL FAIL - Function doesn't exist yet
                result = load_few_shot_examples()

                # ASSERT: Should return list of dictionaries with correct structure
                assert isinstance(result, list), "Should return a list of examples"
                assert len(result) == 3, f"Should return 3 examples, got {len(result)}"

                # Verify first example structure
                first_example = result[0]
                assert (
                    "user_question" in first_example
                ), "Example should have user_question field"
                assert (
                    "next_qualification_question" in first_example
                ), "Example should have next_qualification_question field"
                assert (
                    "ideal_response" in first_example
                ), "Example should have ideal_response field"

                # Verify content matches test data
                assert (
                    first_example["user_question"] == "Qual o valor da mensalidade?"
                ), "User question should match test data"
                assert (
                    "R$ 180,00" in first_example["ideal_response"]
                ), "Response should contain price information"
                assert (
                    "para você mesmo ou para outra pessoa"
                    in first_example["ideal_response"]
                ), "Response should contain qualification question"

                # Verify example with null next_qualification_question
                third_example = result[2]
                assert (
                    third_example["next_qualification_question"] is None
                ), "Should handle null qualification questions"
                assert (
                    "método Kumon" in third_example["ideal_response"]
                ), "Should contain method information"

                print("✅ SUCCESS: load_few_shot_examples loads JSON data correctly")
                print(f"✅ Loaded {len(result)} examples from JSON")
                print(f"✅ First example: {first_example['user_question']}")
                print(
                    f"✅ Response length: {len(first_example['ideal_response'])} chars"
                )

        finally:
            # Cleanup temporary file
            import os

            os.unlink(temp_file_path)

    def test_few_shot_examples_file_exists(self):
        """
        🚨 RED PHASE TDD TEST: Verify the actual few-shot examples file exists.

        This test ensures that the production few_shot_examples.json file exists
        and has the correct structure for the information_node to use.
        """
        # ARRANGE: Import the expected file path
        # ACT & ASSERT: Check if file exists
        # 🚨 THIS WILL FAIL - File and constant don't exist yet
        import os

        from app.utils.prompt_utils import FEW_SHOT_EXAMPLES_PATH

        assert os.path.exists(
            FEW_SHOT_EXAMPLES_PATH
        ), f"Few-shot examples file should exist at {FEW_SHOT_EXAMPLES_PATH}"

        # Load and verify structure
        result = load_few_shot_examples()
        assert isinstance(result, list), "Should return list of examples"
        assert len(result) > 0, "Should have at least one example"

        # Verify each example has required fields
        for i, example in enumerate(result):
            assert "user_question" in example, f"Example {i} missing user_question"
            assert (
                "next_qualification_question" in example
            ), f"Example {i} missing next_qualification_question"
            assert "ideal_response" in example, f"Example {i} missing ideal_response"

            # Verify types
            assert isinstance(
                example["user_question"], str
            ), f"Example {i} user_question should be string"
            assert example["next_qualification_question"] is None or isinstance(
                example["next_qualification_question"], str
            ), f"Example {i} next_qualification_question should be string or null"
            assert isinstance(
                example["ideal_response"], str
            ), f"Example {i} ideal_response should be string"

        print(
            f"✅ SUCCESS: Production few-shot examples file verified with {len(result)} examples"
        )
