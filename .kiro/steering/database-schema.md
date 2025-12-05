---
inclusion: fileMatch
fileMatchPattern: "**/models/**/*.py"
---

# 数据库设计规范

## 数据库技术栈

- **数据库**: PostgreSQL 14+
- **ORM**: SQLAlchemy 2.0 (异步)
- **迁移工具**: Alembic
- **连接池**: asyncpg

## 表结构设计

### LLM 配置管理表

#### providers (供应商表)
```sql
CREATE TABLE providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,  -- openai, anthropic, bedrock, azure, aliyun, baidu, local
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT providers_name_unique UNIQUE (name)
);

CREATE INDEX idx_providers_type ON providers(type);
CREATE INDEX idx_providers_is_active ON providers(is_active);
```

#### endpoints (接入点表)
```sql
CREATE TABLE endpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    base_url VARCHAR(500) NOT NULL,
    api_version VARCHAR(50),
    region VARCHAR(50),
    timeout_connect INTEGER DEFAULT 10,  -- 秒
    timeout_read INTEGER DEFAULT 60,     -- 秒
    retry_count INTEGER DEFAULT 3,
    is_default BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT endpoints_provider_name_unique UNIQUE (provider_id, name)
);

CREATE INDEX idx_endpoints_provider_id ON endpoints(provider_id);
CREATE INDEX idx_endpoints_is_default ON endpoints(is_default);
```

#### credentials (密钥表)
```sql
CREATE TABLE credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    alias VARCHAR(100),
    api_key_encrypted TEXT NOT NULL,
    secret_key_encrypted TEXT,
    expires_at TIMESTAMP,
    quota_limit INTEGER,  -- 每日请求配额
    quota_used INTEGER DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    
    CONSTRAINT credentials_provider_alias_unique UNIQUE (provider_id, alias)
);

CREATE INDEX idx_credentials_provider_id ON credentials(provider_id);
CREATE INDEX idx_credentials_expires_at ON credentials(expires_at);
```

#### models (模型表)
```sql
CREATE TABLE models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    model_id VARCHAR(200) NOT NULL,  -- 供应商的模型标识
    name VARCHAR(200) NOT NULL,
    version VARCHAR(50),
    type VARCHAR(50) NOT NULL,  -- chat, completion, embedding, vision
    context_window INTEGER,
    max_output_tokens INTEGER,
    input_price DECIMAL(10, 6),   -- 每千 Token 价格
    output_price DECIMAL(10, 6),
    capabilities JSONB,  -- {"function_calling": true, "vision": false, ...}
    status VARCHAR(50) NOT NULL DEFAULT 'available',  -- available, maintenance, deprecated
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT models_provider_model_id_unique UNIQUE (provider_id, model_id)
);

CREATE INDEX idx_models_provider_id ON models(provider_id);
CREATE INDEX idx_models_type ON models(type);
CREATE INDEX idx_models_status ON models(status);
CREATE INDEX idx_models_capabilities ON models USING GIN (capabilities);
```

### Agent Team 管理表

#### teams (团队表)
```sql
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    topology_config JSONB NOT NULL,  -- 完整的拓扑配置
    status VARCHAR(50) NOT NULL DEFAULT 'active',  -- active, inactive, error
    timeout_seconds INTEGER DEFAULT 300,
    max_iterations INTEGER DEFAULT 50,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    
    CONSTRAINT teams_name_unique UNIQUE (name)
);

CREATE INDEX idx_teams_status ON teams(status);
CREATE INDEX idx_teams_created_at ON teams(created_at);
CREATE INDEX idx_teams_topology_config ON teams USING GIN (topology_config);
```

#### executions (执行记录表)
```sql
CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    input JSONB NOT NULL,
    output JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'running',  -- running, success, failed, timeout
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    error_message TEXT,
    error_traceback TEXT,
    metadata JSONB,  -- 额外的元数据
    
    CONSTRAINT executions_check_duration CHECK (duration_ms >= 0)
);

CREATE INDEX idx_executions_team_id ON executions(team_id);
CREATE INDEX idx_executions_status ON executions(status);
CREATE INDEX idx_executions_started_at ON executions(started_at DESC);
```

#### execution_logs (执行日志表)
```sql
CREATE TABLE execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,  -- agent_message, tool_call, supervisor_decision, etc.
    node_id VARCHAR(100),
    agent_id VARCHAR(100),
    supervisor_id VARCHAR(100),
    message TEXT,
    metadata JSONB,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT execution_logs_check_identifiers CHECK (
        node_id IS NOT NULL OR agent_id IS NOT NULL OR supervisor_id IS NOT NULL
    )
);

CREATE INDEX idx_execution_logs_execution_id ON execution_logs(execution_id);
CREATE INDEX idx_execution_logs_event_type ON execution_logs(event_type);
CREATE INDEX idx_execution_logs_timestamp ON execution_logs(timestamp);
CREATE INDEX idx_execution_logs_node_id ON execution_logs(node_id);
CREATE INDEX idx_execution_logs_agent_id ON execution_logs(agent_id);
```

#### structured_outputs (结构化输出表)
```sql
CREATE TABLE structured_outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    output_schema JSONB NOT NULL,
    structured_data JSONB NOT NULL,
    schema_valid BOOLEAN NOT NULL,
    validation_errors JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT structured_outputs_execution_id_unique UNIQUE (execution_id)
);

CREATE INDEX idx_structured_outputs_execution_id ON structured_outputs(execution_id);
```

## SQLAlchemy 模型定义

