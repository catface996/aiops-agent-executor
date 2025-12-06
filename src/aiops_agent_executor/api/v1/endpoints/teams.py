"""Agent团队管理API接口

动态创建和管理Agent团队，支持基于拓扑结构的团队编排、执行触发和结果查询。
团队采用三层架构：Global Supervisor → Node Supervisor → Agent。
"""

import uuid
from datetime import datetime, UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from aiops_agent_executor.db.models.team import TeamStatus
from aiops_agent_executor.db.session import get_db_session
from aiops_agent_executor.schemas import (
    ExecutionRequest,
    ExecutionResponse,
    StructuredOutputRequest,
    StructuredOutputResponse,
    TeamCreate,
    TeamCreatedResponse,
    TeamResponse,
    TopologyValidationResult,
    TopologyValidationError,
)
from aiops_agent_executor.services.execution_service import ExecutionService
from aiops_agent_executor.services.team_service import TeamService


class TeamUpdate(BaseModel):
    """Schema for updating a team."""
    team_name: str | None = None
    description: str | None = None
    topology: dict[str, Any] | None = None
    timeout_seconds: int | None = None
    max_iterations: int | None = None
    status: TeamStatus | None = None

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post(
    "",
    response_model=TeamCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建Agent团队",
    description="""
根据资源拓扑结构创建Agent团队。

**拓扑结构说明**:
```
                    [Global Supervisor]
                            │
           ┌────────────────┼────────────────┐
           ▼                ▼                ▼
      [Node A]         [Node B]         [Node C]
      Supervisor       Supervisor       Supervisor
        │ │ │           │ │ │           │ │ │
        A1 A2 A3        B1 B2 B3        C1 C2 C3
```

**核心概念**:
- **Node**: 资源节点，包含一组Agent和一个Node Supervisor
- **Agent**: 执行具体任务的智能体，绑定特定模型和工具
- **Edge**: 节点之间的关系（调用、依赖、集成等）
- **Global Supervisor**: 顶层协调者，管理所有Node之间的协作

**示例请求** (简化版):
```json
{
    "team_name": "故障诊断团队",
    "description": "用于分析系统故障的Agent团队",
    "topology": {
        "nodes": [{
            "node_id": "db-service",
            "node_name": "数据库服务",
            "node_type": "database",
            "agents": [{
                "agent_id": "log-analyzer",
                "agent_name": "日志分析Agent",
                "model_id": "gpt-4",
                "system_prompt": "你是一个日志分析专家...",
                "tools": ["search_logs", "parse_error"]
            }],
            "supervisor_config": {
                "model_id": "gpt-4",
                "system_prompt": "协调数据库相关的分析任务",
                "coordination_strategy": "adaptive"
            }
        }],
        "edges": [{
            "source_node_id": "app-service",
            "target_node_id": "db-service",
            "relation_type": "calls"
        }],
        "global_supervisor": {
            "model_id": "gpt-4",
            "system_prompt": "协调所有节点完成故障诊断",
            "coordination_strategy": "hierarchical"
        }
    },
    "timeout_seconds": 300,
    "max_iterations": 50
}
```

**说明**:
- `model_id`: 指定使用的模型（如 gpt-4, claude-3-opus 等）
- Provider 和 API 密钥在执行时从系统数据库配置中自动获取

**验证规则**:
- 节点ID必须唯一
- Edge引用的节点必须存在
- 单个Team最多100个节点，单节点最多20个Agent
""",
    responses={
        201: {"description": "团队创建成功"},
        400: {"description": "请求参数错误或拓扑验证失败"},
    },
)
async def create_team(
    team_in: TeamCreate,
    db: AsyncSession = Depends(get_db_session),
) -> TeamCreatedResponse:
    """根据拓扑配置创建Agent团队"""
    service = TeamService(db)
    team = await service.create_team(team_in)
    await db.commit()

    # Generate topology summary
    topology = team.topology_config
    nodes = topology.get("nodes", [])
    edges = topology.get("edges", [])
    topology_summary = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "agent_count": sum(len(n.get("agents", [])) for n in nodes),
        "has_global_supervisor": topology.get("global_supervisor") is not None,
    }

    return TeamCreatedResponse(
        team_id=team.id,
        status="created",
        created_at=team.created_at,
        topology_summary=topology_summary,
    )


