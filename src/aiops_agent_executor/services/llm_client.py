"""LLM Client for invoking language models using LangChain.

This module provides a unified interface for calling different LLM providers
using LangChain's ChatModel implementations. Supports OpenAI, Anthropic,
and OpenRouter (via OpenAI-compatible API).
"""

import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class LLMMessage:
    """A message in the conversation."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""

    tool_id: str
    tool_name: str
    arguments: dict[str, Any]


# =============================================================================
# Base Client
# =============================================================================

class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def stream(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str | ToolCall]:
        """Stream a chat completion. Yields text chunks or tool calls."""
        pass


# =============================================================================
# LangChain-based Clients
# =============================================================================

class LangChainClient(BaseLLMClient):
    """LLM client using LangChain's ChatModel.

    Base class for all LangChain-based clients.
    Subclasses implement _create_chat_model to return the appropriate model.
    """

    def __init__(self, provider: str = "langchain"):
        self._provider = provider

    def _convert_messages(self, messages: list[LLMMessage]) -> list[BaseMessage]:
        """Convert LLMMessage to LangChain message format."""
        result = []
        for msg in messages:
            if msg.role == "system":
                result.append(SystemMessage(content=msg.content))
            elif msg.role == "user":
                result.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                result.append(AIMessage(content=msg.content))
            else:
                result.append(HumanMessage(content=msg.content))
        return result

    def _create_chat_model(
        self,
        model: str,
        temperature: float,
        max_tokens: int | None,
    ) -> BaseChatModel:
        """Create a LangChain ChatModel. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement _create_chat_model")

    async def stream(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str | ToolCall]:
        """Stream a chat completion.

        Yields:
            str: Text content chunks
            ToolCall: Tool call when LLM requests a tool
        """
        chat_model = self._create_chat_model(model, temperature, max_tokens)
        langchain_messages = self._convert_messages(messages)

        if tools:
            chat_model = chat_model.bind_tools(tools)

        async for chunk in chat_model.astream(langchain_messages):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content

            if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                for tc in chunk.tool_calls:
                    yield ToolCall(
                        tool_id=tc.get("id", str(uuid.uuid4())),
                        tool_name=tc.get("name", ""),
                        arguments=tc.get("args", {}),
                    )

    async def complete(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[str, list[ToolCall]]:
        """Get complete response (collects all stream chunks).

        Returns:
            Tuple of (content, tool_calls)
        """
        content_parts = []
        tool_calls = []

        async for chunk in self.stream(messages, model, temperature, max_tokens, tools):
            if isinstance(chunk, str):
                content_parts.append(chunk)
            elif isinstance(chunk, ToolCall):
                tool_calls.append(chunk)

        return "".join(content_parts), tool_calls


class OpenAICompatibleClient(LangChainClient):
    """Client for OpenAI-compatible APIs.

    Works with: OpenAI, OpenRouter, Azure OpenAI, vLLM, Ollama, etc.
    """

    def __init__(self, api_key: str, base_url: str | None = None):
        super().__init__(provider="openai")
        self._api_key = api_key
        self._base_url = base_url

    def _create_chat_model(
        self,
        model: str,
        temperature: float,
        max_tokens: int | None,
    ) -> BaseChatModel:
        kwargs = {
            "model": model,
            "temperature": temperature,
            "api_key": self._api_key,
        }
        if self._base_url:
            kwargs["base_url"] = self._base_url
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        return ChatOpenAI(**kwargs)


class AnthropicClient(LangChainClient):
    """Client for Anthropic API."""

    def __init__(self, api_key: str):
        super().__init__(provider="anthropic")
        self._api_key = api_key

    def _create_chat_model(
        self,
        model: str,
        temperature: float,
        max_tokens: int | None,
    ) -> BaseChatModel:
        kwargs = {
            "model": model,
            "temperature": temperature,
            "api_key": self._api_key,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        return ChatAnthropic(**kwargs)


# =============================================================================
# Client Factory
# =============================================================================

# Default base URLs for known providers
PROVIDER_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
}


class LLMClientFactory:
    """Factory for creating LLM clients."""

    @staticmethod
    def create(
        provider: str,
        api_key: str,
        base_url: str | None = None,
    ) -> BaseLLMClient:
        """Create an LLM client.

        Args:
            provider: Provider type (e.g., "openai", "anthropic", "openrouter")
            api_key: API key
            base_url: Optional base URL (overrides default)

        Returns:
            LLM client instance
        """
        provider = provider.lower()

        if provider == "anthropic":
            return AnthropicClient(api_key=api_key)
        else:
            # OpenAI-compatible: openai, openrouter, azure, vllm, ollama, etc.
            url = base_url or PROVIDER_BASE_URLS.get(provider)
            return OpenAICompatibleClient(api_key=api_key, base_url=url)
