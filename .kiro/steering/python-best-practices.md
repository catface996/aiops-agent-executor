---
inclusion: always
---

# Python 最佳实践指南

本文档定义了项目中 Python 开发的最佳实践，确保代码质量、可维护性和团队协作效率。

## 项目结构

### 推荐目录结构
```
aiops-agent-executor/
├── src/
│   └── aiops_agent_executor/      # 主包（使用下划线）
│       ├── __init__.py
│       ├── api/                   # API 层
│       │   ├── __init__.py
│       │   ├── v1/
│       │   │   ├── __init__.py
│       │   │   ├── teams.py
│       │   │   ├── providers.py
│       │   │   └── executions.py
│       │   └── deps.py            # 依赖注入
│       ├── core/                  # 核心配置
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── security.py
│       │   └── exceptions.py
│       ├── models/                # 数据模型
│       │   ├── __init__.py
│       │   ├── database.py        # SQLAlchemy 模型
│       │   └── schemas.py         # Pydantic 模型
│       ├── services/              # 业务逻辑
│       │   ├── __init__.py
│       │   ├── team_service.py
│       │   ├── agent_service.py
│       │   └── llm_service.py
│       ├── agents/                # Agent 相关
│       │   ├── __init__.py
│       │   ├── supervisor.py
│       │   ├── node_team.py
│       │   └── tools/
│       └── main.py                # 应用入口
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # pytest fixtures
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── alembic/                       # 数据库迁移
├── scripts/                       # 工具脚本
├── pyproject.toml                 # 项目配置（推荐）
├── requirements.txt               # 依赖锁定
└── .env.example                   # 环境变量示例
```

### 包命名规范
- 目录名使用 `snake_case`
- 包名与目录名一致
- 避免使用 `-` 连接符（Python 不支持）

## 依赖管理

### Poetry（推荐）
```toml
# pyproject.toml
[tool.poetry]
name = "aiops-agent-executor"
version = "0.1.0"
description = "AIOps Agent Executor System"
python = "^3.11"

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.109.0"
langchain = "^1.1.2"
langgraph = "^1.0.4"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
ruff = "^0.2.0"
mypy = "^1.8.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

### 依赖分组
```bash
# 安装生产依赖
poetry install --only main

# 安装开发依赖
poetry install --with dev

