---
inclusion: fileMatch
fileMatchPattern: "**/api/**/*.py"
---

# API 开发指南

## API 端点设计原则

### RESTful 规范
- 使用名词表示资源，避免动词
- 使用复数形式 (`/teams` 而非 `/team`)
- 使用 HTTP 方法表达操作意图
- 使用嵌套路由表达资源关系

### 版本控制
```python
# 所有 API 必须包含版本号
/api/v1/teams
/api/v1/providers
/api/v1/executions
```

## LLM 配置管理 API

### 供应商管理端点
```python
# app/api/v1/providers.py
from fastapi import APIRouter, HTTPException, status
from app.schemas.provider import ProviderCreate, ProviderResponse, ProviderUpdate

router = APIRouter(prefix="/providers", tags=["providers"])

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ProviderResponse)
async def create_provider(provider: ProviderCreate):
    """创建新的模型供应商配置"""
    pass

@router.get("/", response_model=list[ProviderResponse])
async def list_providers(
    skip: int = 0,
    limit: int = 100,
    is_active: bool | None = None
):
    """获取供应商列表，支持分页和过滤"""
    pass

@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(provider_id: str):
    """获取供应商详情"""
    pass

@router.put("/{provider_id}", response_model=ProviderResponse)
async def update_provider(provider_id: str, provider: ProviderUpdate):
    """更新供应商配置"""
    pass

@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(provider_id: str):
    """删除供应商（软删除）"""
    pass

@router.patch("/{provider_id}/status")
async def toggle_provider_status(provider_id: str, is_active: bool):
    """启用/禁用供应商"""
    pass
```

### 接入点管理端点
```python
@router.post("/providers/{provider_id}/endpoints", status_code=201)
async def create_endpoint(provider_id: str, endpoint: EndpointCreate):
    """为供应商创建接入点"""
    pass

@router.get("/providers/{provider_id}/endpoints")
async def list_endpoints(provider_id: str):
    """获取供应商的所有接入点"""
    pass

@router.post("/endpoints/{endpoint_id}/health-check")
async def health_check_endpoint(endpoint_id: str):
    """执行接入点健康检查"""
    pass
```

### 密钥管理端点
```python
@router.post("/providers/{provider_id}/credentials", status_code=201)
async def add_credential(provider_id: str, credential: CredentialCreate):
    """添加访问密钥（自动加密存储）"""
    # 注意：密钥在存储前必须加密
    pass

@router.get("/providers/{provider_id}/credentials")
async def list_credentials(provider_id: str):
    """获取密钥列表（脱敏显示）"""
    # 返回的密钥必须脱敏，只显示前4位和后4位
    pass

@router.post("/credentials/{credential_id}/validate")
async def validate_credential(credential_id: str):
    """验证密钥有效性"""
    pass
```

### 模型管理端点
```python
@router.post("/providers/{provider_id}/models/sync")
async def sync_models(provider_id: str):
    """从供应商同步可用模型列表"""
    pass

@router.get("/models")
async def list_models(
    provider_id: str | None = None,
    model_type: str | None = None,
    capability: str | None = None
):
    """获取模型列表，支持多维度过滤"""
    pass

@router.get("/models/by-capability/{capability}")
async def get_models_by_capability(capability: str):
    """按能力查询模型"""
    pass
```

## Agent Team 管理 API

### Team 创建和管理
```python
# app/api/v1/teams.py
from fastapi import APIRouter, BackgroundTasks
from app.schemas.team import TeamCreate, TeamResponse, TopologyConfig

router = APIRouter(prefix="/teams", tags=["teams"])

@router.post("/", status_code=201, response_model=TeamResponse)
async def create_team(team_config: TeamCreate):
    """创建 Agent Team
    
    接收拓扑结构配置，验证后创建 Team。
    验证项：
    - 模型供应商和模型 ID 必须存在
    - 工具必须已注册
    - 节点 ID 唯一性
    - 边引用的节点存在性
    """
    pass

@router.get("/", response_model=list[TeamResponse])
async def list_teams(
    page: int = 1,
    size: int = 20,
    status: str | None = None
):
    """获取 Team 列表"""
    pass

@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(team_id: str):
    """获取 Team 详情"""
    pass

@router.delete("/{team_id}", status_code=204)
async def delete_team(team_id: str):
    """删除 Team"""
    pass
```

### Team 执行端点
```python
from fastapi.responses import StreamingResponse
from app.schemas.execution import ExecutionRequest, ExecutionResponse

@router.post("/{team_id}/execute")
async def execute_team(
    team_id: str,
    execution_request: ExecutionRequest,
    background_tasks: BackgroundTasks
):
    """触发 Team 执行
    
    支持流式和非流式两种模式：
    - stream=true: 返回 SSE 流
    - stream=false: 等待执行完成后返回结果
    """
    if execution_request.stream:
        return StreamingResponse(
            execute_team_stream(team_id, execution_request),
            media_type="text/event-stream"
        )
    else:
        result = await execute_team_sync(team_id, execution_request)
        return result

async def execute_team_stream(team_id: str, request: ExecutionRequest):
    """生成 SSE 事件流"""
    yield f"event: execution_start\n"
    yield f"data: {json.dumps({'team_id': team_id, 'execution_id': '...'})}\n\n"
    
    # 执行过程中持续 yield 事件
    async for event in team_executor.execute(team_id, request):
        yield f"event: {event.type}\n"
        yield f"data: {json.dumps(event.data)}\n\n"
    
    yield f"event: execution_complete\n"
    yield f"data: {json.dumps({'status': 'success'})}\n\n"
```

