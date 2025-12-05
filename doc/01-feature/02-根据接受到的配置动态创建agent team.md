# 动态创建Agent Team

## 概述

提供API接口，接收资源节点的拓扑结构数据，动态创建Agent Team，并支持触发执行和结构化输出。

## 技术栈

- **后端框架**: Python + FastAPI
- **Agent框架**: LangChain/LangGraph
- **数据存储**: PostgreSQL
- **消息传递**: SSE (Server-Sent Events) 用于流式输出

## 核心概念

### 资源拓扑结构
```
                         [Global Supervisor]
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
        ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
        │  Node A     │   │  Node B     │   │  Node C     │
        │ ─────────── │   │ ─────────── │   │ ─────────── │
        │ [Supervisor]│   │ [Supervisor]│   │ [Supervisor]│
        │      │      │   │      │      │   │      │      │
        │ ┌────┼────┐ │   │ ┌────┼────┐ │   │ ┌────┼────┐ │
        │ ▼    ▼    ▼ │   │ ▼    ▼    ▼ │   │ ▼    ▼    ▼ │
        │ A1   A2   A3│   │ B1   B2   B3│   │ C1   C2   C3│
        └─────────────┘   └─────────────┘   └─────────────┘
              │                  │                  │
              └────────── calls ─┴─ depends_on ─────┘
                        (Edge Relations)
```

**层级说明:**
- **Global Supervisor**: 顶层协调者，管理所有Node Team之间的协作
- **Node Supervisor**: 每个节点内部的协调者，管理该节点下的Agent组
- **Agent (A1, B1...)**: 执行具体任务的智能体，绑定特定模型和工具
- **Edge Relations**: 节点之间的关系（调用、依赖、集成等）

### 术语定义
- **Node（节点）**: 资源拓扑中的单个资源实体
- **Agent**: 绑定特定模型和工具的智能体
- **Node Team**: 一个节点下的Agent组及其Supervisor
- **Global Supervisor**: 协调所有Node Team的顶层Supervisor
- **Team**: 整个拓扑结构对应的Agent组织

---

## 接口一：创建Agent Team

### 端点
```
POST /api/v1/teams
```

### 功能描述
接收资源节点的拓扑结构数据，动态创建对应的Agent Team。

### 请求体结构

```json
{
  "topology": {
    "nodes": [
      {
        "node_id": "string",
        "node_name": "string",
        "node_type": "string",
        "attributes": {
          "key": "value"
        },
        "agents": [
          {
            "agent_id": "string",
            "agent_name": "string",
            "model_provider": "string",
            "model_id": "string",
            "system_prompt": "string",
            "user_prompt_template": "string",
            "tools": ["tool_name_1", "tool_name_2"],
            "temperature": 0.7,
            "max_tokens": 4096
          }
        ],
        "supervisor_config": {
          "model_provider": "string",
          "model_id": "string",
          "system_prompt": "string",
          "coordination_strategy": "round_robin | priority | adaptive"
        }
      }
    ],
    "edges": [
      {
        "source_node_id": "string",
        "target_node_id": "string",
        "relation_type": "calls | depends_on | integrates | monitors",
        "attributes": {
          "key": "value"
        }
      }
    ],
    "global_supervisor": {
      "model_provider": "string",
      "model_id": "string",
      "system_prompt": "string",
      "coordination_strategy": "hierarchical | parallel | sequential"
    }
  },
  "team_name": "string",
  "description": "string",
  "timeout_seconds": 300,
  "max_iterations": 50
}
```

### 请求参数说明

#### Node（节点）
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| node_id | string | 是 | 节点唯一标识 |
| node_name | string | 是 | 节点名称 |
| node_type | string | 是 | 节点类型（如：service, database, gateway等） |
| attributes | object | 否 | 节点自定义属性 |
| agents | array | 是 | 节点下的Agent列表 |
| supervisor_config | object | 是 | 节点Supervisor配置 |

