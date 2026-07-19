# 水果商城 Agent 第 1–2 周基础能力 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个可本地运行、可自动化验证的多租户水果商城 Agent 基础工作台，覆盖成员权限、操作审计、人工审批、商家知识模型、逐行 CSV 导入和具备降级能力的模型网关。

**Architecture:** 使用 `apps/api` FastAPI 模块化单体和 `apps/web` Next.js 管理端组成 monorepo。PostgreSQL 同时采用显式 `tenant_id` 条件和 RLS 双重隔离；领域模块通过应用服务访问数据库，跨模块只依赖公开 Pydantic DTO/Protocol。所有外部副作用先生成不可变审批请求，首阶段不实现任何自动执行器。

**Tech Stack:** Python 3.12、FastAPI 0.139、Pydantic 2、SQLAlchemy 2 async、Alembic、PostgreSQL 18.4、pgvector 0.8.2、pytest、Next.js 16.2、TypeScript、Vitest、Playwright、Docker Compose。

## Global Constraints

- 后端必须固定为 FastAPI 0.139 和 Python 3.12；前端必须固定为 Next.js 16.2。
- 数据库必须使用 PostgreSQL 18.4 和 pgvector 0.8.2。
- 退款、赔付、改价、改库存、发布抖音内容统一设置 `requires_approval=True`，只能创建 `pending` 审批记录，不得直接修改业务表或调用外部系统。
- 每个租户业务查询必须显式包含 `tenant_id`，数据库 RLS 作为第二道隔离；跨租户访问返回 404，避免泄漏资源是否存在。
- 除 Alembic 自身元数据外，所有应用表必须包含 `created_at`、`updated_at`、`valid_until` 和 `audit_log`；`audit_log` 为 JSONB 摘要，完整事件另存 `audit_events`。
- 地址、电话等敏感字段进入日志或模型提示词前必须替换成 `[REDACTED]`。
- 商品、库存、价格使用 SQL 精确查询；FAQ、话术和产地故事使用 pgvector 语义检索。
- 库存、价格或物流时效过期时返回 `expired`，禁止生成推荐。
- 模型调用超时为 8 秒，失败后最多重试 2 次，再切换备用模型。
- 模型仅在事实错误率 `< 0.02` 且高风险召回率 `>= 0.95` 时合格；合格模型按预估成本升序选择。
- Agent 输出必须通过 Pydantic 校验，并包含 `suggestion_text`、`referenced_knowledge_ids`、`confidence_score`、`risk_level`。
- `ManualImportAdapter` 首版实现 CSV UTF-8/UTF-8 BOM 逐行校验；`DouyinShopAdapter` 仅提供 Mock，任何写方法均创建审批请求。
- 生产代码必须遵循 RED → GREEN → REFACTOR；每个行为先运行对应失败测试，再写最小实现。

---

## File Map

```text
.
├── .env.example
├── docker-compose.yml
├── Makefile
├── apps
│   ├── api
│   │   ├── alembic.ini
│   │   ├── migrations
│   │   │   ├── env.py
│   │   │   └── versions/0001_foundation.py
│   │   ├── pyproject.toml
│   │   ├── src/fruit_agent
│   │   │   ├── app.py
│   │   │   ├── config.py
│   │   │   ├── db.py
│   │   │   ├── logging.py
│   │   │   ├── common/{errors.py,models.py,redaction.py}
│   │   │   ├── identity/{models.py,schemas.py,service.py,router.py,dependencies.py}
│   │   │   ├── audit/{models.py,service.py,middleware.py}
│   │   │   ├── approvals/{models.py,schemas.py,service.py,router.py}
│   │   │   ├── knowledge/{models.py,schemas.py,repository.py,service.py,router.py}
│   │   │   ├── imports/{schemas.py,manual.py,router.py}
│   │   │   ├── commerce/{ports.py,mock_douyin.py}
│   │   │   └── model_gateway/{schemas.py,ports.py,redaction.py,router.py,service.py}
│   │   └── tests
│   │       ├── conftest.py
│   │       ├── integration/test_tenant_rls.py
│   │       └── unit/
│   └── web
│       ├── package.json
│       ├── app/{layout.tsx,page.tsx,members/page.tsx,knowledge/page.tsx,imports/page.tsx,approvals/page.tsx}
│       ├── components/{app-shell.tsx,csv-import-form.tsx}
│       ├── lib/{api.ts,types.ts}
│       └── tests/
└── docs
    ├── architecture.md
    └── runbook.md
```

## Task 1: Monorepo 与可复现开发环境

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/src/fruit_agent/app.py`
- Create: `apps/api/src/fruit_agent/config.py`
- Create: `apps/api/tests/unit/test_health.py`
- Create: `apps/web/package.json`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `Makefile`

**Interfaces:**
- Produces: `fruit_agent.app:create_app() -> FastAPI`
- Produces: `GET /health -> {"status":"ok"}`
- Produces: PostgreSQL DSN `DATABASE_URL` and test DSN `TEST_DATABASE_URL`

- [ ] **Step 1: 写健康检查失败测试**

```python
from fastapi.testclient import TestClient
from fruit_agent.app import create_app


