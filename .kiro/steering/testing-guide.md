---
inclusion: fileMatch
fileMatchPattern: "**/tests/**/*.py"
---

# 测试指南

## 测试策略

### 测试金字塔
```
        /\
       /  \  E2E Tests (少量)
      /────\
     /      \  Integration Tests (适量)
    /────────\
   /          \  Unit Tests (大量)
  /────────────\
```

- **单元测试**: 70% - 测试单个函数/类
- **集成测试**: 20% - 测试模块间交互
- **E2E 测试**: 10% - 测试完整流程

## 测试工具栈

- **测试框架**: pytest
- **异步测试**: pytest-asyncio
- **Mock**: unittest.mock
- **HTTP 测试**: httpx (TestClient)
- **数据库测试**: pytest-postgresql
- **覆盖率**: pytest-cov

## 项目测试结构

```
tests/
├── unit/                    # 单元测试
│   ├── test_models.py
│   ├── test_services.py
│   └── test_utils.py
├── integration/             # 集成测试
│   ├── test_api.py
│   ├── test_database.py
│   └── test_agent_execution.py
├── e2e/                     # 端到端测试
│   └── test_full_workflow.py
├── fixtures/                # 测试数据
│   ├── providers.json
│   └── topologies.json
└── conftest.py             # pytest 配置和 fixtures
```

## 单元测试

### 测试 Pydantic 模型
```python
import pytest
from app.schemas.provider import ProviderCreate, ProviderResponse

def test_provider_create_valid():
    """测试创建有效的供应商配置"""
    provider = ProviderCreate(
        name="OpenAI",
        type="openai",
        description="OpenAI provider"
    )
    assert provider.name == "OpenAI"
    assert provider.type == "openai"

def test_provider_create_invalid_name():
    """测试无效的供应商名称"""
    with pytest.raises(ValueError):
        ProviderCreate(
            name="",  # 空名称应该失败
            type="openai"
        )
```

### 测试服务层
```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.provider_service import ProviderService
from app.models.provider import Provider

@pytest.fixture
def mock_session():
    """Mock 数据库 session"""
    session = AsyncMock()
    return session

@pytest.fixture
def provider_service(mock_session):
    """Provider service fixture"""
    return ProviderService(mock_session)

@pytest.mark.asyncio
async def test_create_provider_success(provider_service, mock_session):
    """测试成功创建供应商"""
    # Arrange
    provider_data = {
        "name": "OpenAI",
        "type": "openai",
        "description": "Test"
    }
    
    # Mock 数据库操作
    mock_session.add = Mock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    
    # Act
    result = await provider_service.create(provider_data)
    
    # Assert
    assert result.name == "OpenAI"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_get_provider_not_found(provider_service, mock_session):
    """测试获取不存在的供应商"""
    # Arrange
    mock_session.execute = AsyncMock(return_value=Mock(scalar_one_or_none=Mock(return_value=None)))
    
    # Act
    result = await provider_service.get_by_id("non-existent-id")
    
    # Assert
    assert result is None
```

### 测试工具函数
```python
from app.utils.encryption import encrypt_api_key, decrypt_api_key

def test_encrypt_decrypt_api_key():
    """测试密钥加密和解密"""
    original_key = "sk-test-1234567890"
    
    # 加密
    encrypted = encrypt_api_key(original_key)
    assert encrypted != original_key
    
    # 解密
    decrypted = decrypt_api_key(encrypted)
    assert decrypted == original_key

def test_encrypt_empty_key():
    """测试加密空密钥"""
    with pytest.raises(ValueError):
        encrypt_api_key("")
```

### 测试 Agent 逻辑
```python
from unittest.mock import AsyncMock, patch
from app.agent.agent import Agent
from app.schemas.agent import AgentConfig

@pytest.fixture
def agent_config():
    return AgentConfig(
        agent_id="test-agent",
        agent_name="Test Agent",
        model_provider="openai",
        model_id="gpt-4",
        system_prompt="You are a test agent",
        tools=["search_logs"],
        temperature=0.7
    )

@pytest.mark.asyncio
async def test_agent_execute_success(agent_config):
    """测试 Agent 成功执行任务"""
    # Arrange
    agent = Agent(agent_config)
    
    # Mock LLM 响应
    with patch.object(agent.executor, 'ainvoke', new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = {
            "output": "Task completed successfully",
            "intermediate_steps": []
        }
        
        # Act
        result = await agent.execute("Test task", {})
        
        # Assert
        assert result["agent_id"] == "test-agent"
        assert "output" in result
        mock_invoke.assert_called_once()

@pytest.mark.asyncio
async def test_agent_tool_not_found(agent_config):
    """测试 Agent 使用未注册的工具"""
    # Arrange
    agent_config.tools = ["non_existent_tool"]
    
    # Act & Assert
    with pytest.raises(ToolNotFoundError):
        Agent(agent_config)
```

