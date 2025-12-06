#!/usr/bin/env python3
"""Test script for LLMService.

Usage:
    DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db" python scripts/test_llm_service.py
"""

import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from aiops_agent_executor.services.llm_service import LLMService
from aiops_agent_executor.services.llm_client import LLMMessage


DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL environment variable is required")
    sys.exit(1)


async def main():
    # Create database connection
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create LLMService
        llm_service = LLMService(session)

        # Create client using database configuration
        print("Creating LLM client from database config...")
        client = await llm_service.create_client_by_provider_name("OpenRouter")
        print(f"Client created: {type(client).__name__}")

        # Test the client
        messages = [
            LLMMessage(role="user", content="用中文介绍一下你自己，50字以内"),
        ]

        print("\nTesting stream()...")
        print("-" * 40)
        async for chunk in client.stream(messages, model="google/gemini-2.5-pro-preview"):
            print(chunk, end="", flush=True)
        print("\n" + "-" * 40)

    await engine.dispose()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