def test_health_returns_ok() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试并确认因模块不存在而失败**

Run: `cd apps/api && python -m pytest tests/unit/test_health.py -q`

Expected: `ModuleNotFoundError: No module named 'fruit_agent'`

- [ ] **Step 3: 创建锁定运行时的后端项目**

```toml
[project]
name = "fruit-growth-agent-api"
version = "0.1.0"
requires-python = "==3.12.*"
dependencies = [
  "fastapi==0.139.*",
  "uvicorn[standard]>=0.35,<0.36",
  "pydantic>=2.11,<3",
  "pydantic-settings>=2.10,<3",
  "sqlalchemy[asyncio]>=2.0.41,<3",
  "psycopg[binary,pool]>=3.2.9,<4",
  "alembic>=1.16,<2",
  "pgvector>=0.4,<0.5",
  "python-multipart>=0.0.20,<0.1",
  "structlog>=25.4,<26",
  "httpx>=0.28,<0.29",
  "tenacity>=9.1,<10",
  "pyjwt[crypto]>=2.10,<3",
]

[project.optional-dependencies]
dev = ["pytest>=8.4,<9", "pytest-asyncio>=1.0,<2", "testcontainers[postgres]>=4.10,<5", "ruff>=0.12,<0.13", "mypy>=1.16,<2"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src"]
```

- [ ] **Step 4: 实现最小应用工厂**

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Fruit Growth Agent", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 5: 配置固定版本数据库容器**

```yaml
services:
  postgres:
    image: pgvector/pgvector:0.8.2-pg18
    environment:
      POSTGRES_DB: fruit_agent
      POSTGRES_USER: fruit_agent
      POSTGRES_PASSWORD: fruit_agent
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fruit_agent -d fruit_agent"]
      interval: 2s
      timeout: 3s
      retries: 20
```

- [ ] **Step 6: 创建 Next.js 16.2 包定义**

```json
{
  "name": "fruit-growth-agent-web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "lint": "eslint .",
    "test": "vitest run"
  },
  "dependencies": {
    "next": "16.2.x",
    "react": "19.x",
    "react-dom": "19.x"
  },
  "devDependencies": {
    "@testing-library/react": "^16.3.0",
    "@types/node": "^24.0.0",
    "@types/react": "^19.1.0",
    "eslint": "^9.0.0",
    "typescript": "^5.8.0",
    "vitest": "^3.2.0"
  }
}
```

- [ ] **Step 7: 验证健康检查通过并提交**

Run: `cd apps/api && python -m pytest tests/unit/test_health.py -q`

Expected: `1 passed`

Commit: `chore: scaffold FastAPI and Next.js workspace`

## Task 2: 数据库基类、迁移与租户 RLS

**Files:**
- Create: `apps/api/src/fruit_agent/db.py`
- Create: `apps/api/src/fruit_agent/common/models.py`
- Create: `apps/api/src/fruit_agent/identity/models.py`
- Create: `apps/api/migrations/env.py`
- Create: `apps/api/migrations/versions/0001_foundation.py`
- Create: `apps/api/tests/integration/test_tenant_rls.py`

**Interfaces:**
- Produces: `TenantOwnedMixin` with `tenant_id`, timestamps, `valid_until`, `audit_log`
- Produces: `tenant_session(session, tenant_id)` transaction context
- Produces: tables `tenants`, `users`, `memberships`

- [ ] **Step 1: 写跨租户不可见的集成测试**

```python
async def test_rls_hides_other_tenant_memberships(db_session, tenant_factory) -> None:
    tenant_a = await tenant_factory()
    tenant_b = await tenant_factory()
    await seed_membership(db_session, tenant_id=tenant_a.id, email="a@example.com")

    async with tenant_session(db_session, tenant_b.id):
        rows = (await db_session.scalars(
            select(Membership).where(Membership.tenant_id == tenant_b.id)
        )).all()

    assert rows == []
```

- [ ] **Step 2: 运行测试并确认 `tenant_session` 不存在**

Run: `cd apps/api && python -m pytest tests/integration/test_tenant_rls.py -q`

Expected: FAIL importing `tenant_session`

- [ ] **Step 3: 实现统一租户字段**

```python
class TenantOwnedMixin:
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    valid_until: Mapped[datetime | None] = mapped_column(nullable=True)
    audit_log: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
```

- [ ] **Step 4: 在事务内设置不可伪造的租户上下文**

```python
@asynccontextmanager
async def tenant_session(session: AsyncSession, tenant_id: UUID):
    async with session.begin():
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        yield session
```

- [ ] **Step 5: 迁移中启用扩展、RLS 和强制策略**

```python
op.execute("CREATE EXTENSION IF NOT EXISTS vector")
for table in ("memberships", "audit_events", "approval_requests", "merchant_knowledge", "product_skus", "model_call_logs"):
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY {table}_tenant_isolation ON {table}
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"""
    )
```

