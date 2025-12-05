---
inclusion: always
---

# AIOps Agent Executor - 项目概览

## 项目简介

AIOps Agent Executor 是一个智能运维代理执行系统，支持动态创建和管理 Agent Team，用于自动化运维任务的执行和协调。

## 核心功能

### 1. LLM 配置管理
- 统一管理多个模型供应商（OpenAI、Anthropic、AWS Bedrock、Azure OpenAI、阿里云、百度等）
- 支持接入点管理、访问密钥管理、模型能力管理
- 提供密钥加密存储和安全管理

### 2. 动态 Agent Team 创建
- 基于资源拓扑结构动态创建 Agent Team
- 支持层级化的 Supervisor 架构（Global Supervisor + Node Supervisor）
- 提供流式执行输出和结构化结果生成

## 技术栈

### 运行环境
- **Python**: 3.11+
- **包管理**: Poetry 或 pip + requirements.txt

### 核心框架
| 依赖 | 版本 | 用途 |
|------|------|------|
| fastapi | ^0.109.0 | Web框架 |
| uvicorn | ^0.27.0 | ASGI服务器 |
| pydantic | ^2.6.0 | 数据验证 |
| pydantic-settings | ^2.1.0 | 配置管理 |

### Agent 框架
| 依赖 | 版本 | 用途 |
|------|------|------|
| langchain | ^1.1.2 | LLM应用框架 |
| langchain-core | ^1.1.0 | LangChain核心（由langchain自动管理） |
| langgraph | ^1.0.4 | Agent工作流编排 |
| langchain-openai | ^0.3.0 | OpenAI集成 |
| langchain-anthropic | ^0.3.0 | Anthropic集成 |
| langchain-aws | ^1.1.0 | AWS Bedrock/SageMaker集成 |
| langchain-community | ^0.3.0 | 社区集成 |

#### 版本兼容性说明

**核心依赖关系（2024-12 验证）：**
```
langchain 1.1.2
├── langchain-core >=1.1.0,<2.0.0 → 解析为 1.1.1
├── pydantic >=2.7.4,<3.0.0
└── langsmith <1.0.0

langgraph 1.0.4
├── langgraph-checkpoint >=2.1.0,<4.0.0 → 解析为 3.0.1
├── langgraph-prebuilt >=1.0.2,<1.1.0 → 解析为 1.0.5
├── langgraph-sdk >=0.2.2,<0.3.0 → 解析为 0.2.12
└── (间接依赖 langchain-core)

langchain-aws 1.1.0
├── boto3 >=1.40.19
├── langchain-core >=1.1.0
└── pydantic >=2.10.6,<3
```

**兼容性结论：**
- `langchain 1.1.2` + `langgraph 1.0.4` + `langchain-aws 1.1.0` 三者兼容
- 共享依赖 `langchain-core 1.1.1`，无版本冲突
- 所有核心库已进入 1.x 稳定版本，适合生产使用

**版本锁定策略：**
- 使用 `^` 语义化版本，允许兼容性更新
- 建议使用 `poetry.lock` 或 `requirements.txt` 锁定具体版本
- 重大升级前需运行兼容性测试

### 数据存储
| 依赖 | 版本 | 用途 |
|------|------|------|
| sqlalchemy | ^2.0.25 | ORM框架 |
| asyncpg | ^0.29.0 | PostgreSQL异步驱动 |
| alembic | ^1.13.0 | 数据库迁移 |
| redis | ^5.0.1 | 缓存（可选） |

### 安全与加密
| 依赖 | 版本 | 用途 |
|------|------|------|
| cryptography | ^42.0.0 | 密钥加密（AES-256） |
| python-jose | ^3.3.0 | JWT处理 |
| passlib | ^1.7.4 | 密码哈希 |

### 流式通信
| 依赖 | 版本 | 用途 |
|------|------|------|
| sse-starlette | ^1.8.2 | SSE服务端支持 |
| httpx | ^0.26.0 | 异步HTTP客户端 |

### 开发与测试
| 依赖 | 版本 | 用途 |
|------|------|------|
| pytest | ^8.0.0 | 测试框架 |
| pytest-asyncio | ^0.23.0 | 异步测试支持 |
| pytest-cov | ^4.1.0 | 覆盖率报告 |
| httpx | ^0.26.0 | API测试客户端 |
| ruff | ^0.2.0 | 代码检查与格式化 |
| mypy | ^1.8.0 | 类型检查 |
| pre-commit | ^3.6.0 | Git钩子管理 |

### 可观测性
| 依赖 | 版本 | 用途 |
|------|------|------|
| structlog | ^24.1.0 | 结构化日志 |
| opentelemetry-api | ^1.22.0 | 分布式追踪 |
| opentelemetry-sdk | ^1.22.0 | OTel SDK |
| prometheus-client | ^0.19.0 | 指标暴露 |

### 基础设施
- **数据库**: PostgreSQL 15+
- **缓存**: Redis 7+ (可选)
- **消息传递**: SSE (Server-Sent Events)
- **容器化**: Docker + Docker Compose

## 架构特点

### 层级化 Agent 架构
```
Global Supervisor (顶层协调)
    ├── Node Team A (节点团队)
    │   ├── Node Supervisor
    │   └── Agents (A1, A2, A3...)
    ├── Node Team B
    └── Node Team C
```

### 关键设计原则
- **动态性**: 根据拓扑配置动态创建 Agent 结构
- **可观测性**: 完整的执行追踪和日志记录
- **可扩展性**: 支持多种模型供应商和工具集成
- **安全性**: 密钥加密存储和权限控制

## 开发规范

### API 设计规范
- RESTful API 风格
- 统一的错误响应格式
- 支持流式和非流式两种响应模式

### 数据模型规范
- 使用 UUID 作为主键
- 时间戳字段统一命名（created_at, updated_at）
- 敏感数据加密存储（_encrypted 后缀）

### 边界条件
- 单个 Team 最多 100 个节点
- 单个节点最多 20 个 Agent
- 拓扑深度最多 10 层
- 执行超时上限 30 分钟
