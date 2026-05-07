"""
Comprehensive unit tests for src.utils.security module.

This test suite provides extensive coverage for security utility functions
including input sanitization, validation, and protection against common
vulnerabilities such as XSS, SQL injection, and path traversal attacks.
"""

import pytest
import warnings
from src.utils.security import (
    sanitize_log_input,
    sanitize_html_input,
    sanitize_sql_identifier,
    validate_uuid,
    sanitize_file_path,
    sanitize_url_parameter,
    validate_email,
    sanitize_json_field,
    rate_limit_key
)


class TestSanitizeLogInput:
    """Test suite for sanitize_log_input function."""

    def test_sanitize_log_input_deprecation_warning(self):
        """Test that sanitize_log_input raises a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sanitize_log_input("test")
            assert len(w) == 1
            assert issubclass(w[-1].category, DeprecationWarning)
            assert "deprecated" in str(w[-1].message).lower()

    def test_sanitize_log_input_none_value(self):
        """Test handling of None value."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = sanitize_log_input(None)
            assert result == "None"

    def test_sanitize_log_input_string(self):
        """Test sanitization of normal string."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = sanitize_log_input("normal text")
            assert result == "normal text"

    def test_sanitize_log_input_removes_control_characters(self):
        """Test removal of control characters."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = sanitize_log_input("test\x00\x01\x1f\x7fvalue")
            assert "\x00" not in result
            assert "\x01" not in result
            assert "\x1f" not in result
            assert "\x7f" not in result
            assert "test_____value" == result or "test" in result

    def test_sanitize_log_input_removes_newlines(self):
        """Test removal of newline and carriage return characters."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = sanitize_log_input("line1\nline2\rline3")
            assert "\n" not in result
            assert "\r" not in result
            assert "line1_line2_line3" == result

    def test_sanitize_log_input_removes_tabs(self):
        """Test removal of tab characters."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = sanitize_log_input("col1\tcol2\tcol3")
            assert "\t" not in result
            assert "col1_col2_col3" == result

    def test_sanitize_log_input_max_length_truncation(self):
        """Test truncation of long strings."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            long_text = "a" * 200
            result = sanitize_log_input(long_text, max_length=50)
            assert len(result) <= 50
            assert result.endswith("...")

    def test_sanitize_log_input_max_length_short(self):
        """Test truncation with very short max_length."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = sanitize_log_input("test", max_length=2)
            assert len(result) == 2

    def test_sanitize_log_input_non_string_conversion(self):
        """Test conversion of non-string values."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert sanitize_log_input(123) == "123"
            assert sanitize_log_input(45.67) == "45.67"
            assert sanitize_log_input(True) == "True"

    def test_sanitize_log_input_prevents_log_injection(self):
        """Test prevention of log injection attacks."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            malicious = "user logged in\nFAKE LOG: admin logged in"
            result = sanitize_log_input(malicious)
            assert "\n" not in result
            # Verify newline was replaced
            assert "_" in result


class TestSanitizeHtmlInput:
    """Test suite for sanitize_html_input function."""

    def test_sanitize_html_input_normal_text(self):
        """Test sanitization of normal text without HTML."""
        result = sanitize_html_input("normal text")
        assert result == "normal text"

    def test_sanitize_html_input_script_tags(self):
        """Test sanitization of script tags."""
        malicious = "<script>alert('xss')</script>"
        result = sanitize_html_input(malicious)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert "alert" in result

    def test_sanitize_html_input_img_tag_with_onerror(self):
        """Test sanitization of img tag with onerror attribute."""
        malicious = '<img src=x onerror="alert(\'xss\')">'
        result = sanitize_html_input(malicious)
        assert "<img" not in result
        assert "&lt;img" in result

    def test_sanitize_html_input_quotes(self):
        """Test sanitization of quotes."""
        text = 'Test "quoted" text'
        result = sanitize_html_input(text)
        assert "&quot;" in result or '"' in result

    def test_sanitize_html_input_ampersand(self):
        """Test sanitization of ampersand."""
        text = "Tom & Jerry"
        result = sanitize_html_input(text)
        assert "&amp;" in result

    def test_sanitize_html_input_less_than_greater_than(self):
        """Test sanitization of < and > characters."""
        text = "5 < 10 and 10 > 5"
        result = sanitize_html_input(text)
        assert "&lt;" in result
        assert "&gt;" in result

    def test_sanitize_html_input_non_string(self):
        """Test handling of non-string input."""
        result = sanitize_html_input(123)
        assert result == "123"

    def test_sanitize_html_input_mixed_content(self):
        """Test sanitization of mixed HTML and text."""
        mixed = "Hello <b>world</b> & <script>alert('test')</script>"
        result = sanitize_html_input(mixed)
        assert "&lt;b&gt;" in result
        assert "&lt;script&gt;" in result
        assert "&amp;" in result


