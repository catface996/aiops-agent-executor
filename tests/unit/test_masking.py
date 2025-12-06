"""Unit tests for sensitive data masking utilities."""

import pytest

from aiops_agent_executor.utils.masking import (
    is_sensitive_key,
    mask_api_key,
    mask_sensitive_data,
)


class TestMaskSensitiveData:
    """Tests for mask_sensitive_data function."""

    def test_mask_openai_api_key(self):
        """Test masking of OpenAI API keys."""
        data = {"api_key": "sk-1234567890abcdefghijklmnop"}

        result = mask_sensitive_data(data)

        assert "sk-1234567890" not in str(result)
        assert "sk-***" in str(result)

    def test_mask_openai_project_key(self):
        """Test masking of OpenAI project API keys."""
        data = {"key": "sk-proj-1234567890abcdefghijklmnop"}

        result = mask_sensitive_data(data)

        assert "sk-proj-1234567890" not in str(result)
        assert "sk-proj-***" in str(result)

    def test_mask_anthropic_api_key(self):
        """Test masking of Anthropic API keys."""
        data = {"api_key": "sk-ant-api03-abcdefghijklmnopqrstuvwx"}

        result = mask_sensitive_data(data)

        assert "sk-ant-api03-abcd" not in str(result)
        assert "sk-ant-***" in str(result)

    def test_mask_aws_access_key(self):
        """Test masking of AWS access keys."""
        data = {"aws_key": "AKIAIOSFODNN7EXAMPLE"}

        result = mask_sensitive_data(data)

        assert "AKIAIOSFODNN7EXAMPLE" not in str(result)
        assert "AKIA***" in str(result)

    def test_mask_bearer_token(self):
        """Test masking of Bearer tokens."""
        data = {"auth": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}

        result = mask_sensitive_data(data)

        assert "eyJhbGciOi" not in str(result)
        assert "Bearer ***" in str(result)

    def test_mask_nested_dict(self):
        """Test masking in nested dictionaries."""
        data = {
            "outer": {
                "inner": {
                    "api_key": "sk-1234567890abcdefghijklmnop"
                }
            }
        }

        result = mask_sensitive_data(data)

        assert "sk-1234567890" not in str(result)
        assert "sk-***" in str(result["outer"]["inner"]["api_key"])

    def test_mask_list_of_dicts(self):
        """Test masking in list of dictionaries."""
        data = [
            {"api_key": "sk-1234567890abcdefghijklmnop"},
            {"api_key": "sk-0987654321zyxwvutsrqponml"},
        ]

        result = mask_sensitive_data(data)

        assert all("sk-***" in item["api_key"] for item in result)

    def test_mask_string_directly(self):
        """Test masking when input is a string."""
        data = "My API key is sk-1234567890abcdefghijklmnop"

        result = mask_sensitive_data(data)

        assert "sk-1234567890" not in result
        assert "sk-***" in result

    def test_preserve_non_sensitive_data(self):
        """Test that non-sensitive data is preserved."""
        data = {
            "name": "Test User",
            "email": "test@example.com",
            "count": 42,
        }

        result = mask_sensitive_data(data)

        assert result["name"] == "Test User"
        assert result["email"] == "test@example.com"
        assert result["count"] == 42

    def test_handle_none_values(self):
        """Test handling of None values."""
        data = {"api_key": None, "name": "test"}

        result = mask_sensitive_data(data)

        assert result["api_key"] is None
        assert result["name"] == "test"

    def test_handle_empty_dict(self):
        """Test handling of empty dictionary."""
        data = {}

        result = mask_sensitive_data(data)

        assert result == {}

    def test_handle_non_dict_types(self):
        """Test handling of non-dict/list/string types."""
        assert mask_sensitive_data(42) == 42
        assert mask_sensitive_data(3.14) == 3.14
        assert mask_sensitive_data(True) is True
        assert mask_sensitive_data(None) is None


class TestMaskApiKey:
    """Tests for mask_api_key function."""

    def test_mask_with_default_visible_chars(self):
        """Test masking with default 4 visible characters."""
        result = mask_api_key("sk-1234567890abcdef")

        assert result.endswith("cdef")
        assert result.startswith("*")
        assert len(result) == len("sk-1234567890abcdef")

    def test_mask_with_custom_visible_chars(self):
        """Test masking with custom visible characters."""
        result = mask_api_key("sk-1234567890abcdef", visible_chars=8)

        assert result.endswith("90abcdef")
        assert result.startswith("*")

    def test_mask_short_key(self):
        """Test masking when key is shorter than visible chars."""
        result = mask_api_key("abc", visible_chars=4)

        assert result == "***"  # All masked

    def test_mask_empty_key(self):
        """Test masking of empty key."""
        result = mask_api_key("")

        assert result == ""

    def test_mask_equal_length(self):
        """Test masking when key length equals visible chars."""
        result = mask_api_key("abcd", visible_chars=4)

        assert result == "****"


class TestIsSensitiveKey:
    """Tests for is_sensitive_key function."""

    def test_api_key_variations(self):
        """Test detection of API key variations."""
        assert is_sensitive_key("api_key") is True
        assert is_sensitive_key("apikey") is True
        assert is_sensitive_key("api-key") is True
        assert is_sensitive_key("API_KEY") is True

    def test_secret_variations(self):
        """Test detection of secret variations."""
        assert is_sensitive_key("secret") is True
        assert is_sensitive_key("secret_key") is True
        assert is_sensitive_key("client_secret") is True

    def test_password_variations(self):
        """Test detection of password variations."""
        assert is_sensitive_key("password") is True
        assert is_sensitive_key("user_password") is True
        assert is_sensitive_key("PASSWORD") is True

    def test_token_variations(self):
        """Test detection of token variations."""
        assert is_sensitive_key("token") is True
        assert is_sensitive_key("access_token") is True
        assert is_sensitive_key("bearer_token") is True

    def test_non_sensitive_keys(self):
        """Test that non-sensitive keys return False."""
        assert is_sensitive_key("name") is False
        assert is_sensitive_key("email") is False
        assert is_sensitive_key("count") is False
        assert is_sensitive_key("id") is False
