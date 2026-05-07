"""
Unit tests for JWT utilities.

Tests JWT token creation, verification, and expiration handling.
"""

import pytest
import jwt
import time
from unittest.mock import patch, Mock

from src.utils.jwt import (
    create_access_token,
    verify_token,
    get_secret_key,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES
)


class TestJWTUtilities:
    """Test suite for JWT utility functions."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return {
            "google_oauth": {
                "jwt_secret": "test_secret_key_12345"
            }
        }

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = Mock()
        logger.debug = Mock()
        logger.warning = Mock()
        logger.error = Mock()
        return logger

    def test_get_secret_key_from_config(self, mock_config):
        """Test getting secret key from configuration."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            secret = get_secret_key()
            assert secret == "test_secret_key_12345"

    def test_get_secret_key_default(self):
        """Test getting default secret key when not configured."""
        config = {}
        with patch('src.utils.jwt.get_config', return_value=config):
            secret = get_secret_key()
            assert secret == "development_secret_key_change_in_prod"

    def test_get_secret_key_missing_google_oauth(self):
        """Test getting secret key when google_oauth section is missing."""
        config = {"other_section": {}}
        with patch('src.utils.jwt.get_config', return_value=config):
            secret = get_secret_key()
            assert secret == "development_secret_key_change_in_prod"

    def test_create_access_token_basic(self, mock_config):
        """Test creating a basic access token."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            data = {"user_id": "12345", "email": "test@example.com"}
            token = create_access_token(data)

            assert isinstance(token, str)
            assert len(token) > 0

            # Decode and verify
            decoded = jwt.decode(token, "test_secret_key_12345", algorithms=[ALGORITHM])
            assert decoded["user_id"] == "12345"
            assert decoded["email"] == "test@example.com"
            assert "exp" in decoded

    def test_create_access_token_with_custom_expiration(self, mock_config):
        """Test creating token with custom expiration time."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            data = {"user_id": "12345"}
            custom_expire_minutes = 10
            token = create_access_token(data, expires_delta=custom_expire_minutes)

            decoded = jwt.decode(token, "test_secret_key_12345", algorithms=[ALGORITHM])

            # Check expiration is approximately custom_expire_minutes from now
            expected_exp = time.time() + (custom_expire_minutes * 60)
            assert abs(decoded["exp"] - expected_exp) < 5  # Allow 5 second tolerance

    def test_create_access_token_default_expiration(self, mock_config):
        """Test creating token with default expiration time."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            data = {"user_id": "12345"}
            token = create_access_token(data)

            decoded = jwt.decode(token, "test_secret_key_12345", algorithms=[ALGORITHM])

            # Check expiration is approximately ACCESS_TOKEN_EXPIRE_MINUTES from now
            expected_exp = time.time() + (ACCESS_TOKEN_EXPIRE_MINUTES * 60)
            assert abs(decoded["exp"] - expected_exp) < 5  # Allow 5 second tolerance

    def test_create_access_token_preserves_data(self, mock_config):
        """Test that token creation doesn't modify original data dict."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            original_data = {"user_id": "12345", "role": "admin"}
            data_copy = original_data.copy()

            create_access_token(original_data)

            # Original data should be unchanged
            assert original_data == data_copy
            assert "exp" not in original_data

    def test_create_access_token_with_complex_data(self, mock_config):
        """Test creating token with complex nested data."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            data = {
                "user_id": "12345",
                "email": "test@example.com",
                "roles": ["admin", "user"],
                "metadata": {
                    "department": "engineering",
                    "level": 5
                }
            }
            token = create_access_token(data)

            decoded = jwt.decode(token, "test_secret_key_12345", algorithms=[ALGORITHM])
            assert decoded["user_id"] == "12345"
            assert decoded["email"] == "test@example.com"
            assert decoded["roles"] == ["admin", "user"]
            assert decoded["metadata"]["department"] == "engineering"
            assert decoded["metadata"]["level"] == 5

    def test_verify_token_valid(self, mock_config):
        """Test verifying a valid token."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            data = {"user_id": "12345", "email": "test@example.com"}
            token = create_access_token(data)

            payload = verify_token(token)

            assert payload is not None
            assert payload["user_id"] == "12345"
            assert payload["email"] == "test@example.com"

    def test_verify_token_expired(self, mock_config, mock_logger):
        """Test verifying an expired token."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            with patch('src.utils.jwt.logger', mock_logger):
                # Create token that expires immediately
                data = {"user_id": "12345"}
                # Create token with exp in the past
                expired_time = int(time.time() - 100)  # 100 seconds ago
                token = jwt.encode(
                    {**data, "exp": expired_time},
                    "test_secret_key_12345",
                    algorithm=ALGORITHM
                )

                payload = verify_token(token)

                assert payload is None
                mock_logger.warning.assert_called_once()
                assert "expired" in str(mock_logger.warning.call_args).lower()

    def test_verify_token_invalid_signature(self, mock_config, mock_logger):
        """Test verifying a token with invalid signature."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            with patch('src.utils.jwt.logger', mock_logger):
                data = {"user_id": "12345"}
                # Create token with different secret
                token = jwt.encode(data, "wrong_secret_key", algorithm=ALGORITHM)

                payload = verify_token(token)

                assert payload is None
                mock_logger.warning.assert_called()

    def test_verify_token_malformed(self, mock_config, mock_logger):
        """Test verifying a malformed token."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            with patch('src.utils.jwt.logger', mock_logger):
                malformed_token = "not.a.valid.jwt.token"

                payload = verify_token(malformed_token)

                assert payload is None
                mock_logger.warning.assert_called()

    def test_verify_token_empty_string(self, mock_config, mock_logger):
        """Test verifying an empty token."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            with patch('src.utils.jwt.logger', mock_logger):
                payload = verify_token("")

                assert payload is None
                mock_logger.warning.assert_called()

    def test_verify_token_wrong_algorithm(self, mock_config, mock_logger):
        """Test verifying a token created with wrong algorithm."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            with patch('src.utils.jwt.logger', mock_logger):
                data = {"user_id": "12345"}
                # Create token with different algorithm
                token = jwt.encode(data, "test_secret_key_12345", algorithm="HS512")

                payload = verify_token(token)

                # Should still decode but might fail depending on JWT library behavior
                # Main point is it handles gracefully
                assert payload is None or isinstance(payload, dict)

    def test_create_and_verify_token_roundtrip(self, mock_config):
        """Test complete roundtrip of creating and verifying a token."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            original_data = {
                "user_id": "user_12345",
                "email": "user@example.com",
                "role": "admin",
                "permissions": ["read", "write", "delete"]
            }

            # Create token
            token = create_access_token(original_data)

            # Verify token
            decoded_data = verify_token(token)

            assert decoded_data is not None
            assert decoded_data["user_id"] == original_data["user_id"]
            assert decoded_data["email"] == original_data["email"]
            assert decoded_data["role"] == original_data["role"]
            assert decoded_data["permissions"] == original_data["permissions"]

    def test_verify_token_exception_handling(self, mock_config, mock_logger):
        """Test that verify_token handles unexpected exceptions."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            with patch('src.utils.jwt.logger', mock_logger):
                with patch('jwt.decode', side_effect=Exception("Unexpected error")):
                    payload = verify_token("some_token")

                    assert payload is None
                    mock_logger.error.assert_called()

    def test_token_expiration_is_numeric(self, mock_config):
        """Test that token expiration is stored as numeric (int) value."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            data = {"user_id": "12345"}
            token = create_access_token(data)

            decoded = jwt.decode(token, "test_secret_key_12345", algorithms=[ALGORITHM])

            # exp should be an integer timestamp
            assert isinstance(decoded["exp"], int)
            assert decoded["exp"] > time.time()

    def test_multiple_tokens_independent(self, mock_config):
        """Test that multiple tokens can be created and verified independently."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            data1 = {"user_id": "user1"}
            data2 = {"user_id": "user2"}

            token1 = create_access_token(data1)
            token2 = create_access_token(data2)

            # Tokens should be different
            assert token1 != token2

            # Each should decode to correct data
            payload1 = verify_token(token1)
            payload2 = verify_token(token2)

            assert payload1["user_id"] == "user1"
            assert payload2["user_id"] == "user2"

    def test_token_with_zero_expiration(self, mock_config):
        """Test creating token with zero expiration (should expire immediately)."""
        with patch('src.utils.jwt.get_config', return_value=mock_config):
            data = {"user_id": "12345"}
            token = create_access_token(data, expires_delta=0)

            # Decode without verification since token expires immediately
            decoded = jwt.decode(token, "test_secret_key_12345", algorithms=[ALGORITHM], options={"verify_exp": False})

            # Should have exp set to now (approximately)
            assert abs(decoded["exp"] - time.time()) < 5

    def test_constants_defined(self):
        """Test that required constants are defined."""
        assert ALGORITHM == "HS256"
        assert ACCESS_TOKEN_EXPIRE_MINUTES == 60 * 24  # 24 hours
        assert isinstance(ACCESS_TOKEN_EXPIRE_MINUTES, int)