### Provider 模型
```python
from sqlalchemy import Column, String, Boolean, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.base import Base

class Provider(Base):
    __tablename__ = "providers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    type = Column(String(50), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # 关系
    endpoints = relationship("Endpoint", back_populates="provider", cascade="all, delete-orphan")
    credentials = relationship("Credential", back_populates="provider", cascade="all, delete-orphan")
    models = relationship("Model", back_populates="provider", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Provider(id={self.id}, name={self.name}, type={self.type})>"
```

### Endpoint 模型
```python
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship

class Endpoint(Base):
    __tablename__ = "endpoints"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    base_url = Column(String(500), nullable=False)
    api_version = Column(String(50))
    region = Column(String(50))
    timeout_connect = Column(Integer, default=10)
    timeout_read = Column(Integer, default=60)
    retry_count = Column(Integer, default=3)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # 关系
    provider = relationship("Provider", back_populates="endpoints")
```

### Credential 模型
```python
class Credential(Base):
    __tablename__ = "credentials"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String(100))
    api_key_encrypted = Column(Text, nullable=False)
    secret_key_encrypted = Column(Text)
    expires_at = Column(TIMESTAMP)
    quota_limit = Column(Integer)
    quota_used = Column(Integer, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    last_used_at = Column(TIMESTAMP)
    
    # 关系
    provider = relationship("Provider", back_populates="credentials")
```

### Model 模型
```python
from sqlalchemy import Column, DECIMAL
from sqlalchemy.dialects.postgresql import JSONB

class Model(Base):
    __tablename__ = "models"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(String(200), nullable=False)
    name = Column(String(200), nullable=False)
    version = Column(String(50))
    type = Column(String(50), nullable=False)
    context_window = Column(Integer)
    max_output_tokens = Column(Integer)
    input_price = Column(DECIMAL(10, 6))
    output_price = Column(DECIMAL(10, 6))
    capabilities = Column(JSONB)
    status = Column(String(50), nullable=False, default="available")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # 关系
    provider = relationship("Provider", back_populates="models")
```

### Team 模型
```python
class Team(Base):
    __tablename__ = "teams"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    topology_config = Column(JSONB, nullable=False)
    status = Column(String(50), nullable=False, default="active")
    timeout_seconds = Column(Integer, default=300)
    max_iterations = Column(Integer, default=50)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(100))
    
    # 关系
    executions = relationship("Execution", back_populates="team", cascade="all, delete-orphan")
```

### Execution 模型
```python
class Execution(Base):
    __tablename__ = "executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    input = Column(JSONB, nullable=False)
    output = Column(JSONB)
    status = Column(String(50), nullable=False, default="running")
    started_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    completed_at = Column(TIMESTAMP)
    duration_ms = Column(Integer)
    error_message = Column(Text)
    error_traceback = Column(Text)
    metadata = Column(JSONB)
    
    # 关系
    team = relationship("Team", back_populates="executions")
    logs = relationship("ExecutionLog", back_populates="execution", cascade="all, delete-orphan")
    structured_output = relationship("StructuredOutput", back_populates="execution", uselist=False)
```

### ExecutionLog 模型
```python
class ExecutionLog(Base):
    __tablename__ = "execution_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)
    node_id = Column(String(100))
    agent_id = Column(String(100))
    supervisor_id = Column(String(100))
    message = Column(Text)
    metadata = Column(JSONB)
    timestamp = Column(TIMESTAMP, nullable=False, server_default=func.now())
    
    # 关系
    execution = relationship("Execution", back_populates="logs")
```

## 数据库操作规范

### 异步查询
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def get_provider_with_models(
    session: AsyncSession,
    provider_id: str
) -> Provider | None:
    """获取供应商及其模型（避免 N+1 查询）"""
    stmt = (
        select(Provider)
        .options(selectinload(Provider.models))
        .where(Provider.id == provider_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
```

### 批量插入
```python
async def bulk_create_models(
    session: AsyncSession,
    models: list[dict]
) -> None:
    """批量创建模型"""
    stmt = insert(Model).values(models)
    await session.execute(stmt)
    await session.commit()
```

### 事务处理
```python
from sqlalchemy.exc import IntegrityError

async def create_provider_with_endpoint(
    session: AsyncSession,
    provider_data: dict,
    endpoint_data: dict
) -> Provider:
    """创建供应商和接入点（事务）"""
    try:
        # 创建供应商
        provider = Provider(**provider_data)
        session.add(provider)
        await session.flush()  # 获取 provider.id
        
        # 创建接入点
        endpoint = Endpoint(**endpoint_data, provider_id=provider.id)
        session.add(endpoint)
        
        await session.commit()
        return provider
        
    except IntegrityError as e:
        await session.rollback()
        raise ValueError(f"Database integrity error: {e}")
```

## 数据迁移

### Alembic 配置
```python
# alembic/env.py
from app.db.base import Base
from app.models import *  # 导入所有模型

target_metadata = Base.metadata
```

### 迁移脚本示例
```python
# alembic/versions/001_create_providers_table.py
def upgrade():
    op.create_table(
        'providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('now()'))
    )
    op.create_index('idx_providers_type', 'providers', ['type'])

def downgrade():
    op.drop_index('idx_providers_type')
    op.drop_table('providers')
```

## 性能优化

### 索引策略
- 为外键添加索引
- 为频繁查询的字段添加索引
- 为 JSONB 字段使用 GIN 索引
- 定期分析查询计划（EXPLAIN ANALYZE）

### 连接池配置
```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False
)
```

### 查询优化
- 使用 `selectinload` 或 `joinedload` 预加载关联数据
- 避免在循环中执行查询
- 使用分页限制结果集大小
- 对大表使用分区