#### Agent
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| agent_id | string | 是 | Agent唯一标识 |
| agent_name | string | 是 | Agent名称 |
| model_provider | string | 是 | 模型供应商（引用LLM配置） |
| model_id | string | 是 | 模型ID（引用LLM配置） |
| system_prompt | string | 是 | 系统提示词 |
| user_prompt_template | string | 否 | 用户提示词模板，支持变量占位符 |
| tools | array | 否 | 可使用的工具列表 |
| temperature | number | 否 | 温度参数，默认0.7 |
| max_tokens | number | 否 | 最大输出Token，默认4096 |

#### Edge（边/关系）
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_node_id | string | 是 | 源节点ID |
| target_node_id | string | 是 | 目标节点ID |
| relation_type | string | 是 | 关系类型 |
| attributes | object | 否 | 关系自定义属性 |

#### 关系类型枚举
- `calls`: 调用关系
- `depends_on`: 依赖关系
- `integrates`: 集成关系
- `monitors`: 监控关系
- `data_flow`: 数据流向

#### 协调策略枚举
**Node Supervisor策略:**
- `round_robin`: 轮询调度
- `priority`: 优先级调度
- `adaptive`: 自适应调度

**Global Supervisor策略:**
- `hierarchical`: 层级执行（逐层向下）
- `parallel`: 并行执行所有Node Team
- `sequential`: 按拓扑顺序串行执行

### 响应体

#### 成功响应 (201 Created)
```json
{
  "team_id": "uuid-string",
  "status": "created",
  "created_at": "2024-01-01T00:00:00Z",
  "topology_summary": {
    "node_count": 3,
    "agent_count": 9,
    "edge_count": 4
  }
}
```

#### 失败响应 (400 Bad Request)
```json
{
  "status": "failed",
  "error_code": "INVALID_TOPOLOGY",
  "error_message": "Node 'node-123' references undefined model provider 'unknown-provider'",
  "details": {
    "invalid_nodes": ["node-123"],
    "missing_references": ["unknown-provider"]
  }
}
```

### 验证规则
1. 所有 `model_provider` 和 `model_id` 必须在LLM配置中存在
2. 所有 `tools` 必须在系统注册的工具列表中
3. 节点ID必须唯一
4. Edge引用的节点必须存在
5. 拓扑结构不能有孤立节点（除非显式允许）

---

## 接口二：触发Agent Team执行

### 端点
```
POST /api/v1/teams/{team_id}/execute
```

### 功能描述
通过Team ID触发Agent Team开始工作，返回流式执行消息。

### 请求参数

#### Path参数
| 参数 | 类型 | 说明 |
|------|------|------|
| team_id | string | Team唯一标识 |

#### 请求体
```json
{
  "input": {
    "task": "string",
    "context": {
      "key": "value"
    }
  },
  "timeout_seconds": 300,
  "stream": true
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| input.task | string | 是 | 执行任务描述 |
| input.context | object | 否 | 任务上下文数据 |
| timeout_seconds | number | 否 | 超时时间（秒），默认300 |
| stream | boolean | 否 | 是否流式返回，默认true |

### 响应

#### 流式响应 (SSE)

**消息标识规则:**
- 每条消息必须包含 `team_id`
- Node级别消息必须包含 `node_id`
- Agent消息必须包含 `agent_id`
- Node Supervisor消息必须包含 `supervisor_id`
- Global Supervisor消息不包含 `node_id`（因为它在节点层级之上）

```
Content-Type: text/event-stream

event: execution_start
data: {"team_id": "team-456", "execution_id": "exec-123", "started_at": "2024-01-01T00:00:00Z"}

event: global_supervisor_message
data: {"team_id": "team-456", "supervisor_id": "global-sup-1", "message": "Starting topology analysis...", "timestamp": "..."}

