# Implementation Plan: Agent团队动态编排

**Branch**: `002-agent-orchestration` | **Date**: 2024-12-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-agent-orchestration/spec.md`

## Summary

实现Agent团队动态编排功能，支持根据资源拓扑结构动态创建和执行Agent团队。核心特性包括：
- 三层协调架构（Global Supervisor → Node Supervisor → Agent）
- 拓扑配置管理与校验（无孤立节点、无循环依赖）
- SSE流式执行状态推送
- JSON Schema结构化输出
- 执行历史查询与管理

技术方案基于现有LangGraph框架实现Agent编排，使用FastAPI SSE进行流式推送。

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, SQLAlchemy (async), LangChain/LangGraph, Pydantic v2
**Storage**: PostgreSQL (asyncpg)
**Testing**: pytest + pytest-asyncio
**Target Platform**: Linux server
**Project Type**: Single backend API service
**Performance Goals**: 100并发执行，SSE延迟<2s，历史查询<3s
**Constraints**: 执行超时5分钟，SSE连接超时30s，历史保留30天
**Scale/Scope**: 支持10节点拓扑，100并发执行

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| 遵循现有架构模式 | PASS | 复用services/schemas/api模式 |
| 依赖已有LLM配置 | PASS | Provider/Model/Credential已实现 |
| 测试覆盖要求 | PASS | 将为新功能添加单元/集成测试 |

## Project Structure

### Documentation (this feature)

```text
specs/002-agent-orchestration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI specs)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/aiops_agent_executor/
├── db/models/
│   └── team.py                    # 扩展Team/Execution/ExecutionLog模型
├── schemas/
│   ├── team.py                    # Team相关Pydantic schemas (扩展)
│   └── execution.py               # NEW: Execution schemas
├── services/
│   ├── team_service.py            # NEW: Team CRUD + topology validation
│   └── execution_service.py       # NEW: Execution management + orchestration
├── agents/
│   ├── supervisor.py              # NEW: Global/Node Supervisor实现
│   ├── executor.py                # NEW: Agent执行器
│   └── graph.py                   # NEW: LangGraph workflow定义
├── api/v1/endpoints/
│   ├── teams.py                   # 扩展Teams API
│   └── executions.py              # NEW: Executions API + SSE
└── utils/
    ├── topology.py                # NEW: 拓扑校验工具
    └── schema_parser.py           # NEW: JSON Schema解析与验证

tests/
├── unit/
│   ├── test_team_service.py
│   ├── test_execution_service.py
│   └── test_topology.py
├── integration/
│   ├── test_teams_api.py
│   ├── test_executions_api.py
│   └── test_sse_streaming.py
└── conftest.py
```

**Structure Decision**: 遵循现有单体API架构，在相应目录下添加新模块。agents/目录专门存放LangGraph相关编排逻辑。

## Complexity Tracking

> No violations - complexity within acceptable bounds.

| Aspect | Assessment |
|--------|------------|
| 新增服务数 | 2个 (team_service, execution_service) |
| 新增API端点 | ~8个 |
| 数据模型扩展 | 扩展现有Team模型，可能新增TopologySnapshot |
| 外部依赖 | 仅使用现有LangGraph依赖 |
