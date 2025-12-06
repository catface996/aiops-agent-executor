# Research: Agent团队动态编排

**Feature**: 002-agent-orchestration
**Date**: 2024-12-06

## Research Topics

### 1. LangGraph Multi-Agent Orchestration

**Decision**: 使用 LangGraph 的 StateGraph 构建三层协调架构

**Rationale**:
- 项目已依赖 langgraph>=0.2.0
- StateGraph 支持条件路由、并行执行和状态管理
- 内置支持 checkpoint 和 streaming
- 可与现有 LangChain 模型无缝集成

**Alternatives Considered**:
- 纯 LangChain AgentExecutor: 不支持复杂拓扑结构
- 自定义状态机: 需要大量额外开发，无现成的 streaming 支持
- Crew AI: 额外依赖，与现有 LangChain 生态不一致

**Implementation Pattern**:
```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# 定义状态
class TeamState(TypedDict):
    task: str
    node_results: dict[str, Any]
    current_node: str
    status: str

# 创建图
graph = StateGraph(TeamState)
graph.add_node("global_supervisor", global_supervisor_fn)
graph.add_node("node_supervisor", node_supervisor_fn)
graph.add_node("agent_executor", agent_executor_fn)
```

### 2. SSE (Server-Sent Events) Implementation

**Decision**: 使用 FastAPI 的 StreamingResponse 配合 asyncio.Queue

**Rationale**:
- FastAPI 原生支持 StreamingResponse
- 无需额外依赖
- 支持异步生成器模式
- 符合 HTTP/1.1 标准，兼容性好

**Alternatives Considered**:
- WebSocket: 双向通信，本场景不需要
- Long Polling: 效率低，延迟高
- Server-Sent Events (第三方库): 增加依赖

**Implementation Pattern**:
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio

async def event_generator(execution_id: str):
    queue = asyncio.Queue()
    # 注册队列到执行监听器
    while True:
        event = await queue.get()
        yield f"data: {json.dumps(event)}\n\n"
        if event.get("type") == "complete":
            break

@app.get("/executions/{id}/stream")
async def stream_execution(id: str):
    return StreamingResponse(
        event_generator(id),
        media_type="text/event-stream"
    )
```

### 3. Topology Validation (DAG)

**Decision**: 使用 DFS 进行循环检测，使用并查集检测孤立节点

**Rationale**:
- 纯 Python 实现，无需额外依赖
- 算法复杂度 O(V+E)，满足性能要求
- 可提供详细的错误信息

**Alternatives Considered**:
- NetworkX: 功能强大但依赖重
- graphlib.TopologicalSorter: Python 3.9+ 内置，但错误信息有限

**Implementation Pattern**:
```python
def validate_topology(nodes: list, edges: list) -> ValidationResult:
    # 1. 构建邻接表
    graph = defaultdict(list)
    in_degree = defaultdict(int)

    # 2. 检测循环 (Kahn's algorithm)
    # 3. 检测孤立节点
    # 4. 验证节点引用

    return ValidationResult(valid=True, errors=[])
```

### 4. JSON Schema Validation for Output

**Decision**: 使用 jsonschema 库进行验证，结合 LLM 重试机制

**Rationale**:
- jsonschema 是 Python 标准 JSON Schema 验证库
- 支持 Draft 7 及以上版本
- 可集成到 LangChain output parser

**Alternatives Considered**:
- Pydantic: 更适合预定义结构，动态 schema 支持较弱
- fastjsonschema: 更快但功能有限

**Implementation Pattern**:
```python
from jsonschema import validate, ValidationError
from tenacity import retry, stop_after_attempt

@retry(stop=stop_after_attempt(3))
async def parse_structured_output(raw_output: str, schema: dict) -> dict:
    try:
        result = json.loads(raw_output)
        validate(instance=result, schema=schema)
        return result
    except (json.JSONDecodeError, ValidationError):
        # 重新调用 LLM 获取正确格式
        raise
```

### 5. Concurrent Execution Limiting

**Decision**: 使用 asyncio.Semaphore 控制并发执行数

**Rationale**:
- Python 标准库，无额外依赖
- 与 async/await 模式完美配合
- 简单高效

**Alternatives Considered**:
- 外部队列 (Redis/RabbitMQ): 增加运维复杂度
- 数据库锁: 性能开销大

**Implementation Pattern**:
```python
class ExecutionManager:
    def __init__(self, max_concurrent: int = 100):
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def execute(self, team_id: str, task: str):
        async with self._semaphore:
            return await self._run_execution(team_id, task)
```

### 6. Execution Snapshot (Configuration Versioning)

**Decision**: 执行时将当前 topology_config 复制到 Execution 记录

**Rationale**:
- 简单直接，无需复杂版本管理
- 保证执行结果可追溯
- 存储开销可接受（JSONB 压缩）

**Alternatives Considered**:
- 独立版本表: 增加复杂度
- Git-like 版本控制: 过度设计

**Implementation Pattern**:
```python
class Execution(Base):
    # ... existing fields
    topology_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
