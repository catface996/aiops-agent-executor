---
inclusion: fileMatch
fileMatchPattern: "**/agent/**/*.py"
---

# Agent 开发指南

## LangGraph 架构设计

### 层级化 Supervisor 架构

```python
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

# 定义状态
class TeamState(TypedDict):
    messages: list[BaseMessage]
    current_node: str
    node_results: dict[str, Any]
    global_context: dict[str, Any]
    next_action: str

class NodeState(TypedDict):
    messages: list[BaseMessage]
    current_agent: str
    agent_results: dict[str, Any]
    node_context: dict[str, Any]
```

### Global Supervisor 实现

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

class GlobalSupervisor:
    """顶层协调者，管理所有 Node Team"""
    
    def __init__(self, config: GlobalSupervisorConfig, topology: TopologyConfig):
        self.config = config
        self.topology = topology
        self.llm = self._create_llm()
        self.node_teams = self._create_node_teams()
        
    def _create_llm(self):
        """根据配置创建 LLM"""
        return create_llm_from_config(
            self.config.model_provider,
            self.config.model_id
        )
    
    def _create_node_teams(self) -> dict[str, NodeTeam]:
        """为每个节点创建 Node Team"""
        teams = {}
        for node_config in self.topology.nodes:
            teams[node_config.node_id] = NodeTeam(node_config)
        return teams
    
    async def coordinate(self, state: TeamState) -> TeamState:
        """协调各个 Node Team 的执行"""
        
        # 构建 Supervisor 提示词
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.config.system_prompt),
            ("human", self._build_coordination_prompt(state))
        ])
        
        # 决策下一步行动
        response = await self.llm.ainvoke(prompt.format_messages())
        
        # 解析决策
        decision = self._parse_decision(response.content)
        
        # 更新状态
        state["next_action"] = decision["action"]
        state["current_node"] = decision.get("target_node")
        
        return state
    
    def _build_coordination_prompt(self, state: TeamState) -> str:
        """构建协调提示词"""
        return f"""
        当前任务：{state['messages'][-1].content}
        
        可用节点：
        {self._format_available_nodes()}
        
        已完成节点：
        {self._format_completed_nodes(state)}
        
        节点关系：
        {self._format_topology_edges()}
        
        请决定下一步行动：
        1. 选择一个节点执行任务
        2. 并行执行多个节点
        3. 汇总结果并结束
        """
    
    def _format_available_nodes(self) -> str:
        """格式化可用节点信息"""
        nodes_info = []
        for node_id, team in self.node_teams.items():
            agents = [a.agent_name for a in team.agents]
            nodes_info.append(f"- {node_id}: {', '.join(agents)}")
        return "\n".join(nodes_info)
```

### Node Supervisor 实现

```python
class NodeSupervisor:
    """节点级协调者，管理节点内的 Agent 组"""
    
    def __init__(self, config: SupervisorConfig, agents: list[Agent]):
        self.config = config
        self.agents = {agent.agent_id: agent for agent in agents}
        self.llm = self._create_llm()
        
    async def coordinate(self, state: NodeState) -> NodeState:
        """协调节点内的 Agent 执行"""
        
        # 根据策略选择 Agent
        if self.config.coordination_strategy == "round_robin":
            next_agent = self._round_robin_select(state)
        elif self.config.coordination_strategy == "priority":
            next_agent = self._priority_select(state)
        else:  # adaptive
            next_agent = await self._adaptive_select(state)
        
        state["current_agent"] = next_agent
        return state
    
    async def _adaptive_select(self, state: NodeState) -> str:
        """使用 LLM 自适应选择 Agent"""
        prompt = f"""
        当前任务：{state['messages'][-1].content}
        
        可用 Agents：
        {self._format_agents()}
        
        已完成工作：
        {self._format_completed_work(state)}
        
        请选择最适合处理当前任务的 Agent。
        """
        
        response = await self.llm.ainvoke(prompt)
        return self._parse_agent_selection(response.content)
```

### Agent 实现

```python
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import Tool

class Agent:
    """执行具体任务的智能体"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm = self._create_llm()
        self.tools = self._load_tools()
        self.executor = self._create_executor()
        
    def _create_llm(self):
        """创建 LLM"""
        return create_llm_from_config(
            self.config.model_provider,
            self.config.model_id,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
    
    def _load_tools(self) -> list[Tool]:
        """加载工具"""
        tools = []
        for tool_name in self.config.tools:
            tool = get_registered_tool(tool_name)
            if not tool:
                raise ToolNotFoundError(f"Tool '{tool_name}' not registered")
            tools.append(tool)
        return tools
    
    def _create_executor(self) -> AgentExecutor:
        """创建 Agent 执行器"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.config.system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        agent = create_openai_tools_agent(self.llm, self.tools, prompt)
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            return_intermediate_steps=True
        )
    
    async def execute(self, task: str, context: dict) -> dict:
        """执行任务"""
        # 构建输入
        input_text = self._build_input(task, context)
        
        # 执行
        result = await self.executor.ainvoke({"input": input_text})
        
        return {
            "agent_id": self.config.agent_id,
            "output": result["output"],
            "intermediate_steps": result.get("intermediate_steps", [])
        }
    
    def _build_input(self, task: str, context: dict) -> str:
        """构建输入，支持模板变量"""
        if self.config.user_prompt_template:
            return self.config.user_prompt_template.format(
                task=task,
                **context
            )
        return task
