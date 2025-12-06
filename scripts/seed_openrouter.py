#!/usr/bin/env python3
"""Seed script for OpenRouter provider configuration.

This script creates the OpenRouter provider, endpoint, and popular models
in the database using the application's API.

OpenRouter API Documentation: https://openrouter.ai/docs/api/reference/overview
Base URL: https://openrouter.ai/api/v1
Chat Completions Endpoint: POST /chat/completions

Usage:
    # Make sure the server is running first
    python scripts/seed_openrouter.py

    # Or specify a custom base URL
    python scripts/seed_openrouter.py --base-url http://localhost:8000
"""

import argparse
import sys
from decimal import Decimal

import httpx

# Default API base URL
DEFAULT_BASE_URL = "http://localhost:8000"

# OpenRouter configuration
OPENROUTER_CONFIG = {
    "provider": {
        "name": "OpenRouter",
        "type": "openrouter",
        "description": (
            "OpenRouter is an API aggregator that provides unified access to multiple "
            "LLM providers including OpenAI, Anthropic, Google, Meta, and more. "
            "It offers a single API endpoint compatible with the OpenAI API format."
        ),
        "is_active": True,
    },
    "endpoint": {
        "name": "OpenRouter API v1",
        "base_url": "https://openrouter.ai/api/v1",
        "api_version": "v1",
        "region": "global",
        "timeout_connect": 30,
        "timeout_read": 120,
        "retry_count": 3,
        "retry_interval": 1,
        "is_default": True,
        "is_active": True,
    },
    "models": [
        # OpenAI Models
        {
            "model_id": "openai/gpt-4o",
            "name": "GPT-4o",
            "version": "2024-05",
            "type": "chat",
            "context_window": 128000,
            "max_output_tokens": 16384,
            "input_price": "0.0025",
            "output_price": "0.01",
            "capabilities": {"vision": True, "function_calling": True, "json_mode": True},
        },
        {
            "model_id": "openai/gpt-4o-mini",
            "name": "GPT-4o Mini",
            "version": "2024-07",
            "type": "chat",
            "context_window": 128000,
            "max_output_tokens": 16384,
            "input_price": "0.00015",
            "output_price": "0.0006",
            "capabilities": {"vision": True, "function_calling": True, "json_mode": True},
        },
        {
            "model_id": "openai/gpt-4-turbo",
            "name": "GPT-4 Turbo",
            "version": "2024-04",
            "type": "chat",
            "context_window": 128000,
            "max_output_tokens": 4096,
            "input_price": "0.01",
            "output_price": "0.03",
            "capabilities": {"vision": True, "function_calling": True, "json_mode": True},
        },
        # Anthropic Models
        {
            "model_id": "anthropic/claude-3.5-sonnet",
            "name": "Claude 3.5 Sonnet",
            "version": "20241022",
            "type": "chat",
            "context_window": 200000,
            "max_output_tokens": 8192,
            "input_price": "0.003",
            "output_price": "0.015",
            "capabilities": {"vision": True, "function_calling": True},
        },
        {
            "model_id": "anthropic/claude-3-opus",
            "name": "Claude 3 Opus",
            "version": "20240229",
            "type": "chat",
            "context_window": 200000,
            "max_output_tokens": 4096,
            "input_price": "0.015",
            "output_price": "0.075",
            "capabilities": {"vision": True, "function_calling": True},
        },
        {
            "model_id": "anthropic/claude-3-haiku",
            "name": "Claude 3 Haiku",
            "version": "20240307",
            "type": "chat",
            "context_window": 200000,
            "max_output_tokens": 4096,
            "input_price": "0.00025",
            "output_price": "0.00125",
            "capabilities": {"vision": True, "function_calling": True},
        },
        # Google Models
        {
            "model_id": "google/gemini-pro-1.5",
            "name": "Gemini Pro 1.5",
            "version": "2024",
            "type": "chat",
            "context_window": 1000000,
            "max_output_tokens": 8192,
            "input_price": "0.00125",
            "output_price": "0.005",
            "capabilities": {"vision": True, "function_calling": True},
        },
        {
            "model_id": "google/gemini-flash-1.5",
            "name": "Gemini Flash 1.5",
            "version": "2024",
            "type": "chat",
            "context_window": 1000000,
            "max_output_tokens": 8192,
            "input_price": "0.000075",
            "output_price": "0.0003",
            "capabilities": {"vision": True, "function_calling": True},
        },
        # Meta Models
        {
            "model_id": "meta-llama/llama-3.1-405b-instruct",
            "name": "Llama 3.1 405B",
            "version": "3.1",
            "type": "chat",
            "context_window": 131072,
            "max_output_tokens": 4096,
            "input_price": "0.003",
            "output_price": "0.003",
            "capabilities": {"function_calling": True},
        },
        {
            "model_id": "meta-llama/llama-3.1-70b-instruct",
            "name": "Llama 3.1 70B",
            "version": "3.1",
            "type": "chat",
            "context_window": 131072,
            "max_output_tokens": 4096,
            "input_price": "0.00035",
            "output_price": "0.0004",
            "capabilities": {"function_calling": True},
        },
        {
            "model_id": "meta-llama/llama-3.1-8b-instruct",
            "name": "Llama 3.1 8B",
            "version": "3.1",
            "type": "chat",
            "context_window": 131072,
            "max_output_tokens": 4096,
            "input_price": "0.00006",
            "output_price": "0.00006",
            "capabilities": {"function_calling": True},
        },
        # Mistral Models
        {
            "model_id": "mistralai/mistral-large",
            "name": "Mistral Large",
            "version": "2024",
            "type": "chat",
            "context_window": 128000,
            "max_output_tokens": 4096,
            "input_price": "0.002",
            "output_price": "0.006",
            "capabilities": {"function_calling": True},
        },
        {
            "model_id": "mistralai/mixtral-8x7b-instruct",
            "name": "Mixtral 8x7B",
            "version": "v0.1",
            "type": "chat",
            "context_window": 32000,
            "max_output_tokens": 4096,
            "input_price": "0.00024",
            "output_price": "0.00024",
            "capabilities": {"function_calling": True},
        },
        # DeepSeek Models
        {
            "model_id": "deepseek/deepseek-chat",
            "name": "DeepSeek Chat",
            "version": "v2",
            "type": "chat",
            "context_window": 128000,
            "max_output_tokens": 4096,
            "input_price": "0.00014",
            "output_price": "0.00028",
            "capabilities": {"function_calling": True},
        },
        {
            "model_id": "deepseek/deepseek-coder",
            "name": "DeepSeek Coder",
            "version": "v2",
            "type": "chat",
            "context_window": 128000,
            "max_output_tokens": 4096,
            "input_price": "0.00014",
            "output_price": "0.00028",
            "capabilities": {"code_generation": True},
        },
        # Qwen Models
        {
            "model_id": "qwen/qwen-2.5-72b-instruct",
            "name": "Qwen 2.5 72B",
            "version": "2.5",
            "type": "chat",
            "context_window": 131072,
            "max_output_tokens": 8192,
            "input_price": "0.00035",
            "output_price": "0.0004",
            "capabilities": {"function_calling": True},
        },
        {
            "model_id": "qwen/qwen-2.5-coder-32b-instruct",
            "name": "Qwen 2.5 Coder 32B",
            "version": "2.5",
            "type": "chat",
            "context_window": 131072,
            "max_output_tokens": 8192,
            "input_price": "0.00018",
            "output_price": "0.00018",
            "capabilities": {"code_generation": True},
        },
        # Google Gemini 2.5 Pro (Latest - with thinking capabilities)
        {
            "model_id": "google/gemini-2.5-pro-preview",
            "name": "Gemini 2.5 Pro Preview",
            "version": "2.5",
            "type": "chat",
            "context_window": 1048576,  # 1M tokens
            "max_output_tokens": 65536,  # 65K tokens
            "input_price": "0.00125",   # $1.25 per 1M tokens
            "output_price": "0.01",     # $10 per 1M tokens
            "capabilities": {
                "vision": True,
                "function_calling": True,
                "thinking": True,       # Advanced reasoning
                "multimodal": True,     # Text, image, file, audio, video
                "audio": True,
                "video": True,
            },
        },
    ],
}