```

### 7. Error Handling & Retry Strategy

**Decision**: 使用 tenacity 库实现指数退避重试

**Rationale**:
- 项目已依赖 tenacity>=9.0.0
- 支持多种重试策略
- 与 async 兼容

**Implementation Pattern**:
```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(LLMServiceError)
)
async def call_llm(prompt: str) -> str:
    # LLM 调用逻辑
    pass
```

## Dependencies Summary

| Dependency | Version | Purpose | Status |
|------------|---------|---------|--------|
| langgraph | >=0.2.0 | Agent orchestration | Already in pyproject.toml |
| tenacity | >=9.0.0 | Retry mechanism | Already in pyproject.toml |
| jsonschema | - | Output validation | Need to add |

### 8. Data Retention (30-Day Cleanup)

**Decision**: 使用 APScheduler 定时任务清理过期数据

**Rationale**:
- 不引入外部调度系统（如Celery）
- APScheduler 轻量级，可直接嵌入应用
- 支持 async job 执行

**Implementation Pattern**:
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

scheduler = AsyncIOScheduler()

async def cleanup_expired_executions():
    cutoff = datetime.utcnow() - timedelta(days=30)
    async with get_session() as db:
        await db.execute(
            delete(Execution).where(Execution.created_at < cutoff)
        )
        await db.commit()

# 每天凌晨2点执行
scheduler.add_job(cleanup_expired_executions, 'cron', hour=2)
```

**Alternative**: 使用 PostgreSQL 分区表按月分区，自动DROP旧分区

### 9. Sensitive Data Masking

**Decision**: 在 API 响应序列化层进行脱敏

**Rationale**:
- 集中处理，避免遗漏
- 不影响数据库存储（可能需要用于调试）
- 可配置脱敏规则

**Implementation Pattern**:
```python
import re

SENSITIVE_PATTERNS = [
    (r'sk-[a-zA-Z0-9]{48}', '***API_KEY***'),  # OpenAI
    (r'sk-ant-[a-zA-Z0-9-]{95}', '***API_KEY***'),  # Anthropic
    (r'"api_key":\s*"[^"]+?"', '"api_key": "***"'),
]

def mask_sensitive_data(data: dict) -> dict:
    json_str = json.dumps(data)
    for pattern, replacement in SENSITIVE_PATTERNS:
        json_str = re.sub(pattern, replacement, json_str)
    return json.loads(json_str)

class ExecutionDetailResponse(BaseModel):
    @model_validator(mode='after')
    def mask_secrets(self) -> 'ExecutionDetailResponse':
        if self.input_data:
            self.input_data = mask_sensitive_data(self.input_data)
        if self.output_data:
            self.output_data = mask_sensitive_data(self.output_data)
        return self
```

### 10. Execution Cancellation

**Decision**: 使用状态标志位 + asyncio 协程取消

**Rationale**:
- 简单可靠
- 不需要外部依赖
- 与 LangGraph 中断机制兼容

**Implementation Pattern**:
```python
class ExecutionManager:
    def __init__(self):
        self._running_tasks: dict[str, asyncio.Task] = {}

    async def cancel_execution(self, execution_id: str):
        # 1. 更新数据库状态
        async with get_session() as db:
            execution = await db.get(Execution, execution_id)
            if execution.status != ExecutionStatus.RUNNING:
                raise BadRequestError("Execution not running")
            execution.status = ExecutionStatus.CANCELLED
            await db.commit()

        # 2. 取消协程
        if execution_id in self._running_tasks:
            self._running_tasks[execution_id].cancel()
            try:
                await self._running_tasks[execution_id]
            except asyncio.CancelledError:
                pass
```

## Dependencies Summary

| Dependency | Version | Purpose | Status |
|------------|---------|---------|--------|
| langgraph | >=0.2.0 | Agent orchestration | Already in pyproject.toml |
| tenacity | >=9.0.0 | Retry mechanism | Already in pyproject.toml |
| jsonschema | - | Output validation | Need to add |
| apscheduler | >=3.10.0 | Data cleanup scheduling | Need to add |

## Action Items

1. 添加 `jsonschema` 到 pyproject.toml dependencies
2. 添加 `apscheduler` 到 pyproject.toml dependencies
3. 在 team.py 模型中添加 topology_snapshot 字段到 Execution
4. 创建 utils/topology.py 实现 DAG 验证
5. 创建 agents/ 目录结构实现 LangGraph workflow
6. 在 schemas/ 中实现敏感数据脱敏逻辑
7. 创建 utils/scheduler.py 实现定时清理任务