- [ ] **Step 6: 运行迁移和隔离测试**

Run: `cd apps/api && alembic upgrade head && python -m pytest tests/integration/test_tenant_rls.py -q`

Expected: `1 passed`

Commit: `feat: enforce tenant isolation with PostgreSQL RLS`

## Task 3: 身份认证与 RBAC

**Files:**
- Create: `apps/api/src/fruit_agent/identity/schemas.py`
- Create: `apps/api/src/fruit_agent/identity/service.py`
- Create: `apps/api/src/fruit_agent/identity/dependencies.py`
- Create: `apps/api/src/fruit_agent/identity/router.py`
- Create: `apps/api/tests/unit/test_rbac.py`
- Create: `apps/api/tests/integration/test_members_api.py`

**Interfaces:**
- Produces: roles `owner | operator | support | implementer`
- Produces: `TenantPrincipal(user_id, tenant_id, role)`
- Produces: `require_permissions(*permissions)`
- Produces: `GET/POST /api/v1/members`

- [ ] **Step 1: 写权限矩阵失败测试**

```python
@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        ("owner", "members:write", True),
        ("implementer", "members:write", True),
        ("operator", "members:write", False),
        ("support", "knowledge:read", True),
        ("support", "knowledge:write", False),
    ],
)
def test_role_permissions(role: Role, permission: str, allowed: bool) -> None:
    assert has_permission(role, permission) is allowed
```

- [ ] **Step 2: 运行测试并确认权限函数缺失**

Run: `cd apps/api && python -m pytest tests/unit/test_rbac.py -q`

Expected: FAIL importing `has_permission`

- [ ] **Step 3: 实现封闭权限矩阵**

```python
ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.owner: frozenset({"members:read", "members:write", "knowledge:read", "knowledge:write", "approval:decide", "audit:read"}),
    Role.implementer: frozenset({"members:read", "members:write", "knowledge:read", "knowledge:write", "imports:write", "audit:read"}),
    Role.operator: frozenset({"members:read", "knowledge:read", "knowledge:write", "imports:write", "approval:request"}),
    Role.support: frozenset({"knowledge:read", "approval:request"}),
}


def has_permission(role: Role, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS[role]
```

- [ ] **Step 4: JWT 只接受服务端签发的租户成员身份**

```python
async def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TenantPrincipal:
    claims = jwt.decode(credentials.credentials, settings.jwt_public_key, algorithms=["RS256"], audience="fruit-agent-api")
    claimed_tenant_id = UUID(claims["tenant_id"])
    async with tenant_session(session, claimed_tenant_id):
        membership = await session.scalar(
            select(Membership).where(
                Membership.tenant_id == claimed_tenant_id,
                Membership.user_id == UUID(claims["sub"]),
                Membership.status == "active",
            )
        )
    if membership is None:
        raise HTTPException(status_code=401, detail="invalid tenant membership")
    return TenantPrincipal(user_id=membership.user_id, tenant_id=membership.tenant_id, role=membership.role)
```

- [ ] **Step 5: 测试成员写入权限和跨租户 404**

Run: `cd apps/api && python -m pytest tests/unit/test_rbac.py tests/integration/test_members_api.py -q`

Expected: all tests pass

Commit: `feat: add tenant membership authentication and RBAC`

## Task 4: 审计日志、请求关联与敏感信息脱敏

**Files:**
- Create: `apps/api/src/fruit_agent/common/redaction.py`
- Create: `apps/api/src/fruit_agent/audit/models.py`
- Create: `apps/api/src/fruit_agent/audit/service.py`
- Create: `apps/api/src/fruit_agent/audit/middleware.py`
- Create: `apps/api/src/fruit_agent/logging.py`
- Create: `apps/api/tests/unit/test_redaction.py`
- Create: `apps/api/tests/integration/test_audit.py`

**Interfaces:**
- Produces: `redact(value: object) -> object`
- Produces: `AuditService.record(action, entity_type, entity_id, before, after)`
- Produces: response header `X-Request-ID`

- [ ] **Step 1: 写手机号和地址脱敏测试**

```python
def test_redact_replaces_sensitive_values_recursively() -> None:
    payload = {"phone": "13800138000", "profile": {"address": "上海市浦东新区", "name": "张三"}}
    assert redact(payload) == {
        "phone": "[REDACTED]",
        "profile": {"address": "[REDACTED]", "name": "张三"},
    }
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd apps/api && python -m pytest tests/unit/test_redaction.py -q`

Expected: FAIL importing `redact`

- [ ] **Step 3: 实现递归字段级脱敏**

```python
SENSITIVE_KEYS = {"phone", "mobile", "address", "shipping_address", "receiver_phone"}


def redact(value: object) -> object:
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if str(k).lower() in SENSITIVE_KEYS else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
```

- [ ] **Step 4: 审计事件只接受脱敏后的 before/after**

