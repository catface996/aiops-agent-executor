#!/usr/bin/env python3
"""Test script for SSE streaming execution.

Usage:
    DATABASE_URL="postgresql+asyncpg://..." python scripts/test_sse_execution.py

This script:
1. Fetches API key from the database (requires a configured OpenRouter provider)
2. Creates a test team with the API key embedded in topology
3. Runs SSE streaming execution
4. Cleans up the test team
"""

import asyncio
import os
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aiops_agent_executor.services.execution_service import ExecutionService
from aiops_agent_executor.services.team_service import TeamService
from aiops_agent_executor.services.credential_service import CredentialService
from aiops_agent_executor.db.models.provider import Provider, Credential, ProviderType
from aiops_agent_executor.schemas.team import (
    TeamCreate,
    TopologyConfig,
    NodeConfig,
    EdgeConfig,
    AgentConfig,
    SupervisorConfig,
    GlobalSupervisorConfig,
)


DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL environment variable is required")
    sys.exit(1)


async def get_openrouter_api_key(session: AsyncSession) -> str | None:
    """Fetch OpenRouter API key from database."""
    # Find OpenRouter provider
    query = select(Provider).where(Provider.type == ProviderType.OPENROUTER)
    result = await session.execute(query)
    provider = result.scalar_one_or_none()

    if not provider:
        print("⚠️ No OpenRouter provider found in database")
        return None

    # Find active credential
    query = (
        select(Credential)
        .where(Credential.provider_id == provider.id)
        .where(Credential.is_active == True)  # noqa: E712
        .order_by(Credential.created_at.desc())
        .limit(1)
    )
    result = await session.execute(query)
    credential = result.scalar_one_or_none()

    if not credential:
        print("⚠️ No active credential found for OpenRouter provider")
        return None

    # Decrypt API key
    cred_service = CredentialService(session)
    api_key = cred_service.decrypt_api_key(credential)
    print(f"✅ Found OpenRouter API key: {credential.api_key_hint}")
    return api_key


async def create_test_team(session: AsyncSession, api_key: str | None = None) -> uuid.UUID:
    """Create a test team for execution."""
    team_service = TeamService(session)

    # Create a simple topology using schemas/team.py definitions
    # Note: api_key is injected into the topology config for testing
    topology = TopologyConfig(
        nodes=[
            NodeConfig(
                node_id="analysis-node",
                node_name="问题分析组",
                node_type="analysis",
                agents=[
                    AgentConfig(
                        agent_id="log-analyzer",
                        agent_name="日志分析Agent",
                        model_provider="openrouter",
                        model_id="openai/gpt-4o-mini",
                        system_prompt="你是一个日志分析专家，能够快速定位问题原因。分析问题时请简洁明了。",
                        temperature=0.3,
                        api_key=api_key,  # Inject API key
                    ),
                ],
                supervisor_config=SupervisorConfig(
                    model_provider="openrouter",
                    model_id="openai/gpt-4o-mini",
                    system_prompt="协调分析节点内的Agent完成任务。",
                    coordination_strategy="adaptive",
                    api_key=api_key,  # Inject API key
                ),
            ),
        ],
        edges=[],
        global_supervisor=GlobalSupervisorConfig(
            model_provider="openrouter",
            model_id="openai/gpt-4o-mini",
            system_prompt="你是团队协调者，负责分配任务给各个节点。",
            coordination_strategy="hierarchical",
            api_key=api_key,  # Inject API key
        ),
    )

    team_create = TeamCreate(
        team_name=f"测试团队-{uuid.uuid4().hex[:8]}",
        description="SSE 流式测试团队",
        topology=topology,
        timeout_seconds=120,
        max_iterations=10,
    )

    team = await team_service.create_team(team_create)
    await session.commit()

    print(f"✅ 创建测试团队: {team.id}")
    return team.id


async def test_sse_execution(session: AsyncSession, team_id: uuid.UUID):
    """Test SSE streaming execution."""
    exec_service = ExecutionService(session)

    # Start execution
    print(f"\n🚀 开始执行任务...")
    execution = await exec_service.start_execution(
        team_id=team_id,
        input_data={
            "task": "分析系统响应变慢的原因",
            "context": {
                "service": "order-service",
                "symptom": "响应时间从 200ms 上升到 2000ms",
            },
        },
        timeout_seconds=120,
    )
    await session.commit()
    print(f"   执行ID: {execution.id}")

    # Stream events
    print(f"\n📡 接收 SSE 事件流...")
    print("-" * 60)

    event_count = 0
    async for event in exec_service.execute_stream(execution.id):
        event_count += 1
        event_type = event.event.value
        data = event.data

        # Format output based on event type
        if event_type == "execution_start":
            print(f"🚀 [{event_type}] 执行开始")
        elif event_type == "global_supervisor_decision":
            action = data.get("action", "unknown")
            reasoning = data.get("reasoning", "")[:80]
            print(f"🎯 [{event_type}] action={action}")
            print(f"   理由: {reasoning}...")
        elif event_type == "node_supervisor_decision":
            action = data.get("action", "unknown")
            print(f"📦 [{event_type}] action={action}")
        elif event_type == "agent_message":
            agent_id = data.get("agent_id", "unknown")
            message = data.get("message", "")[:100]
            print(f"🤖 [{event_type}] {agent_id}")
            print(f"   {message}...")
        elif event_type == "node_complete":
            node_id = data.get("node_id", "unknown")
            status = data.get("status", "unknown")
            print(f"✅ [{event_type}] {node_id} - {status}")
        elif event_type == "execution_complete":
            status = data.get("status", "unknown")
            output = data.get("output", "")[:200]
            print(f"🎉 [{event_type}] status={status}")
            print(f"   输出: {output}...")
        elif event_type == "execution_error":
            error = data.get("error", "unknown")
            print(f"❌ [{event_type}] {error}")
        else:
            print(f"📌 [{event_type}] {data}")

    print("-" * 60)
    print(f"\n📊 总计 {event_count} 个事件")

    await session.commit()


async def cleanup_team(session: AsyncSession, team_id: uuid.UUID):
    """Clean up test team."""
    team_service = TeamService(session)
    try:
        await team_service.delete_team(team_id)
        await session.commit()
        print(f"\n🧹 清理测试团队: {team_id}")
    except Exception as e:
        print(f"\n⚠️ 清理失败: {e}")


async def main():
    print("=" * 60)
    print("SSE 流式执行测试")
    print("=" * 60)

    # Create database connection
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    team_id = None
    try:
        async with async_session() as session:
            # Create test team
            team_id = await create_test_team(session)

            # Test SSE execution
            await test_sse_execution(session, team_id)

            # Cleanup
            await cleanup_team(session, team_id)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

        # Try to cleanup on error
        if team_id:
            async with async_session() as session:
                await cleanup_team(session, team_id)

    finally:
        await engine.dispose()

    print("\n✅ 测试完成!")


if __name__ == "__main__":
    asyncio.run(main())
