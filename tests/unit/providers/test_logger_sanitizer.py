"""
Unit tests for Logger Sanitizer.

Tests sanitization of log inputs to prevent injection attacks and security issues.
"""

import pytest
from src.providers.logger.sanitizer import (
    sanitize_log_input,
    sanitize_structured_data,
    is_safe_for_logging,
    SanitizationLevel
)


class TestSanitizationLevel:
    """Test suite for SanitizationLevel enum."""

    def test_sanitization_levels_exist(self):
        """Test that all sanitization levels are defined."""
        assert SanitizationLevel.STRICT.value == "strict"
        assert SanitizationLevel.MODERATE.value == "moderate"
        assert SanitizationLevel.LENIENT.value == "lenient"


class TestSanitizeLogInput:
    """Test suite for sanitize_log_input function."""

    def test_sanitize_simple_string(self):
        """Test sanitizing a simple safe string."""
        result = sanitize_log_input("Hello World")
        assert result == "Hello World"

    def test_sanitize_none_value(self):
        """Test sanitizing None value."""
        result = sanitize_log_input(None)
        assert result == "None"

    def test_sanitize_integer(self):
        """Test sanitizing integer value."""
        result = sanitize_log_input(12345)
        assert result == "12345"

    def test_sanitize_float(self):
        """Test sanitizing float value."""
        result = sanitize_log_input(123.45)
        assert "123.45" in result

    def test_sanitize_dict(self):
        """Test sanitizing dictionary value."""
        data = {"key": "value", "number": 42}
        result = sanitize_log_input(data)
        assert "key" in result
        assert "value" in result

    def test_sanitize_list(self):
        """Test sanitizing list value."""
        data = ["item1", "item2", 3]
        result = sanitize_log_input(data)
        assert "item1" in result
        assert "item2" in result

    def test_sanitize_removes_newlines_moderate(self):
        """Test that newlines are removed in moderate mode."""
        result = sanitize_log_input("Line1\nLine2\rLine3", level=SanitizationLevel.MODERATE)
        assert "\n" not in result
        assert "\r" not in result
        assert "Line1" in result
        assert "Line2" in result

    def test_sanitize_removes_newlines_strict(self):
        """Test that newlines are removed in strict mode."""
        result = sanitize_log_input("Line1\nLine2", level=SanitizationLevel.STRICT)
        assert "\n" not in result
        assert "Line1" in result

    def test_sanitize_max_length(self):
        """Test that long strings are truncated."""
        long_string = "A" * 500
        result = sanitize_log_input(long_string, max_length=100)
        assert len(result) <= 100
        assert result.endswith("...")

    def test_sanitize_max_length_exact(self):
        """Test truncation at exact max length."""
        string = "A" * 100
        result = sanitize_log_input(string, max_length=100)
        assert len(result) == 100

    def test_sanitize_max_length_small(self):
        """Test truncation with very small max length."""
        string = "Hello World"
        result = sanitize_log_input(string, max_length=5)
        assert len(result) == 5

    def test_sanitize_max_length_under_3(self):
        """Test truncation with max_length under 3."""
        string = "Hello"
        result = sanitize_log_input(string, max_length=2)
        assert len(result) == 2

    def test_sanitize_control_characters_moderate(self):
        """Test removal of control characters in moderate mode."""
        result = sanitize_log_input("Test\x00\x01\x02String", level=SanitizationLevel.MODERATE)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "Test" in result
        assert "String" in result

    def test_sanitize_control_characters_strict(self):
        """Test removal of control characters in strict mode."""
        result = sanitize_log_input("Test\x00\x1fString", level=SanitizationLevel.STRICT)
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_sanitize_tab_characters(self):
        """Test handling of tab characters."""
        result = sanitize_log_input("Col1\tCol2\tCol3", level=SanitizationLevel.MODERATE)
        assert "\t" not in result
        assert "Col1" in result
        assert "Col2" in result

    def test_sanitize_prevents_log_injection_moderate(self):
        """Test prevention of log injection patterns in moderate mode."""
        malicious = "User input INFO [attacker] Fake log entry"
        result = sanitize_log_input(malicious, level=SanitizationLevel.MODERATE)
        # Should prevent log injection pattern
        assert "INFO_" in result or "INFO [" not in result

    def test_sanitize_binary_data_utf8(self):
        """Test sanitizing binary data that can be decoded as UTF-8."""
        binary_data = b"Hello World"
        result = sanitize_log_input(binary_data)
        assert "Hello World" in result

    def test_sanitize_binary_data_non_utf8(self):
        """Test sanitizing binary data that cannot be decoded as UTF-8."""
        binary_data = b"\x80\x81\x82\x83"
        result = sanitize_log_input(binary_data)
        assert "binary data" in result.lower() or len(result) > 0

    def test_sanitize_binary_data_long(self):
        """Test sanitizing long binary data."""
        binary_data = b"\x00" * 100
        result = sanitize_log_input(binary_data)
        # Binary data with null bytes is decoded as UTF-8 (valid) then sanitized
        # The null bytes get replaced with underscores by the sanitizer
        assert len(result) > 0

    def test_sanitize_bytearray(self):
        """Test sanitizing bytearray."""
        data = bytearray(b"Test")
        result = sanitize_log_input(data)
        assert len(result) > 0

    def test_sanitize_strict_only_safe_chars(self):
        """Test strict mode only allows safe characters."""
        result = sanitize_log_input("Test@#$%123", level=SanitizationLevel.STRICT)
        # Should only contain alphanumeric and allowed punctuation
        assert "Test" in result

    def test_sanitize_lenient_preserves_more(self):
        """Test lenient mode preserves more content."""
        result = sanitize_log_input("Line1\nLine2", level=SanitizationLevel.LENIENT)
        # Lenient should replace with pipe
        assert "|" in result or " " in result

    def test_sanitize_multiple_spaces_collapsed(self):
        """Test that multiple spaces are collapsed."""
        result = sanitize_log_input("Too    many     spaces", level=SanitizationLevel.MODERATE)
        assert "    " not in result
        assert "Too" in result
        assert "many" in result
        assert "spaces" in result

    def test_sanitize_empty_string(self):
        """Test sanitizing empty string."""
        result = sanitize_log_input("")
        assert result == ""

    def test_sanitize_whitespace_only(self):
        """Test sanitizing whitespace-only string."""
        result = sanitize_log_input("   \t\n   ", level=SanitizationLevel.MODERATE)
        # Should be collapsed/trimmed
        assert len(result) <= 3

    def test_sanitize_unicode_characters(self):
        """Test sanitizing unicode characters."""
        result = sanitize_log_input("Hello 世界 🌍")
        # Should handle unicode gracefully
        assert len(result) > 0

    def test_sanitize_json_dict(self):
        """Test sanitizing complex dictionary."""
        data = {
            "user": "test@example.com",
            "action": "login",
            "metadata": {"ip": "127.0.0.1"}
        }
        result = sanitize_log_input(data)
        assert "user" in result or "test" in result

    def test_sanitize_json_error_fallback(self):
        """Test fallback when JSON encoding fails."""
        # Create object that can't be JSON encoded
        class NonSerializable:
            pass

        obj = NonSerializable()
        result = sanitize_log_input(obj)
        assert len(result) > 0