```python
event = AuditEvent(
    tenant_id=principal.tenant_id,
    actor_id=principal.user_id,
    request_id=request_id,
    action=action,
    entity_type=entity_type,
    entity_id=entity_id,
    before=redact(before),
    after=redact(after),
)
session.add(event)
```

- [ ] **Step 5: 验证成功和异常请求均带 request ID，写操作产生审计事件**

Run: `cd apps/api && python -m pytest tests/unit/test_redaction.py tests/integration/test_audit.py -q`

Expected: all tests pass and no phone/address appears in captured logs

Commit: `feat: add redacted immutable audit trail`

## Task 5: 人工审批安全边界

**Files:**
- Create: `apps/api/src/fruit_agent/approvals/models.py`
- Create: `apps/api/src/fruit_agent/approvals/schemas.py`
- Create: `apps/api/src/fruit_agent/approvals/service.py`
- Create: `apps/api/src/fruit_agent/approvals/router.py`
- Create: `apps/api/tests/unit/test_approval_policy.py`
- Create: `apps/api/tests/integration/test_approvals_api.py`

**Interfaces:**
- Produces: `RiskyAction = refund | compensate | change_price | change_inventory | publish_douyin`
- Produces: `ApprovalRequest(status="pending", requires_approval=True)`
- Produces: `POST /api/v1/approvals` and `POST /api/v1/approvals/{id}/decision`
- Does not produce: action executor

- [ ] **Step 1: 写高风险动作永远待审批的失败测试**

```python
@pytest.mark.parametrize("action", list(RiskyAction))
async def test_risky_action_only_creates_pending_request(action, approval_service) -> None:
    request = await approval_service.request(action=action, payload={"amount": 100})
    assert request.requires_approval is True
    assert request.status == ApprovalStatus.pending
```

- [ ] **Step 2: 运行测试并确认服务不存在**

Run: `cd apps/api && python -m pytest tests/unit/test_approval_policy.py -q`

Expected: FAIL importing `ApprovalService`

- [ ] **Step 3: 实现只创建审批记录的服务**

```python
async def request(self, *, tenant_id: UUID, actor_id: UUID, action: RiskyAction, payload: dict[str, object]) -> ApprovalRequest:
    item = ApprovalRequest(
        tenant_id=tenant_id,
        requested_by=actor_id,
        action=action,
        payload=redact(payload),
        requires_approval=True,
        status=ApprovalStatus.pending,
    )
    self.session.add(item)
    await self.session.flush()
    return item
```

- [ ] **Step 4: 决策只改变审批状态，不执行 payload**

```python
item = await session.scalar(
    select(ApprovalRequest).where(
        ApprovalRequest.tenant_id == principal.tenant_id,
        ApprovalRequest.id == approval_id,
        ApprovalRequest.status == ApprovalStatus.pending,
    )
)
if item is None:
    raise NotFoundError("approval request not found")
item.status = decision
item.decided_by = principal.user_id
item.decided_at = utcnow()
```

- [ ] **Step 5: 验证审批后库存、价格、退款表均无变化**

Run: `cd apps/api && python -m pytest tests/unit/test_approval_policy.py tests/integration/test_approvals_api.py -q`

Expected: all tests pass

Commit: `feat: enforce approval-only risky actions`

## Task 6: 商家知识与商品 SKU 精确事实模型

**Files:**
- Create: `apps/api/src/fruit_agent/knowledge/models.py`
- Create: `apps/api/src/fruit_agent/knowledge/schemas.py`
- Create: `apps/api/src/fruit_agent/knowledge/repository.py`
- Create: `apps/api/src/fruit_agent/knowledge/service.py`
- Create: `apps/api/src/fruit_agent/knowledge/router.py`
- Create: `apps/api/tests/unit/test_knowledge_freshness.py`
- Create: `apps/api/tests/integration/test_knowledge_queries.py`

**Interfaces:**
- Produces: `MerchantKnowledge`, `ProductSKU`
- Produces: `ExactFactResult(status="ok" | "expired" | "conflict")`
- Produces: `get_sku_exact(tenant_id, sku_code, now)`
- Produces: `search_semantic(tenant_id, query_embedding, knowledge_types)`

- [ ] **Step 1: 写过期 SKU 禁止推荐测试**

```python
async def test_expired_price_returns_expired_without_recommendation(service, expired_sku) -> None:
    result = await service.get_recommendable_sku(
        tenant_id=expired_sku.tenant_id, sku_code=expired_sku.sku_code
    )
    assert result.status == "expired"
    assert result.sku is None
```

- [ ] **Step 2: 运行测试并确认服务缺失**

Run: `cd apps/api && python -m pytest tests/unit/test_knowledge_freshness.py -q`

Expected: FAIL importing `KnowledgeService`

- [ ] **Step 3: 实现显式租户精确查询和新鲜度判断**