# 导出 requirements.txt
poetry export -f requirements.txt --output requirements.txt
```

### 版本约束策略
| 符号 | 含义 | 示例 |
|------|------|------|
| `^` | 兼容更新 | `^1.1.2` → `>=1.1.2,<2.0.0` |
| `~` | 补丁更新 | `~1.1.2` → `>=1.1.2,<1.2.0` |
| `==` | 精确版本 | `==1.1.2` |
| `>=,<` | 范围限制 | `>=1.0.0,<2.0.0` |

## 代码质量工具

### Ruff（推荐替代 flake8 + isort + black）
```toml
# pyproject.toml
[tool.ruff]
target-version = "py311"
line-length = 100
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
]
ignore = [
    "E501",   # line too long (handled by formatter)
    "B008",   # function call in default argument
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false

[tool.ruff.isort]
known-first-party = ["aiops_agent_executor"]
```

### MyPy 类型检查
```toml
# pyproject.toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

### Pre-commit 配置
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.2.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic>=2.0
          - types-redis
```

## 类型注解最佳实践

### 基础类型注解
```python
from typing import Any
from collections.abc import Sequence, Mapping, Callable, Awaitable

# Python 3.10+ 语法（推荐）
def process_items(
    items: list[str],                    # 列表
    mapping: dict[str, int],             # 字典
    optional: str | None = None,         # 可选（替代 Optional）
    union_type: str | int = "default",   # 联合类型（替代 Union）
) -> tuple[bool, str]:                   # 元组返回
    ...

# 使用 collections.abc 替代 typing（Python 3.9+）
def process_sequence(items: Sequence[str]) -> Mapping[str, Any]:
    ...

# 可调用类型
Handler = Callable[[str, int], Awaitable[dict[str, Any]]]
```

### Pydantic 模型类型
```python
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import UUID
from enum import Enum

class TeamStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"

class TeamBase(BaseModel):
    """Team 基础模型"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
    )

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    status: TeamStatus = Field(default=TeamStatus.ACTIVE)

class TeamCreate(TeamBase):
    """创建 Team 请求"""
    topology_config: dict[str, Any]

class TeamResponse(TeamBase):
    """Team 响应"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 泛型类型
```python
from typing import Generic, TypeVar

T = TypeVar("T")
ID = TypeVar("ID", str, UUID)

class Repository(Generic[T, ID]):
    """泛型仓库基类"""

    async def get(self, id: ID) -> T | None:
        ...

    async def create(self, entity: T) -> T:
        ...

    async def list(self, skip: int = 0, limit: int = 100) -> list[T]:
        ...

class TeamRepository(Repository[Team, UUID]):
    """Team 仓库实现"""
    pass
```

## 异步编程最佳实践

### 异步上下文管理器
```python
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# 数据库会话管理
engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### 并发执行
```python
import asyncio
from collections.abc import Coroutine

async def execute_agents_parallel(
    agents: list[Agent],
    task: str,
) -> list[AgentResult]:
    """并发执行多个 Agent"""

    # 创建任务列表
    tasks: list[Coroutine[Any, Any, AgentResult]] = [
        agent.execute(task) for agent in agents
    ]

    # 并发执行，收集结果
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理异常
    processed_results: list[AgentResult] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("agent_execution_failed", agent_id=agents[i].id, error=str(result))
            processed_results.append(AgentResult(status="error", error=str(result)))
        else:
            processed_results.append(result)

    return processed_results
```

### 异步迭代器（用于流式输出）
```python
from collections.abc import AsyncIterator
from typing import Any

async def stream_execution(
    team_id: str,
    task: str,
) -> AsyncIterator[dict[str, Any]]:
    """流式执行 Team 任务"""

    yield {"event": "execution_start", "team_id": team_id}

    async for message in execute_team_stream(team_id, task):
        yield {
            "event": "agent_message",
            "team_id": team_id,
            **message,
        }

    yield {"event": "execution_complete", "team_id": team_id}
```

### 超时和取消处理
```python
import asyncio
from asyncio import TimeoutError

async def execute_with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout_seconds: float,
) -> T:
    """带超时的异步执行"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except TimeoutError:
        logger.warning("execution_timeout", timeout=timeout_seconds)
        raise ExecutionTimeoutError(f"Execution timed out after {timeout_seconds}s")

# 优雅取消
async def cancellable_execution(task: asyncio.Task[Any]) -> None:
    try:
        await task
    except asyncio.CancelledError:
        logger.info("task_cancelled")
        # 清理资源
        raise
```

## 错误处理最佳实践

### 自定义异常层次
```python
# core/exceptions.py
class AppException(Exception):
    """应用基础异常"""

    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

class NotFoundError(AppException):
    """资源未找到"""

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} with ID '{resource_id}' not found",
            error_code=f"{resource.upper()}_NOT_FOUND",
            status_code=404,
            details={"resource": resource, "id": resource_id},
        )

class ValidationError(AppException):
    """验证错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )

class ExecutionTimeoutError(AppException):
    """执行超时"""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            error_code="EXECUTION_TIMEOUT",
            status_code=408,
        )
```

### FastAPI 异常处理器
```python
# api/exception_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "error_message": exc.message,
            "details": exc.details,
        },
    )

# main.py
app.add_exception_handler(AppException, app_exception_handler)
```

### 结果类型模式（替代异常）
```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")

@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T

@dataclass(frozen=True)
class Err(Generic[E]):
    error: E

Result = Ok[T] | Err[E]

