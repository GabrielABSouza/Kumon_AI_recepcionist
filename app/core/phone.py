"""
Phone number utilities for E.164 formatting.
"""
import re
from typing import Optional


def format_e164(raw: str, default_country_code: str = "55") -> str:
    """
    Format a phone number to E.164 standard.

    Args:
        raw: Raw phone number string
        default_country_code: Default country code if not present (Brazil = 55)

    Returns:
        E.164 formatted phone number (e.g., +5511999999999)

    Raises:
        ValueError: If the phone number cannot be formatted to E.164
    """
    if not raw:
        raise ValueError("Phone number cannot be empty")

    # Remove all non-digit characters except +
    cleaned = re.sub(r"[^\d+]", "", raw)

    # Remove leading zeros
    cleaned = cleaned.lstrip("0")

    # If it starts with +, validate it
    if cleaned.startswith("+"):
        # Must have at least country code + number (minimum 10 digits total)
        if len(cleaned) < 11:  # +55 11 99999999 minimum
            raise ValueError(f"Phone number too short: {raw}")
        return cleaned

    # If it starts with country code (55 for Brazil)
    if cleaned.startswith(default_country_code) and len(cleaned) >= 12:
        return f"+{cleaned}"

    # If it's just the local number
    if default_country_code == "55" and len(cleaned) == 11:  # Brazil: 11 999999999
        return f"+{default_country_code}{cleaned}"
    elif default_country_code == "1" and len(cleaned) == 10:  # US: 555 1234567
        return f"+{default_country_code}{cleaned}"
    elif default_country_code == "44" and len(cleaned) == 10:  # UK: 20 71234567
        return f"+{default_country_code}{cleaned}"

    # If it's missing area code but has 9 digits (mobile)
    if len(cleaned) == 9 and cleaned[0] == "9":
        raise ValueError(f"Phone number missing area code: {raw}")

    # Cannot determine valid E.164 format
    raise ValueError(f"Invalid phone number format: {raw}")


def is_valid_e164(phone: str) -> bool:
    """
    Check if a phone number is in valid E.164 format.

    Args:
        phone: Phone number to validate

    Returns:
        True if valid E.164 format, False otherwise
    """
    if not phone:
        return False

    # E.164: + followed by 1-15 digits
    pattern = r"^\+[1-9]\d{1,14}$"
    return bool(re.match(pattern, phone))


def extract_country_code(e164_phone: str) -> Optional[str]:
    """
    Extract country code from E.164 phone number.

    Args:
        e164_phone: E.164 formatted phone number

    Returns:
        Country code or None if invalid
    """
    if not is_valid_e164(e164_phone):
        return None

    # Common country codes (can be 1-3 digits)
    # This is a simplified version - full implementation would need ITU-T E.164 table
    if e164_phone.startswith("+1"):  # USA, Canada
        return "1"
    elif e164_phone.startswith("+55"):  # Brazil
        return "55"
    elif e164_phone.startswith("+44"):  # UK
        return "44"

    # Try to extract 2-digit code
    if len(e164_phone) >= 3:
        return e164_phone[1:3]

    return None