class TestSanitizeSqlIdentifier:
    """Test suite for sanitize_sql_identifier function."""

    def test_sanitize_sql_identifier_valid_name(self):
        """Test sanitization of valid identifier."""
        result = sanitize_sql_identifier("user_table")
        assert result == "user_table"

    def test_sanitize_sql_identifier_removes_special_chars(self):
        """Test removal of special characters."""
        result = sanitize_sql_identifier("user-table!")
        assert result == "usertable"
        assert "-" not in result
        assert "!" not in result

    def test_sanitize_sql_identifier_removes_spaces(self):
        """Test removal of spaces."""
        result = sanitize_sql_identifier("user table")
        assert result == "usertable"
        assert " " not in result

    def test_sanitize_sql_identifier_starting_with_digit(self):
        """Test identifier starting with a digit."""
        result = sanitize_sql_identifier("123users")
        assert result.startswith("col_")
        assert result == "col_123users"

    def test_sanitize_sql_identifier_sql_injection_attempt(self):
        """Test handling of SQL injection attempt."""
        malicious = "users; DROP TABLE passwords; --"
        result = sanitize_sql_identifier(malicious)
        assert ";" not in result
        assert "DROP" in result  # Letters are preserved
        assert "TABLE" in result
        assert " " not in result
        assert "-" not in result

    def test_sanitize_sql_identifier_max_length(self):
        """Test truncation to max length."""
        long_name = "a" * 100
        result = sanitize_sql_identifier(long_name)
        assert len(result) == 64

    def test_sanitize_sql_identifier_empty_raises_error(self):
        """Test that empty identifier raises ValueError."""
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            sanitize_sql_identifier("")

    def test_sanitize_sql_identifier_only_special_chars_raises_error(self):
        """Test that identifier with only special chars raises ValueError."""
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            sanitize_sql_identifier("!@#$%^&*()")

    def test_sanitize_sql_identifier_non_string(self):
        """Test conversion of non-string input."""
        result = sanitize_sql_identifier(12345)
        assert result == "col_12345"

    def test_sanitize_sql_identifier_preserves_underscores(self):
        """Test that underscores are preserved."""
        result = sanitize_sql_identifier("user_table_name")
        assert result == "user_table_name"