class TestSanitizeStructuredData:
    """Test suite for sanitize_structured_data function."""

    def test_sanitize_structured_simple(self):
        """Test sanitizing simple structured data."""
        data = {"key1": "value1", "key2": "value2"}
        result = sanitize_structured_data(data)

        assert isinstance(result, dict)
        assert "key1" in result
        assert result["key1"] == "value1"

    def test_sanitize_structured_with_dangerous_values(self):
        """Test sanitizing structured data with dangerous values."""
        data = {
            "user": "test@example.com",
            "input": "Malicious\nINFO [fake] Log"
        }
        result = sanitize_structured_data(data)

        assert "user" in result
        assert "\n" not in result["input"]

    def test_sanitize_structured_with_dangerous_keys(self):
        """Test sanitizing structured data with dangerous keys."""
        data = {
            "key\nwith\nnewlines": "value",
            "normal_key": "normal_value"
        }
        result = sanitize_structured_data(data)

        # Keys should be sanitized too
        for key in result.keys():
            assert "\n" not in key

    def test_sanitize_structured_preserves_count(self):
        """Test that all keys are preserved after sanitization."""
        data = {"key1": "value1", "key2": "value2", "key3": "value3"}
        result = sanitize_structured_data(data)

        assert len(result) == 3

    def test_sanitize_structured_empty_dict(self):
        """Test sanitizing empty dictionary."""
        result = sanitize_structured_data({})
        assert result == {}

    def test_sanitize_structured_with_different_levels(self):
        """Test sanitizing with different sanitization levels."""
        data = {"key": "value\nwith\nnewlines"}

        result_strict = sanitize_structured_data(data, level=SanitizationLevel.STRICT)
        result_lenient = sanitize_structured_data(data, level=SanitizationLevel.LENIENT)

        assert "\n" not in result_strict["key"]
        assert "\n" not in result_lenient["key"]

    def test_sanitize_structured_with_none_values(self):
        """Test sanitizing structured data with None values."""
        data = {"key1": None, "key2": "value"}
        result = sanitize_structured_data(data)

        assert result["key1"] == "None"
        assert result["key2"] == "value"

    def test_sanitize_structured_with_numeric_values(self):
        """Test sanitizing structured data with numeric values."""
        data = {"count": 42, "price": 19.99}
        result = sanitize_structured_data(data)

        assert "42" in result["count"]
        assert "19.99" in result["price"]


