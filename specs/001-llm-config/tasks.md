# Tasks: LLM配置管理

**Input**: Design documents from `/specs/001-llm-config/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: 单元测试和集成测试包含在各用户故事中，确保可独立验证。

**Organization**: 任务按用户故事分组，支持独立实现和测试。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行执行（不同文件，无依赖）
- **[Story]**: 所属用户故事（US1, US2, US3, US4）
- 包含精确文件路径

## Path Conventions

本项目为单体项目：`src/aiops_agent_executor/`，`tests/`

---

## Phase 1: Setup（项目初始化）

**Purpose**: 确保项目结构和基础依赖就绪

- [ ] T001 验证项目结构符合plan.md定义
  - **验证方法**：【静态检查】确认src/aiops_agent_executor/services/目录存在
- [ ] T002 创建数据库迁移脚本初始化 in alembic/
  - **验证方法**：【构建验证】执行 `alembic revision --autogenerate` 成功生成迁移文件
- [ ] T003 [P] 配置测试夹具 in tests/conftest.py
  - **验证方法**：【构建验证】执行 `pytest --collect-only` 无报错

---

## Phase 2: Foundational（基础设施）

**Purpose**: 所有用户故事依赖的核心基础设施，**必须**在用户故事实现前完成

**⚠️ CRITICAL**: 此阶段未完成前，任何用户故事都不能开始

- [ ] T004 实现自定义异常类体系 in src/aiops_agent_executor/core/exceptions.py
  - 创建 AppException 基类及 NotFoundError, BadRequestError, ConflictError, ServiceUnavailableError, InternalError
  - **验证方法**：【构建验证】执行 `python -c "from aiops_agent_executor.core.exceptions import *"` 无报错
- [ ] T005 [P] 实现全局异常处理器 in src/aiops_agent_executor/api/v1/exception_handlers.py
  - 注册到FastAPI应用，统一错误响应格式
  - **验证方法**：【运行时验证】启动应用，访问不存在的路由返回标准错误JSON
- [ ] T006 [P] 完善AES-256加密工具 in src/aiops_agent_executor/core/security.py
  - 实现 encrypt_credential() 和 decrypt_credential() 方法，使用AES-256-GCM模式
  - **验证方法**：【单元测试】执行 `pytest tests/unit/test_security.py`
- [ ] T007 执行数据库迁移
  - **验证方法**：【运行时验证】执行 `alembic upgrade head` 成功，数据库表已创建

**Checkpoint**: 基础设施就绪 - 用户故事实现可以开始

---

## Phase 3: User Story 1 - 供应商配置管理 (Priority: P1) 🎯 MVP

**Goal**: 实现供应商的CRUD操作，支持8种供应商类型

**Independent Test**: 创建OpenAI供应商 → 查询列表 → 更新名称 → 禁用 → 删除

### 实现

- [ ] T008 [P] [US1] 创建供应商服务层 in src/aiops_agent_executor/services/provider_service.py
  - 实现 create_provider(), get_provider(), list_providers(), update_provider(), delete_provider(), update_provider_status()
  - **验证方法**：【构建验证】执行 `python -c "from aiops_agent_executor.services.provider_service import ProviderService"` 无报错
- [ ] T009 [US1] 实现供应商API端点业务逻辑 in src/aiops_agent_executor/api/v1/endpoints/providers.py
  - 替换所有 HTTP_501_NOT_IMPLEMENTED 为实际业务逻辑调用
  - **验证方法**：【运行时验证】POST /api/v1/providers 创建供应商返回201
- [ ] T010 [US1] 添加供应商删除前检查逻辑（是否被Agent团队使用）
  - 在 delete_provider 中查询 Team 表引用
  - **验证方法**：【运行时验证】删除被使用的供应商返回409 Conflict
- [ ] T011 [P] [US1] 编写供应商服务单元测试 in tests/unit/test_provider_service.py
  - 覆盖所有CRUD操作和边界条件
  - **验证方法**：【单元测试】执行 `pytest tests/unit/test_provider_service.py` 全部通过
- [ ] T012 [P] [US1] 编写供应商API集成测试 in tests/integration/test_provider_api.py
  - **验证方法**：【单元测试】执行 `pytest tests/integration/test_provider_api.py` 全部通过

**Checkpoint**: 供应商管理功能完整可用，可独立测试

---

## Phase 4: User Story 2 - 接入点配置管理 (Priority: P1)

**Goal**: 实现接入点的CRUD、健康检查和轮询负载均衡

**Independent Test**: 为供应商添加接入点 → 设置默认 → 健康检查 → 验证轮询分配

### 实现

- [ ] T013 [P] [US2] 创建轮询负载均衡器 in src/aiops_agent_executor/utils/load_balancer.py
  - 实现 RoundRobinLoadBalancer 类，支持健康接入点过滤
  - **验证方法**：【单元测试】执行 `pytest tests/unit/test_load_balancer.py`
- [ ] T014 [P] [US2] 创建接入点服务层 in src/aiops_agent_executor/services/endpoint_service.py
  - 实现 create_endpoint(), list_endpoints(), update_endpoint(), delete_endpoint(), health_check()
  - 确保每个供应商至少保留一个接入点，只能有一个默认接入点
  - **验证方法**：【构建验证】执行 `python -c "from aiops_agent_executor.services.endpoint_service import EndpointService"` 无报错
- [ ] T015 [US2] 实现接入点API端点业务逻辑 in src/aiops_agent_executor/api/v1/endpoints/endpoints.py
  - 替换所有 HTTP_501_NOT_IMPLEMENTED 为实际业务逻辑调用
  - **验证方法**：【运行时验证】POST /api/v1/providers/{id}/endpoints 创建接入点返回201
- [ ] T016 [US2] 实现健康检查功能
  - 检测接入点连通性、延迟，更新 health_status 字段
  - **验证方法**：【运行时验证】POST /api/v1/endpoints/{id}/health-check 返回健康状态
- [ ] T017 [P] [US2] 编写接入点服务单元测试 in tests/unit/test_endpoint_service.py
  - **验证方法**：【单元测试】执行 `pytest tests/unit/test_endpoint_service.py` 全部通过
- [ ] T018 [P] [US2] 编写接入点API集成测试 in tests/integration/test_endpoint_api.py
  - **验证方法**：【单元测试】执行 `pytest tests/integration/test_endpoint_api.py` 全部通过

**Checkpoint**: 接入点管理和健康检查功能完整可用

---

## Phase 5: User Story 3 - 密钥安全管理 (Priority: P1)

**Goal**: 实现密钥的加密存储、脱敏显示和验证功能

**Independent Test**: 添加密钥 → 查询（验证脱敏）→ 验证密钥有效性 → 轮换密钥

### 实现

- [ ] T019 [P] [US3] 创建密钥服务层 in src/aiops_agent_executor/services/credential_service.py
  - 实现 create_credential(), list_credentials(), update_credential(), delete_credential(), validate_credential()
  - 调用 security.py 的加密/解密方法
  - 确保每个供应商至少保留一个有效密钥
  - **验证方法**：【构建验证】执行 `python -c "from aiops_agent_executor.services.credential_service import CredentialService"` 无报错
- [ ] T020 [US3] 实现密钥API端点业务逻辑 in src/aiops_agent_executor/api/v1/endpoints/credentials.py
  - 替换所有 HTTP_501_NOT_IMPLEMENTED 为实际业务逻辑调用
  - **验证方法**：【运行时验证】POST /api/v1/providers/{id}/credentials 添加密钥返回201
- [ ] T021 [US3] 实现密钥脱敏逻辑
  - 返回 api_key_hint 格式 ****xxxx，不返回原始密钥
  - **验证方法**：【运行时验证】GET /api/v1/providers/{id}/credentials 返回脱敏格式
- [ ] T022 [US3] 实现密钥验证功能
  - 调用供应商API验证密钥有效性，更新 validation_status
  - **验证方法**：【运行时验证】POST /api/v1/credentials/{id}/validate 返回验证结果
- [ ] T023 [P] [US3] 编写密钥服务单元测试 in tests/unit/test_credential_service.py
  - 验证加密存储、脱敏显示、删除约束
  - **验证方法**：【单元测试】执行 `pytest tests/unit/test_credential_service.py` 全部通过
- [ ] T024 [P] [US3] 编写密钥API集成测试 in tests/integration/test_credential_api.py
  - **验证方法**：【单元测试】执行 `pytest tests/integration/test_credential_api.py` 全部通过

**Checkpoint**: 密钥安全管理功能完整可用，加密和脱敏逻辑正确

---

## Phase 6: User Story 4 - 模型配置管理 (Priority: P2)

**Goal**: 实现模型同步、手动添加和按能力查询

**Independent Test**: 同步模型列表 → 按能力筛选 → 更新定价 → 手动添加模型

### 实现

- [ ] T025 [P] [US4] 创建供应商适配器基类 in src/aiops_agent_executor/adapters/base.py
  - 定义 ProviderAdapter 抽象基类，包含 list_models(), validate_credential() 接口
  - **验证方法**：【构建验证】执行 `python -c "from aiops_agent_executor.adapters.base import ProviderAdapter"` 无报错
- [ ] T026 [P] [US4] 实现OpenAI适配器 in src/aiops_agent_executor/adapters/openai_adapter.py
  - 实现模型列表获取和密钥验证
  - **验证方法**：【构建验证】执行 `python -c "from aiops_agent_executor.adapters.openai_adapter import OpenAIAdapter"` 无报错
- [ ] T027 [P] [US4] 实现Anthropic适配器 in src/aiops_agent_executor/adapters/anthropic_adapter.py
  - **验证方法**：【构建验证】执行 `python -c "from aiops_agent_executor.adapters.anthropic_adapter import AnthropicAdapter"` 无报错
- [ ] T028 [P] [US4] 创建模型服务层 in src/aiops_agent_executor/services/model_service.py
  - 实现 sync_models(), list_models(), get_model(), update_model(), create_model(), get_models_by_capability()
  - 同步策略：新模型INSERT，已有UPDATE，下线标记deprecated
  - **验证方法**：【构建验证】执行 `python -c "from aiops_agent_executor.services.model_service import ModelService"` 无报错
- [ ] T029 [US4] 实现模型API端点业务逻辑 in src/aiops_agent_executor/api/v1/endpoints/models.py
  - 替换所有 HTTP_501_NOT_IMPLEMENTED 为实际业务逻辑调用
  - **验证方法**：【运行时验证】POST /api/v1/providers/{id}/models/sync 同步模型返回200
- [ ] T030 [US4] 实现模型手动创建功能
  - 支持Ollama、vLLM等不支持自动同步的供应商
  - **验证方法**：【运行时验证】POST /api/v1/providers/{id}/models 创建模型返回201
- [ ] T031 [US4] 实现按能力查询模型
  - 使用JSONB capabilities字段的GIN索引
  - **验证方法**：【运行时验证】GET /api/v1/models/by-capability/function_calling 返回模型列表
- [ ] T032 [P] [US4] 编写模型服务单元测试 in tests/unit/test_model_service.py
  - **验证方法**：【单元测试】执行 `pytest tests/unit/test_model_service.py` 全部通过
- [ ] T033 [P] [US4] 编写模型API集成测试 in tests/integration/test_model_api.py
  - **验证方法**：【单元测试】执行 `pytest tests/integration/test_model_api.py` 全部通过

**Checkpoint**: 模型管理功能完整可用，同步和查询功能正常

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 跨用户故事的优化和完善

- [ ] T034 [P] 更新services/__init__.py导出所有服务类
  - **验证方法**：【构建验证】执行 `python -c "from aiops_agent_executor.services import ProviderService, EndpointService, CredentialService, ModelService"` 无报错
- [ ] T035 [P] 更新adapters/__init__.py导出所有适配器
  - **验证方法**：【构建验证】执行 `python -c "from aiops_agent_executor.adapters import OpenAIAdapter, AnthropicAdapter"` 无报错
- [ ] T036 运行完整测试套件并确保通过
  - **验证方法**：【单元测试】执行 `pytest tests/ --cov=src/aiops_agent_executor` 覆盖率≥80%
- [ ] T037 验证quickstart.md中的所有示例
  - **验证方法**：【运行时验证】按quickstart.md执行所有curl命令，全部成功
- [ ] T038 代码清理和优化
  - 移除所有TODO注释，确保无未实现的功能
  - **验证方法**：【静态检查】执行 `grep -r "TODO" src/` 无输出

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 无依赖 - 可立即开始
- **Phase 2 (Foundational)**: 依赖Phase 1 - **阻塞所有用户故事**
- **Phase 3-6 (User Stories)**: 全部依赖Phase 2完成
  - 用户故事可并行执行（如有多人）
  - 或按优先级顺序执行（P1 → P2）
- **Phase 7 (Polish)**: 依赖所有用户故事完成

### User Story Dependencies

- **US1 (供应商管理)**: Phase 2完成后可开始 - 无其他用户故事依赖
- **US2 (接入点管理)**: Phase 2完成后可开始 - 逻辑上关联US1但可独立测试
- **US3 (密钥管理)**: Phase 2完成后可开始 - 逻辑上关联US1但可独立测试
- **US4 (模型管理)**: Phase 2完成后可开始 - 同步功能需要US2和US3的接入点和密钥

### Within Each User Story

- 服务层 → API端点 → 特定功能 → 测试
- 核心实现 → 集成验证

### Parallel Opportunities

- Phase 1: T003可并行
- Phase 2: T005, T006可并行
- Phase 3 (US1): T008, T011, T012可并行
- Phase 4 (US2): T013, T014, T017, T018可并行
- Phase 5 (US3): T019, T023, T024可并行
- Phase 6 (US4): T025, T026, T027, T028, T032, T033可并行
- Phase 7: T034, T035可并行

---

## Parallel Example: Phase 4 (User Story 2)

```bash
# 并行执行服务和工具开发：
Task: "T013 创建轮询负载均衡器 in src/aiops_agent_executor/utils/load_balancer.py"
Task: "T014 创建接入点服务层 in src/aiops_agent_executor/services/endpoint_service.py"

