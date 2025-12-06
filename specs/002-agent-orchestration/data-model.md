# Data Model: Agent团队动态编排

**Feature**: 002-agent-orchestration
**Date**: 2024-12-06

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Provider (existing)                        │
│                    ┌───────────────────────────┐                     │
│                    │         Model             │                     │
│                    └───────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ references
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                              Team                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    TopologyConfig (JSONB)                    │    │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐                  │    │
│  │  │  Node   │───▶│  Node   │───▶│  Node   │                  │    │
│  │  │(Agent)  │    │(Superv) │    │(Agent)  │                  │    │
│  │  └─────────┘    └─────────┘    └─────────┘                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ has many
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           Execution                                  │
│  - topology_snapshot (JSONB)                                        │
│  - input_data / output_data                                         │
│  - status tracking                                                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ has many
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         ExecutionLog                                 │
│  - event_type, node_id, agent_id                                    │
│  - message, extra_data                                              │
└─────────────────────────────────────────────────────────────────────┘
```

## Entity Definitions

### Team (Extended)

**Purpose**: Agent团队配置，包含拓扑结构定义

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | 团队唯一标识 |
| name | String(200) | NOT NULL, INDEX | 团队名称 |
| description | Text | NULLABLE | 团队描述 |
| topology_config | JSONB | NOT NULL | 拓扑配置（节点、边、Agent配置） |
| timeout_seconds | Integer | DEFAULT 300 | 执行超时时间（秒） |
| max_iterations | Integer | DEFAULT 50 | 最大迭代次数 |
| status | Enum | DEFAULT ACTIVE | 团队状态 |
| created_at | Timestamp | AUTO | 创建时间 |
| updated_at | Timestamp | AUTO | 更新时间 |

**Status Values**: ACTIVE, INACTIVE, ERROR

### TopologyConfig (JSONB Schema)

```json
{
  "nodes": [
    {
      "id": "string",
      "name": "string",
      "type": "global_supervisor | node_supervisor | agent",
      "agent_config": {
        "role": "string",
        "instructions": "string",
        "model_id": "uuid",
        "tools": ["string"],
        "temperature": 0.7,
        "max_tokens": 4096
      },
      "metadata": {}
    }
  ],
  "edges": [
    {
      "source": "node_id",
      "target": "node_id",
      "condition": "string (optional)"
    }
  ],
  "entry_point": "node_id",
  "output_schema": {}
}
```

### Execution (Extended)

**Purpose**: 执行记录，保存执行状态和结果

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | 执行唯一标识 |
| team_id | UUID | FK(teams.id) | 关联团队 |
| topology_snapshot | JSONB | NOT NULL | 执行时的拓扑配置快照 |
| input_data | JSONB | NOT NULL | 输入数据（task, parameters） |
| output_data | JSONB | NULLABLE | 输出结果 |
| output_schema | JSONB | NULLABLE | 期望的输出 JSON Schema |
| status | Enum | DEFAULT PENDING | 执行状态 |
| started_at | Timestamp | NULLABLE | 开始时间 |
| completed_at | Timestamp | NULLABLE | 完成时间 |
| duration_ms | Integer | NULLABLE | 执行耗时（毫秒） |
| error_message | Text | NULLABLE | 错误信息 |
| node_results | JSONB | NULLABLE | 各节点执行结果 |
| created_at | Timestamp | AUTO | 创建时间 |
| updated_at | Timestamp | AUTO | 更新时间 |

**Status Values**: PENDING, RUNNING, SUCCESS, FAILED, TIMEOUT, CANCELLED

### ExecutionLog (Existing, extended usage)

**Purpose**: 执行过程中的事件日志

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | 日志唯一标识 |
| execution_id | UUID | FK(executions.id) | 关联执行 |
| event_type | String(50) | NOT NULL, INDEX | 事件类型 |
| node_id | String(100) | NULLABLE | 节点ID |
| agent_id | String(100) | NULLABLE | Agent ID |
| supervisor_id | String(100) | NULLABLE | Supervisor ID |
| message | Text | NULLABLE | 日志消息 |
| extra_data | JSONB | NULLABLE | 额外数据 |
| timestamp | Timestamp | NOT NULL | 事件时间 |

**Event Types**:
- `execution_started` - 执行开始
- `node_entered` - 进入节点
- `node_completed` - 节点完成
- `node_failed` - 节点失败
- `node_skipped` - 节点跳过（依赖失败）
- `agent_thinking` - Agent思考中
- `agent_response` - Agent响应
- `llm_retry` - LLM重试
- `execution_completed` - 执行完成
- `execution_failed` - 执行失败
- `execution_timeout` - 执行超时

## Validation Rules

### Team Validation

1. **Name uniqueness**: 团队名称在系统内唯一
2. **Topology validity**:
   - 所有边的 source/target 必须引用有效节点
   - 不允许循环依赖（DAG）
   - 不允许孤立节点（除入口点外）
   - 必须有且仅有一个入口点
3. **Agent config validity**:
   - model_id 必须引用有效的 Model 记录
   - tools 必须是系统支持的工具列表

### Execution Validation

1. **Team status**: 只能对 ACTIVE 状态的团队触发执行
2. **Input data**: 必须包含 task 字段
3. **Output schema**: 如提供，必须是有效的 JSON Schema

## State Transitions

### Team Status

```
┌────────┐
│ ACTIVE │◀──────────────────────────┐
└────┬───┘                           │
     │ deactivate                    │ activate
     ▼                               │
┌──────────┐                         │
│ INACTIVE │─────────────────────────┘
└────┬─────┘
     │ validation error
     ▼
┌───────┐
│ ERROR │
└───────┘
```

### Execution Status

```
┌─────────┐
│ PENDING │
└────┬────┘
     │ start
     ▼
┌─────────┐
│ RUNNING │
└────┬────┘
     │
     ├──────────────┬──────────────┬──────────────┐
     │ success      │ failure      │ timeout      │ cancel
     ▼              ▼              ▼              ▼
┌─────────┐   ┌────────┐   ┌─────────┐   ┌───────────┐
│ SUCCESS │   │ FAILED │   │ TIMEOUT │   │ CANCELLED │
└─────────┘   └────────┘   └─────────┘   └───────────┘
```

## Indexes

### Team

- `idx_teams_name` on `name` (already exists)
- `idx_teams_status` on `status`

### Execution

- `idx_executions_team_id` on `team_id`
- `idx_executions_status` on `status`
- `idx_executions_created_at` on `created_at DESC`
- `idx_executions_team_status_created` on `(team_id, status, created_at DESC)` (compound)

### ExecutionLog

- `idx_execution_logs_execution_id` on `execution_id`
- `idx_execution_logs_event_type` on `event_type` (already exists)
- `idx_execution_logs_timestamp` on `timestamp DESC`

## Migration Notes

1. **Execution table changes**:
   - ADD COLUMN `topology_snapshot` JSONB NOT NULL (需要默认值或迁移脚本)
   - ADD COLUMN `output_schema` JSONB NULLABLE
   - ADD COLUMN `node_results` JSONB NULLABLE

2. **Data migration**:
   - 对于现有 Execution 记录，从关联 Team 复制 topology_config 到 topology_snapshot

3. **Index creation**:
   - 创建上述新索引以支持查询性能要求
