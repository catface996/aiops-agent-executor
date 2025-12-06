"""密钥管理API接口

安全管理LLM供应商的API密钥，支持加密存储、密钥验证和轮换。
所有密钥使用AES-256加密存储，返回时自动脱敏处理。
"""

import uuid

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from aiops_agent_executor.db.session import get_db_session
from aiops_agent_executor.schemas import (
    CredentialCreate,
    CredentialResponse,
    CredentialUpdate,
    ValidationResult,
)
from aiops_agent_executor.services.credential_service import CredentialService

router = APIRouter(tags=["credentials"])


def get_credential_service(db: AsyncSession = Depends(get_db_session)) -> CredentialService:
    """Dependency to get credential service instance."""
    return CredentialService(db)


@router.post(
    "/providers/{provider_id}/credentials",
    response_model=CredentialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="添加密钥",
    description="""
为指定供应商添加新的API访问密钥。

**安全说明**:
- 密钥使用AES-256加密后存储
- 存储后原始密钥不可查看
- 建议定期轮换密钥

**密钥类型**:
| 供应商 | 需要的密钥 |
|--------|-----------|
| OpenAI | api_key |
| Anthropic | api_key |
| AWS Bedrock | api_key (Access Key) + secret_key (Secret Key) |
| Azure OpenAI | api_key |
| 阿里云 | api_key |
| 百度 | api_key + secret_key |

**示例请求**:
```json
{
    "alias": "生产环境密钥",
    "api_key": "sk-xxxxxxxxxxxxxxxx",
    "secret_key": null,
    "expires_at": "2025-12-31T23:59:59Z",
    "quota_limit": 1000000
}
```

**配额说明**:
- `quota_limit`: 可选，设置该密钥的使用配额限制
- `expires_at`: 可选，设置密钥过期时间，到期后自动失效
""",
    responses={
        201: {"description": "密钥添加成功"},
        400: {"description": "请求参数错误或超出密钥数量限制"},
        404: {"description": "供应商不存在"},
    },
)
async def create_credential(
    provider_id: uuid.UUID = Path(..., description="供应商ID"),
    credential_in: CredentialCreate = ...,
    service: CredentialService = Depends(get_credential_service),
) -> CredentialResponse:
    """为供应商添加新的API密钥"""
    credential = await service.create_credential(provider_id, credential_in)
    return CredentialResponse.model_validate(credential)


@router.get(
    "/providers/{provider_id}/credentials",
    response_model=list[CredentialResponse],
    summary="获取密钥列表",
    description="""
获取指定供应商的所有密钥配置（密钥值已脱敏）。

**返回信息**:
- 密钥别名和ID
- 脱敏后的API Key（仅显示末4位）
- 过期时间和配额信息
- 状态信息

**脱敏规则**:
- API Key: `****xxxx`（仅显示末4位）
- Secret Key: 完全隐藏，仅显示是否已配置

**安全提示**:
原始密钥值不可查询，如需更新请使用更新接口重新设置。
""",
    responses={
        200: {"description": "成功返回密钥列表（已脱敏）"},
        404: {"description": "供应商不存在"},
    },
)
async def list_provider_credentials(
    provider_id: uuid.UUID = Path(..., description="供应商ID"),
    service: CredentialService = Depends(get_credential_service),
) -> list[CredentialResponse]:
    """获取供应商的所有密钥（脱敏显示）"""
    credentials = await service.list_credentials(provider_id)
    return [CredentialResponse.model_validate(c) for c in credentials]


@router.put(
    "/credentials/{credential_id}",
    response_model=CredentialResponse,
    summary="更新密钥",
    description="""
更新密钥的配置信息。

**可更新字段**:
- `alias`: 密钥别名
- `api_key`: API密钥（可选，不传则保持原值）
- `secret_key`: Secret密钥（可选）
- `expires_at`: 过期时间
- `quota_limit`: 配额限制
- `is_active`: 启用/禁用

**密钥轮换**:
更新`api_key`字段即可完成密钥轮换，旧密钥立即失效。

**注意事项**:
- 更新密钥后，使用旧密钥的请求会立即失败
- 建议在低峰期执行密钥轮换
- 轮换前请确保新密钥已验证有效
""",
    responses={
        200: {"description": "密钥更新成功"},
        400: {"description": "请求参数错误"},
        404: {"description": "密钥不存在"},
    },
)
async def update_credential(
    credential_id: uuid.UUID = Path(..., description="密钥ID"),
    credential_in: CredentialUpdate = ...,
    service: CredentialService = Depends(get_credential_service),
) -> CredentialResponse:
    """更新密钥配置"""
    credential = await service.update_credential(credential_id, credential_in)
    return CredentialResponse.model_validate(credential)


@router.delete(
    "/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除密钥",
    description="""
删除指定的API密钥。

**删除限制**:
- 不能删除供应商唯一的有效密钥
- 建议先禁用密钥观察影响，再执行删除

**删除后果**:
- 密钥立即失效
- 使用该密钥的Agent调用会失败
- 删除操作不可恢复

**建议流程**:
1. 先添加新密钥并验证
2. 禁用旧密钥观察系统运行
3. 确认无问题后删除旧密钥
""",
    responses={
        204: {"description": "密钥删除成功"},
        400: {"description": "不能删除唯一的有效密钥"},
        404: {"description": "密钥不存在"},
    },
)
async def delete_credential(
    credential_id: uuid.UUID = Path(..., description="密钥ID"),
    service: CredentialService = Depends(get_credential_service),
) -> None:
    """删除密钥"""
    await service.delete_credential(credential_id)


@router.post(
    "/credentials/{credential_id}/validate",
    response_model=ValidationResult,
    summary="验证密钥",
    description="""
验证密钥的有效性，通过实际调用供应商API进行测试。

**验证内容**:
- 密钥格式正确性
- 密钥认证有效性
- 账户配额状态
- 权限范围检查

**返回结果**:
```json
{
    "valid": true,
    "validated_at": "2024-01-01T00:00:00Z",
    "details": {
        "account_status": "active",
        "remaining_quota": 850000
    }
}
```

**验证失败示例**:
```json
{
    "valid": false,
    "validated_at": "2024-01-01T00:00:00Z",
    "error": {
        "code": "EXPIRED",
        "message": "Credential has expired"
    }
}
```

**使用场景**:
- 新增密钥后验证有效性
- 定期检查密钥状态
- 排查认证相关问题
""",
    responses={
        200: {"description": "验证完成，返回验证结果"},
        404: {"description": "密钥不存在"},
    },
)
async def validate_credential(
    credential_id: uuid.UUID = Path(..., description="密钥ID"),
    service: CredentialService = Depends(get_credential_service),
) -> ValidationResult:
    """验证密钥有效性"""
    return await service.validate_credential(credential_id)
