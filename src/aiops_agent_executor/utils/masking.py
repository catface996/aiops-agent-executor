"""Sensitive data masking utilities.

Provides functions to mask API keys and other sensitive data in responses.
"""

import re
from typing import Any


# Patterns for common API key formats
API_KEY_PATTERNS = [
    # OpenAI API keys: sk-... or sk-proj-...
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "sk-***"),
    (re.compile(r"sk-proj-[a-zA-Z0-9]{20,}"), "sk-proj-***"),
    # Anthropic API keys: sk-ant-...
    (re.compile(r"sk-ant-[a-zA-Z0-9-]{20,}"), "sk-ant-***"),
    # AWS access keys
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA***"),
    # Generic Bearer tokens
    (re.compile(r"Bearer\s+[a-zA-Z0-9._-]{20,}"), "Bearer ***"),
    # Generic API key pattern (long alphanumeric strings)
    (re.compile(r"(?:api[_-]?key|apikey|token)[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_-]{20,})[\"']?", re.IGNORECASE), "***"),
]


def mask_sensitive_data(data: dict[str, Any] | list[Any] | str | Any) -> Any:
    """Mask sensitive data in a dictionary, list, or string.

    Recursively processes nested structures and masks API keys
    matching known patterns.

    Args:
        data: Data to process (dict, list, string, or other)

    Returns:
        Data with sensitive information masked
    """
    if isinstance(data, dict):
        return {key: mask_sensitive_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    elif isinstance(data, str):
        return _mask_string(data)
    else:
        return data


def _mask_string(text: str) -> str:
    """Mask sensitive patterns in a string.

    Args:
        text: String to process

    Returns:
        String with sensitive patterns masked
    """
    result = text

    for pattern, replacement in API_KEY_PATTERNS:
        result = pattern.sub(replacement, result)

    return result


def mask_api_key(api_key: str, visible_chars: int = 4) -> str:
    """Mask an API key showing only the last few characters.

    Args:
        api_key: The API key to mask
        visible_chars: Number of characters to show at the end

    Returns:
        Masked API key like '***xxxx'
    """
    if not api_key:
        return ""

    if len(api_key) <= visible_chars:
        return "*" * len(api_key)

    masked_length = len(api_key) - visible_chars
    return "*" * masked_length + api_key[-visible_chars:]


def is_sensitive_key(key: str) -> bool:
    """Check if a dictionary key likely contains sensitive data.

    Args:
        key: Dictionary key name

    Returns:
        True if the key likely contains sensitive data
    """
    sensitive_keywords = [
        "api_key",
        "apikey",
        "api-key",
        "secret",
        "password",
        "token",
        "credential",
        "auth",
        "bearer",
        "private",
    ]

    key_lower = key.lower()
    return any(keyword in key_lower for keyword in sensitive_keywords)