def create_provider(client: httpx.Client, base_url: str) -> dict:
    """Create the OpenRouter provider."""
    print("Creating OpenRouter provider...")

    response = client.post(
        f"{base_url}/api/v1/providers",
        json=OPENROUTER_CONFIG["provider"],
    )

    if response.status_code == 201:
        provider = response.json()
        print(f"  ✓ Created provider: {provider['name']} (ID: {provider['id']})")
        return provider
    elif response.status_code == 409:
        # Already exists, try to get it
        print("  Provider already exists, fetching...")
        list_response = client.get(f"{base_url}/api/v1/providers")
        if list_response.status_code == 200:
            providers = list_response.json()
            for p in providers:
                if p["name"] == "OpenRouter":
                    print(f"  ✓ Found existing provider: {p['name']} (ID: {p['id']})")
                    return p
        raise Exception("Failed to find existing provider")
    else:
        raise Exception(f"Failed to create provider: {response.status_code} - {response.text}")


def create_endpoint(client: httpx.Client, base_url: str, provider_id: str) -> dict:
    """Create the OpenRouter endpoint."""
    print("Creating OpenRouter endpoint...")

    response = client.post(
        f"{base_url}/api/v1/providers/{provider_id}/endpoints",
        json=OPENROUTER_CONFIG["endpoint"],
    )

    if response.status_code == 201:
        endpoint = response.json()
        print(f"  ✓ Created endpoint: {endpoint['name']} ({endpoint['base_url']})")
        return endpoint
    elif response.status_code == 409:
        print("  Endpoint already exists")
        return {}
    else:
        raise Exception(f"Failed to create endpoint: {response.status_code} - {response.text}")