```python
sku = await self.session.scalar(
    select(ProductSKU).where(
        ProductSKU.tenant_id == tenant_id,
        ProductSKU.sku_code == sku_code,
    )
)
if sku is None:
    return ExactFactResult(status="not_found", sku=None)
if sku.valid_until is None or sku.valid_until <= self.clock.now():
    return ExactFactResult(status="expired", sku=None)
return ExactFactResult(status="ok", sku=ProductSKURead.model_validate(sku))
```

- [ ] **Step 4: 语义检索仅允许叙事类知识并显式过滤租户**

```python
SEMANTIC_TYPES = {KnowledgeType.faq, KnowledgeType.talking_point, KnowledgeType.origin_story}
stmt = (
    select(MerchantKnowledge)
    .where(
        MerchantKnowledge.tenant_id == tenant_id,
        MerchantKnowledge.knowledge_type.in_(SEMANTIC_TYPES & set(knowledge_types)),
        MerchantKnowledge.review_status == ReviewStatus.approved,
        MerchantKnowledge.valid_until > now,
    )
    .order_by(MerchantKnowledge.embedding.cosine_distance(query_embedding))
    .limit(limit)
)
```

- [ ] **Step 5: 冲突事实返回来源列表并要求转人工**

```python
return ExactFactResult(
    status="conflict",
    sku=None,
    conflict_source_ids=[row.source_id for row in conflicting_rows],
    requires_human=True,
)
```

- [ ] **Step 6: 验证精确查询、过期、冲突和语义类型限制**

Run: `cd apps/api && python -m pytest tests/unit/test_knowledge_freshness.py tests/integration/test_knowledge_queries.py -q`

Expected: all tests pass

Commit: `feat: add tenant-safe merchant knowledge and SKU facts`

## Task 7: ManualImportAdapter 逐行 CSV 导入

**Files:**
- Create: `apps/api/src/fruit_agent/imports/schemas.py`
- Create: `apps/api/src/fruit_agent/imports/manual.py`
- Create: `apps/api/src/fruit_agent/imports/router.py`
- Create: `apps/api/tests/fixtures/products_mixed.csv`
- Create: `apps/api/tests/unit/test_csv_import.py`
- Create: `apps/api/tests/integration/test_import_api.py`

**Interfaces:**
- Produces: `ImportResult(total_rows, imported_rows, failed_rows, errors)`
- Produces: `RowError(row_number, field, reason, suggestion)`
- Produces: `POST /api/v1/imports/products`

- [ ] **Step 1: 写混合有效/无效行导入测试**

```python
async def test_csv_import_reports_each_invalid_row(adapter, tenant_id) -> None:
    result = await adapter.import_products(
        tenant_id=tenant_id,
        content=b"sku_code,name,price,inventory,valid_until\nA1,\xe8\x8b\xb9\xe6\x9e\x9c,29.90,10,2030-01-01T00:00:00Z\nA2,\xe6\xa2\xa8,-1,x,2020-01-01T00:00:00Z\n",
    )
    assert result.total_rows == 2
    assert result.imported_rows == 1
    assert result.failed_rows == 1
    assert {(e.row_number, e.field) for e in result.errors} == {(3, "price"), (3, "inventory"), (3, "valid_until")}
```

- [ ] **Step 2: 运行测试并确认适配器缺失**

Run: `cd apps/api && python -m pytest tests/unit/test_csv_import.py -q`

Expected: FAIL importing `ManualImportAdapter`

- [ ] **Step 3: 定义严格行模型**

```python
class ProductImportRow(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    sku_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    inventory: int = Field(ge=0)
    valid_until: AwareDatetime

    @field_validator("valid_until")
    @classmethod
    def require_future_validity(cls, value: datetime) -> datetime:
        if value <= datetime.now(UTC):
            raise ValueError("valid_until must be in the future")
        return value
```

- [ ] **Step 4: 实现 BOM、表头和每行错误收集**

```python
text_content = content.decode("utf-8-sig")
reader = csv.DictReader(io.StringIO(text_content))
if set(reader.fieldnames or []) != REQUIRED_HEADERS:
    raise ImportFormatError("CSV headers must exactly match the product template")
for row_number, raw in enumerate(reader, start=2):
    try:
        valid.append(ProductImportRow.model_validate(raw))
    except ValidationError as exc:
        errors.extend(to_row_errors(row_number, exc))
```

- [ ] **Step 5: 只写有效行，每条写入都显式携带 tenant_id**

```python
for row in valid:
    self.session.add(
        ProductSKU(tenant_id=tenant_id, **row.model_dump(), audit_log=[{"event": "csv_import"}])
    )
await self.session.flush()
```

- [ ] **Step 6: 验证空文件、错误编码、重复 SKU、非法日期和跨租户隔离**

Run: `cd apps/api && python -m pytest tests/unit/test_csv_import.py tests/integration/test_import_api.py -q`

Expected: all tests pass

Commit: `feat: add row-validated manual CSV imports`

## Task 8: CommerceAdapter 与只读抖店 Mock

