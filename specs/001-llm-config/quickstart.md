# Quickstart: LLM配置管理

**Feature Branch**: `001-llm-config`
**Created**: 2025-12-06

## 开发环境设置

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -e ".[dev]"
```

### 2. 数据库设置

```bash
# 启动PostgreSQL (Docker)
docker-compose up -d postgres

# 运行数据库迁移
alembic upgrade head
```

### 3. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑必要配置
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/aiops
# ENCRYPTION_KEY=your-32-byte-encryption-key!!!!
```

### 4. 启动开发服务器

```bash
# 方式1: 直接启动
PYTHONPATH=src uvicorn aiops_agent_executor.main:app --reload

# 方式2: 使用Makefile
make run
```

### 5. 访问API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

---

## 快速测试

### 1. 创建供应商

```bash
curl -X POST http://localhost:8000/api/v1/providers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "OpenAI Production",
    "type": "openai",
    "description": "生产环境OpenAI配置"
  }'
```

### 2. 添加接入点

```bash
curl -X POST http://localhost:8000/api/v1/providers/{provider_id}/endpoints \
  -H "Content-Type: application/json" \
  -d '{
    "name": "主接入点",
    "base_url": "https://api.openai.com/v1",
    "timeout_connect": 30,
    "timeout_read": 120,
    "retry_count": 3,
    "is_default": true
  }'
```

### 3. 添加密钥

```bash
curl -X POST http://localhost:8000/api/v1/providers/{provider_id}/credentials \
  -H "Content-Type: application/json" \
  -d '{
    "alias": "生产密钥",
    "api_key": "sk-xxxxxxxxxxxxxxxx",
    "quota_limit": 1000000
  }'
```

### 4. 同步模型列表

```bash
curl -X POST http://localhost:8000/api/v1/providers/{provider_id}/models/sync
```

### 5. 查询模型

```bash
# 按能力查询
curl http://localhost:8000/api/v1/models/by-capability/function_calling

# 按类型筛选
curl "http://localhost:8000/api/v1/models?type=chat&status=available"
```

---

## 运行测试

```bash
# 运行所有测试
pytest

# 运行带覆盖率
pytest --cov=src/aiops_agent_executor

# 运行特定模块测试
pytest tests/unit/test_provider_service.py

# 运行集成测试
pytest tests/integration/
```

---

## 常见问题

### Q: 加密密钥长度错误

```
ValueError: Encryption key must be exactly 32 bytes
```

**解决**: 确保 `ENCRYPTION_KEY` 环境变量恰好是32字节的字符串。

### Q: 数据库连接失败

```
asyncpg.exceptions.ConnectionDoesNotExistError
```

**解决**:
1. 确认PostgreSQL服务已启动
2. 检查 `DATABASE_URL` 配置
3. 确认数据库已创建

### Q: 模型同步失败

```
ProviderConnectionError: Cannot connect to provider API
```

**解决**:
1. 检查接入点URL是否正确
2. 验证密钥是否有效
3. 检查网络连接

---

## 项目结构参考

```
src/aiops_agent_executor/
├── main.py                    # 应用入口
├── core/
│   ├── config.py              # 配置管理
│   ├── security.py            # 加密工具
│   └── logging.py             # 日志配置
├── db/
│   ├── models/                # SQLAlchemy模型
│   └── session.py             # 数据库会话
├── schemas/                   # Pydantic模型
├── services/                  # 业务逻辑层
├── api/v1/endpoints/          # API端点
└── utils/                     # 工具函数
```

---

## 下一步

1. 阅读 [spec.md](./spec.md) 了解完整需求
2. 阅读 [data-model.md](./data-model.md) 了解数据模型
3. 查看 [contracts/openapi.yaml](./contracts/openapi.yaml) 了解API规范
4. 执行 `/speckit.tasks` 生成实现任务列表
