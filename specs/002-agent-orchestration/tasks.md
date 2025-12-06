# Tasks: Agent团队动态编排

**Input**: Design documents from `/specs/002-agent-orchestration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: 本任务列表包含测试任务以确保代码质量。

**Organization**: 任务按用户故事分组，支持独立实现和测试。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行执行（不同文件，无依赖）
- **[Story]**: 所属用户故事（US1-US5）
- 描述中包含精确文件路径

## Path Conventions

- **Single project**: `src/aiops_agent_executor/`, `tests/` at repository root

---

## Phase 1: Setup (依赖管理与配置)

**Purpose**: 添加新依赖并创建基础目录结构

- [ ] T001 添加 `jsonschema` 依赖到 `pyproject.toml` dependencies 部分
- [ ] T002 添加 `apscheduler>=3.10.0` 依赖到 `pyproject.toml` dependencies 部分
- [ ] T003 [P] 创建 `src/aiops_agent_executor/agents/__init__.py` 模块初始化文件
- [ ] T004 [P] 创建 `src/aiops_agent_executor/utils/topology.py` 空文件
- [ ] T005 [P] 创建 `src/aiops_agent_executor/utils/scheduler.py` 空文件
- [ ] T006 [P] 创建 `src/aiops_agent_executor/utils/masking.py` 空文件
- [ ] T007 运行 `pip install -e ".[dev]"` 安装新依赖

---

## Phase 2: Foundational (数据模型与核心工具)

**Purpose**: 扩展数据模型，实现核心工具函数，为所有用户故事奠定基础

**⚠️ CRITICAL**: 所有用户故事必须等待此阶段完成

### 数据库模型扩展

- [ ] T008 扩展 `src/aiops_agent_executor/db/models/team.py` 中的 Execution 模型，添加 `topology_snapshot` (JSONB, NOT NULL)、`output_schema` (JSONB, nullable)、`node_results` (JSONB, nullable) 字段
- [ ] T009 更新 `src/aiops_agent_executor/db/models/__init__.py` 导出新增的字段相关类型

### 数据库迁移

- [ ] T010 创建 Alembic 迁移脚本 `alembic revision --autogenerate -m "add execution topology snapshot and output schema"`
- [ ] T011 运行迁移 `alembic upgrade head`

### 核心工具实现

- [ ] T012 [P] 实现拓扑校验工具 `src/aiops_agent_executor/utils/topology.py`：包含 `validate_topology(nodes, edges)` 函数，检测循环依赖(DFS)、孤立节点、无效引用，返回 `ValidationResult(valid, errors)`
- [ ] T013 [P] 实现敏感数据脱敏工具 `src/aiops_agent_executor/utils/masking.py`：包含 `mask_sensitive_data(data: dict)` 函数，正则匹配 OpenAI/Anthropic API 密钥并替换为 `***`
- [ ] T014 [P] 实现定时任务调度器 `src/aiops_agent_executor/utils/scheduler.py`：包含 `ExecutionCleanupScheduler` 类，使用 APScheduler 每日凌晨2点清理超过30天的执行记录

### Pydantic Schemas 扩展

- [ ] T015 创建 `src/aiops_agent_executor/schemas/topology.py`：定义 `NodeConfig`、`EdgeConfig`、`AgentConfig`、`TopologyConfig`、`TopologyValidationResult` schemas
- [ ] T016 创建 `src/aiops_agent_executor/schemas/execution.py`：定义 `ExecutionCreate`、`ExecutionResponse`、`ExecutionDetailResponse`、`ExecutionLogResponse` schemas，`ExecutionDetailResponse` 使用 `@model_validator` 调用脱敏函数
- [ ] T017 扩展 `src/aiops_agent_executor/schemas/team.py`：添加 `TeamCreate`、`TeamUpdate`、`TeamResponse` schemas（包含 TopologyConfig）
- [ ] T018 更新 `src/aiops_agent_executor/schemas/__init__.py` 导出所有新增 schemas

### 单元测试 (Foundational)

- [ ] T019 [P] 创建 `tests/unit/test_topology.py`：测试循环检测、孤立节点检测、无效引用检测
- [ ] T020 [P] 创建 `tests/unit/test_masking.py`：测试 API 密钥脱敏功能

**Checkpoint**: 基础设施就绪 - 可以开始用户故事实现

---

## Phase 3: User Story 1 - 创建Agent团队配置 (Priority: P1) 🎯 MVP

**Goal**: 运维管理员能够定义包含节点、边关系和Agent配置的团队拓扑

**Independent Test**:
- 创建包含3个节点的简单拓扑配置
- 提交无效配置验证错误返回
- 验证同名团队创建被拒绝

### Tests for User Story 1

- [ ] T021 [P] [US1] 创建 `tests/integration/test_teams_api.py`：测试 POST /teams 创建团队、GET /teams 列表、GET /teams/{id} 详情、PATCH /teams/{id} 更新、DELETE /teams/{id} 删除
- [ ] T022 [P] [US1] 在 `tests/integration/test_teams_api.py` 添加拓扑校验测试：无效节点引用返回400、循环依赖返回400、孤立节点返回400

### Implementation for User Story 1

- [ ] T023 [US1] 创建 `src/aiops_agent_executor/services/team_service.py`：实现 `TeamService` 类，包含 `create_team`、`get_team`、`list_teams`、`update_team`、`delete_team`、`validate_topology` 方法
- [ ] T024 [US1] 在 `src/aiops_agent_executor/services/__init__.py` 导出 `TeamService`
- [ ] T025 [US1] 扩展 `src/aiops_agent_executor/api/v1/endpoints/teams.py`：实现 POST /teams（创建团队，调用拓扑校验）、GET /teams（列表查询）、GET /teams/{team_id}（详情）、PATCH /teams/{team_id}（更新）、DELETE /teams/{team_id}（删除前检查是否有RUNNING执行，有则返回409）
- [ ] T026 [US1] 在 `src/aiops_agent_executor/api/v1/endpoints/teams.py` 添加 POST /teams/{team_id}/validate 端点，返回拓扑校验结果
- [ ] T027 [US1] 在 `src/aiops_agent_executor/api/v1/router.py` 确认 teams router 已注册

**Checkpoint**: User Story 1 完成 - 可以独立测试团队配置的CRUD和校验功能

---

## Phase 4: User Story 2 - 触发团队执行任务 (Priority: P1)

**Goal**: 运维管理员能够触发已配置的团队执行任务，系统自动协调执行流程

**Independent Test**:
- 对有效团队触发执行，获得执行ID
- 对无效LLM配置的团队触发执行，收到错误
- 查询执行状态获得进度信息

### Tests for User Story 2

- [ ] T028 [P] [US2] 创建 `tests/integration/test_executions_api.py`：测试 POST /teams/{id}/executions 触发执行、GET /executions/{id} 查询状态
- [ ] T029 [P] [US2] 在 `tests/unit/test_execution_service.py` 测试并发限制（Semaphore）、LLM重试逻辑

### Implementation for User Story 2

#### LangGraph Agent 编排

- [ ] T030 [P] [US2] 创建 `src/aiops_agent_executor/agents/state.py`：定义 `TeamState(TypedDict)` 状态类型，包含 task、node_results、current_node、status、failed_nodes 字段
- [ ] T031 [P] [US2] 创建 `src/aiops_agent_executor/agents/nodes.py`：实现 `global_supervisor_node`、`node_supervisor_node`、`agent_executor_node` 节点函数
- [ ] T032 [US2] 创建 `src/aiops_agent_executor/agents/graph.py`：使用 LangGraph StateGraph 构建执行图，根据 TopologyConfig 动态添加节点和边，实现条件路由（失败跳过下游）
- [ ] T033 [US2] 更新 `src/aiops_agent_executor/agents/__init__.py` 导出 `build_execution_graph` 函数

#### Execution Service

- [ ] T034 [US2] 创建 `src/aiops_agent_executor/services/execution_service.py`：实现 `ExecutionService` 类，包含 `trigger_execution`（执行前校验所有Agent的model_id引用有效、创建执行记录、保存topology_snapshot、启动异步执行）、`get_execution`、`list_executions` 方法
- [ ] T035 [US2] 在 `ExecutionService` 中实现 `ExecutionManager` 内部类：使用 `asyncio.Semaphore(100)` 控制并发，并发达到100时抛出 `ExecutionConcurrencyError`，维护 `_running_tasks` 字典
- [ ] T036 [US2] 在 `ExecutionService` 中实现 LLM 调用包装器：使用 tenacity 实现指数退避重试（1s, 2s, 4s），最多3次
- [ ] T037 [US2] 在 `src/aiops_agent_executor/services/__init__.py` 导出 `ExecutionService`

#### API Endpoints

- [ ] T038 [US2] 创建 `src/aiops_agent_executor/api/v1/endpoints/executions.py`：实现 POST /teams/{team_id}/executions（触发执行，并发超限返回HTTP 429）、GET /executions/{execution_id}（查询详情，包含node_results各节点状态）、GET /teams/{team_id}/executions（列表查询，支持 status/start_time/end_time 过滤）
- [ ] T039 [US2] 在 `src/aiops_agent_executor/api/v1/endpoints/executions.py` 添加 POST /executions/{execution_id}/cancel（取消执行）端点
- [ ] T040 [US2] 在 `src/aiops_agent_executor/api/v1/router.py` 注册 executions router

**Checkpoint**: User Story 2 完成 - 可以触发执行并查询状态

---

## Phase 5: User Story 3 - 实时获取执行状态和结果 (Priority: P2)

**Goal**: 运维管理员能够通过SSE实时监控执行过程

**Independent Test**:
- 触发执行后订阅SSE流，接收状态更新事件
- 断开重连后继续接收事件
- 执行完成后SSE流自动关闭

### Tests for User Story 3

- [ ] T041 [P] [US3] 在 `tests/integration/test_sse_streaming.py` 创建 SSE 流式测试：测试事件接收、断线重连（Last-Event-ID）

### Implementation for User Story 3

- [ ] T042 [US3] 创建 `src/aiops_agent_executor/services/event_service.py`：实现 `EventService` 类，管理执行事件队列（per execution_id），提供 `publish_event` 和 `subscribe` 方法
- [ ] T043 [US3] 在 `src/aiops_agent_executor/services/__init__.py` 导出 `EventService`
- [ ] T044 [US3] 修改 `src/aiops_agent_executor/agents/nodes.py`：在每个节点函数中调用 `EventService.publish_event` 发布状态变化事件
- [ ] T045 [US3] 在 `src/aiops_agent_executor/api/v1/endpoints/executions.py` 添加 GET /executions/{execution_id}/stream 端点：返回 `StreamingResponse` (text/event-stream)，支持 Last-Event-ID header 进行断线重连
- [ ] T046 [US3] 实现 ExecutionLog 写入：每个事件同时写入 `execution_logs` 表用于断线重连查询

**Checkpoint**: User Story 3 完成 - SSE流式监控功能可用

---

## Phase 6: User Story 4 - 获取结构化输出 (Priority: P2)

**Goal**: 运维管理员能够指定输出JSON Schema，系统确保输出符合Schema

**Independent Test**:
- 提交带 output_schema 的执行请求，验证返回符合Schema
- Schema 验证失败时重试并最终返回原始输出

### Tests for User Story 4

- [ ] T047 [P] [US4] 在 `tests/unit/test_schema_parser.py` 创建 JSON Schema 验证测试：测试成功验证、验证失败重试、最终返回原始输出

### Implementation for User Story 4

- [ ] T048 [US4] 创建 `src/aiops_agent_executor/utils/schema_parser.py`：实现 `validate_output_schema(output: str, schema: dict)` 函数，使用 jsonschema 验证，失败时 raise `SchemaValidationError`
- [ ] T049 [US4] 创建 `src/aiops_agent_executor/agents/output_parser.py`：实现 `StructuredOutputParser` 类，包装 LLM 调用并使用 tenacity 重试3次确保输出符合 Schema
- [ ] T050 [US4] 修改 `src/aiops_agent_executor/agents/graph.py`：在执行图最终节点添加 `StructuredOutputParser` 处理，如果 execution 有 output_schema 则进行验证
- [ ] T051 [US4] 修改 `src/aiops_agent_executor/services/execution_service.py`：执行完成时，如果 Schema 验证最终失败，记录 `parse_error` 到 `extra_data` 并保存原始输出

**Checkpoint**: User Story 4 完成 - 结构化输出功能可用

---

## Phase 7: User Story 5 - 查询执行历史 (Priority: P3)

**Goal**: 运维管理员能够查询和筛选执行历史记录

**Independent Test**:
- 执行多个任务后查询历史列表
- 按时间范围和状态筛选记录
- 验证敏感信息已脱敏

### Tests for User Story 5

- [ ] T052 [P] [US5] 在 `tests/integration/test_executions_api.py` 添加执行历史查询测试：测试分页、时间筛选、状态筛选
- [ ] T053 [P] [US5] 在 `tests/integration/test_executions_api.py` 添加敏感信息脱敏测试：验证返回数据中 API 密钥已被脱敏

### Implementation for User Story 5

- [ ] T054 [US5] 在 `src/aiops_agent_executor/api/v1/endpoints/executions.py` GET /executions/{execution_id}/logs 端点：支持 event_type、node_id 过滤和分页
- [ ] T055 [US5] 在 `src/aiops_agent_executor/services/execution_service.py` 添加 `list_execution_logs` 方法
- [ ] T056 [US5] 创建数据库索引迁移：`alembic revision -m "add execution history indexes"` 添加 `idx_executions_team_status_created` 复合索引
- [ ] T057 [US5] 运行索引迁移 `alembic upgrade head`

**Checkpoint**: User Story 5 完成 - 执行历史查询功能可用

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 完善文档、性能优化和安全加固

- [ ] T058 [P] 在 `src/aiops_agent_executor/main.py` 中初始化并启动 `ExecutionCleanupScheduler`（应用启动时启动调度器）
- [ ] T059 [P] 在 `src/aiops_agent_executor/main.py` 中添加应用关闭时的清理逻辑（停止调度器、取消运行中的执行）
- [ ] T060 [P] 创建 `tests/integration/test_cleanup_scheduler.py`：测试过期数据清理功能
- [ ] T061 在 `src/aiops_agent_executor/core/exceptions.py` 添加 `TopologyValidationError`、`ExecutionConcurrencyError`、`SchemaValidationError` 异常类
- [ ] T062 在 `src/aiops_agent_executor/api/v1/exception_handlers.py` 添加新异常类型的处理器
- [ ] T063 运行 `pytest tests/` 确保所有测试通过
- [ ] T064 运行 `ruff check src/` 和 `ruff format src/` 确保代码风格一致
- [ ] T065 运行 `mypy src/` 检查类型标注
- [ ] T066 使用 quickstart.md 中的示例手动验证完整流程

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ← BLOCKS all user stories
    ↓
┌───────────────────────────────────────────────────────┐
│  Phase 3 (US1: 团队配置) ← MVP                        │
│      ↓                                                │
│  Phase 4 (US2: 触发执行) ← 依赖 US1 的 Team 实体      │
│      ↓                                                │
│  Phase 5 (US3: SSE流式) ← 依赖 US2 的执行功能         │
│      ↓                                                │
│  Phase 6 (US4: 结构化输出) ← 可与 US3 并行            │
│      ↓                                                │
│  Phase 7 (US5: 执行历史) ← 依赖 US2 的执行记录        │
└───────────────────────────────────────────────────────┘
    ↓
Phase 8 (Polish)
```

