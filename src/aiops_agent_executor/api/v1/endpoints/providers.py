"""供应商管理API接口

提供LLM模型供应商的完整生命周期管理，包括创建、查询、更新、删除和状态管理。
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from aiops_agent_executor.db.session import get_db_session
from aiops_agent_executor.schemas import (
    ProviderCreate,
    ProviderResponse,
    ProviderUpdate,
)
from aiops_agent_executor.services.provider_service import ProviderService

router = APIRouter(prefix="/providers", tags=["providers"])


def get_provider_service(db: AsyncSession = Depends(get_db_session)) -> ProviderService:
    """Dependency to get provider service instance."""
    return ProviderService(db)


@router.post(
    "",
    response_model=ProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建供应商",
    description="""
创建一个新的LLM模型供应商配置。

**支持的供应商类型**:
- `openai` - OpenAI (GPT系列)
- `anthropic` - Anthropic (Claude系列)
- `aws_bedrock` - AWS Bedrock (多模型托管)
- `azure_openai` - Azure OpenAI Service
- `aliyun_dashscope` - 阿里云通义千问
- `baidu_qianfan` - 百度文心一言
- `ollama` - Ollama (本地部署)
- `vllm` - vLLM (本地部署)

**使用流程**:
1. 创建供应商 → 2. 添加接入点 → 3. 配置密钥 → 4. 同步模型

**示例请求**:
```json
{
    "name": "OpenAI Production",
    "type": "openai",
    "description": "生产环境OpenAI配置"
}
```
""",
    responses={
        201: {"description": "供应商创建成功"},
        400: {"description": "请求参数错误"},
        409: {"description": "供应商名称已存在"},
    },
)
async def create_provider(
    provider_in: ProviderCreate,
    service: ProviderService = Depends(get_provider_service),
) -> ProviderResponse:
    """创建新的LLM供应商配置"""
    provider = await service.create_provider(provider_in)
    return ProviderResponse.model_validate(provider)


@router.get(
    "",
    response_model=list[ProviderResponse],
    summary="获取供应商列表",
    description="""
分页获取所有已配置的LLM供应商列表。

**查询参数**:
- `skip`: 跳过的记录数（用于分页）
- `limit`: 返回的最大记录数
- `is_active`: 筛选启用/禁用状态的供应商

**返回信息**:
返回供应商的基本信息，不包含敏感的密钥数据。

**排序规则**:
按创建时间倒序排列，最新创建的供应商排在前面。
""",
    responses={
        200: {"description": "成功返回供应商列表"},
    },
)
async def list_providers(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回的最大记录数"),
    is_active: bool | None = Query(None, description="筛选启用状态：true=仅启用, false=仅禁用, 不传=全部"),
    service: ProviderService = Depends(get_provider_service),
) -> list[ProviderResponse]:
    """获取供应商列表"""
    providers = await service.list_providers(skip=skip, limit=limit, is_active=is_active)
    return [ProviderResponse.model_validate(p) for p in providers]


@router.get(
    "/{provider_id}",
    response_model=ProviderResponse,
    summary="获取供应商详情",
    description="""
根据供应商ID获取详细信息。

**返回内容**:
- 供应商基本信息（名称、类型、描述）
- 状态信息（是否启用）
- 时间戳（创建时间、更新时间）

**注意**: 此接口不返回关联的接入点、密钥和模型信息，请使用对应的子资源接口查询。
""",
    responses={
        200: {"description": "成功返回供应商详情"},
        404: {"description": "供应商不存在"},
    },
)
async def get_provider(
    provider_id: uuid.UUID,
    service: ProviderService = Depends(get_provider_service),
) -> ProviderResponse:
    """获取指定供应商的详细信息"""
    provider = await service.get_provider(provider_id)
    return ProviderResponse.model_validate(provider)


@router.put(
    "/{provider_id}",
    response_model=ProviderResponse,
    summary="更新供应商信息",
    description="""
更新供应商的配置信息。

**可更新字段**:
- `name`: 供应商名称
- `description`: 供应商描述
- `is_active`: 启用/禁用状态

**注意事项**:
- 供应商类型（type）创建后不可修改
- 禁用供应商会影响所有使用该供应商的Agent执行
- 名称修改需确保唯一性

**示例请求**:
```json
{
    "name": "OpenAI Production - Updated",
    "description": "更新后的描述信息",
    "is_active": true
}
```
""",
    responses={
        200: {"description": "供应商更新成功"},
        400: {"description": "请求参数错误"},
        404: {"description": "供应商不存在"},
        409: {"description": "供应商名称已被占用"},
    },
)
async def update_provider(
    provider_id: uuid.UUID,
    provider_in: ProviderUpdate,
    service: ProviderService = Depends(get_provider_service),
) -> ProviderResponse:
    """更新供应商配置"""
    provider = await service.update_provider(provider_id, provider_in)
    return ProviderResponse.model_validate(provider)


@router.delete(
    "/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除供应商",
    description="""
删除指定的供应商配置。

**删除行为**:
- 执行物理删除，关联的接入点、密钥、模型配置会一并级联删除
- 删除后不可恢复

**前置检查**:
- 如有正在运行的Agent团队使用此供应商，删除会被拒绝
- 建议先禁用供应商，确认无影响后再删除

**注意**: 此操作不可逆，请谨慎执行。
""",
    responses={
        204: {"description": "供应商删除成功"},
        404: {"description": "供应商不存在"},
        409: {"description": "供应商正在被使用，无法删除"},
    },
)
async def delete_provider(
    provider_id: uuid.UUID,
    service: ProviderService = Depends(get_provider_service),
) -> None:
    """删除供应商"""
    await service.delete_provider(provider_id)


@router.patch(
    "/{provider_id}/status",
    response_model=ProviderResponse,
    summary="更新供应商状态",
    description="""
快速切换供应商的启用/禁用状态。

**使用场景**:
- 临时禁用某个供应商进行维护
- 在多个供应商之间快速切换
- 紧急情况下快速下线某个供应商

**状态影响**:
- 禁用后，使用该供应商的新请求会被拒绝
- 正在执行中的任务不受影响
- 重新启用后立即生效

**请求示例**:
```
PATCH /api/v1/providers/{id}/status?is_active=false
```
""",
    responses={
        200: {"description": "状态更新成功"},
        404: {"description": "供应商不存在"},
    },
)
async def update_provider_status(
    provider_id: uuid.UUID,
    is_active: bool = Query(..., description="目标状态：true=启用, false=禁用"),
    service: ProviderService = Depends(get_provider_service),
) -> ProviderResponse:
    """更新供应商启用状态"""
    provider = await service.update_provider_status(provider_id, is_active)
    return ProviderResponse.model_validate(provider)