@router.get(
    "",
    response_model=list[TeamResponse],
    summary="获取团队列表",
    description="""
分页获取所有已创建的Agent团队。

**筛选参数**:
- `status`: 按状态筛选（active/inactive/error）

**返回信息**:
- 团队基本信息（名称、描述）
- 配置参数（超时时间、最大迭代数）
- 状态和时间戳

**排序规则**:
按创建时间倒序排列。
""",
    responses={
        200: {"description": "成功返回团队列表"},
    },
)
async def list_teams(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    status_filter: str | None = Query(None, alias="status", description="状态筛选: active/inactive/error"),
    db: AsyncSession = Depends(get_db_session),
) -> list[TeamResponse]:
    """获取Agent团队列表"""
    service = TeamService(db)

    # Parse status filter
    team_status = None
    if status_filter:
        try:
            team_status = TeamStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter: {status_filter}. Valid values: active, inactive, error",
            )

    skip = (page - 1) * size
    teams, _total = await service.list_teams(skip=skip, limit=size, status=team_status)

    return [TeamResponse.model_validate(team) for team in teams]


@router.get(
    "/{team_id}",
    response_model=TeamResponse,
    summary="获取团队详情",
    description="""
获取指定团队的详细信息。

**返回内容**:
- 团队基本信息
- 完整的拓扑配置
- 执行参数设置
- 状态信息
""",
    responses={
        200: {"description": "成功返回团队详情"},
        404: {"description": "团队不存在"},
    },
)
async def get_team(
    team_id: uuid.UUID = Path(..., description="团队ID"),
    db: AsyncSession = Depends(get_db_session),
) -> TeamResponse:
    """获取指定团队的详细信息"""
    service = TeamService(db)
    team = await service.get_team(team_id)

    return TeamResponse.model_validate(team)


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除团队",
    description="""
删除指定的Agent团队。

**删除内容**:
- 团队配置信息
- 关联的执行历史
- 执行日志记录

**删除限制**:
- 如果团队有正在运行的执行任务，删除会被拒绝
- 建议先等待执行完成或取消执行

**注意**: 删除操作不可恢复。
""",
    responses={
        204: {"description": "团队删除成功"},
        404: {"description": "团队不存在"},
        409: {"description": "团队有正在运行的任务，无法删除"},
    },
)
async def delete_team(
    team_id: uuid.UUID = Path(..., description="团队ID"),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """删除Agent团队"""
    service = TeamService(db)
    await service.delete_team(team_id)
    await db.commit()


@router.patch(
    "/{team_id}",
    response_model=TeamResponse,
    summary="更新团队配置",
    description="""
更新指定团队的配置信息。

**可更新字段**:
- `team_name`: 团队名称
- `description`: 团队描述
- `topology`: 拓扑配置（会进行验证）
- `timeout_seconds`: 执行超时时间
- `max_iterations`: 最大迭代次数
- `status`: 团队状态

**注意**: 更新拓扑配置时会重新进行验证。
""",
    responses={
        200: {"description": "更新成功"},
        400: {"description": "请求参数错误或拓扑验证失败"},
        404: {"description": "团队不存在"},
        409: {"description": "团队名称已存在"},
    },
)
async def update_team(
    team_id: uuid.UUID = Path(..., description="团队ID"),
    team_update: TeamUpdate = ...,
    db: AsyncSession = Depends(get_db_session),
) -> TeamResponse:
    """更新团队配置"""
    service = TeamService(db)

    update_data = team_update.model_dump(exclude_unset=True)
    team = await service.update_team(team_id, update_data)
    await db.commit()

    return TeamResponse.model_validate(team)


@router.post(
    "/{team_id}/validate",
    response_model=TopologyValidationResult,
    summary="验证团队拓扑",
    description="""
验证指定团队的拓扑配置是否有效。

**验证内容**:
- 节点ID唯一性
- 边引用的节点存在性
- 循环检测
- 孤立节点检测

**返回结果**:
- `valid`: 是否通过验证
- `errors`: 错误信息列表（如有）
""",
    responses={
        200: {"description": "验证完成"},
        404: {"description": "团队不存在"},
    },
)
async def validate_team_topology(
    team_id: uuid.UUID = Path(..., description="团队ID"),
    db: AsyncSession = Depends(get_db_session),
) -> TopologyValidationResult:
    """验证团队拓扑配置"""
    service = TeamService(db)
    team = await service.get_team(team_id)

    validation_result = service.validate_topology(team.topology_config)

    return TopologyValidationResult(
        valid=validation_result.valid,
        errors=[
            TopologyValidationError(code="VALIDATION_ERROR", message=err)
            for err in validation_result.errors
        ],
    )


@router.post(
    "/{team_id}/execute",
    response_model=None,
    summary="执行团队任务",
    description="""
触发Agent团队开始执行任务。

**执行模式**:
- `stream=true` (默认): 通过SSE流式返回执行过程
- `stream=false`: 等待执行完成后返回最终结果

**SSE事件类型**:
| 事件 | 说明 |
|------|------|
| execution_start | 执行开始 |
| global_supervisor_message | 全局协调者消息 |
| global_supervisor_decision | 全局协调者决策 |
| node_supervisor_message | 节点协调者消息 |
| node_supervisor_decision | 节点协调者决策 |
| agent_message | Agent输出消息 |
| tool_call | 工具调用记录 |
| node_complete | 单个节点完成 |
| execution_complete | 整体执行完成 |
| execution_error | 执行错误 |
| heartbeat | 心跳保活（每30秒） |

**SSE消息示例**:
```
event: agent_message
data: {"team_id": "xxx", "node_id": "db-service", "agent_id": "log-analyzer", "message": "发现3条错误日志...", "timestamp": "..."}

event: tool_call
data: {"team_id": "xxx", "node_id": "db-service", "agent_id": "log-analyzer", "tool": "search_logs", "input": {...}, "output": {...}}
```

**请求示例**:
```json
{
    "input": {
        "task": "分析过去1小时的系统故障原因",
        "context": {
            "time_range": "1h",
            "severity": "error"
        }
    },
    "timeout_seconds": 300,
    "stream": true
}
```
""",
    responses={
        200: {"description": "执行成功（非流式）或SSE流开始（流式）"},
        404: {"description": "团队不存在"},
        408: {"description": "执行超时"},
        409: {"description": "团队已有正在执行的任务"},
    },
)
async def execute_team(
    team_id: uuid.UUID = Path(..., description="团队ID"),
    execution_in: ExecutionRequest = ...,
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse | ExecutionResponse:
    """触发团队执行任务"""
    exec_service = ExecutionService(db)

    # Create execution record
    execution = await exec_service.start_execution(
        team_id=team_id,
        input_data=execution_in.input.model_dump(),
        timeout_seconds=execution_in.timeout_seconds,
    )
    await db.commit()

    if execution_in.stream:
        # SSE streaming response
        async def event_generator():
            async for event in exec_service.execute_stream(execution.id):
                yield event.to_sse_format()
            await db.commit()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Non-streaming execution
        result = await exec_service.execute_sync(execution.id)
        await db.commit()

        # Refresh execution to get latest state
        await db.refresh(execution)

        return ExecutionResponse.model_validate(execution)


@router.post(
    "/{team_id}/structured-output",
    response_model=StructuredOutputResponse,
    summary="生成结构化输出",
    description="""
基于执行结果生成符合指定Schema的结构化输出。

**用途**:
- 将自由文本结果转换为标准JSON格式
- 提取特定字段用于下游处理
- 生成符合API规范的响应

**请求参数**:
- `execution_id`: 指定执行ID，不填则使用最近一次执行
- `output_schema`: JSON Schema定义的输出结构
- `include_raw_output`: 是否包含原始输出

**Schema示例**:
```json
{
    "output_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "执行摘要"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                        "description": {"type": "string"},
                        "recommendation": {"type": "string"}
                    }
                }
            }
        },
        "required": ["summary", "issues"]
    }
}
```

**返回结果**:
```json
{
    "team_id": "xxx",
    "execution_id": "xxx",
    "structured_output": {
        "summary": "发现3个问题需要关注",
        "issues": [...]
    },
    "schema_validation": {
        "valid": true,
        "errors": []
    }
}
```
""",
    responses={
        200: {"description": "结构化输出生成成功"},
        404: {"description": "团队或执行记录不存在"},
        422: {"description": "无法生成符合Schema的输出"},
    },
)
async def get_structured_output(
    team_id: uuid.UUID = Path(..., description="团队ID"),
    output_request: StructuredOutputRequest = ...,
    db: AsyncSession = Depends(get_db_session),
) -> StructuredOutputResponse:
    """生成结构化输出"""
    exec_service = ExecutionService(db)

    # Get the execution
    if output_request.execution_id:
        execution = await exec_service.get_execution(output_request.execution_id)
    else:
        # Get latest execution for team
        executions = await exec_service.list_executions(team_id=team_id, limit=1)
        if not executions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No executions found for this team",
            )
        execution = executions[0]

    # Validate team matches
    if execution.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Execution does not belong to the specified team",
        )

    # Generate structured output using mock for now
    # In production, this would use LLM to extract structured data
    raw_output = execution.output_data or {}
    structured_output = {
        "summary": raw_output.get("result", "No output available")[:500],
        "execution_id": str(execution.id),
        "status": execution.status.value,
    }

    # Validate against schema if provided
    validation_result = {"valid": True, "errors": []}
    if output_request.output_schema:
        try:
            import jsonschema
            jsonschema.validate(structured_output, output_request.output_schema)
        except jsonschema.ValidationError as e:
            validation_result = {"valid": False, "errors": [str(e.message)]}

    return StructuredOutputResponse(
        team_id=team_id,
        execution_id=execution.id,
        structured_output=structured_output,
        schema_validation=validation_result,
        raw_output=raw_output if output_request.include_raw_output else None,
    )