**Files:**
- Create: `apps/api/src/fruit_agent/commerce/ports.py`
- Create: `apps/api/src/fruit_agent/commerce/mock_douyin.py`
- Create: `apps/api/tests/unit/test_douyin_mock.py`

**Interfaces:**
- Produces: `CommerceAdapter` read protocols
- Produces: `DouyinShopAdapterMock`
- Risky writes delegate to `ApprovalService.request`

- [ ] **Step 1: 写 Mock 改库存不执行的失败测试**

```python
async def test_change_inventory_creates_approval_only(mock_adapter, approval_repo) -> None:
    result = await mock_adapter.change_inventory(tenant_id=TENANT_ID, sku_code="A1", quantity=5)
    assert result.status == "pending"
    assert result.requires_approval is True
    assert await approval_repo.count(TENANT_ID) == 1
    assert mock_adapter.executed_actions == []
```

- [ ] **Step 2: 运行测试并确认 Mock 缺失**

Run: `cd apps/api && python -m pytest tests/unit/test_douyin_mock.py -q`

Expected: FAIL importing `DouyinShopAdapterMock`

- [ ] **Step 3: 定义端口并实现审批委托**

```python
class CommerceAdapter(Protocol):
    async def get_product(self, *, tenant_id: UUID, sku_code: str) -> ProductSKURead | None: ...
    async def change_inventory(self, *, tenant_id: UUID, sku_code: str, quantity: int) -> ApprovalRead: ...


async def change_inventory(self, *, tenant_id: UUID, sku_code: str, quantity: int) -> ApprovalRead:
    return await self.approvals.request(
        tenant_id=tenant_id,
        actor_id=self.actor_id,
        action=RiskyAction.change_inventory,
        payload={"sku_code": sku_code, "quantity": quantity},
    )
```

- [ ] **Step 4: 验证所有五类高风险写方法**

Run: `cd apps/api && python -m pytest tests/unit/test_douyin_mock.py -q`

Expected: all tests pass

Commit: `feat: define commerce port and approval-only Douyin mock`

## Task 9: 模型网关、供应商选择、重试与降级

**Files:**
- Create: `apps/api/src/fruit_agent/model_gateway/schemas.py`
- Create: `apps/api/src/fruit_agent/model_gateway/ports.py`
- Create: `apps/api/src/fruit_agent/model_gateway/redaction.py`
- Create: `apps/api/src/fruit_agent/model_gateway/service.py`
- Create: `apps/api/src/fruit_agent/model_gateway/router.py`
- Create: `apps/api/tests/unit/test_model_selection.py`
- Create: `apps/api/tests/unit/test_model_failover.py`
- Create: `apps/api/tests/integration/test_model_call_audit.py`

**Interfaces:**
- Produces: `AgentSuggestion`
- Produces: `ModelProvider.complete(prompt, timeout_seconds) -> ProviderResponse`
- Produces: `ModelGateway.suggest(tenant_id, prompt, knowledge_ids)`
- Produces: `POST /api/v1/model-gateway/suggestions`

- [ ] **Step 1: 写最低成本合格模型选择测试**

```python
def test_selects_lowest_cost_qualified_model() -> None:
    candidates = [
        model("qwen-fast", cost=0.001, fact_error_rate=0.018, risk_recall=0.96),
        model("glm-cheap", cost=0.0005, fact_error_rate=0.025, risk_recall=0.97),
        model("qwen-pro", cost=0.003, fact_error_rate=0.010, risk_recall=0.99),
    ]
    assert select_model(candidates).name == "qwen-fast"
```

- [ ] **Step 2: 写 8 秒超时、2 次重试后备用模型降级测试**

```python
async def test_retries_twice_then_falls_back(primary, fallback, gateway) -> None:
    primary.complete.side_effect = TimeoutError
    fallback.complete.return_value = valid_provider_response()
    result = await gateway.suggest(TENANT_ID, {"message": "推荐苹果"}, [])
    assert primary.complete.await_count == 3
    assert fallback.complete.await_count == 1
    assert result.degraded is True
```

- [ ] **Step 3: 运行两项测试并确认失败原因正确**

Run: `cd apps/api && python -m pytest tests/unit/test_model_selection.py tests/unit/test_model_failover.py -q`

Expected: FAIL importing gateway functions

- [ ] **Step 4: 定义强类型输出**

```python
class AgentSuggestion(BaseModel):
    suggestion_text: str = Field(min_length=1, max_length=4000)
    referenced_knowledge_ids: list[UUID]
    confidence_score: float = Field(ge=0, le=1)
    risk_level: Literal["low", "medium", "high", "critical"]
```

- [ ] **Step 5: 实现合格过滤与成本排序**

```python
def select_model(candidates: Sequence[ModelProfile]) -> ModelProfile:
    qualified = [m for m in candidates if m.fact_error_rate < 0.02 and m.high_risk_recall >= 0.95]
    if not qualified:
        raise NoQualifiedModelError("no model satisfies quality thresholds")
    return min(qualified, key=lambda m: m.estimated_cost_per_1k_tokens)
```

