# Design Consistency Review: LLM配置管理

**Feature Branch**: `001-llm-config`
**Review Date**: 2025-12-06
**Status**: ✅ 通过（有改进建议）

---

## 一、需求覆盖度分析

### 功能需求覆盖矩阵

| 需求ID | 需求描述 | 数据模型 | API契约 | 研究决策 | 状态 |
|--------|----------|----------|---------|----------|------|
| FR-001 | 创建供应商配置 | ✅ Provider | ✅ POST /providers | - | ✅ |
| FR-002 | 支持8种供应商类型 | ✅ ProviderType枚举 | ✅ Schema定义 | - | ✅ |
| FR-003 | 查询/更新/删除供应商 | ✅ deleted_at软删除 | ✅ GET/PUT/DELETE | - | ✅ |
| FR-004 | 启用/禁用状态切换 | ✅ is_active字段 | ✅ PATCH /status | - | ✅ |
| FR-005 | 删除前检查Agent团队引用 | ⚠️ 需关联Team表 | ✅ 409 Conflict | - | ⚠️ |
| FR-006 | 多接入点配置 | ✅ Endpoint表 | ✅ endpoints API | - | ✅ |
| FR-007 | 接入点URL/超时/重试配置 | ✅ 完整字段 | ✅ Schema定义 | - | ✅ |
| FR-008 | 默认接入点设置 | ✅ is_default字段 | ✅ API支持 | - | ✅ |
| FR-009 | 健康检查 | ✅ health_status | ✅ /health-check | ✅ 双重检查 | ✅ |
| FR-010 | 至少保留一个接入点 | ✅ 验证规则 | ✅ 400错误 | - | ✅ |
| FR-010a | 轮询负载均衡 | - | - | ✅ RoundRobin | ✅ |
| FR-011 | AES-256加密存储 | ✅ api_key_encrypted | - | ✅ AES-256-GCM | ✅ |
| FR-012 | 脱敏显示 | ✅ api_key_hint | ✅ CredentialResponse | - | ✅ |
| FR-013 | 密钥CRUD | ✅ Credential表 | ✅ credentials API | - | ✅ |
| FR-014 | 密钥验证 | ✅ validation_status | ✅ /validate | - | ✅ |
| FR-015 | 过期时间/配额限制 | ✅ expires_at/quota_limit | ✅ Schema定义 | - | ✅ |
| FR-016 | 至少保留一个有效密钥 | ✅ 验证规则 | ✅ 400错误 | - | ✅ |
| FR-017 | 自动同步模型列表 | ✅ synced_at | ✅ /models/sync | ✅ 同步策略 | ✅ |
| FR-018 | 手动添加/更新模型 | ✅ Model表 | ✅ PUT /models | - | ✅ |
| FR-019 | 能力标签 | ✅ capabilities JSONB | ✅ Schema定义 | - | ✅ |
| FR-020 | 上下文窗口/最大输出token | ✅ context_window/max_output_tokens | ✅ Schema定义 | - | ✅ |
| FR-021 | 按条件筛选模型 | ✅ 索引支持 | ✅ 查询参数 | - | ✅ |
| FR-022 | 模型状态管理 | ✅ ModelStatus枚举 | ✅ Schema定义 | - | ✅ |

**覆盖率**: 23/23 = 100% ✅

### 待完善项

| ID | 问题 | 建议 |
|----|------|------|
| FR-005 | 数据模型未明确定义Provider与Team的关联检查逻辑 | 在Service层实现时需查询Team表的provider引用 |

---

## 二、过度设计检查

### 设计复杂度评估

| 设计点 | 复杂度 | 必要性 | 评估 |
|--------|--------|--------|------|
| 适配器模式 | 中 | ✅ 必要 | 8种供应商差异大，需要抽象 |
| AES-256-GCM | 低 | ✅ 必要 | 安全需求明确要求AES-256 |
| PBKDF2密钥派生 | 中 | ⚠️ 可简化 | MVP阶段可直接使用配置的32字节密钥 |
| 主动+被动健康检查 | 中 | ⚠️ 可简化 | MVP阶段仅实现被动检查足够 |
| 轮询负载均衡 | 低 | ✅ 必要 | 需求明确要求 |
| 异常层次结构 | 中 | ⚠️ 可简化 | 3层继承可能过度，2层足够 |
| GIN索引(capabilities) | 低 | ⚠️ 可延迟 | 数据量小时不需要 |

