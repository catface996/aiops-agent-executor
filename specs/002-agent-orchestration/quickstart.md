# Quickstart: Agent团队动态编排

本指南帮助开发者快速理解和实现 Agent 团队动态编排功能。

## 概述

Agent 团队动态编排允许根据资源拓扑结构创建多层级 Agent 团队，支持：
- 三层协调架构（Global Supervisor → Node Supervisor → Agent）
- DAG 拓扑配置与校验
- SSE 实时执行状态推送
- JSON Schema 结构化输出

## 快速开始

### 1. 创建 Agent 团队

```bash
curl -X POST http://localhost:8000/api/v1/teams \
  -H "Content-Type: application/json" \
  -d '{
    "name": "database-health-check-team",
    "description": "数据库健康检查Agent团队",
    "topology_config": {
      "nodes": [
        {
          "id": "supervisor",
          "name": "Global Supervisor",
          "type": "global_supervisor",
          "agent_config": {
            "role": "coordinator",
            "instructions": "协调所有数据库检查任务，汇总结果",
            "model_id": "<your-model-uuid>",
            "temperature": 0.3
          }
        },
        {
          "id": "mysql_checker",
          "name": "MySQL Checker",
          "type": "agent",
          "agent_config": {
            "role": "database_checker",
            "instructions": "检查MySQL数据库连接和性能指标",
            "model_id": "<your-model-uuid>",
            "tools": ["mysql_connect", "query_executor"]
          }
        },
        {
          "id": "postgres_checker",
          "name": "PostgreSQL Checker",
          "type": "agent",
          "agent_config": {
            "role": "database_checker",
            "instructions": "检查PostgreSQL数据库连接和性能指标",
            "model_id": "<your-model-uuid>",
            "tools": ["postgres_connect", "query_executor"]
          }
        }
      ],
      "edges": [
        {"source": "supervisor", "target": "mysql_checker"},
        {"source": "supervisor", "target": "postgres_checker"}
      ],
      "entry_point": "supervisor"
    },
    "timeout_seconds": 300
  }'
```

### 2. 触发执行

```bash
curl -X POST http://localhost:8000/api/v1/teams/<team-id>/executions \
  -H "Content-Type: application/json" \
  -d '{
    "task": "检查所有数据库的健康状态并生成报告",
    "parameters": {
      "include_metrics": true,
      "check_slow_queries": true
    },
    "output_schema": {
      "type": "object",
      "required": ["status", "databases"],
      "properties": {
        "status": {"type": "string", "enum": ["healthy", "warning", "critical"]},
        "databases": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": {"type": "string"},
              "status": {"type": "string"},
              "metrics": {"type": "object"}
            }
          }
        }
      }
    }
  }'
```

### 3. 实时监控执行（SSE）

```bash
curl -N http://localhost:8000/api/v1/executions/<execution-id>/stream
```

SSE 事件格式：
```
event: node_entered
data: {"node_id": "mysql_checker", "timestamp": "2024-12-06T10:00:00Z"}

event: agent_response
data: {"node_id": "mysql_checker", "message": "MySQL连接成功，延迟5ms"}

event: execution_completed
data: {"status": "success", "output": {...}}
```

### 4. 查询执行结果

```bash
curl http://localhost:8000/api/v1/executions/<execution-id>
```

## 核心概念

### 拓扑配置 (TopologyConfig)

```json
{
  "nodes": [...],      // 节点列表
  "edges": [...],      // 边列表（定义执行流程）
  "entry_point": "...", // 入口节点ID
  "output_schema": {}  // 可选的输出Schema
}
```

### 节点类型

| 类型 | 说明 | 用途 |
|------|------|------|
| `global_supervisor` | 全局协调者 | 分解任务、汇总结果 |
| `node_supervisor` | 节点组协调者 | 管理特定节点组 |
| `agent` | 执行者 | 执行具体任务 |

### 执行状态

| 状态 | 说明 |
|------|------|
| `pending` | 等待执行 |
| `running` | 执行中 |
| `success` | 执行成功 |
| `failed` | 执行失败 |
| `timeout` | 执行超时 |
| `cancelled` | 已取消 |

## 最佳实践

### 1. 拓扑设计

- 保持 DAG 结构（无循环依赖）
- 每个团队设置合理的超时时间
- 使用 Global Supervisor 协调复杂任务

### 2. 错误处理

- 失败节点的下游任务会被自动跳过
- 独立分支继续执行
- LLM 调用自动重试（指数退避，最多3次）

### 3. 结构化输出

- 使用 `output_schema` 确保输出格式一致
- Schema 验证失败时自动重试（最多3次）
- 最终失败返回原始输出和解析错误

### 4. SSE 重连

- 使用 `Last-Event-ID` header 恢复断点
- 客户端应实现自动重连机制
- SSE 连接超时30秒

## 代码示例

### Python 客户端

```python
import httpx
import json

# 创建团队
async def create_team(client: httpx.AsyncClient, team_config: dict):
    response = await client.post("/api/v1/teams", json=team_config)
    return response.json()

# 触发执行
async def trigger_execution(client: httpx.AsyncClient, team_id: str, task: str):
    response = await client.post(
        f"/api/v1/teams/{team_id}/executions",
        json={"task": task}
    )
    return response.json()

# 流式监控
async def stream_execution(client: httpx.AsyncClient, execution_id: str):
    async with client.stream("GET", f"/api/v1/executions/{execution_id}/stream") as response:
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                event = json.loads(line[5:])
                print(f"Event: {event}")
```

### JavaScript 客户端（SSE）

```javascript
const eventSource = new EventSource(`/api/v1/executions/${executionId}/stream`);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data);
};

eventSource.addEventListener('execution_completed', (event) => {
  const data = JSON.parse(event.data);
  console.log('Execution completed:', data);
  eventSource.close();
});

eventSource.onerror = (error) => {
  console.error('SSE Error:', error);
  // 实现重连逻辑
};
```

## 下一步

- 查看 [data-model.md](./data-model.md) 了解数据模型详情
- 查看 [contracts/openapi.yaml](./contracts/openapi.yaml) 获取完整 API 规范
- 查看 [research.md](./research.md) 了解技术决策背景
