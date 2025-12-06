# Research: LLM配置管理

**Feature Branch**: `001-llm-config`
**Created**: 2025-12-06

## 1. 供应商API集成模式

### Decision
采用适配器模式(Adapter Pattern)统一不同供应商的API接口，每个供应商实现独立的Adapter类。

### Rationale
- 各供应商API差异较大（认证方式、端点路径、响应格式）
- 适配器模式允许独立扩展新供应商而不修改核心代码
- 便于单独测试和mock每个供应商

### Alternatives Considered
- **直接调用**: 代码耦合度高，难以维护
- **策略模式**: 适用于算法切换，但供应商差异超出算法范畴

---

## 2. 密钥加密方案

### Decision
使用AES-256-GCM加密模式，密钥派生使用PBKDF2。

### Rationale
- AES-256是业界标准对称加密算法
- GCM模式提供认证加密(AEAD)，防止篡改
- PBKDF2密钥派生增加暴力破解难度
- Python cryptography库原生支持

### Alternatives Considered
- **AES-256-CBC**: 不提供完整性验证
- **RSA非对称加密**: 密钥管理复杂，性能较差
- **HashiCorp Vault**: 引入外部依赖，MVP阶段过于复杂

### Implementation Notes
```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
# 使用12字节nonce，16字节tag
```

---

## 3. 轮询负载均衡实现

### Decision
使用基于索引的轮询(Round-Robin)，配合健康状态过滤。

### Rationale
- 实现简单，分配均匀
- 健康检查过滤确保只使用可用接入点
- 无需维护复杂的权重或连接计数

### Alternatives Considered
- **加权轮询**: 当前场景无差异化需求
- **最少连接**: 需要维护连接状态，复杂度高
- **随机选择**: 分布不够均匀

### Implementation Notes
```python
class RoundRobinLoadBalancer:
    def __init__(self):
        self._index = 0
        self._lock = asyncio.Lock()

    async def get_next(self, healthy_endpoints: list) -> Endpoint:
        async with self._lock:
            endpoint = healthy_endpoints[self._index % len(healthy_endpoints)]
            self._index += 1
            return endpoint
```

---

## 4. 健康检查策略

### Decision
采用主动+被动双重健康检查机制。

### Rationale
- 主动检查: 定期(可配置间隔)向接入点发送探测请求
- 被动检查: 实际请求失败时标记为unhealthy
- 两者结合确保及时发现和恢复

### Alternatives Considered
- **仅主动检查**: 实际故障响应延迟
- **仅被动检查**: 可能导致用户请求失败
- **外部监控系统**: MVP阶段引入外部依赖不必要

### Health Status Definitions
| 状态 | 条件 |
|------|------|
| healthy | 最近3次探测成功，延迟<阈值 |
| degraded | 最近3次探测成功，但延迟>阈值 |
| unhealthy | 最近3次探测失败超过1次 |

---

## 5. 模型同步机制

### Decision
采用按需同步+手动触发方式，不使用后台定时任务。

### Rationale
- 避免不必要的API调用消耗配额
- 管理员可控同步时机
- MVP阶段简化实现

### Alternatives Considered
- **定时自动同步**: 增加系统复杂度，可能浪费API配额
- **Webhook通知**: 多数供应商不支持模型变更通知

### Sync Strategy
1. 调用供应商模型列表API
2. 对比本地数据库记录
3. 新模型: INSERT
4. 已有模型: UPDATE (更新能力、定价等)
5. 已下线模型: 标记deprecated (不删除)

---

## 6. 数据库事务策略

### Decision
使用SQLAlchemy异步会话，每个API请求一个事务。

### Rationale
- FastAPI + SQLAlchemy async是标准组合
- 请求级事务确保数据一致性
- 依赖注入模式便于测试

### Implementation Pattern
```python
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

---

## 7. 供应商SDK集成

### Decision
使用langchain生态的供应商集成包作为主要SDK。

### Rationale
- langchain-openai, langchain-anthropic已在依赖中
- 统一的API抽象
- 活跃的社区维护

### Supported Providers

| 供应商 | SDK | 模型同步支持 |
|--------|-----|-------------|
| OpenAI | langchain-openai | ✅ API支持 |
| Anthropic | langchain-anthropic | ✅ API支持 |
| AWS Bedrock | boto3 + langchain | ✅ API支持 |
| Azure OpenAI | langchain-openai | ✅ API支持 |
| 阿里云通义 | dashscope | ✅ API支持 |
| 百度文心 | qianfan | ⚠️ 部分支持 |
| Ollama | langchain-community | ❌ 本地枚举 |
| vLLM | langchain-community | ❌ 本地枚举 |

---

## 8. 错误处理策略

### Decision
使用自定义异常类，统一错误响应格式。

### Rationale
- 便于区分业务错误和系统错误
- 统一的错误响应便于前端处理
- 可扩展的错误码体系

### Exception Hierarchy
```
AppException (base)
├── NotFoundError (404)
├── ValidationError (400)
├── ConflictError (409)
├── ProviderError (503)
│   ├── ProviderConnectionError
│   ├── ProviderAuthError
│   └── ProviderRateLimitError
└── EncryptionError (500)
```

---

## Summary

所有技术决策已确定，无NEEDS CLARIFICATION遗留。准备进入Phase 1设计阶段。