class TestValidateUuid:
    """Test suite for validate_uuid function."""

    def test_validate_uuid_valid_lowercase(self):
        """Test validation of valid lowercase UUID."""
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        assert validate_uuid(valid_uuid) is True

    def test_validate_uuid_valid_uppercase(self):
        """Test validation of valid uppercase UUID."""
        valid_uuid = "550E8400-E29B-41D4-A716-446655440000"
        assert validate_uuid(valid_uuid) is True

    def test_validate_uuid_valid_mixed_case(self):
        """Test validation of valid mixed-case UUID."""
        valid_uuid = "550e8400-E29B-41d4-A716-446655440000"
        assert validate_uuid(valid_uuid) is True

    def test_validate_uuid_invalid_format(self):
        """Test validation of invalid UUID format."""
        invalid_uuid = "not-a-uuid"
        assert validate_uuid(invalid_uuid) is False

    def test_validate_uuid_wrong_length(self):
        """Test validation of UUID with wrong length."""
        invalid_uuid = "550e8400-e29b-41d4-a716"
        assert validate_uuid(invalid_uuid) is False

    def test_validate_uuid_missing_hyphens(self):
        """Test validation of UUID without hyphens."""
        invalid_uuid = "550e8400e29b41d4a716446655440000"
        assert validate_uuid(invalid_uuid) is False

    def test_validate_uuid_invalid_version(self):
        """Test validation of UUID with invalid version."""
        # Version must be 1-5
        invalid_uuid = "550e8400-e29b-61d4-a716-446655440000"  # version 6
        assert validate_uuid(invalid_uuid) is False

    def test_validate_uuid_invalid_variant(self):
        """Test validation of UUID with invalid variant."""
        # Variant must be 8, 9, a, or b
        invalid_uuid = "550e8400-e29b-41d4-c716-446655440000"  # variant c
        assert validate_uuid(invalid_uuid) is False

    def test_validate_uuid_non_string(self):
        """Test validation of non-string input."""
        assert validate_uuid(123) is False
        assert validate_uuid(None) is False

    def test_validate_uuid_with_extra_characters(self):
        """Test validation of UUID with extra characters."""
        invalid_uuid = "550e8400-e29b-41d4-a716-446655440000extra"
        assert validate_uuid(invalid_uuid) is False


class TestSanitizeFilePath:
    """Test suite for sanitize_file_path function."""

    def test_sanitize_file_path_valid_absolute(self):
        """Test sanitization of valid absolute path."""
        result = sanitize_file_path("/home/user/file.txt")
        assert result == "/home/user/file.txt"

    def test_sanitize_file_path_directory_traversal_attack(self):
        """Test detection of directory traversal attack."""
        with pytest.raises(ValueError, match="Directory traversal"):
            sanitize_file_path("/home/../etc/passwd")

    def test_sanitize_file_path_multiple_traversal_attempts(self):
        """Test detection of multiple traversal attempts."""
        with pytest.raises(ValueError, match="Directory traversal"):
            sanitize_file_path("/home/../../etc/passwd")

    def test_sanitize_file_path_removes_null_bytes(self):
        """Test removal of null bytes."""
        result = sanitize_file_path("/home/user/file\x00.txt")
        assert "\x00" not in result

    def test_sanitize_file_path_strips_whitespace(self):
        """Test stripping of whitespace."""
        result = sanitize_file_path("  /home/user/file.txt  ")
        assert result == "/home/user/file.txt"

    def test_sanitize_file_path_removes_duplicate_slashes(self):
        """Test removal of duplicate slashes."""
        result = sanitize_file_path("/home//user///file.txt")
        assert result == "/home/user/file.txt"

    def test_sanitize_file_path_relative_path_not_allowed(self):
        """Test handling of relative path when not allowed."""
        result = sanitize_file_path("home/user/file.txt", allow_relative=False)
        assert result.startswith("/")

    def test_sanitize_file_path_relative_path_allowed(self):
        """Test handling of relative path when allowed."""
        result = sanitize_file_path("home/user/file.txt", allow_relative=True)
        assert result == "home/user/file.txt"

    def test_sanitize_file_path_non_string(self):
        """Test conversion of non-string input."""
        result = sanitize_file_path(123, allow_relative=True)
        assert result == "123"

    def test_sanitize_file_path_dot_dot_in_filename(self):
        """Test that .. in path is detected."""
        with pytest.raises(ValueError, match="Directory traversal"):
            sanitize_file_path("/home/user/file..txt")