- [ ] **Step 6: 实现每供应商 8 秒超时和总计 3 次尝试**

```python
async for attempt in AsyncRetrying(
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((TimeoutError, ProviderUnavailableError)),
    reraise=True,
):
    with attempt:
        async with asyncio.timeout(8):
            response = await provider.complete(redacted_prompt)
```

- [ ] **Step 7: 输出前验证引用 ID 属于当前租户**

```python
known_ids = set(await self.session.scalars(
    select(MerchantKnowledge.id).where(
        MerchantKnowledge.tenant_id == tenant_id,
        MerchantKnowledge.id.in_(suggestion.referenced_knowledge_ids),
    )
))
if known_ids != set(suggestion.referenced_knowledge_ids):
    raise InvalidModelOutputError("model referenced unknown tenant knowledge")
```

- [ ] **Step 8: 对所有输入先调用 `redact`，调用日志记录供应商、延迟、成本、重试和降级，不记录原始敏感 prompt**

Run: `cd apps/api && python -m pytest tests/unit/test_model_selection.py tests/unit/test_model_failover.py tests/integration/test_model_call_audit.py -q`

Expected: all tests pass

Commit: `feat: add quality-gated model gateway with failover`

## Task 10: 统一异常、结构化日志与 API 装配

**Files:**
- Create: `apps/api/src/fruit_agent/common/errors.py`
- Modify: `apps/api/src/fruit_agent/app.py`
- Modify: all module routers
- Create: `apps/api/tests/integration/test_error_contract.py`

**Interfaces:**
- Produces: `{"error":{"code","message","request_id","details"}}`
- Produces: JSON logs with `request_id`, `tenant_id`, `actor_id`, `operation`, `duration_ms`, `outcome`

- [ ] **Step 1: 写验证错误和内部错误契约测试**

```python
def test_validation_error_has_stable_contract(client) -> None:
    response = client.post("/api/v1/imports/products", files={})
    assert response.status_code == 422
    assert set(response.json()["error"]) == {"code", "message", "request_id", "details"}
```

- [ ] **Step 2: 运行测试并确认默认 FastAPI 422 格式不匹配**

Run: `cd apps/api && python -m pytest tests/integration/test_error_contract.py -q`

Expected: assertion failure because response contains `detail`

- [ ] **Step 3: 注册领域异常、校验异常和兜底处理器**

```python
@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {
            "code": "validation_error",
            "message": "request validation failed",
            "request_id": request.state.request_id,
            "details": redact(exc.errors()),
        }},
    )
```

- [ ] **Step 4: 装配所有路由并验证 OpenAPI**

Run: `cd apps/api && python -m pytest tests -q`

Expected: complete API suite passes with no warnings

Commit: `feat: standardize API errors and structured logging`

## Task 11: Next.js 最小管理工作台

**Files:**
- Create: `apps/web/app/layout.tsx`
- Create: `apps/web/app/page.tsx`
- Create: `apps/web/app/members/page.tsx`
- Create: `apps/web/app/knowledge/page.tsx`
- Create: `apps/web/app/imports/page.tsx`
- Create: `apps/web/app/approvals/page.tsx`
- Create: `apps/web/components/app-shell.tsx`
- Create: `apps/web/components/csv-import-form.tsx`
- Create: `apps/web/lib/api.ts`
- Create: `apps/web/lib/types.ts`
- Create: `apps/web/tests/csv-import-form.test.tsx`

**Interfaces:**
- Consumes: members, knowledge, imports and approvals REST endpoints
- Produces: import summary with per-row errors
- Produces: approvals view with explicit `pending/approved/rejected`; no “执行” button

- [ ] **Step 1: 写逐行错误展示失败测试**

```tsx
it("renders every CSV row error", async () => {
  server.use(importHandler({
    total_rows: 2,
    imported_rows: 1,
    failed_rows: 1,
    errors: [
      { row_number: 3, field: "price", reason: "must be greater than 0", suggestion: "输入正数价格" },
      { row_number: 3, field: "inventory", reason: "must be an integer", suggestion: "输入整数库存" }
    ]
  }));
  render(<CsvImportForm />);
  await userEvent.upload(screen.getByLabelText("选择 CSV"), csvFile);
  await userEvent.click(screen.getByRole("button", { name: "校验并导入" }));
  expect(await screen.findAllByTestId("row-error")).toHaveLength(2);
});
```

- [ ] **Step 2: 运行测试并确认组件缺失**

Run: `cd apps/web && npm test -- csv-import-form.test.tsx`

Expected: FAIL resolving `CsvImportForm`

- [ ] **Step 3: 实现带租户请求头的统一客户端**

```ts
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
    ...init,
    headers: {
      ...init?.headers,
      Authorization: `Bearer ${await getAccessToken()}`,
      "X-Request-ID": crypto.randomUUID(),
    },
    cache: "no-store",
  });
  if (!response.ok) throw await response.json();
  return response.json() as Promise<T>;
}
```

