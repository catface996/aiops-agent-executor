# LLM配置管理

## 概述

支持对不同模型供应商的模型进行统一管理，为Agent系统提供灵活的模型配置能力。

## 技术栈

- **后端框架**: Python + FastAPI
- **数据存储**: PostgreSQL
- **Agent框架**: LangChain/LangGraph

## 功能需求

### 1. 供应商管理

#### 1.1 支持的供应商类型
- OpenAI
- Anthropic (Claude)
- AWS Bedrock
- Azure OpenAI
- 阿里云通义千问
- 百度文心一言
- 本地部署模型 (Ollama, vLLM)

#### 1.2 供应商CRUD操作
- 创建供应商配置
- 查询供应商列表
- 更新供应商配置
- 删除供应商配置（软删除）
- 启用/禁用供应商

### 2. 接入点管理

#### 2.1 接入点属性
- 接入点名称
- 基础URL (Base URL)
- API版本
- 区域/地域 (Region)
- 超时设置（连接超时、读取超时）
- 重试策略（重试次数、重试间隔）

#### 2.2 接入点操作
- 为供应商配置多个接入点
- 设置默认接入点
- 接入点健康检查
- 接入点故障转移配置

### 3. 访问密钥管理

#### 3.1 密钥属性
- API Key
- Secret Key（如适用）
- 访问令牌 (Access Token)
- 密钥别名/描述
- 过期时间
- 使用配额限制

#### 3.2 密钥安全
- 密钥加密存储（AES-256）
- 密钥脱敏显示
- 密钥轮换支持
- 密钥使用审计日志

#### 3.3 密钥操作
- 添加新密钥
- 验证密钥有效性
- 更新密钥
- 撤销/删除密钥

### 4. 可用模型管理

#### 4.1 模型属性
- 模型ID/名称
- 模型版本
- 所属供应商
- 模型类型（Chat、Completion、Embedding、Vision等）
- 上下文窗口大小 (Context Window)
- 最大输出Token数
- 定价信息（输入/输出每千Token价格）
- 模型状态（可用、维护中、已废弃）

#### 4.2 模型操作
- 同步供应商可用模型列表
- 手动添加/编辑模型
- 设置模型默认参数
- 模型可用性测试

### 5. 模型能力管理

#### 5.1 能力标签
- 文本生成 (Text Generation)
- 对话 (Chat/Conversation)
- 代码生成 (Code Generation)
- 函数调用 (Function Calling / Tool Use)
- 视觉理解 (Vision)
- 嵌入向量 (Embedding)
- 结构化输出 (Structured Output / JSON Mode)
- 流式输出 (Streaming)

#### 5.2 能力评估
- 为每个模型标记支持的能力
- 能力强度评分（1-5分）
- 推荐使用场景

## API设计

### 供应商API

```
POST   /api/v1/providers              # 创建供应商
GET    /api/v1/providers              # 获取供应商列表
GET    /api/v1/providers/{id}         # 获取供应商详情
PUT    /api/v1/providers/{id}         # 更新供应商
DELETE /api/v1/providers/{id}         # 删除供应商
PATCH  /api/v1/providers/{id}/status  # 更新供应商状态
```

### 接入点API

```
POST   /api/v1/providers/{provider_id}/endpoints       # 创建接入点
GET    /api/v1/providers/{provider_id}/endpoints       # 获取接入点列表
PUT    /api/v1/endpoints/{id}                          # 更新接入点
DELETE /api/v1/endpoints/{id}                          # 删除接入点
POST   /api/v1/endpoints/{id}/health-check             # 健康检查
```

### 密钥API

```
POST   /api/v1/providers/{provider_id}/credentials     # 添加密钥
GET    /api/v1/providers/{provider_id}/credentials     # 获取密钥列表（脱敏）
PUT    /api/v1/credentials/{id}                        # 更新密钥
DELETE /api/v1/credentials/{id}                        # 删除密钥
POST   /api/v1/credentials/{id}/validate               # 验证密钥
```

### 模型API

```
POST   /api/v1/providers/{provider_id}/models/sync     # 同步模型列表
GET    /api/v1/models                                  # 获取所有模型列表
GET    /api/v1/models/{id}                             # 获取模型详情
PUT    /api/v1/models/{id}                             # 更新模型配置
GET    /api/v1/models/by-capability/{capability}       # 按能力查询模型
```

## 数据模型

### Provider（供应商）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | String | 供应商名称 |
| type | Enum | 供应商类型 |
| description | String | 描述 |
| is_active | Boolean | 是否启用 |
| created_at | Timestamp | 创建时间 |
| updated_at | Timestamp | 更新时间 |

### Endpoint（接入点）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| provider_id | UUID | 外键-供应商 |
| name | String | 接入点名称 |
| base_url | String | 基础URL |
| api_version | String | API版本 |
| region | String | 区域 |
| timeout_connect | Integer | 连接超时(秒) |
| timeout_read | Integer | 读取超时(秒) |
| retry_count | Integer | 重试次数 |
| is_default | Boolean | 是否默认 |
| is_active | Boolean | 是否启用 |

### Credential（密钥）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| provider_id | UUID | 外键-供应商 |
| alias | String | 密钥别名 |
| api_key_encrypted | String | 加密后的API Key |
| secret_key_encrypted | String | 加密后的Secret Key |
| expires_at | Timestamp | 过期时间 |
| quota_limit | Integer | 配额限制 |
| is_active | Boolean | 是否启用 |

### Model（模型）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| provider_id | UUID | 外键-供应商 |
| model_id | String | 模型标识 |
| name | String | 模型名称 |
| version | String | 版本 |
| type | Enum | 模型类型 |
| context_window | Integer | 上下文窗口 |
| max_output_tokens | Integer | 最大输出Token |
| input_price | Decimal | 输入价格 |
| output_price | Decimal | 输出价格 |
| capabilities | JSONB | 能力列表 |
| status | Enum | 状态 |

## 非功能需求

### 安全性
- 所有密钥必须加密存储
- API访问需要认证
- 敏感操作需要记录审计日志

### 性能
- 配置查询响应时间 < 100ms
- 支持配置缓存，减少数据库查询

### 可用性
- 配置变更实时生效
- 支持配置导入/导出

## 边界条件

- 单个供应商最多配置10个接入点
- 单个供应商最多配置20个密钥
- 模型名称长度限制：100字符
- API Key长度限制：500字符