def create_models(client: httpx.Client, base_url: str, provider_id: str) -> list:
    """Create the OpenRouter models."""
    print(f"Creating {len(OPENROUTER_CONFIG['models'])} models...")

    created_models = []
    for model_config in OPENROUTER_CONFIG["models"]:
        response = client.post(
            f"{base_url}/api/v1/providers/{provider_id}/models",
            json=model_config,
        )

        if response.status_code == 201:
            model = response.json()
            print(f"  ✓ Created model: {model['name']} ({model['model_id']})")
            created_models.append(model)
        elif response.status_code == 409:
            print(f"  - Model already exists: {model_config['name']}")
        else:
            print(f"  ✗ Failed to create model {model_config['name']}: {response.status_code}")

    return created_models


def main():
    parser = argparse.ArgumentParser(description="Seed OpenRouter configuration")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"Seeding OpenRouter configuration to {base_url}")
    print("=" * 60)

    with httpx.Client(timeout=30.0) as client:
        # Check if server is running
        try:
            health = client.get(f"{base_url}/health")
            if health.status_code != 200:
                print(f"Server health check failed: {health.status_code}")
                sys.exit(1)
        except httpx.ConnectError:
            print(f"Cannot connect to server at {base_url}")
            print("Make sure the server is running: uvicorn aiops_agent_executor.main:app --reload")
            sys.exit(1)

        try:
            # Create provider
            provider = create_provider(client, base_url)
            provider_id = provider["id"]

            # Create endpoint
            create_endpoint(client, base_url, provider_id)

            # Create models
            create_models(client, base_url, provider_id)

            print("=" * 60)
            print("✓ OpenRouter configuration seeded successfully!")
            print()
            print("OpenRouter API Information:")
            print(f"  Base URL: {OPENROUTER_CONFIG['endpoint']['base_url']}")
            print(f"  Chat Endpoint: {OPENROUTER_CONFIG['endpoint']['base_url']}/chat/completions")
            print()
            print("Next steps:")
            print("  1. Add your OpenRouter API key via the credentials API:")
            print(f"     POST {base_url}/api/v1/providers/{provider_id}/credentials")
            print('     {"alias": "my-key", "api_key": "sk-or-..."}')
            print()
            print("  2. Get your API key from: https://openrouter.ai/keys")

        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