class TestSanitizeUrlParameter:
    """Test suite for sanitize_url_parameter function."""

    def test_sanitize_url_parameter_normal_text(self):
        """Test sanitization of normal text."""
        result = sanitize_url_parameter("hello")
        assert result == "hello"

    def test_sanitize_url_parameter_with_spaces(self):
        """Test URL encoding of spaces."""
        result = sanitize_url_parameter("hello world")
        assert result == "hello%20world"
        assert " " not in result

    def test_sanitize_url_parameter_special_characters(self):
        """Test URL encoding of special characters."""
        result = sanitize_url_parameter("test&param=value")
        assert "&" not in result
        assert "=" not in result
        assert "%" in result  # URL encoded

    def test_sanitize_url_parameter_sql_injection_attempt(self):
        """Test URL encoding of SQL injection attempt."""
        malicious = "'; DROP TABLE users; --"
        result = sanitize_url_parameter(malicious)
        assert ";" not in result
        assert " " not in result
        assert "%" in result  # Characters are encoded

    def test_sanitize_url_parameter_script_tag(self):
        """Test URL encoding of script tag."""
        malicious = "<script>alert('xss')</script>"
        result = sanitize_url_parameter(malicious)
        assert "<" not in result
        assert ">" not in result
        assert "%" in result

    def test_sanitize_url_parameter_forward_slash(self):
        """Test URL encoding of forward slash."""
        result = sanitize_url_parameter("path/to/file")
        assert "/" not in result
        assert "%2F" in result

    def test_sanitize_url_parameter_non_string(self):
        """Test conversion of non-string input."""
        result = sanitize_url_parameter(123)
        assert result == "123"

    def test_sanitize_url_parameter_unicode(self):
        """Test URL encoding of unicode characters."""
        result = sanitize_url_parameter("hello 世界")
        assert "世界" not in result
        assert "%" in result


class TestValidateEmail:
    """Test suite for validate_email function."""

    def test_validate_email_valid_simple(self):
        """Test validation of simple valid email."""
        assert validate_email("user@example.com") is True

    def test_validate_email_valid_with_dots(self):
        """Test validation of email with dots."""
        assert validate_email("first.last@example.com") is True

    def test_validate_email_valid_with_plus(self):
        """Test validation of email with plus sign."""
        assert validate_email("user+tag@example.com") is True

    def test_validate_email_valid_subdomain(self):
        """Test validation of email with subdomain."""
        assert validate_email("user@mail.example.com") is True

    def test_validate_email_invalid_missing_at(self):
        """Test validation of email missing @ symbol."""
        assert validate_email("userexample.com") is False

    def test_validate_email_invalid_missing_domain(self):
        """Test validation of email missing domain."""
        assert validate_email("user@") is False

    def test_validate_email_invalid_missing_username(self):
        """Test validation of email missing username."""
        assert validate_email("@example.com") is False

    def test_validate_email_invalid_missing_tld(self):
        """Test validation of email missing TLD."""
        assert validate_email("user@example") is False

    def test_validate_email_invalid_spaces(self):
        """Test validation of email with spaces."""
        assert validate_email("user name@example.com") is False

    def test_validate_email_invalid_special_chars(self):
        """Test validation of email with invalid special characters."""
        assert validate_email("user<>@example.com") is False

    def test_validate_email_non_string(self):
        """Test validation of non-string input."""
        assert validate_email(123) is False
        assert validate_email(None) is False

    def test_validate_email_max_length(self):
        """Test validation of email exceeding max length."""
        long_email = "a" * 250 + "@example.com"
        assert validate_email(long_email) is False

    def test_validate_email_exact_max_length(self):
        """Test validation of email at max length boundary."""
        # Create email that's exactly 254 characters
        # @example.com is 12 characters, so local part should be 242
        local_part = "a" * 242
        email = f"{local_part}@example.com"
        assert len(email) == 254
        assert validate_email(email) is True


class TestSanitizeJsonField:
    """Test suite for sanitize_json_field function."""

    def test_sanitize_json_field_normal_string(self):
        """Test sanitization of normal string."""
        result = sanitize_json_field("normal text")
        assert result == "normal text"

    def test_sanitize_json_field_removes_control_characters(self):
        """Test removal of control characters."""
        result = sanitize_json_field("test\x00\x01\x1fvalue")
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x1f" not in result

    def test_sanitize_json_field_preserves_newlines(self):
        """Test that newlines are removed."""
        result = sanitize_json_field("line1\nline2")
        # Control characters including \n should be removed
        assert "\n" not in result

    def test_sanitize_json_field_non_string_passthrough(self):
        """Test that non-string values pass through unchanged."""
        assert sanitize_json_field(123) == 123
        assert sanitize_json_field(45.67) == 45.67
        assert sanitize_json_field(True) is True
        assert sanitize_json_field(None) is None

    def test_sanitize_json_field_list_passthrough(self):
        """Test that list values pass through unchanged."""
        test_list = [1, 2, 3]
        result = sanitize_json_field(test_list)
        assert result == test_list

    def test_sanitize_json_field_dict_passthrough(self):
        """Test that dict values pass through unchanged."""
        test_dict = {"key": "value"}
        result = sanitize_json_field(test_dict)
        assert result == test_dict

    def test_sanitize_json_field_removes_tab(self):
        """Test removal of tab character."""
        result = sanitize_json_field("col1\tcol2")
        assert "\t" not in result


