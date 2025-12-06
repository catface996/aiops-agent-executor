"""模型管理API接口

管理LLM供应商提供的可用模型，包括模型能力、定价、上下文窗口等配置。
支持从供应商自动同步模型列表，也支持手动添加自定义模型配置。
"""

import uuid

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from aiops_agent_executor.db.models import ModelStatus, ModelType
from aiops_agent_executor.db.session import get_db_session
from aiops_agent_executor.schemas import (
    ModelCreate,
    ModelResponse,
    ModelUpdate,
)
from aiops_agent_executor.services.model_service import ModelService

router = APIRouter(tags=["models"])


def get_model_service(db: AsyncSession = Depends(get_db_session)) -> ModelService:
    """Dependency to get model service instance."""
    return ModelService(db)


@router.post(
    "/providers/{provider_id}/models/sync",
    response_model=list[ModelResponse],
    summary="同步模型列表",
    description="""
从供应商API自动同步可用模型列表。

**同步内容**:
- 模型ID和名称
- 上下文窗口大小
- 最大输出Token数
- 模型能力标签
- 定价信息（如可获取）

**同步策略**:
- 新模型自动添加
- 已有模型更新信息
- 已下线模型标记为废弃（不自动删除）

**支持自动同步的供应商**:
- OpenAI: 完全支持
- Anthropic: 完全支持
- AWS Bedrock: 支持（需要正确的区域配置）
- Azure OpenAI: 支持（需要部署名称）
- 阿里云: 支持
- 百度: 部分支持

**返回结果**:
返回同步后的完整模型列表，包含新增和更新的模型。

**注意**: 同步可能需要几秒钟，请耐心等待。
""",
    responses={
        200: {"description": "模型同步成功"},
        404: {"description": "供应商不存在"},
        400: {"description": "供应商未配置有效的密钥"},
        503: {"description": "无法连接供应商API"},
    },
)
async def sync_provider_models(
    provider_id: uuid.UUID = Path(..., description="供应商ID"),
    service: ModelService = Depends(get_model_service),
) -> list[ModelResponse]:
    """从供应商同步可用模型列表"""
    models = await service.sync_models(provider_id)
    return [ModelResponse.model_validate(m) for m in models]


@router.post(
    "/providers/{provider_id}/models",
    response_model=ModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="手动添加模型",
    description="""
为供应商手动添加模型配置。

**使用场景**:
- 添加供应商API中未列出的模型
- 添加自托管模型（如Ollama、vLLM）
- 添加私有部署的模型

**示例请求**:
```json
{
    "model_id": "llama3-70b",
    "name": "Llama 3 70B",
    "type": "chat",
    "context_window": 8192,
    "max_output_tokens": 4096,
    "capabilities": {
        "text_generation": true,
        "chat": true,
        "streaming": true
    }
}
```
""",
    responses={
        201: {"description": "模型创建成功"},
        400: {"description": "模型ID已存在"},
        404: {"description": "供应商不存在"},
    },
)
async def create_model(
    provider_id: uuid.UUID = Path(..., description="供应商ID"),
    model_in: ModelCreate = ...,
    service: ModelService = Depends(get_model_service),
) -> ModelResponse:
    """手动为供应商添加模型"""
    model = await service.create_model(provider_id, model_in)
    return ModelResponse.model_validate(model)


@router.get(
    "/models",
    response_model=list[ModelResponse],
    summary="获取所有模型",
    description="""
获取系统中所有已配置的LLM模型。

**筛选参数**:
- `provider_id`: 按供应商筛选
- `type`: 按模型类型筛选（chat/completion/embedding/vision）
- `capability`: 按能力筛选（如function_calling）
- `status`: 按状态筛选（available/maintenance/deprecated）

**模型类型说明**:
| 类型 | 说明 | 典型用途 |
|------|------|----------|
| chat | 对话模型 | 智能对话、问答 |
| completion | 补全模型 | 文本生成、代码补全 |
| embedding | 嵌入模型 | 向量化、语义搜索 |
| vision | 视觉模型 | 图像理解、多模态 |

**排序规则**:
按供应商分组，组内按模型名称排序。
""",
    responses={
        200: {"description": "成功返回模型列表"},
    },
)
async def list_models(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(50, ge=1, le=200, description="返回的最大记录数"),
    provider_id: uuid.UUID | None = Query(None, description="按供应商ID筛选"),
    model_type: ModelType | None = Query(
        None, alias="type", description="按模型类型筛选: chat/completion/embedding/vision"
    ),
    capability: str | None = Query(
        None, description="按能力筛选: function_calling/vision/streaming等"
    ),
    model_status: ModelStatus | None = Query(
        None, alias="status", description="按状态筛选: available/maintenance/deprecated"
    ),
    service: ModelService = Depends(get_model_service),
) -> list[ModelResponse]:
    """获取所有模型列表"""
    models = await service.list_models(
        provider_id=provider_id,
        model_type=model_type,
        capability=capability,
        status=model_status,
        skip=skip,
        limit=limit,
    )
    return [ModelResponse.model_validate(m) for m in models]