## 集成测试

### 测试 API 端点
```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.fixture
async def client():
    """HTTP 测试客户端"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_create_provider_api(client):
    """测试创建供应商 API"""
    # Arrange
    provider_data = {
        "name": "OpenAI",
        "type": "openai",
        "description": "Test provider"
    }
    
    # Act
    response = await client.post("/api/v1/providers", json=provider_data)
    
    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "OpenAI"
    assert "id" in data

@pytest.mark.asyncio
async def test_get_provider_not_found(client):
    """测试获取不存在的供应商"""
    # Act
    response = await client.get("/api/v1/providers/non-existent-id")
    
    # Assert
    assert response.status_code == 404
    data = response.json()
    assert data["error_code"] == "PROVIDER_NOT_FOUND"

@pytest.mark.asyncio
async def test_create_team_invalid_topology(client):
    """测试创建无效拓扑的 Team"""
    # Arrange
    invalid_topology = {
        "topology": {
            "nodes": [],  # 空节点列表
            "edges": [],
            "global_supervisor": {}
        },
        "team_name": "Test Team"
    }
    
    # Act
    response = await client.post("/api/v1/teams", json=invalid_topology)
    
    # Assert
    assert response.status_code == 400
    data = response.json()
    assert "error_code" in data
```

### 测试数据库操作
```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.models.provider import Provider

@pytest.fixture
async def test_db():
    """测试数据库"""
    engine = create_async_engine("postgresql+asyncpg://test:test@localhost/test_db")
    
    # 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建 session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    yield async_session
    
    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.mark.asyncio
async def test_provider_crud(test_db):
    """测试供应商 CRUD 操作"""
    async with test_db() as session:
        # Create
        provider = Provider(
            name="OpenAI",
            type="openai",
            description="Test"
        )
        session.add(provider)
        await session.commit()
        await session.refresh(provider)
        
        provider_id = provider.id
        assert provider_id is not None
        
        # Read
        result = await session.get(Provider, provider_id)
        assert result.name == "OpenAI"
        
        # Update
        result.description = "Updated"
        await session.commit()
        await session.refresh(result)
        assert result.description == "Updated"
        
        # Delete
        await session.delete(result)
        await session.commit()
        
        deleted = await session.get(Provider, provider_id)
        assert deleted is None
```

### 测试 Agent 执行流程
```python
@pytest.mark.asyncio
async def test_agent_team_execution():
    """测试 Agent Team 完整执行流程"""
    # Arrange
    topology = TopologyConfig(
        nodes=[
            NodeConfig(
                node_id="node-1",
                node_name="Test Node",
                node_type="service",
                agents=[
                    AgentConfig(
                        agent_id="agent-1",
                        agent_name="Test Agent",
                        model_provider="openai",
                        model_id="gpt-4",
                        system_prompt="Test",
                        tools=[]
                    )
                ],
                supervisor_config=SupervisorConfig(
                    model_provider="openai",
                    model_id="gpt-4",
                    system_prompt="Test supervisor",
                    coordination_strategy="round_robin"
                )
            )
        ],
        edges=[],
        global_supervisor=GlobalSupervisorConfig(
            model_provider="openai",
            model_id="gpt-4",
            system_prompt="Test global supervisor",
            coordination_strategy="sequential"
        )
    )
    
    team = GlobalTeam(topology)
    
    # Act
    result = await team.execute("Test task", {})
    
    # Assert
    assert result["status"] == "success"
    assert "results" in result
```

## E2E 测试

