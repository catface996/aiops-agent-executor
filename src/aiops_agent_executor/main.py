"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from aiops_agent_executor.api.v1.exception_handlers import register_exception_handlers
from aiops_agent_executor.api.v1.router import api_router
from aiops_agent_executor.core.config import get_settings
from aiops_agent_executor.core.logging import get_logger, setup_logging
from aiops_agent_executor.schemas import ErrorResponse, HealthResponse

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    setup_logging()
    logger.info("Starting AIOps Agent Executor", version=settings.app_version)
    yield
    # Shutdown
    logger.info("Shutting down AIOps Agent Executor")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    description = """
# AIOps Agent Executor API

智能运维Agent执行器 - 提供LLM模型配置管理和动态Agent团队编排能力。

## 核心功能

### 1. LLM配置管理
统一管理多种大语言模型供应商的配置，包括：
- **供应商管理**: 支持OpenAI、Anthropic、AWS Bedrock、Azure OpenAI、阿里云、百度等
- **接入点配置**: 管理API端点、超时设置、重试策略
- **密钥管理**: 安全存储和管理API密钥（AES-256加密）
- **模型管理**: 配置可用模型及其能力标签

### 2. Agent团队动态编排
根据资源拓扑结构动态创建和执行Agent团队：
- **拓扑配置**: 定义节点、边关系和Agent配置
- **层级协调**: Global Supervisor → Node Supervisor → Agent 三层架构
- **流式执行**: 通过SSE实时推送执行状态和结果
- **结构化输出**: 按JSON Schema生成标准化输出

## 快速开始

1. 创建供应商配置 (`POST /api/v1/providers`)
2. 添加接入点和密钥
3. 同步可用模型 (`POST /api/v1/providers/{id}/models/sync`)
4. 创建Agent团队 (`POST /api/v1/teams`)
5. 触发执行 (`POST /api/v1/teams/{id}/execute`)

## 技术栈
- **框架**: FastAPI + SQLAlchemy (异步)
- **数据库**: PostgreSQL
- **Agent框架**: LangChain / LangGraph
"""

    tags_metadata = [
        {
            "name": "health",
            "description": "健康检查接口，用于监控服务运行状态",
        },
        {
            "name": "providers",
            "description": "**供应商管理** - 管理LLM模型供应商（如OpenAI、Anthropic等）的基本信息和状态",
        },
        {
            "name": "endpoints",
            "description": "**接入点管理** - 配置供应商的API接入点，包括URL、超时、重试策略等",
        },
        {
            "name": "credentials",
            "description": "**密钥管理** - 安全管理API密钥，支持加密存储、密钥验证和轮换",
        },
        {
            "name": "models",
            "description": "**模型管理** - 管理可用的LLM模型，包括模型能力、定价、上下文窗口等信息",
        },
        {
            "name": "teams",
            "description": "**Agent团队** - 动态创建和管理Agent团队，支持拓扑配置、执行触发和结果查询",
        },
    ]

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=description,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        openapi_tags=tags_metadata,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(api_router)

    # Register exception handlers
    register_exception_handlers(app)

    # Health check endpoint
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["health"],
        summary="服务健康检查",
        description="""
检查服务的运行状态。

**用途**:
- 容器编排平台（K8s）的存活探针和就绪探针
- 负载均衡器的健康检查
- 监控系统的可用性检测

**返回信息**:
- `status`: 服务状态，正常时为 "healthy"
- `version`: 当前服务版本号
- `environment`: 运行环境（development/staging/production）
""",
    )
    async def health_check() -> HealthResponse:
        """健康检查接口"""
        return HealthResponse(
            status="healthy",
            version=settings.app_version,
            environment=settings.environment,
        )

    return app


app = create_app()


def main() -> None:
    """Run the application with uvicorn."""
    import uvicorn

    uvicorn.run(
        "aiops_agent_executor.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers if not settings.debug else 1,
    )


if __name__ == "__main__":
    main()