@router.get(
    "/{team_id}/executions",
    response_model=list[ExecutionResponse],
    summary="获取执行历史",
    description="""
获取指定团队的执行历史记录。

**返回信息**:
- 执行ID和时间信息
- 输入参数和输出结果
- 执行状态和耗时
- 错误信息（如有）

**筛选参数**:
- `status`: 按执行状态筛选

**排序规则**:
按执行时间倒序排列，最近的执行排在前面。

**历史保留**:
执行历史默认保留30天，可在系统配置中调整。
""",
    responses={
        200: {"description": "成功返回执行历史"},
        404: {"description": "团队不存在"},
    },
)
async def list_team_executions(
    team_id: uuid.UUID = Path(..., description="团队ID"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    execution_status: str | None = Query(None, alias="status", description="状态筛选: pending/running/success/failed/timeout"),
    db: AsyncSession = Depends(get_db_session),
) -> list[ExecutionResponse]:
    """获取团队的执行历史"""
    from aiops_agent_executor.db.models.team import ExecutionStatus

    # Verify team exists
    team_service = TeamService(db)
    await team_service.get_team(team_id)

    exec_service = ExecutionService(db)

    # Parse status filter
    status_enum = None
    if execution_status:
        try:
            status_enum = ExecutionStatus(execution_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {execution_status}",
            )

    skip = (page - 1) * size
    executions = await exec_service.list_executions(
        team_id=team_id,
        status=status_enum,
        skip=skip,
        limit=size,
    )

    return [ExecutionResponse.model_validate(ex) for ex in executions]


@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionResponse,
    summary="获取执行详情",
    description="""
获取指定执行的详细信息。

**返回内容**:
- 执行基本信息（ID、团队ID、状态）
- 输入参数
- 输出结果（如已完成）
- 时间信息（开始、完成、耗时）
- 错误信息（如执行失败）

**执行状态说明**:
| 状态 | 说明 |
|------|------|
| pending | 等待执行 |
| running | 正在执行 |
| success | 执行成功 |
| failed | 执行失败 |
| timeout | 执行超时 |
| cancelled | 已取消 |
""",
    responses={
        200: {"description": "成功返回执行详情"},
        404: {"description": "执行记录不存在"},
    },
)
async def get_execution(
    execution_id: uuid.UUID = Path(..., description="执行ID"),
    db: AsyncSession = Depends(get_db_session),
) -> ExecutionResponse:
    """获取指定执行的详细信息"""
    exec_service = ExecutionService(db)
    execution = await exec_service.get_execution(execution_id)

    return ExecutionResponse.model_validate(execution)
