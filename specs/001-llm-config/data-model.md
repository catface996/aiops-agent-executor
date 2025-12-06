# Data Model: LLM配置管理

**Feature Branch**: `001-llm-config`
**Created**: 2025-12-06

## Entity Relationship Diagram

```
┌─────────────────┐
│    Provider     │
│─────────────────│
│ id (PK, UUID)   │
│ name            │
│ type (enum)     │
│ description     │
│ is_active       │
│ created_at      │
│ updated_at      │
│ deleted_at      │
└────────┬────────┘
         │ 1:N
    ┌────┴────┬────────────┐
    │         │            │
    ▼         ▼            ▼
┌─────────┐ ┌──────────┐ ┌─────────┐
│Endpoint │ │Credential│ │  Model  │
│─────────│ │──────────│ │─────────│
│ id (PK) │ │ id (PK)  │ │ id (PK) │
│provider │ │ provider │ │provider │
│ (FK)    │ │ (FK)     │ │ (FK)    │
│ ...     │ │ ...      │ │ ...     │
└─────────┘ └──────────┘ └─────────┘
```

---

## 1. Provider（供应商）

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-gen | 唯一标识符 |
| name | VARCHAR(100) | NOT NULL, UNIQUE | 供应商名称 |
| type | ENUM | NOT NULL | 供应商类型 |
| description | TEXT | NULLABLE | 描述信息 |
| is_active | BOOLEAN | DEFAULT true | 启用状态 |
| created_at | TIMESTAMP | NOT NULL, auto | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL, auto | 更新时间 |
| deleted_at | TIMESTAMP | NULLABLE | 软删除时间 |

### Provider Type Enum

```python
class ProviderType(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AWS_BEDROCK = "aws_bedrock"
    AZURE_OPENAI = "azure_openai"
    ALIYUN_DASHSCOPE = "aliyun_dashscope"
    BAIDU_QIANFAN = "baidu_qianfan"
    OLLAMA = "ollama"
    VLLM = "vllm"
```

### Validation Rules

- `name`: 1-100字符，唯一
- `type`: 必须是ProviderType枚举值
- 软删除: `deleted_at IS NOT NULL` 表示已删除

### State Transitions

```
[created] → [active] ←→ [inactive] → [deleted]
                ↓
          [in_use] (有Agent团队引用时)
```

---

## 2. Endpoint（接入点）

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-gen | 唯一标识符 |
| provider_id | UUID | FK, NOT NULL | 所属供应商 |
| name | VARCHAR(100) | NOT NULL | 接入点名称 |
| base_url | VARCHAR(500) | NOT NULL | API基础URL |
| api_version | VARCHAR(50) | NULLABLE | API版本 |
| region | VARCHAR(50) | NULLABLE | 区域标识 |
| timeout_connect | INTEGER | DEFAULT 30 | 连接超时(秒) |
| timeout_read | INTEGER | DEFAULT 120 | 读取超时(秒) |
| retry_count | INTEGER | DEFAULT 3 | 重试次数 |
| is_default | BOOLEAN | DEFAULT false | 是否默认 |
| is_active | BOOLEAN | DEFAULT true | 启用状态 |
| health_status | ENUM | DEFAULT healthy | 健康状态 |
| last_health_check | TIMESTAMP | NULLABLE | 最后健康检查时间 |
| created_at | TIMESTAMP | NOT NULL, auto | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL, auto | 更新时间 |

### Health Status Enum

```python
class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
```

### Validation Rules

- `base_url`: 必须是有效URL格式
- `timeout_connect`: 1-300秒
- `timeout_read`: 1-600秒
- `retry_count`: 0-10次
- 每个Provider只能有一个`is_default=true`的Endpoint
- 每个Provider至少保留一个Endpoint

### Indexes

- `idx_endpoint_provider`: (provider_id)
- `idx_endpoint_default`: (provider_id, is_default) WHERE is_default = true

---