# 使用示例
async def create_team(config: TeamConfig) -> Result[Team, str]:
    if not config.nodes:
        return Err("Team must have at least one node")

    team = await team_repository.create(config)
    return Ok(team)

# 调用方处理
match await create_team(config):
    case Ok(team):
        return TeamResponse.model_validate(team)
    case Err(error):
        raise ValidationError(error)
```

## 配置管理

### Pydantic Settings
```python
# core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用配置
    app_name: str = "AIOps Agent Executor"
    debug: bool = False

    # 数据库配置
    database_url: str
    database_pool_size: int = 10

    # Redis 配置（可选）
    redis_url: str | None = None

    # 安全配置
    encryption_key: str  # Fernet key
    jwt_secret: str
    jwt_algorithm: str = "HS256"

    # Agent 配置
    default_timeout_seconds: int = 300
    max_nodes_per_team: int = 100
    max_agents_per_node: int = 20

@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()

settings = get_settings()
```

### 环境变量示例
```bash
# .env.example
# 数据库
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/aiops

# Redis（可选）
REDIS_URL=redis://localhost:6379/0

# 安全
ENCRYPTION_KEY=your-fernet-key-here
JWT_SECRET=your-jwt-secret-here

# 调试
DEBUG=false
```

## 日志最佳实践

### Structlog 配置
```python
# core/logging.py
import structlog
import logging
from typing import Any

def configure_logging(debug: bool = False) -> None:
    """配置结构化日志"""

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if debug:
        # 开发环境：彩色控制台输出
        shared_processors.append(structlog.dev.ConsoleRenderer())
    else:
        # 生产环境：JSON 格式
        shared_processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 配置标准库日志
    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )
```

### 日志使用模式
```python
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

logger = structlog.get_logger()

# 绑定请求上下文
async def logging_middleware(request: Request, call_next):
    clear_contextvars()
    bind_contextvars(
        request_id=request.headers.get("X-Request-ID", str(uuid4())),
        path=request.url.path,
    )

    response = await call_next(request)
    return response

# 业务日志
async def execute_team(team_id: str, task: str) -> ExecutionResult:
    log = logger.bind(team_id=team_id)

    log.info("team_execution_started", task=task)

    try:
        result = await do_execution(team_id, task)
        log.info("team_execution_completed", duration_ms=result.duration_ms)
        return result
    except Exception as e:
        log.error("team_execution_failed", error=str(e), exc_info=True)
        raise