- [ ] **Step 4: 实现导入摘要、成员表、知识新鲜度标签和审批状态页面**

审批页只提供“批准/拒绝”决策，不出现“执行退款”“发布”“修改库存”等按钮；成功决策后文案明确显示“已记录决策，未执行外部动作”。

- [ ] **Step 5: 运行前端测试、Lint 和生产构建**

Run: `cd apps/web && npm test && npm run lint && npm run build`

Expected: all tests pass, lint clean, Next.js build succeeds

Commit: `feat: add foundation management workspace`

## Task 12: 安全回归、文档与阶段验收

**Files:**
- Create: `apps/api/tests/security/test_cross_tenant_matrix.py`
- Create: `apps/api/tests/security/test_prompt_redaction.py`
- Create: `apps/api/tests/security/test_risky_actions.py`
- Create: `apps/api/tests/integration/test_foundation_flow.py`
- Create: `docs/architecture.md`
- Create: `docs/runbook.md`
- Modify: `README.md`

**Interfaces:**
- Produces: one-command local startup and verification
- Produces: evidence for every week 1–2 acceptance rule

- [ ] **Step 1: 写端到端基础流程测试**

```python
async def test_foundation_flow(client, owner_token, csv_file) -> None:
    member = await create_member(client, owner_token, role="operator")
    imported = await upload_products(client, owner_token, csv_file)
    suggestion = await request_suggestion(client, owner_token, "推荐苹果")
    approval = await request_inventory_change(client, owner_token, "A1", 8)

    assert member["role"] == "operator"
    assert imported["failed_rows"] == 0
    assert suggestion["referenced_knowledge_ids"]
    assert approval == {"status": "pending", "requires_approval": True}
```

- [ ] **Step 2: 运行测试并确认尚未满足的装配问题**

Run: `cd apps/api && python -m pytest tests/integration/test_foundation_flow.py -q`

Expected: FAIL until all routes and fixtures are connected

- [ ] **Step 3: 只修复装配缺口，不新增领域能力**

将应用工厂、测试容器、种子数据和 Mock 模型供应商连接到完整流程；不得在此步骤新增第三方 OAuth、真实退款、真实改价或真实发布逻辑。

- [ ] **Step 4: 运行完整验证矩阵**

Run:

```text
docker compose config
cd apps/api && ruff check . && mypy src && python -m pytest -q
cd apps/web && npm test && npm run lint && npm run build
```

Expected:

```text
Docker Compose configuration valid
Ruff: All checks passed
Mypy: Success: no issues found
Pytest: all tests passed
Vitest: all tests passed
ESLint: no errors or warnings
Next.js: production build completed
```

- [ ] **Step 5: 编写运行手册和架构决策**

`docs/runbook.md` 必须包含：环境变量、迁移、首次租户创建、CSV 模板、备份恢复、模型供应商故障、审计查询和租户数据导出/删除流程。

`docs/architecture.md` 必须包含：模块边界、RLS 请求流程、审批状态机、精确/语义检索分流、模型选择与降级序列，以及明确的“不在第 1–2 周范围”列表。

- [ ] **Step 6: 最终提交**

Commit: `docs: add foundation architecture and operations runbook`

## Acceptance Checklist

- [ ] 两个租户使用相同资源 ID 探测时，任何 API 和数据库查询均无法读写对方数据。
- [ ] 四种角色的权限矩阵由单元测试和 API 测试共同覆盖。
- [ ] 每个写操作生成带 request ID、actor、tenant、before/after 的脱敏审计事件。
- [ ] 五类高风险动作只能生成 `requires_approval=True`、`pending` 的审批记录。
- [ ] 除 Alembic 元数据外，所有应用表包含 `created_at`、`updated_at`、`valid_until`、`audit_log`。
- [ ] 结构化事实只走精确 SQL，语义检索只覆盖 FAQ、话术和产地故事。
- [ ] 过期与冲突事实不会进入推荐，分别返回 `expired` 和 `conflict`。
- [ ] CSV 无效行逐条返回行号、字段、原因和修复建议；有效行不受无效行污染。
- [ ] 地址和电话不会出现在模型 prompt、应用日志、模型调用日志或审计 before/after 中。
- [ ] 模型网关满足质量门槛、最低成本选择、8 秒超时、2 次重试和备用模型降级。
- [ ] Agent 建议始终满足统一 Pydantic JSON 契约，且引用均属于当前租户。
- [ ] 抖店适配器仅为 Mock，不包含 OAuth 或真实外部写调用。
- [ ] 后端全套测试、类型检查和 lint 通过；前端测试、lint 和生产构建通过。

## Explicitly Out of Scope

- 飞鸽消息自动读取或发送。
- 抖店 OAuth、回调验签、正式订单/售后 API。
- 退款、赔付、改价、改库存或抖音发布的真实执行器。
- 客服副驾完整业务流程、短视频 Agent、增长看板和复杂计费。
- Excel 二进制 `.xlsx` 解析；本阶段 UI 可提示用户另存为 UTF-8 CSV。
