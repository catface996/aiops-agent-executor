"""LLM Client for invoking language models.

This module provides a unified interface for calling different LLM providers.
Currently uses mock responses - will be replaced with real API calls when keys are provided.
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any


@dataclass
class LLMMessage:
    """A message in the conversation."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    content: str
    model: str
    provider: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    response_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""

    tool_id: str
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponseWithTools:
    """Response from an LLM call that may include tool calls."""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    response_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse | LLMResponseWithTools:
        """Send a chat completion request."""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ):
        """Stream a chat completion request. Yields chunks of text."""
        pass


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing and development.

    Returns predefined responses based on the system prompt and user message.
    Will be replaced with real API calls when LLM keys are provided.
    """

    # Mock response templates based on agent roles
    MOCK_RESPONSES = {
        "analyzer": "Based on my analysis, I found the following issues:\n1. High CPU usage on server-01\n2. Memory leak detected in the application\n3. Database connection timeout errors\n\nRecommendation: Scale up resources and restart the affected services.",
        "coordinator": "I will coordinate the following tasks:\n1. Assign log analysis to Agent-1\n2. Assign metrics collection to Agent-2\n3. Aggregate results and generate report\n\nProceeding with task distribution.",
        "db-analyzer": "Database analysis complete:\n- Query performance: 85% within SLA\n- Slow queries identified: 3\n- Index recommendations: Add index on users.email\n- Connection pool status: Healthy",
        "log-analyzer": "Log analysis results:\n- Total logs processed: 10,000\n- Errors found: 15\n- Warnings found: 45\n- Critical patterns: Connection refused errors at 14:30",
        "default": "Task completed successfully. I have processed the request and generated the following output based on the provided context.",
    }

    def __init__(self, delay_seconds: float = 0.5):
        """Initialize mock client with optional delay to simulate API latency.

        Args:
            delay_seconds: Simulated API response delay
        """
        self.delay_seconds = delay_seconds
        self.call_count = 0

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Return a mock chat response."""
        self.call_count += 1

        # Simulate API latency
        await asyncio.sleep(self.delay_seconds)

        # Extract role from system prompt
        role = self._extract_role(messages)

        # Generate response based on role
        response_content = self._generate_response(role, messages)

        return LLMResponse(
            content=response_content,
            model=model,
            provider="mock",
            usage={
                "prompt_tokens": sum(len(m.content.split()) for m in messages) * 2,
                "completion_tokens": len(response_content.split()) * 2,
                "total_tokens": sum(len(m.content.split()) for m in messages) * 2
                + len(response_content.split()) * 2,
            },
            finish_reason="stop",
        )

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ):
        """Stream a mock chat response, yielding chunks of text."""
        self.call_count += 1

        # Extract role and generate full response
        role = self._extract_role(messages)
        full_response = self._generate_response(role, messages)

        # Simulate streaming by yielding words
        words = full_response.split()
        for i, word in enumerate(words):
            await asyncio.sleep(self.delay_seconds / len(words))
            yield word + (" " if i < len(words) - 1 else "")

    def _extract_role(self, messages: list[LLMMessage]) -> str:
        """Extract the agent role from system prompt."""
        for msg in messages:
            if msg.role == "system":
                content_lower = msg.content.lower()
                for role in self.MOCK_RESPONSES:
                    if role in content_lower:
                        return role
        return "default"

    def _generate_response(self, role: str, messages: list[LLMMessage]) -> str:
        """Generate a mock response based on role and context."""
        base_response = self.MOCK_RESPONSES.get(role, self.MOCK_RESPONSES["default"])

        # Add context from user message if available
        user_messages = [m for m in messages if m.role == "user"]
        if user_messages:
            last_user_msg = user_messages[-1].content
            if "error" in last_user_msg.lower():
                base_response = f"Investigating the error: {last_user_msg[:100]}...\n\n{base_response}"

        return base_response


class LLMClientFactory:
    """Factory for creating LLM clients based on provider."""

    _clients: dict[str, BaseLLMClient] = {}
    _use_mock: bool = True  # Set to False when real API keys are available

    @classmethod
    def get_client(cls, provider: str, **kwargs) -> BaseLLMClient:
        """Get or create an LLM client for the specified provider.

        Args:
            provider: The LLM provider name (e.g., "openai", "anthropic", "bedrock")
            **kwargs: Additional configuration for the client

        Returns:
            An LLM client instance
        """
        if cls._use_mock:
            # Return mock client for all providers during development
            if "mock" not in cls._clients:
                cls._clients["mock"] = MockLLMClient()
            return cls._clients["mock"]

        # TODO: Implement real clients when API keys are available
        # if provider == "openai":
        #     return OpenAIClient(**kwargs)
        # elif provider == "anthropic":
        #     return AnthropicClient(**kwargs)
        # elif provider == "bedrock":
        #     return BedrockClient(**kwargs)

        # Default to mock for unknown providers
        if "mock" not in cls._clients:
            cls._clients["mock"] = MockLLMClient()
        return cls._clients["mock"]

    @classmethod
    def set_use_mock(cls, use_mock: bool) -> None:
        """Enable or disable mock mode.

        Args:
            use_mock: If True, always return mock clients
        """
        cls._use_mock = use_mock

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached clients."""
        cls._clients.clear()