# 服务完成后，并行执行测试：
Task: "T017 编写接入点服务单元测试 in tests/unit/test_endpoint_service.py"
Task: "T018 编写接入点API集成测试 in tests/integration/test_endpoint_api.py"
```

---

## Implementation Strategy

### MVP First (仅User Story 1)

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational (CRITICAL)
3. 完成 Phase 3: User Story 1 - 供应商管理
4. **STOP and VALIDATE**: 测试供应商CRUD全流程
5. 可部署/演示基础版本

### Incremental Delivery

1. Setup + Foundational → 基础设施就绪
2. + User Story 1 → 供应商管理可用 → Deploy (MVP)
3. + User Story 2 → 接入点管理可用 → Deploy
4. + User Story 3 → 密钥管理可用 → Deploy
5. + User Story 4 → 模型管理可用 → Deploy (完整版)
6. 每个用户故事独立交付价值

### Parallel Team Strategy

多开发者场景：

1. 团队共同完成 Setup + Foundational
2. Foundational 完成后：
   - 开发者 A: User Story 1 (供应商)
   - 开发者 B: User Story 2 (接入点)
   - 开发者 C: User Story 3 (密钥)
   - 开发者 D: User Story 4 (模型)
3. 各用户故事独立完成和集成

---

## Notes

- [P] 任务 = 不同文件，无依赖，可并行
- [Story] 标签映射到spec.md中的用户故事
- 每个用户故事应可独立完成和测试
- 每个任务完成后提交代码
- 在任何Checkpoint处可停止验证
- 避免：模糊任务、同文件冲突、破坏独立性的跨故事依赖
