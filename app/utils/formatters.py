"""
Utility functions for safe data formatting and display.

This module provides defensive validation functions to prevent
data corruption bugs, specifically addressing the phone=nown issue.
"""
from typing import Any, Union


def safe_phone_display(phone: Union[str, None, Any]) -> str:
    """
    Safely get last 4 digits of phone number for display/logging.

    This function prevents the 'nown' corruption bug that occurred when
    state.get('phone', 'unknown')[-4:] was applied to invalid data.

    Args:
        phone: Phone number (can be str, None, or any type)

    Returns:
        str: Last 4 digits of valid phone, or 'unknown' for invalid input

    Examples:
        safe_phone_display("5511999999999") -> "9999"
        safe_phone_display("123") -> "unknown" (too short)
        safe_phone_display(None) -> "unknown" (None input)
        safe_phone_display("") -> "unknown" (empty string)
    """
    # Handle None or non-string inputs
    if phone is None:
        return "unknown"

    # Convert to string if not already
    if not isinstance(phone, str):
        phone_str = str(phone)
    else:
        phone_str = phone

    # Handle empty or very short strings
    if not phone_str or len(phone_str) < 4:
        return "unknown"

    # Validate that it contains only digits (basic phone validation)
    # Remove common phone formatting characters
    cleaned_phone = (
        phone_str.replace("-", "")
        .replace(" ", "")
        .replace("(", "")
        .replace(")", "")
        .replace("+", "")
    )

    if not cleaned_phone.isdigit():
        return "unknown"

    # Return last 4 digits safely
    return cleaned_phone[-4:]


def safe_copy_state(state: dict) -> dict:
    """
    Create a deep copy of state with validation of critical fields.

    This function ensures that critical fields like 'phone' are preserved
    correctly during state transitions between LangGraph nodes.

    Args:
        state: State dictionary to copy

    Returns:
        dict: Deep copy with validated critical fields
    """
    import copy

    # Create deep copy to prevent reference sharing
    new_state = copy.deepcopy(state)

    # Validate critical fields
    if "phone" in new_state:
        phone = new_state["phone"]
        if not isinstance(phone, str):
            # Convert to string if not already, but preserve original if valid
            if phone is not None:
                new_state["phone"] = str(phone)
            else:
                # Log warning for debugging
                print(f"WARNING: Phone field was None, preserving as None")

    return new_state


def validate_state_integrity(state: dict, context: str = "unknown") -> bool:
    """
    Validate that state dictionary contains expected critical fields.

    Args:
        state: State dictionary to validate
        context: Context string for logging (e.g., "qualification_node_entry")

    Returns:
        bool: True if state is valid, False if corruption detected
    """
    critical_fields = ["phone", "message_id"]

    for field in critical_fields:
        if field not in state:
            print(f"STATE_CORRUPTION_WARNING: Missing field '{field}' in {context}")
            return False

        value = state[field]
        if value is None:
            print(f"STATE_CORRUPTION_WARNING: Field '{field}' is None in {context}")
            return False

        if field == "phone" and not isinstance(value, str):
            print(
                f"STATE_CORRUPTION_WARNING: Phone field is not string in {context}: {type(value)}"
            )
            return False

    return True
