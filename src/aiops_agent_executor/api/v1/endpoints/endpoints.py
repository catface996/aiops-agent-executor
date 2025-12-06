"""接入点管理API接口

管理LLM供应商的API接入点配置，包括URL、超时设置、重试策略等。
每个供应商可配置多个接入点，支持故障转移和负载均衡。
"""

import uuid

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from aiops_agent_executor.db.session import get_db_session
from aiops_agent_executor.schemas import (
    EndpointCreate,
    EndpointResponse,
    EndpointUpdate,
    HealthCheckResult,
)
from aiops_agent_executor.services.endpoint_service import EndpointService

router = APIRouter(tags=["endpoints"])


def get_endpoint_service(db: AsyncSession = Depends(get_db_session)) -> EndpointService:
    """Dependency to get endpoint service instance."""
    return EndpointService(db)


@router.post(
    "/providers/{provider_id}/endpoints",
    response_model=EndpointResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建接入点",
    description="""
为指定供应商创建新的API接入点。

**接入点用途**:
- 配置供应商的API访问地址
- 设置连接参数（超时、重试）
- 支持多区域部署和故障转移

**配置说明**:
| 参数 | 说明 | 默认值 |
|------|------|--------|
| base_url | API基础URL | 必填 |
| api_version | API版本 | 可选 |
| region | 区域标识 | 可选 |
| timeout_connect | 连接超时(秒) | 30 |
| timeout_read | 读取超时(秒) | 120 |
| retry_count | 重试次数 | 3 |
| is_default | 是否默认接入点 | false |

**示例请求**:
```json
{
    "name": "美西区域",
    "base_url": "https://api.openai.com/v1",
    "region": "us-west-2",
    "timeout_connect": 30,
    "timeout_read": 120,
    "retry_count": 3,
    "is_default": true
}
```

**注意**: 每个供应商只能有一个默认接入点，设置新的默认会自动取消原有默认。
""",
    responses={
        201: {"description": "接入点创建成功"},
        400: {"description": "请求参数错误或超出接入点数量限制"},
        404: {"description": "供应商不存在"},
    },
)
async def create_endpoint(
    provider_id: uuid.UUID = Path(..., description="供应商ID"),
    endpoint_in: EndpointCreate = ...,
    service: EndpointService = Depends(get_endpoint_service),
) -> EndpointResponse:
    """为供应商创建新的接入点"""
    endpoint = await service.create_endpoint(provider_id, endpoint_in)
    return EndpointResponse.model_validate(endpoint)


@router.get(
    "/providers/{provider_id}/endpoints",
    response_model=list[EndpointResponse],
    summary="获取接入点列表",
    description="""
获取指定供应商的所有接入点配置。

**返回信息**:
- 接入点基本配置（名称、URL、区域）
- 超时和重试设置
- 状态信息（是否启用、是否默认）

**排序规则**:
默认接入点排在首位，其余按创建时间排序。

**使用建议**:
- 建议为每个供应商配置至少2个接入点实现高可用
- 不同区域的接入点可用于就近访问优化
""",
    responses={
        200: {"description": "成功返回接入点列表"},
        404: {"description": "供应商不存在"},
    },
)
async def list_provider_endpoints(
    provider_id: uuid.UUID = Path(..., description="供应商ID"),
    service: EndpointService = Depends(get_endpoint_service),
) -> list[EndpointResponse]:
    """获取供应商的所有接入点"""
    endpoints = await service.list_endpoints(provider_id)
    return [EndpointResponse.model_validate(e) for e in endpoints]


@router.put(
    "/endpoints/{endpoint_id}",
    response_model=EndpointResponse,
    summary="更新接入点",
    description="""
更新接入点的配置信息。

**可更新字段**:
- `name`: 接入点名称
- `base_url`: API基础URL
- `api_version`: API版本
- `region`: 区域标识
- `timeout_connect`: 连接超时时间
- `timeout_read`: 读取超时时间
- `retry_count`: 重试次数
- `is_default`: 是否设为默认
- `is_active`: 是否启用

**更新影响**:
- 修改超时设置会影响后续的API调用
- 修改URL需确保新地址可访问
- 禁用默认接入点会自动选择另一个启用的接入点作为默认
""",
    responses={
        200: {"description": "接入点更新成功"},
        400: {"description": "请求参数错误"},
        404: {"description": "接入点不存在"},
    },
)
async def update_endpoint(
    endpoint_id: uuid.UUID = Path(..., description="接入点ID"),
    endpoint_in: EndpointUpdate = ...,
    service: EndpointService = Depends(get_endpoint_service),
) -> EndpointResponse:
    """更新接入点配置"""
    endpoint = await service.update_endpoint(endpoint_id, endpoint_in)
    return EndpointResponse.model_validate(endpoint)


@router.delete(
    "/endpoints/{endpoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除接入点",
    description="""
删除指定的接入点配置。

**删除限制**:
- 不能删除唯一的接入点（供应商至少需要一个接入点）
- 删除默认接入点会自动将另一个接入点设为默认

**注意**: 删除操作不可恢复，请确认后执行。
""",
    responses={
        204: {"description": "接入点删除成功"},
        400: {"description": "不能删除唯一的接入点"},
        404: {"description": "接入点不存在"},
    },
)
async def delete_endpoint(
    endpoint_id: uuid.UUID = Path(..., description="接入点ID"),
    service: EndpointService = Depends(get_endpoint_service),
) -> None:
    """删除接入点"""
    await service.delete_endpoint(endpoint_id)


@router.post(
    "/endpoints/{endpoint_id}/health-check",
    response_model=HealthCheckResult,
    summary="健康检查",
    description="""
对指定接入点执行健康检查，验证其可用性。

**检查内容**:
- 网络连通性测试
- API响应时间测量

**返回结果**:
```json
{
    "status": "healthy",
    "latency_ms": 156,
    "checked_at": "2024-01-01T00:00:00Z",
    "details": {
        "http_status": 200
    }
}
```

**状态说明**:
- `healthy`: 接入点正常可用
- `degraded`: 可用但响应较慢
- `unhealthy`: 接入点不可用

**使用场景**:
- 定期巡检接入点状态
- 故障排查时验证连通性
- 新增接入点后的验证测试
""",
    responses={
        200: {"description": "健康检查完成"},
        404: {"description": "接入点不存在"},
    },
)
async def health_check_endpoint(
    endpoint_id: uuid.UUID = Path(..., description="接入点ID"),
    service: EndpointService = Depends(get_endpoint_service),
) -> HealthCheckResult:
    """执行接入点健康检查"""
    return await service.health_check(endpoint_id)