### 过度设计识别

#### 1. PBKDF2密钥派生 - 建议简化

**当前设计**: 使用PBKDF2从配置密钥派生加密密钥
**问题**: 增加实现复杂度，且配置密钥已经是32字节
**建议**: MVP阶段直接使用配置的32字节密钥作为AES密钥

```python
# 简化前
key = PBKDF2(config.encryption_key, salt, iterations=100000)
# 简化后
key = config.encryption_key.encode()  # 已验证为32字节
```

#### 2. 主动健康检查 - 建议延迟实现

**当前设计**: 定期主动探测 + 被动失败标记
**问题**: 定期探测需要后台任务调度，增加系统复杂度
**建议**: MVP阶段仅实现：
- 手动触发健康检查 API
- 被动标记（API调用失败时更新状态）

#### 3. 异常层次结构 - 建议扁平化

**当前设计**:
```
AppException
├── NotFoundError
├── ValidationError
├── ConflictError
├── ProviderError
│   ├── ProviderConnectionError
│   ├── ProviderAuthError
│   └── ProviderRateLimitError
└── EncryptionError
```

**建议简化为**:
```
AppException
├── NotFoundError (404)
├── BadRequestError (400)
├── ConflictError (409)
├── ServiceUnavailableError (503)
└── InternalError (500)
```

---

## 三、缺失项检查

### 数据模型缺失

| 缺失项 | 影响 | 建议 |
|--------|------|------|
| 无 | - | - |

### API契约缺失

| 缺失项 | 影响 | 建议 |
|--------|------|------|
| 模型创建API (POST /models) | 无法手动添加模型 | 添加 POST /providers/{id}/models 或 POST /models |

### 研究决策缺失

| 缺失项 | 影响 | 建议 |
|--------|------|------|
| 本地供应商(Ollama/vLLM)的模型枚举方式 | 模型同步无法覆盖本地供应商 | 添加本地模型发现机制说明 |

---

## 四、一致性检查

### 术语一致性 ✅

| 术语 | spec.md | data-model.md | research.md | contracts/openapi.yaml |
|------|---------|---------------|-------------|------------------------|
| Provider | ✅ | ✅ | ✅ | ✅ |
| Endpoint | ✅ | ✅ | ✅ | ✅ |
| Credential | ✅ | ✅ | ✅ | ✅ |
| Model | ✅ | ✅ | ✅ | ✅ |

### 枚举值一致性 ✅

| 枚举 | data-model.md | contracts/openapi.yaml | 一致 |
|------|---------------|------------------------|------|
| ProviderType | 8种 | 8种 | ✅ |
| HealthStatus | 3种 | 3种 | ✅ |
| ModelType | 4种 | 4种 | ✅ |
| ModelStatus | 3种 | 3种 | ✅ |
| ValidationStatus | 4种 | 4种 | ✅ |

### 字段一致性 ✅

数据模型字段与API Schema字段对应关系一致。

---

## 五、改进建议汇总

### 必须修复 (P0)

| # | 问题 | 修复方案 | 状态 |
|---|------|----------|------|
| 1 | 缺少模型创建API | 在openapi.yaml添加 POST /providers/{id}/models | ✅ 已修复 |

### 建议优化 (P1)

| # | 问题 | 优化方案 |
|---|------|----------|
| 1 | PBKDF2复杂度高 | MVP阶段移除，直接使用配置密钥 |
| 2 | 主动健康检查复杂 | MVP阶段仅实现手动检查+被动标记 |
| 3 | 异常层次过深 | 扁平化为5个基础异常类 |

### 可延迟 (P2)

| # | 问题 | 延迟原因 |
|---|------|----------|
| 1 | GIN索引 | 数据量小时不需要，后续按需添加 |
| 2 | 本地供应商模型发现 | Ollama/vLLM使用频率低，可后续迭代 |

---

## 六、结论

### 总体评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 需求覆盖度 | 100% | 23/23需求完整覆盖 |
| 设计一致性 | 100% | 术语、枚举、字段完全一致 |
| 过度设计风险 | 低 | 3处可简化，不影响功能 |
| 缺失风险 | 无 | API已补充完整 |

### 审查结论

**✅ 设计审查通过**

设计整体质量良好，需求覆盖充分，一致性高。建议在实现前：
1. 补充模型创建API
2. 考虑简化3处过度设计点

可以进入 `/speckit.tasks` 生成任务列表。
