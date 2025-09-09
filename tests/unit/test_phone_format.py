"""
Unit tests for phone number E.164 formatting.
"""
import pytest

from app.core.phone import extract_country_code, format_e164, is_valid_e164


class TestPhoneFormatE164:
    """Test suite for E.164 phone formatting."""

    def test_format_e164_happy_path(self):
        """Test various phone formats convert to E.164."""
        test_cases = [
            # Input, Expected output
            ("11999999999", "+5511999999999"),  # Brazilian mobile without country
            ("5511999999999", "+5511999999999"),  # Brazilian with country
            ("+5511999999999", "+5511999999999"),  # Already E.164
            ("(11) 99999-9999", "+5511999999999"),  # Formatted Brazilian
            ("011 99999-9999", "+5511999999999"),  # With leading zero
            ("11 9 9999-9999", "+5511999999999"),  # With spaces
            ("(11)99999.9999", "+5511999999999"),  # With dots
            ("+1-555-123-4567", "+15551234567"),  # US format
        ]

        for input_phone, expected in test_cases:
            result = format_e164(input_phone)
            assert result == expected, f"Failed for input: {input_phone}"

    def test_format_e164_invalid_input_raises(self):
        """Test that invalid inputs raise ValueError."""
        invalid_inputs = [
            "",  # Empty
            "abc",  # Letters only
            "123",  # Too short
            "99999",  # Missing area code
            "+",  # Just plus sign
            "+123",  # Too short with country code
            "999999999",  # 9 digits without area code
        ]

        for invalid in invalid_inputs:
            with pytest.raises(ValueError) as exc_info:
                format_e164(invalid)
            assert (
                "Invalid phone number" in str(exc_info.value)
                or "Phone number too short" in str(exc_info.value)
                or "Phone number cannot be empty" in str(exc_info.value)
                or "missing area code" in str(exc_info.value)
            )

    def test_is_valid_e164(self):
        """Test E.164 validation."""
        # Valid E.164 numbers
        valid_numbers = [
            "+5511999999999",  # Brazil
            "+15551234567",  # US
            "+442071234567",  # UK
            "+861234567890",  # China
        ]

        for number in valid_numbers:
            assert is_valid_e164(number) is True, f"Should be valid: {number}"

        # Invalid E.164 numbers
        invalid_numbers = [
            "5511999999999",  # Missing +
            "+055119999999",  # Leading zero after +
            "+",  # Just plus
            "",  # Empty
            None,  # None
            "+123456789012345678",  # Too long (>15 digits)
            "++5511999999999",  # Double plus
            "+55 11 99999999",  # Has spaces
        ]

        for number in invalid_numbers:
            assert is_valid_e164(number) is False, f"Should be invalid: {number}"

    def test_extract_country_code(self):
        """Test country code extraction."""
        test_cases = [
            ("+5511999999999", "55"),  # Brazil
            ("+15551234567", "1"),  # US/Canada
            ("+442071234567", "44"),  # UK
            ("+861234567890", "86"),  # China (simplified)
        ]

        for phone, expected_code in test_cases:
            result = extract_country_code(phone)
            assert result == expected_code, f"Failed for {phone}"

        # Invalid inputs should return None
        assert extract_country_code("invalid") is None
        assert extract_country_code("") is None
        assert extract_country_code("5511999999999") is None  # Missing +

    def test_format_e164_with_different_default_country(self):
        """Test formatting with different default country codes."""
        # US default
        result = format_e164("5551234567", default_country_code="1")
        assert result == "+15551234567"

        # UK default
        result = format_e164("2071234567", default_country_code="44")
        assert result == "+442071234567"

    def test_format_e164_preserves_international_format(self):
        """Test that international format is preserved."""
        international_numbers = [
            "+442071234567",  # UK
            "+33123456789",  # France
            "+4912345678901",  # Germany
            "+81312345678",  # Japan
        ]

        for number in international_numbers:
            result = format_e164(number)
            assert result == number, f"Should preserve: {number}"