### User Story Dependencies

| Story | 依赖 | 可并行 |
|-------|------|--------|
| US1 (团队配置) | Foundational | 独立 |
| US2 (触发执行) | US1 | 需等待 US1 |
| US3 (SSE流式) | US2 | 需等待 US2 |
| US4 (结构化输出) | US2 | 可与 US3 并行 |
| US5 (执行历史) | US2 | 可与 US3/US4 并行 |

### Within Each User Story

1. Tests 先写（如包含）
2. Models/Schemas 先于 Services
3. Services 先于 API Endpoints
4. 核心实现先于集成

---

## Parallel Opportunities

### Phase 2 并行任务组

```bash
# 可并行执行（不同文件）：
T012: utils/topology.py
T013: utils/masking.py
T014: utils/scheduler.py
T015: schemas/topology.py
T016: schemas/execution.py
T019: tests/unit/test_topology.py
T020: tests/unit/test_masking.py
```

### US2 并行任务组

```bash
# Agent 相关可并行：
T030: agents/state.py
T031: agents/nodes.py

# 测试可并行：
T028: tests/integration/test_executions_api.py
T029: tests/unit/test_execution_service.py
```

### US3/US4/US5 并行策略

```bash
# 在 US2 完成后，以下可由不同开发者并行：
Developer A: Phase 5 (US3 - SSE)
Developer B: Phase 6 (US4 - 结构化输出)
Developer C: Phase 7 (US5 - 执行历史)
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2)

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational
3. 完成 Phase 3: User Story 1 (团队配置)
4. 完成 Phase 4: User Story 2 (触发执行)
5. **STOP and VALIDATE**: 可以创建团队并触发执行
6. 部署/演示 MVP

### Incremental Delivery

1. Setup + Foundational → 基础就绪
2. + US1 (团队配置) → 可配置团队
3. + US2 (触发执行) → **MVP: 可执行任务**
4. + US3 (SSE流式) → 实时监控
5. + US4 (结构化输出) → 自动化集成
6. + US5 (执行历史) → 审计追溯
7. + Polish → 生产就绪

---

## Notes

- 本项目在现有 aiops-agent-executor 基础上扩展，复用已有架构模式
- LangGraph 是核心编排引擎，需重点关注 agents/ 目录实现
- SSE 流式推送使用 FastAPI 原生 StreamingResponse
- 敏感信息脱敏在 Schema 序列化层实现
- 30天数据清理使用 APScheduler 嵌入式调度
- 所有任务ID按执行顺序编号，便于追踪进度