## 3. Credential（密钥）

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-gen | 唯一标识符 |
| provider_id | UUID | FK, NOT NULL | 所属供应商 |
| alias | VARCHAR(100) | NOT NULL | 密钥别名 |
| api_key_encrypted | BYTEA | NOT NULL | 加密后的API Key |
| secret_key_encrypted | BYTEA | NULLABLE | 加密后的Secret Key |
| api_key_hint | VARCHAR(20) | NOT NULL | API Key提示(末4位) |
| has_secret_key | BOOLEAN | DEFAULT false | 是否有Secret Key |
| expires_at | TIMESTAMP | NULLABLE | 过期时间 |
| quota_limit | INTEGER | NULLABLE | 配额限制 |
| quota_used | INTEGER | DEFAULT 0 | 已用配额 |
| is_active | BOOLEAN | DEFAULT true | 启用状态 |
| last_validated_at | TIMESTAMP | NULLABLE | 最后验证时间 |
| validation_status | ENUM | NULLABLE | 验证状态 |
| created_at | TIMESTAMP | NOT NULL, auto | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL, auto | 更新时间 |

### Validation Status Enum

```python
class ValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    QUOTA_EXCEEDED = "quota_exceeded"
```

### Validation Rules

- `api_key_encrypted`: AES-256-GCM加密
- `api_key_hint`: 格式 `****xxxx` (4个*号 + 末4位)
- `expires_at`: 如设置，系统应在到期前提醒
- 每个Provider至少保留一个`is_active=true`的Credential

### Security Notes

- 原始密钥仅在创建/更新时接收，不存储明文
- 解密仅在实际调用供应商API时进行
- 日志中禁止记录任何密钥信息

---

## 4. Model（模型）

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-gen | 唯一标识符 |
| provider_id | UUID | FK, NOT NULL | 所属供应商 |
| model_id | VARCHAR(100) | NOT NULL | 供应商模型ID |
| name | VARCHAR(200) | NOT NULL | 模型显示名称 |
| model_type | ENUM | NOT NULL | 模型类型 |
| context_window | INTEGER | NULLABLE | 上下文窗口大小 |
| max_output_tokens | INTEGER | NULLABLE | 最大输出Token数 |
| input_price | DECIMAL(10,6) | NULLABLE | 输入价格(每千Token) |
| output_price | DECIMAL(10,6) | NULLABLE | 输出价格(每千Token) |
| capabilities | JSONB | DEFAULT {} | 能力标签 |
| status | ENUM | DEFAULT available | 模型状态 |
| synced_at | TIMESTAMP | NULLABLE | 最后同步时间 |
| created_at | TIMESTAMP | NOT NULL, auto | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL, auto | 更新时间 |

### Model Type Enum

```python
class ModelType(str, Enum):
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    VISION = "vision"
```

### Model Status Enum

```python
class ModelStatus(str, Enum):
    AVAILABLE = "available"
    MAINTENANCE = "maintenance"
    DEPRECATED = "deprecated"
```

### Capabilities JSON Structure

```json
{
    "text_generation": true,
    "chat": true,
    "function_calling": true,
    "vision": false,
    "streaming": true,
    "json_mode": true,
    "code_generation": true
}
```

### Validation Rules

- `model_id`: 供应商内唯一 (provider_id, model_id) UNIQUE
- `context_window`: 正整数
- `capabilities`: 必须是有效JSON对象

### Indexes

- `idx_model_provider`: (provider_id)
- `idx_model_provider_model_id`: (provider_id, model_id) UNIQUE
- `idx_model_status`: (status)
- `idx_model_capabilities`: GIN index on capabilities

---

## Migration Strategy

### Alembic Migration Files

```
alembic/versions/
├── 001_create_provider_table.py
├── 002_create_endpoint_table.py
├── 003_create_credential_table.py
└── 004_create_model_table.py
```

### Data Seeding

初始化数据种子（常用供应商默认配置）:

```python
DEFAULT_ENDPOINTS = {
    ProviderType.OPENAI: "https://api.openai.com/v1",
    ProviderType.ANTHROPIC: "https://api.anthropic.com",
    ProviderType.AZURE_OPENAI: "https://{resource}.openai.azure.com",
    # ... etc
}
```
