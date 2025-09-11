"""
Utility functions for prompt generation and few-shot learning.
"""
import json
import os

# Path to the few-shot examples JSON file (relative to this file)
import pathlib
from typing import Any, Dict, List

FEW_SHOT_EXAMPLES_PATH = str(
    pathlib.Path(__file__).parent.parent / "data" / "few_shot_examples.json"
)


def load_few_shot_examples() -> List[Dict[str, Any]]:
    """
    Load few-shot examples from JSON file for prompt enhancement.

    Returns:
        List[Dict[str, Any]]: List of example dictionaries containing:
            - user_question (str): The user's question/input
            - next_qualification_question (str | None): Next qualification question if applicable
            - ideal_response (str): The ideal combined response

    Raises:
        FileNotFoundError: If the few-shot examples file doesn't exist
        json.JSONDecodeError: If the JSON file is malformed
        ValueError: If the JSON structure is invalid
    """
    try:
        # Check if file exists
        if not os.path.exists(FEW_SHOT_EXAMPLES_PATH):
            raise FileNotFoundError(
                f"Few-shot examples file not found: {FEW_SHOT_EXAMPLES_PATH}"
            )

        # Load JSON data
        with open(FEW_SHOT_EXAMPLES_PATH, encoding="utf-8") as file:
            examples = json.load(file)

        # Validate structure
        if not isinstance(examples, list):
            raise ValueError("Few-shot examples JSON must contain a list at root level")

        # Validate each example
        for i, example in enumerate(examples):
            if not isinstance(example, dict):
                raise ValueError(f"Example {i} must be a dictionary")

            required_fields = [
                "user_question",
                "next_qualification_question",
                "ideal_response",
            ]
            for field in required_fields:
                if field not in example:
                    raise ValueError(f"Example {i} missing required field: {field}")

            # Validate field types
            if not isinstance(example["user_question"], str):
                raise ValueError(f"Example {i} user_question must be a string")

            if example["next_qualification_question"] is not None and not isinstance(
                example["next_qualification_question"], str
            ):
                raise ValueError(
                    f"Example {i} next_qualification_question must be string or null"
                )

            if not isinstance(example["ideal_response"], str):
                raise ValueError(f"Example {i} ideal_response must be a string")

        print(f"PROMPT_UTILS|loaded_examples|count={len(examples)}")
        return examples

    except FileNotFoundError as e:
        print(f"PROMPT_UTILS|error|type=file_not_found|path={FEW_SHOT_EXAMPLES_PATH}")
        raise e
    except json.JSONDecodeError as e:
        print(f"PROMPT_UTILS|error|type=json_decode|details={str(e)}")
        raise e
    except ValueError as e:
        print(f"PROMPT_UTILS|error|type=validation|details={str(e)}")
        raise e


def format_few_shot_examples_for_prompt(examples: List[Dict[str, Any]]) -> str:
    """
    Format few-shot examples into a string suitable for inclusion in LLM prompts.

    Args:
        examples: List of example dictionaries from load_few_shot_examples()

    Returns:
        str: Formatted string with examples ready for prompt inclusion
    """
    if not examples:
        return "Nenhum exemplo disponível."

    formatted_examples = []

    for i, example in enumerate(examples, 1):
        user_question = example["user_question"]
        next_qualification = example["next_qualification_question"]
        ideal_response = example["ideal_response"]

        # Format each example with clear structure
        example_text = f"""EXEMPLO {i}:
Pergunta do usuário: "{user_question}"
Próxima pergunta de qualificação: {f'"{next_qualification}"' if next_qualification else 'Nenhuma'}
Resposta ideal: "{ideal_response}"
"""
        formatted_examples.append(example_text)

    return "\n".join(formatted_examples)