```

## 测试最佳实践

### Pytest 配置
```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = [
    "-v",
    "--strict-markers",
    "--cov=src/aiops_agent_executor",
    "--cov-report=term-missing",
    "--cov-report=html",
]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "e2e: End-to-end tests",
    "slow: Slow tests",
]
```

### Fixtures 组织
```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from aiops_agent_executor.main import app
from aiops_agent_executor.core.config import settings

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """测试数据库会话"""
    engine = create_async_engine(settings.test_database_url)
    async with AsyncSession(engine) as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """测试客户端"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

@pytest.fixture
def sample_team_config() -> dict:
    """示例 Team 配置"""
    return {
        "team_name": "Test Team",
        "topology": {
            "nodes": [...],
            "edges": [...],
        },
    }
```

### 测试模式
```python
# tests/unit/test_team_service.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.unit
async def test_create_team_success(sample_team_config):
    """测试成功创建 Team"""
    # Arrange
    mock_repo = AsyncMock()
    mock_repo.create.return_value = Team(id=uuid4(), **sample_team_config)

    service = TeamService(repository=mock_repo)

    # Act
    result = await service.create_team(sample_team_config)

    # Assert
    assert result.status == "created"
    mock_repo.create.assert_called_once()

@pytest.mark.unit
async def test_create_team_validation_error():
    """测试无效配置抛出验证错误"""
    service = TeamService()

    with pytest.raises(ValidationError) as exc_info:
        await service.create_team({"team_name": ""})

    assert "team_name" in str(exc_info.value)

# tests/integration/test_teams_api.py
@pytest.mark.integration
async def test_create_team_api(client: AsyncClient, sample_team_config):
    """测试创建 Team API"""
    response = await client.post("/api/v1/teams", json=sample_team_config)

    assert response.status_code == 201
    data = response.json()
    assert "team_id" in data
    assert data["status"] == "created"
```

## 性能优化

### 连接池管理
```python
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

# 生产环境：使用连接池
engine = create_async_engine(
    settings.database_url,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # 检查连接有效性
)

# 测试环境：禁用连接池
test_engine = create_async_engine(
    settings.test_database_url,
    poolclass=NullPool,
)
```

### 缓存策略
```python
from functools import lru_cache
from aiocache import cached, Cache
from aiocache.serializers import JsonSerializer

# 同步缓存（内存）
@lru_cache(maxsize=256)
def get_model_capabilities(model_id: str) -> list[str]:
    """缓存模型能力列表"""
    ...

# 异步缓存（Redis）
@cached(
    ttl=300,
    cache=Cache.REDIS,
    serializer=JsonSerializer(),
    key_builder=lambda f, *args, **kwargs: f"model:{args[0]}",
)
async def get_model_config(model_id: str) -> ModelConfig:
    """缓存模型配置"""
    ...

# 手动缓存失效
async def invalidate_model_cache(model_id: str) -> None:
    cache = Cache(Cache.REDIS)
    await cache.delete(f"model:{model_id}")
```

### 批量操作
```python
from sqlalchemy import insert

async def bulk_create_agents(agents: list[AgentCreate]) -> list[Agent]:
    """批量创建 Agent"""
    async with get_db_session() as session:
        # 使用批量插入
        stmt = insert(AgentModel).values([a.model_dump() for a in agents])
        result = await session.execute(stmt.returning(AgentModel))
        return [Agent.model_validate(row) for row in result.scalars()]
```

## 安全最佳实践

### 密钥轮换支持
```python
from cryptography.fernet import Fernet, MultiFernet

class KeyManager:
    """支持密钥轮换的管理器"""

    def __init__(self, keys: list[str]):
        fernets = [Fernet(key) for key in keys]
        self._multi_fernet = MultiFernet(fernets)

    def encrypt(self, data: str) -> str:
        return self._multi_fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        return self._multi_fernet.decrypt(encrypted.encode()).decode()

    def rotate(self, encrypted: str) -> str:
        """轮换到最新密钥"""
        return self._multi_fernet.rotate(encrypted.encode()).decode()
```

### 输入清理
```python
import re
from pydantic import field_validator

class SafeInput(BaseModel):
    """安全输入模型"""

    query: str

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        # 移除潜在危险字符
        v = re.sub(r'[<>"\']', '', v)
        # 限制长度
        return v[:1000]
```

## 文档字符串规范

### Google 风格（推荐）
```python
def create_agent_team(
    topology: TopologyConfig,
    *,
    timeout: int = 300,
    validate: bool = True,
) -> Team:
    """创建 Agent Team。

    根据提供的拓扑结构配置，动态创建包含多个节点和 Agent 的团队。
    支持层级化的 Supervisor 架构。

    Args:
        topology: 拓扑结构配置，包含节点、边和 Supervisor 配置。
        timeout: 创建超时时间（秒）。默认 300。
        validate: 是否验证拓扑配置。默认 True。

    Returns:
        创建的 Team 对象，包含 team_id 和状态信息。

    Raises:
        ValidationError: 当拓扑配置无效时。
        ModelNotFoundError: 当引用的模型不存在时。
        TimeoutError: 当创建超时时。

    Example:
        >>> topology = TopologyConfig(
        ...     nodes=[NodeConfig(node_id="n1", agents=[...])],
        ...     edges=[],
        ... )
        >>> team = create_agent_team(topology)
        >>> print(team.team_id)
        'abc-123-def'

    Note:
        此函数是异步的，但提供同步包装器用于兼容性。
    """
    ...
```