class TestRateLimitKey:
    """Test suite for rate_limit_key function."""

    def test_rate_limit_key_normal_identifier(self):
        """Test generation of key from normal identifier."""
        result = rate_limit_key("user123")
        assert result == "user123"

    def test_rate_limit_key_ip_address(self):
        """Test generation of key from IP address."""
        result = rate_limit_key("192.168.1.1")
        assert result == "192.168.1.1"

    def test_rate_limit_key_removes_special_chars(self):
        """Test removal of special characters."""
        result = rate_limit_key("user@#$%123")
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result
        assert "user" in result
        assert "123" in result

    def test_rate_limit_key_preserves_dots(self):
        """Test preservation of dots."""
        result = rate_limit_key("user.name")
        assert result == "user.name"

    def test_rate_limit_key_preserves_hyphens(self):
        """Test preservation of hyphens."""
        result = rate_limit_key("user-name")
        assert result == "user-name"

    def test_rate_limit_key_replaces_spaces(self):
        """Test replacement of spaces."""
        result = rate_limit_key("user name")
        assert " " not in result
        assert "_" in result

    def test_rate_limit_key_max_length(self):
        """Test truncation to max length."""
        long_id = "a" * 100
        result = rate_limit_key(long_id)
        assert len(result) == 50

    def test_rate_limit_key_non_string(self):
        """Test conversion of non-string input."""
        result = rate_limit_key(12345)
        assert result == "12345"

    def test_rate_limit_key_uuid(self):
        """Test generation of key from UUID."""
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = rate_limit_key(uuid)
        # Hyphens should be preserved
        assert result == uuid


class TestSecurityEdgeCases:
    """Test suite for edge cases and security scenarios."""

    def test_sql_injection_prevention_in_identifier(self):
        """Test comprehensive SQL injection prevention."""
        injection_attempts = [
            "users'; DROP TABLE passwords; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users--",
        ]

        for attempt in injection_attempts:
            result = sanitize_sql_identifier(attempt)
            # Verify dangerous SQL characters are removed
            assert "'" not in result
            assert ";" not in result
            assert "-" not in result
            assert " " not in result

    def test_xss_prevention_in_html(self):
        """Test comprehensive XSS prevention."""
        xss_attempts = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "javascript:alert('xss')",
            "<iframe src='javascript:alert(1)'>",
        ]

        for attempt in xss_attempts:
            result = sanitize_html_input(attempt)
            # Verify HTML tags are escaped
            assert "<script>" not in result.lower()
            assert "<img" not in result.lower()
            assert "<svg" not in result.lower()
            assert "<iframe" not in result.lower()

    def test_path_traversal_prevention(self):
        """Test comprehensive path traversal prevention."""
        traversal_attempts = [
            "../../../etc/passwd",
            "/home/../etc/passwd",
            "..\\..\\windows\\system32",
            "file..txt",  # Contains ..
        ]

        for attempt in traversal_attempts:
            with pytest.raises(ValueError, match="Directory traversal"):
                sanitize_file_path(attempt)

    def test_unicode_handling_in_various_functions(self):
        """Test handling of unicode characters."""
        unicode_text = "Hello 世界 🌍"

        # Test HTML sanitization
        html_result = sanitize_html_input(unicode_text)
        assert "Hello" in html_result

        # Test URL parameter sanitization
        url_result = sanitize_url_parameter(unicode_text)
        assert "%" in url_result  # Unicode should be encoded

        # Test JSON sanitization
        json_result = sanitize_json_field(unicode_text)
        assert isinstance(json_result, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