### 结构化输出端点
```python
from app.schemas.structured_output import StructuredOutputRequest, StructuredOutputResponse

@router.post("/{team_id}/structured-output", response_model=StructuredOutputResponse)
async def generate_structured_output(
    team_id: str,
    request: StructuredOutputRequest
):
    """生成结构化输出
    
    基于执行结果和提供的 JSON Schema，生成结构化数据。
    使用 LLM 的结构化输出能力（如 OpenAI 的 JSON mode）。
    """
    pass
```

### 执行历史端点
```python
@router.get("/{team_id}/executions")
async def list_executions(
    team_id: str,
    page: int = 1,
    size: int = 20,
    status: str | None = None
):
    """获取 Team 的执行历史"""
    pass

@router.get("/executions/{execution_id}")
async def get_execution_detail(execution_id: str):
    """获取执行详情，包括完整日志"""
    pass
```

## 请求/响应模型示例

### Provider 模型
```python
from pydantic import BaseModel, Field
from datetime import datetime

class ProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., description="供应商类型：openai, anthropic, bedrock 等")
    description: str | None = None

class ProviderResponse(BaseModel):
    id: str
    name: str
    type: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
```

### Team 模型
```python
class NodeConfig(BaseModel):
    node_id: str
    node_name: str
    node_type: str
    attributes: dict = Field(default_factory=dict)
    agents: list[AgentConfig]
    supervisor_config: SupervisorConfig

class EdgeConfig(BaseModel):
    source_node_id: str
    target_node_id: str
    relation_type: str
    attributes: dict = Field(default_factory=dict)

class TopologyConfig(BaseModel):
    nodes: list[NodeConfig] = Field(..., min_items=1, max_items=100)
    edges: list[EdgeConfig] = Field(default_factory=list)
    global_supervisor: GlobalSupervisorConfig

class TeamCreate(BaseModel):
    topology: TopologyConfig
    team_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    timeout_seconds: int = Field(default=300, ge=1, le=1800)
    max_iterations: int = Field(default=50, ge=1, le=200)

class TeamResponse(BaseModel):
    team_id: str
    status: str
    created_at: datetime
    topology_summary: dict
```

## 错误处理

### 标准错误响应
```python
class ErrorDetail(BaseModel):
    error_code: str
    error_message: str
    details: dict | None = None

# 使用示例
@router.get("/{team_id}")
async def get_team(team_id: str):
    team = await team_service.get_by_id(team_id)
    if not team:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "TEAM_NOT_FOUND",
                "error_message": f"Team with ID '{team_id}' not found"
            }
        )
    return team
```

### 常见错误码
- `TEAM_NOT_FOUND`: Team 不存在
- `INVALID_TOPOLOGY`: 拓扑配置无效
- `MODEL_NOT_FOUND`: 引用的模型不存在
- `TOOL_NOT_REGISTERED`: 工具未注册
- `EXECUTION_TIMEOUT`: 执行超时
- `CREDENTIAL_INVALID`: 密钥无效
- `VALIDATION_ERROR`: 输入验证失败

## 性能优化

### 分页
```python
# 所有列表接口必须支持分页
@router.get("/teams")
async def list_teams(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    skip = (page - 1) * size
    teams = await team_service.list(skip=skip, limit=size)
    total = await team_service.count()
    
    return {
        "items": teams,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }
```

### 缓存
```python
from fastapi_cache.decorator import cache

@router.get("/models")
@cache(expire=300)  # 缓存 5 分钟
async def list_models():
    return await model_service.list_all()
```

## 安全性

### 认证和授权
```python
from fastapi import Depends, Security
from app.auth import get_current_user, require_permission

@router.post("/teams", dependencies=[Depends(get_current_user)])
async def create_team(team_config: TeamCreate):
    """需要认证才能创建 Team"""
    pass

@router.delete("/{team_id}")
async def delete_team(
    team_id: str,
    current_user = Depends(require_permission("team:delete"))
):
    """需要特定权限才能删除"""
    pass
```

### 速率限制
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/{team_id}/execute")
@limiter.limit("10/minute")  # 每分钟最多 10 次
async def execute_team(team_id: str, request: ExecutionRequest):
    pass
```

## 文档和示例

### OpenAPI 配置
```python
# 为每个端点添加详细的文档
@router.post(
    "/",
    status_code=201,
    response_model=TeamResponse,
    summary="创建 Agent Team",
    description="接收拓扑结构配置，动态创建 Agent Team",
    responses={
        201: {"description": "Team 创建成功"},
        400: {"description": "拓扑配置无效"},
        404: {"description": "引用的模型或工具不存在"}
    }
)
async def create_team(team_config: TeamCreate):
    pass
```

### 请求示例
```python
class TeamCreate(BaseModel):
    # ... 字段定义
    
    class Config:
        json_schema_extra = {
            "example": {
                "topology": {
                    "nodes": [
                        {
                            "node_id": "node-1",
                            "node_name": "Log Analyzer",
                            "node_type": "service",
                            "agents": [...]
                        }
                    ],
                    "edges": [],
                    "global_supervisor": {...}
                },
                "team_name": "AIOps Diagnostic Team",
                "timeout_seconds": 300
            }
        }
```