### 测试完整工作流
```python
@pytest.mark.asyncio
async def test_full_aiops_workflow(client):
    """测试完整的 AIOps 工作流"""
    
    # 1. 创建供应商
    provider_response = await client.post("/api/v1/providers", json={
        "name": "OpenAI",
        "type": "openai"
    })
    assert provider_response.status_code == 201
    provider_id = provider_response.json()["id"]
    
    # 2. 添加密钥
    credential_response = await client.post(
        f"/api/v1/providers/{provider_id}/credentials",
        json={
            "alias": "main-key",
            "api_key": "sk-test-key"
        }
    )
    assert credential_response.status_code == 201
    
    # 3. 同步模型
    sync_response = await client.post(f"/api/v1/providers/{provider_id}/models/sync")
    assert sync_response.status_code == 200
    
    # 4. 创建 Team
    team_response = await client.post("/api/v1/teams", json={
        "topology": {...},  # 完整拓扑配置
        "team_name": "E2E Test Team"
    })
    assert team_response.status_code == 201
    team_id = team_response.json()["team_id"]
    
    # 5. 执行 Team
    execution_response = await client.post(
        f"/api/v1/teams/{team_id}/execute",
        json={
            "input": {"task": "Analyze system health"},
            "stream": False
        }
    )
    assert execution_response.status_code == 200
    result = execution_response.json()
    assert result["status"] == "success"
    
    # 6. 生成结构化输出
    structured_response = await client.post(
        f"/api/v1/teams/{team_id}/structured-output",
        json={
            "output_schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"}
                }
            }
        }
    )
    assert structured_response.status_code == 200
    assert "structured_output" in structured_response.json()
```

## 测试 Fixtures

### conftest.py
```python
import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient

from app.main import app
from app.db.base import Base
from app.core.config import settings

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """数据库 session fixture"""
    engine = create_async_engine(settings.TEST_DATABASE_URL)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP 客户端 fixture"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def sample_provider_data():
    """示例供应商数据"""
    return {
        "name": "OpenAI",
        "type": "openai",
        "description": "Test provider"
    }

@pytest.fixture
def sample_topology():
    """示例拓扑配置"""
    return {
        "nodes": [
            {
                "node_id": "node-1",
                "node_name": "Test Node",
                "node_type": "service",
                "agents": [...],
                "supervisor_config": {...}
            }
        ],
        "edges": [],
        "global_supervisor": {...}
    }
```

## 测试覆盖率

### 运行测试并生成覆盖率报告
```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/unit/test_models.py

# 生成覆盖率报告
pytest --cov=app --cov-report=html --cov-report=term

# 只运行标记的测试
pytest -m "not slow"
```

### 覆盖率目标
- 整体覆盖率: > 80%
- 核心业务逻辑: > 90%
- API 端点: 100%

## Mock 和 Patch

### Mock LLM 调用
```python
@pytest.fixture
def mock_llm():
    """Mock LLM 响应"""
    with patch('app.agent.agent.ChatOpenAI') as mock:
        mock_instance = AsyncMock()
        mock_instance.ainvoke.return_value = AIMessage(content="Mocked response")
        mock.return_value = mock_instance
        yield mock

@pytest.mark.asyncio
async def test_with_mock_llm(mock_llm):
    """使用 Mock LLM 测试"""
    agent = Agent(agent_config)
    result = await agent.execute("test", {})
    assert "output" in result
```

### Mock 外部服务
```python
@pytest.fixture
def mock_external_api():
    """Mock 外部 API 调用"""
    with patch('httpx.AsyncClient.post') as mock:
        mock.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"result": "success"}
        )
        yield mock
```

## 性能测试

### 测试响应时间
```python
import time

@pytest.mark.asyncio
async def test_api_response_time(client):
    """测试 API 响应时间"""
    start = time.time()
    response = await client.get("/api/v1/providers")
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 0.1  # 应在 100ms 内响应
```

### 负载测试
```python
@pytest.mark.asyncio
async def test_concurrent_executions(client):
    """测试并发执行"""
    tasks = [
        client.post(f"/api/v1/teams/{team_id}/execute", json={...})
        for _ in range(10)
    ]
    
    results = await asyncio.gather(*tasks)
    
    assert all(r.status_code == 200 for r in results)
```

## 测试最佳实践

1. **测试命名**: 使用描述性名称，说明测试内容和预期结果
2. **AAA 模式**: Arrange (准备) → Act (执行) → Assert (断言)
3. **独立性**: 每个测试应该独立，不依赖其他测试
4. **清理**: 使用 fixtures 确保测试后清理资源
5. **Mock 外部依赖**: 不依赖真实的外部服务
6. **测试边界条件**: 测试正常情况和异常情况
7. **持续集成**: 在 CI/CD 中自动运行测试