@router.get(
    "/models/{model_id}",
    response_model=ModelResponse,
    summary="获取模型详情",
    description="""
获取指定模型的详细配置信息。

**返回内容**:
- 基本信息：ID、名称、版本、所属供应商
- 能力配置：上下文窗口、最大输出Token
- 定价信息：输入/输出每千Token价格
- 能力标签：支持的功能列表
- 状态信息：当前可用状态

**能力标签说明**:
```json
{
    "capabilities": {
        "text_generation": true,
        "chat": true,
        "function_calling": true,
        "vision": false,
        "streaming": true,
        "json_mode": true
    }
}
```
""",
    responses={
        200: {"description": "成功返回模型详情"},
        404: {"description": "模型不存在"},
    },
)
async def get_model(
    model_id: uuid.UUID = Path(..., description="模型ID"),
    service: ModelService = Depends(get_model_service),
) -> ModelResponse:
    """获取指定模型的详细信息"""
    model = await service.get_model(model_id)
    return ModelResponse.model_validate(model)


@router.put(
    "/models/{model_id}",
    response_model=ModelResponse,
    summary="更新模型配置",
    description="""
更新模型的配置信息。

**可更新字段**:
- `name`: 显示名称
- `context_window`: 上下文窗口大小
- `max_output_tokens`: 最大输出Token数
- `input_price`: 输入价格（每千Token）
- `output_price`: 输出价格（每千Token）
- `capabilities`: 能力标签
- `status`: 状态（available/maintenance/deprecated）

**更新场景**:
- 修正自动同步的错误信息
- 添加自定义能力标签
- 调整定价信息
- 标记模型维护或废弃状态

**注意**: 模型ID（model_id）和供应商关联不可修改。
""",
    responses={
        200: {"description": "模型更新成功"},
        400: {"description": "请求参数错误"},
        404: {"description": "模型不存在"},
    },
)
async def update_model(
    model_id: uuid.UUID = Path(..., description="模型ID"),
    model_in: ModelUpdate = ...,
    service: ModelService = Depends(get_model_service),
) -> ModelResponse:
    """更新模型配置"""
    model = await service.update_model(model_id, model_in)
    return ModelResponse.model_validate(model)


@router.get(
    "/models/by-capability/{capability}",
    response_model=list[ModelResponse],
    summary="按能力查询模型",
    description="""
查询具有指定能力的所有模型。

**常用能力标签**:
| 能力 | 说明 |
|------|------|
| text_generation | 文本生成 |
| chat | 对话能力 |
| code_generation | 代码生成 |
| function_calling | 函数/工具调用 |
| vision | 图像理解 |
| embedding | 向量嵌入 |
| json_mode | JSON格式输出 |
| streaming | 流式输出 |

**使用场景**:
- 查找支持函数调用的模型用于Agent
- 查找支持视觉的模型处理图像任务
- 查找嵌入模型用于RAG系统

**返回结果**:
返回所有具有指定能力且状态为可用的模型，按推荐度排序。
""",
    responses={
        200: {"description": "成功返回符合条件的模型列表"},
    },
)
async def get_models_by_capability(
    capability: str = Path(..., description="能力标签名称"),
    service: ModelService = Depends(get_model_service),
) -> list[ModelResponse]:
    """按能力查询模型"""
    models = await service.get_models_by_capability(capability)
    return [ModelResponse.model_validate(m) for m in models]