event: global_supervisor_decision
data: {"team_id": "team-456", "supervisor_id": "global-sup-1", "decision": "Dispatching to Node A and Node B in parallel", "timestamp": "..."}

event: node_supervisor_message
data: {"team_id": "team-456", "node_id": "node-a", "supervisor_id": "sup-node-a", "message": "Received task, coordinating agents...", "timestamp": "..."}

event: node_supervisor_decision
data: {"team_id": "team-456", "node_id": "node-a", "supervisor_id": "sup-node-a", "decision": "Delegating to agent-1 for log analysis", "timestamp": "..."}

event: agent_message
data: {"team_id": "team-456", "node_id": "node-a", "agent_id": "agent-1", "message": "Starting analysis...", "timestamp": "..."}

event: agent_message
data: {"team_id": "team-456", "node_id": "node-a", "agent_id": "agent-2", "message": "Found 3 issues...", "timestamp": "..."}

event: tool_call
data: {"team_id": "team-456", "node_id": "node-a", "agent_id": "agent-1", "tool": "search_logs", "input": {...}, "output": {...}, "timestamp": "..."}

event: node_complete
data: {"team_id": "team-456", "node_id": "node-a", "supervisor_id": "sup-node-a", "result": "...", "timestamp": "..."}

event: global_supervisor_message
data: {"team_id": "team-456", "supervisor_id": "global-sup-1", "message": "All nodes completed, aggregating results...", "timestamp": "..."}

event: execution_complete
data: {"team_id": "team-456", "execution_id": "exec-123", "status": "success", "duration_ms": 12500, "result": {...}}
```

#### 事件类型
| 事件 | 说明 | 必含字段 |
|------|------|----------|
| execution_start | 执行开始 | team_id, execution_id |
| global_supervisor_message | Global Supervisor消息 | team_id, supervisor_id |
| global_supervisor_decision | Global Supervisor决策 | team_id, supervisor_id |
| node_supervisor_message | Node Supervisor消息 | team_id, node_id, supervisor_id |
| node_supervisor_decision | Node Supervisor决策 | team_id, node_id, supervisor_id |
| agent_message | Agent输出消息 | team_id, node_id, agent_id |
| tool_call | 工具调用记录 | team_id, node_id, agent_id |
| node_complete | 单个Node Team完成 | team_id, node_id, supervisor_id |
| execution_complete | 整体执行完成 | team_id, execution_id |
| execution_error | 执行错误 | team_id, (node_id, agent_id 可选) |
| heartbeat | 心跳保活（每30秒） | team_id |

#### 非流式响应 (stream=false)
```json
{
  "execution_id": "exec-123",
  "team_id": "team-456",
  "status": "success",
  "started_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T00:00:12Z",
  "duration_ms": 12500,
  "result": {
    "summary": "...",
    "node_results": [
      {
        "node_id": "node-a",
        "status": "success",
        "output": "..."
      }
    ]
  }
}
```

### 错误响应

#### 404 Not Found
```json
{
  "error_code": "TEAM_NOT_FOUND",
  "error_message": "Team with ID 'team-456' not found"
}
```

#### 408 Request Timeout
```json
{
  "error_code": "EXECUTION_TIMEOUT",
  "error_message": "Execution timed out after 300 seconds",
  "partial_result": {...}
}
```

---

## 接口三：结构化输出

### 端点
```
POST /api/v1/teams/{team_id}/structured-output
```

### 功能描述
基于Team执行结果，按照指定模板生成结构化输出。

### 请求参数

#### Path参数
| 参数 | 类型 | 说明 |
|------|------|------|
| team_id | string | Team唯一标识 |

#### 请求体
```json
{
  "execution_id": "string",
  "output_schema": {
    "type": "object",
    "properties": {
      "summary": {
        "type": "string",
        "description": "执行结果摘要"
      },
      "issues": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
            "description": {"type": "string"},
            "affected_node": {"type": "string"},
            "recommendation": {"type": "string"}
          }
        }
      },
      "metrics": {
        "type": "object",
        "properties": {
          "total_nodes_analyzed": {"type": "integer"},
          "issues_found": {"type": "integer"},
          "execution_time_ms": {"type": "integer"}
        }
      }
    },
    "required": ["summary", "issues"]
  },
  "include_raw_output": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| execution_id | string | 否 | 指定执行ID，不填则使用最近一次执行 |