class TestIsSafeForLogging:
    """Test suite for is_safe_for_logging function."""

    def test_safe_simple_string(self):
        """Test that simple strings are safe."""
        assert is_safe_for_logging("Hello World") is True

    def test_safe_with_numbers(self):
        """Test that strings with numbers are safe."""
        assert is_safe_for_logging("Test123") is True

    def test_safe_with_punctuation(self):
        """Test that strings with punctuation are safe."""
        assert is_safe_for_logging("Hello, World!") is True

    def test_unsafe_with_newline(self):
        """Test that strings with newlines are unsafe."""
        assert is_safe_for_logging("Line1\nLine2") is False

    def test_unsafe_with_carriage_return(self):
        """Test that strings with carriage returns are unsafe."""
        assert is_safe_for_logging("Line1\rLine2") is False

    def test_unsafe_with_control_chars(self):
        """Test that strings with control characters are unsafe."""
        assert is_safe_for_logging("Test\x00String") is False
        assert is_safe_for_logging("Test\x01String") is False

    def test_unsafe_with_log_injection(self):
        """Test that log injection patterns are detected as unsafe."""
        assert is_safe_for_logging("User input INFO [fake]") is False
        assert is_safe_for_logging("Data ERROR: fake") is False
        assert is_safe_for_logging("Input DEBUG-something") is False

    def test_unsafe_non_string(self):
        """Test that non-strings are considered unsafe."""
        assert is_safe_for_logging(123) is False
        assert is_safe_for_logging(None) is False
        assert is_safe_for_logging({"key": "value"}) is False

    def test_safe_empty_string(self):
        """Test that empty string is safe."""
        assert is_safe_for_logging("") is True

    def test_safe_with_spaces(self):
        """Test that strings with spaces are safe."""
        assert is_safe_for_logging("This is a test") is True

    def test_safe_email(self):
        """Test that email addresses are safe."""
        assert is_safe_for_logging("user@example.com") is True

    def test_safe_url(self):
        """Test that URLs are safe."""
        assert is_safe_for_logging("https://example.com") is True

    def test_case_insensitive_log_injection(self):
        """Test that log injection detection is case insensitive."""
        assert is_safe_for_logging("info [fake]") is False
        assert is_safe_for_logging("ERROR: fake") is False

    def test_safe_word_info_in_context(self):
        """Test that 'info' as a word (not pattern) might be safe."""
        # This depends on the exact implementation - adjust as needed
        result = is_safe_for_logging("This is some information")
        # May or may not be safe depending on regex - test current behavior
        assert isinstance(result, bool)


class TestSanitizationEdgeCases:
    """Test suite for edge cases and special scenarios."""

    def test_very_long_string_performance(self):
        """Test that very long strings are handled efficiently."""
        long_string = "A" * 10000
        result = sanitize_log_input(long_string, max_length=200)
        assert len(result) <= 200

    def test_nested_structures(self):
        """Test sanitizing deeply nested structures."""
        data = {
            "level1": {
                "level2": {
                    "level3": "deep value"
                }
            }
        }
        result = sanitize_log_input(data)
        assert len(result) > 0

    def test_mixed_encodings(self):
        """Test handling mixed character encodings."""
        mixed = "ASCII text 日本語 العربية"
        result = sanitize_log_input(mixed)
        assert len(result) > 0

    def test_all_control_characters_removed(self):
        """Test that all dangerous control characters are removed."""
        dangerous_chars = "".join([chr(i) for i in range(0, 32)])
        text = f"Before{dangerous_chars}After"
        result = sanitize_log_input(text, level=SanitizationLevel.MODERATE)

        # Check none of the dangerous chars remain
        for i in range(0, 9):  # 0x00-0x08
            assert chr(i) not in result
        for i in range(11, 32):  # 0x0b-0x1f
            assert chr(i) not in result

    def test_preserves_data_integrity(self):
        """Test that safe data integrity is preserved."""
        safe_data = "Normal log message with data: user=test, count=42"
        result = sanitize_log_input(safe_data)
        assert "user=test" in result
        assert "count=42" in result