```

## LangGraph 图构建

### Node Team 图

```python
class NodeTeam:
    """节点团队，包含 Supervisor 和多个 Agent"""
    
    def __init__(self, config: NodeConfig):
        self.config = config
        self.supervisor = NodeSupervisor(
            config.supervisor_config,
            self._create_agents(config.agents)
        )
        self.agents = {
            agent.agent_id: agent 
            for agent in self._create_agents(config.agents)
        }
        self.graph = self._build_graph()
    
    def _create_agents(self, agent_configs: list[AgentConfig]) -> list[Agent]:
        """创建所有 Agent"""
        return [Agent(config) for config in agent_configs]
    
    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 图"""
        workflow = StateGraph(NodeState)
        
        # 添加 Supervisor 节点
        workflow.add_node("supervisor", self.supervisor.coordinate)
        
        # 添加 Agent 节点
        for agent_id, agent in self.agents.items():
            workflow.add_node(agent_id, agent.execute)
        
        # 添加边
        workflow.set_entry_point("supervisor")
        
        # Supervisor 到 Agent 的条件边
        workflow.add_conditional_edges(
            "supervisor",
            self._route_to_agent,
            {agent_id: agent_id for agent_id in self.agents.keys()}
        )
        
        # Agent 回到 Supervisor
        for agent_id in self.agents.keys():
            workflow.add_edge(agent_id, "supervisor")
        
        # Supervisor 决定是否结束
        workflow.add_conditional_edges(
            "supervisor",
            self._should_continue,
            {
                "continue": "supervisor",
                "end": END
            }
        )
        
        return workflow.compile()
    
    def _route_to_agent(self, state: NodeState) -> str:
        """路由到指定 Agent"""
        return state["current_agent"]
    
    def _should_continue(self, state: NodeState) -> str:
        """判断是否继续"""
        if state.get("task_completed"):
            return "end"
        return "continue"
    
    async def execute(self, task: str, context: dict) -> dict:
        """执行节点任务"""
        initial_state = NodeState(
            messages=[HumanMessage(content=task)],
            current_agent="",
            agent_results={},
            node_context=context
        )
        
        final_state = await self.graph.ainvoke(initial_state)
        
        return {
            "node_id": self.config.node_id,
            "results": final_state["agent_results"],
            "messages": final_state["messages"]
        }
```

### Global Team 图

```python
class GlobalTeam:
    """全局团队，包含 Global Supervisor 和所有 Node Team"""
    
    def __init__(self, topology: TopologyConfig):
        self.topology = topology
        self.supervisor = GlobalSupervisor(
            topology.global_supervisor,
            topology
        )
        self.node_teams = self._create_node_teams()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """构建全局图"""
        workflow = StateGraph(TeamState)
        
        # 添加 Global Supervisor
        workflow.add_node("global_supervisor", self.supervisor.coordinate)
        
        # 添加 Node Team 节点
        for node_id, team in self.node_teams.items():
            workflow.add_node(node_id, team.execute)
        
        # 设置入口
        workflow.set_entry_point("global_supervisor")
        
        # 条件路由
        workflow.add_conditional_edges(
            "global_supervisor",
            self._route_to_node,
            {node_id: node_id for node_id in self.node_teams.keys()}
        )
        
        # Node 回到 Global Supervisor
        for node_id in self.node_teams.keys():
            workflow.add_edge(node_id, "global_supervisor")
        
        # 结束条件
        workflow.add_conditional_edges(
            "global_supervisor",
            self._should_end,
            {"continue": "global_supervisor", "end": END}
        )
        
        return workflow.compile()
    
    async def execute(self, task: str, context: dict) -> dict:
        """执行全局任务"""
        initial_state = TeamState(
            messages=[HumanMessage(content=task)],
            current_node="",
            node_results={},
            global_context=context,
            next_action=""
        )
        
        final_state = await self.graph.ainvoke(initial_state)
        
        return {
            "status": "success",
            "results": final_state["node_results"],
            "messages": final_state["messages"]
        }
```

## 工具开发

### 工具注册系统

```python
from typing import Callable
from langchain.tools import Tool

# 全局工具注册表
_TOOL_REGISTRY: dict[str, Tool] = {}

def register_tool(name: str):
    """工具注册装饰器"""
    def decorator(func: Callable):
        tool = Tool(
            name=name,
            func=func,
            description=func.__doc__ or ""
        )
        _TOOL_REGISTRY[name] = tool
        return func
    return decorator

def get_registered_tool(name: str) -> Tool | None:
    """获取已注册的工具"""
    return _TOOL_REGISTRY.get(name)

def list_registered_tools() -> list[str]:
    """列出所有已注册的工具"""
    return list(_TOOL_REGISTRY.keys())
```

### 工具实现示例

```python
@register_tool("search_logs")
def search_logs(query: str, time_range: str = "1h") -> str:
    """搜索系统日志
    
    Args:
        query: 搜索关键词或正则表达式
        time_range: 时间范围，支持 1h, 24h, 7d 等格式
    
    Returns:
        匹配的日志条目，JSON 格式
    """
    # 实现日志搜索逻辑
    results = log_service.search(query, time_range)
    return json.dumps(results, ensure_ascii=False)

@register_tool("query_metrics")
def query_metrics(metric_name: str, aggregation: str = "avg") -> str:
    """查询系统指标
    
    Args:
        metric_name: 指标名称（如 cpu_usage, memory_usage）
        aggregation: 聚合方式（avg, max, min, sum）
    
    Returns:
        指标数据，JSON 格式
    """
    data = metrics_service.query(metric_name, aggregation)
    return json.dumps(data)

@register_tool("execute_command")
def execute_command(command: str, target: str) -> str:
    """在目标主机执行命令
    
    Args:
        command: 要执行的命令
        target: 目标主机 IP 或主机名
    
    Returns:
        命令执行结果
    """
    # 注意：需要权限控制和安全检查
    result = ssh_service.execute(target, command)
    return result
```

## 流式输出实现

### SSE 事件生成器

```python
import asyncio
from typing import AsyncGenerator
from app.schemas.events import ExecutionEvent

async def execute_with_streaming(
    team: GlobalTeam,
    task: str,
    context: dict
) -> AsyncGenerator[ExecutionEvent, None]:
    """执行任务并生成流式事件"""
    
    # 发送开始事件
    yield ExecutionEvent(
        type="execution_start",
        data={
            "team_id": team.team_id,
            "started_at": datetime.utcnow().isoformat()
        }
    )
    
    # 执行任务
    try:
        async for event in team.execute_streaming(task, context):
            yield event
            
        # 发送完成事件
        yield ExecutionEvent(
            type="execution_complete",
            data={"status": "success"}
        )
        
    except Exception as e:
        # 发送错误事件
        yield ExecutionEvent(
            type="execution_error",
            data={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
```

### 在 Agent 中集成流式输出

```python
class Agent:
    async def execute_streaming(
        self,
        task: str,
        context: dict
    ) -> AsyncGenerator[ExecutionEvent, None]:
        """流式执行任务"""
        
        # 发送 Agent 开始消息
        yield ExecutionEvent(
            type="agent_message",
            data={
                "agent_id": self.config.agent_id,
                "message": f"Starting task: {task}"
            }
        )
        
        # 流式执行
        async for chunk in self.executor.astream({"input": task}):
            if "actions" in chunk:
                # 工具调用
                for action in chunk["actions"]:
                    yield ExecutionEvent(
                        type="tool_call",
                        data={
                            "agent_id": self.config.agent_id,
                            "tool": action.tool,
                            "input": action.tool_input
                        }
                    )
            
            if "output" in chunk:
                # Agent 输出
                yield ExecutionEvent(
                    type="agent_message",
                    data={
                        "agent_id": self.config.agent_id,
                        "message": chunk["output"]
                    }
                )
```

## 错误处理和重试

### Agent 级别错误处理

```python
class Agent:
    async def execute(self, task: str, context: dict) -> dict:
        """执行任务，带重试机制"""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                result = await self._execute_internal(task, context)
                return result
                
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                raise
                
            except Exception as e:
                logger.error(
                    "agent_execution_failed",
                    agent_id=self.config.agent_id,
                    error=str(e),
                    attempt=attempt + 1
                )
                if attempt < max_retries - 1:
                    continue
                raise
```

### 超时控制

```python
import asyncio

async def execute_with_timeout(
    team: GlobalTeam,
    task: str,
    context: dict,
    timeout_seconds: int
) -> dict:
    """带超时的执行"""
    try:
        result = await asyncio.wait_for(
            team.execute(task, context),
            timeout=timeout_seconds
        )
        return result
        
    except asyncio.TimeoutError:
        logger.warning(
            "execution_timeout",
            team_id=team.team_id,
            timeout=timeout_seconds
        )
        raise ExecutionTimeoutError(
            f"Execution timed out after {timeout_seconds} seconds"
        )
```

## 性能优化

### 并行执行

```python
async def execute_nodes_parallel(
    node_teams: dict[str, NodeTeam],
    task: str,
    context: dict
) -> dict[str, Any]:
    """并行执行多个 Node Team"""
    
    tasks = [
        team.execute(task, context)
        for team in node_teams.values()
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理结果
    node_results = {}
    for node_id, result in zip(node_teams.keys(), results):
        if isinstance(result, Exception):
            node_results[node_id] = {"error": str(result)}
        else:
            node_results[node_id] = result
    
    return node_results
```

### 缓存 LLM 响应

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_llm_response(prompt: str, model: str) -> str:
    """缓存 LLM 响应（用于确定性任务）"""
    # 注意：只对确定性任务使用缓存
    pass
```