| output_schema | object | 是 | JSON Schema格式的输出模板 |
| include_raw_output | boolean | 否 | 是否包含原始输出，默认false |

### 响应

#### 成功响应 (200 OK)
```json
{
  "team_id": "team-456",
  "execution_id": "exec-123",
  "structured_output": {
    "summary": "分析完成，发现3个问题需要关注",
    "issues": [
      {
        "severity": "high",
        "description": "数据库连接池耗尽",
        "affected_node": "db-service",
        "recommendation": "增加连接池大小或优化查询"
      }
    ],
    "metrics": {
      "total_nodes_analyzed": 5,
      "issues_found": 3,
      "execution_time_ms": 12500
    }
  },
  "schema_validation": {
    "valid": true,
    "errors": []
  }
}
```

#### Schema验证失败 (422 Unprocessable Entity)
```json
{
  "error_code": "SCHEMA_GENERATION_FAILED",
  "error_message": "Unable to generate output matching the provided schema",
  "schema_validation": {
    "valid": false,
    "errors": [
      {
        "path": "$.issues[0].severity",
        "message": "Value 'urgent' is not in enum ['critical', 'high', 'medium', 'low']"
      }
    ]
  },
  "partial_output": {...}
}
```

---

## 辅助接口

### 获取Team状态
```
GET /api/v1/teams/{team_id}
```

### 列出所有Teams
```
GET /api/v1/teams?page=1&size=20&status=active
```

### 删除Team
```
DELETE /api/v1/teams/{team_id}
```

### 获取执行历史
```
GET /api/v1/teams/{team_id}/executions?page=1&size=20
```

### 获取执行详情
```
GET /api/v1/executions/{execution_id}
```

---

## 数据模型

### Team
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | String | Team名称 |
| description | String | 描述 |
| topology_config | JSONB | 拓扑结构配置 |
| status | Enum | 状态（active, inactive, error） |
| created_at | Timestamp | 创建时间 |
| updated_at | Timestamp | 更新时间 |

### Execution
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| team_id | UUID | 外键-Team |
| input | JSONB | 执行输入 |
| output | JSONB | 执行输出 |
| status | Enum | 状态（running, success, failed, timeout） |
| started_at | Timestamp | 开始时间 |
| completed_at | Timestamp | 完成时间 |
| duration_ms | Integer | 执行时长 |
| error_message | String | 错误信息 |

### ExecutionLog
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| execution_id | UUID | 外键-Execution |
| event_type | String | 事件类型 |
| agent_id | String | Agent ID |
| node_id | String | Node ID |
| message | Text | 消息内容 |
| metadata | JSONB | 元数据 |
| timestamp | Timestamp | 时间戳 |

---

## 非功能需求

### 性能
- Team创建响应时间 < 500ms
- 流式消息延迟 < 100ms
- 支持并发执行多个Team（至少10个并发）

### 可靠性
- 执行超时自动终止
- 支持执行中断和恢复
- 执行日志持久化存储

### 可观测性
- 执行过程完整追踪
- Agent级别的性能指标
- 错误详细堆栈记录

### 安全性
- Team执行需要授权
- 敏感数据不记录到日志
- 工具调用权限控制

---

## 边界条件

- 单个Team最多包含100个节点
- 单个节点最多包含20个Agent
- 拓扑深度最多10层
- 单次执行超时上限：30分钟
- 执行历史保留：30天
- 流式连接超时：5分钟无消息自动断开
