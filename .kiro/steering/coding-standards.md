---
inclusion: always
---

# 编码规范

## Python 代码规范

### 代码风格
- 遵循 PEP 8 规范
- 使用 Black 进行代码格式化
- 使用 isort 管理导入顺序
- 使用 mypy 进行类型检查

### 命名约定
- **类名**: PascalCase (例: `AgentTeam`, `ModelProvider`)
- **函数/方法**: snake_case (例: `create_team`, `execute_agent`)
- **常量**: UPPER_SNAKE_CASE (例: `MAX_NODES_PER_TEAM`)
- **私有成员**: 前缀下划线 (例: `_internal_method`)

### 类型注解
```python
# 必须为所有函数添加类型注解
def create_agent(
    agent_id: str,
    model_provider: str,
    tools: list[str] | None = None
) -> Agent:
    ...

# 使用 Pydantic 模型定义数据结构
from pydantic import BaseModel, Field

class AgentConfig(BaseModel):
    agent_id: str = Field(..., description="Agent 唯一标识")
    model_provider: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
```

## FastAPI 开发规范

### 路由组织
```python
# 按功能模块组织路由
# app/api/v1/teams.py
from fastapi import APIRouter

router = APIRouter(prefix="/teams", tags=["teams"])

@router.post("/", status_code=201)
async def create_team(team_config: TeamConfig) -> TeamResponse:
    ...
```

### 请求/响应模型
- 使用 Pydantic 模型定义所有请求和响应
- 添加清晰的字段描述和验证规则
- 使用 `Field` 添加约束和示例

### 错误处理
```python
from fastapi import HTTPException

# 使用统一的错误响应格式
class ErrorResponse(BaseModel):
    error_code: str
    error_message: str
    details: dict | None = None

# 抛出标准 HTTP 异常
if not team:
    raise HTTPException(
        status_code=404,
        detail={
            "error_code": "TEAM_NOT_FOUND",
            "error_message": f"Team with ID '{team_id}' not found"
        }
    )
```

## LangChain/LangGraph 规范

### Agent 创建
```python
from langchain.agents import AgentExecutor
from langchain.chat_models import ChatOpenAI

# 使用配置化的模型创建
def create_llm_from_config(provider: str, model_id: str) -> BaseChatModel:
    config = get_model_config(provider, model_id)
    return ChatOpenAI(
        model=config.model_id,
        api_key=decrypt_api_key(config.credential),
        temperature=config.temperature
    )
```

### 工具定义
```python
from langchain.tools import Tool

# 使用装饰器定义工具
@tool
def search_logs(query: str, time_range: str) -> str:
    """搜索系统日志
    
    Args:
        query: 搜索关键词
        time_range: 时间范围 (例: "1h", "24h")
    
    Returns:
        匹配的日志条目
    """
    ...
```

## 数据库规范

### SQLAlchemy 模型
```python
from sqlalchemy import Column, String, Boolean, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

class Team(Base):
    __tablename__ = "teams"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    topology_config = Column(JSONB, nullable=False)
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
```

### 查询规范
- 使用异步 SQLAlchemy (asyncpg)
- 避免 N+1 查询问题，使用 `joinedload` 或 `selectinload`
- 为频繁查询的字段添加索引

## 安全规范

### 密钥管理
```python
from cryptography.fernet import Fernet

# 使用 Fernet 加密密钥
def encrypt_api_key(api_key: str) -> str:
    cipher = Fernet(settings.ENCRYPTION_KEY)
    return cipher.encrypt(api_key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    cipher = Fernet(settings.ENCRYPTION_KEY)
    return cipher.decrypt(encrypted_key.encode()).decode()
```

### 输入验证
- 所有用户输入必须验证
- 使用 Pydantic 的验证器
- 防止 SQL 注入、XSS 等攻击

## 日志规范

### 结构化日志
```python
import structlog

logger = structlog.get_logger()

# 使用结构化日志
logger.info(
    "agent_execution_started",
    team_id=team_id,
    agent_id=agent_id,
    execution_id=execution_id
)

# 不要记录敏感信息
logger.info("model_config_loaded", provider=provider)  # ✓
logger.info("api_key", key=api_key)  # ✗ 禁止
```

## 测试规范

### 单元测试
```python
import pytest
from unittest.mock import Mock, patch

@pytest.mark.asyncio
async def test_create_team_success():
    # Arrange
    team_config = TeamConfig(...)
    
    # Act
    result = await create_team(team_config)
    
    # Assert
    assert result.status == "created"
    assert result.topology_summary.node_count == 3
```

### 集成测试
- 使用 TestClient 测试 API 端点
- 使用测试数据库（不影响生产数据）
- 测试完整的请求-响应流程

## 性能优化

### 异步编程
- 所有 I/O 操作使用 async/await
- 使用 `asyncio.gather` 并发执行独立任务
- 避免阻塞操作

### 缓存策略
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_model_config(provider: str, model_id: str) -> ModelConfig:
    # 缓存模型配置，减少数据库查询
    ...
```

## 文档规范

### Docstring
```python
def create_agent_team(topology: TopologyConfig) -> Team:
    """创建 Agent Team
    
    根据提供的拓扑结构配置，动态创建包含多个节点和 Agent 的团队。
    
    Args:
        topology: 拓扑结构配置，包含节点、边和 Supervisor 配置
        
    Returns:
        创建的 Team 对象，包含 team_id 和状态信息
        
    Raises:
        ValidationError: 当拓扑配置无效时
        ModelNotFoundError: 当引用的模型不存在时
        
    Example:
        >>> topology = TopologyConfig(nodes=[...], edges=[...])
        >>> team = create_agent_team(topology)
        >>> print(team.team_id)
    """
    ...
```

### API 文档
- 使用 FastAPI 自动生成的 OpenAPI 文档
- 为所有端点添加清晰的描述和示例
- 使用 `response_model` 定义响应结构
