# 完整功能演示实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 建立一套真实数据库驱动、可重复初始化、仅限开发环境登录，并能展示当前全部产品模块的本地演示系统。

**架构：** 后端增加隔离的 `demo` 模块，负责固定演示标识、幂等数据初始化和短期 RS256 演示会话；前端通过显式演示入口申请会话，并继续使用现有真实 API。所有演示能力由后端 `DEMO_MODE` 和前端 `NEXT_PUBLIC_DEMO_MODE` 双重开关控制，默认关闭且在非开发环境中失败关闭。

**技术栈：** Python 3.12、FastAPI 0.139、SQLAlchemy 2、PostgreSQL 18/pgvector、PyJWT/cryptography、Next.js 16.2、React 19、TypeScript、Pytest、Vitest。

## 全局约束

- 演示数据只能写入固定的 `果序生鲜（华东）` 演示租户，禁止修改其他租户。
- `ENVIRONMENT=development` 且 `DEMO_MODE=true` 时，后端演示会话才可用。
- `NEXT_PUBLIC_DEMO_MODE=true` 时，前端演示入口才可见。
- 私钥只保存在本地并被 Git 忽略；前端不得嵌入私钥、永久令牌或密码。
- 令牌使用 RS256，最长有效期 30 分钟，只允许 4 个固定演示角色。
- 客户、订单、电话和地址全部使用虚构数据；敏感格式仍必须经过现有脱敏流程。
- 高风险案例只展示转人工或审批，不得执行真实电商操作。
- 所有行为变更坚持先写失败测试，再写最小实现。

## 文件结构

- 新建 `apps/api/src/fruit_agent/demo/constants.py`：固定租户、用户、商品、知识、审批和客服案例标识及数据。
- 新建 `apps/api/src/fruit_agent/demo/auth.py`：演示模式判断、RS256 密钥读取和短期令牌签发。
- 新建 `apps/api/src/fruit_agent/demo/router.py`：仅限开发环境的演示会话接口。
- 新建 `apps/api/src/fruit_agent/demo/seed.py`：迁移检查和幂等演示数据初始化命令。
- 新建 `apps/api/src/fruit_agent/demo/__init__.py`：演示模块边界。
- 修改 `apps/api/src/fruit_agent/config.py`：演示开关和密钥路径配置。
- 修改 `apps/api/src/fruit_agent/app.py`：注册演示路由。
- 新建 `apps/api/tests/unit/test_demo_auth.py`：演示模式和令牌单元测试。
- 新建 `apps/api/tests/integration/test_demo_session.py`：演示接口环境、角色和成员验证。
- 新建 `apps/api/tests/integration/test_demo_seed.py`：幂等和租户隔离验证。
- 新建 `apps/web/components/demo-entry.tsx`：角色选择、建立会话和错误重试。
- 修改 `apps/web/lib/api.ts`、`apps/web/lib/types.ts`：演示会话类型和 API。
- 修改 `apps/web/app/page.tsx`、`apps/web/components/app-shell.tsx`：演示入口、动态身份和展示指引。
- 新建 `apps/web/tests/demo-entry.test.tsx`：前端演示登录测试。
- 新建 `apps/web/public/demo-products.csv`：可下载并导入的 UTF-8 示例。
- 修改 `.env.example`、`.gitignore`、`README.md`、`docs/runbook.md`：配置、启动和讲解说明。
- 新建 `videos/fruit-growth-agent-demo/`：真实操作捕获、HyperFrames 品牌、字幕脚本、故事板、合成文件、快照和最终 MP4。

---

### 任务 1：开发环境演示认证

**文件：**
- 新建：`apps/api/src/fruit_agent/demo/__init__.py`
- 新建：`apps/api/src/fruit_agent/demo/constants.py`
- 新建：`apps/api/src/fruit_agent/demo/auth.py`
- 新建：`apps/api/src/fruit_agent/demo/router.py`
- 修改：`apps/api/src/fruit_agent/config.py`
- 修改：`apps/api/src/fruit_agent/app.py`
- 测试：`apps/api/tests/unit/test_demo_auth.py`
- 测试：`apps/api/tests/integration/test_demo_session.py`

**接口：**
- 生成：`demo_enabled(settings: Settings) -> bool`
- 生成：`issue_demo_token(role: Role, settings: Settings, now: datetime | None = None) -> DemoSessionRead`
- 生成：`POST /api/v1/demo/session`，请求 `{ "role": "owner" }`，响应 `{ "access_token", "expires_at", "role" }`
- 依赖：固定的 `DEMO_TENANT_ID` 和 `DEMO_USERS: dict[Role, UUID]`

- [ ] **步骤 1：为演示模式失败关闭和短期令牌编写失败测试**

```python
def test_demo_mode_requires_development_and_explicit_switch() -> None:
    assert not demo_enabled(Settings(environment="production", demo_mode=True))
    assert not demo_enabled(Settings(environment="development", demo_mode=False))
    assert demo_enabled(Settings(environment="development", demo_mode=True))


def test_demo_token_contains_only_fixed_identity_and_short_expiry(
    demo_settings: Settings,
) -> None:
    now = datetime(2026, 7, 21, tzinfo=UTC)
    session = issue_demo_token(Role.owner, demo_settings, now=now)
    claims = jwt.decode(
        session.access_token,
        demo_settings.jwt_public_key,
        algorithms=["RS256"],
        audience=demo_settings.jwt_audience,
    )
    assert claims["tenant_id"] == str(DEMO_TENANT_ID)
    assert claims["sub"] == str(DEMO_USERS[Role.owner])
    assert datetime.fromtimestamp(claims["exp"], UTC) == now + timedelta(minutes=30)
    assert set(claims) == {"sub", "tenant_id", "aud", "iat", "exp"}
```

- [ ] **步骤 2：运行测试并确认因演示模块尚不存在而失败**

运行：`cd apps/api; .\.venv\Scripts\python.exe -m pytest tests/unit/test_demo_auth.py -q`

预期：导入 `fruit_agent.demo.auth` 失败。

- [ ] **步骤 3：实现配置、固定身份和令牌签发**

```python
class Settings(BaseSettings):
    # 保留现有字段
    demo_mode: bool = False
    demo_private_key_path: str = ".demo/rs256-private.pem"
    demo_public_key_path: str = ".demo/rs256-public.pem"


DEMO_TENANT_ID = UUID("10000000-0000-4000-8000-000000000001")
DEMO_USERS = {
    Role.owner: UUID("10000000-0000-4000-8000-000000000011"),
    Role.operator: UUID("10000000-0000-4000-8000-000000000012"),
    Role.support: UUID("10000000-0000-4000-8000-000000000013"),
    Role.implementer: UUID("10000000-0000-4000-8000-000000000014"),
}


def demo_enabled(settings: Settings) -> bool:
    return settings.environment == "development" and settings.demo_mode
```

`issue_demo_token` 必须从本地私钥路径读取密钥，以当前时间签发最长 30 分钟令牌，并返回 Pydantic 响应对象；不得打印令牌。

- [ ] **步骤 4：为路由关闭、非法角色和缺少成员编写集成测试**

```python
async def test_demo_session_is_hidden_when_disabled(client: AsyncClient) -> None:
    response = await client.post("/api/v1/demo/session", json={"role": "owner"})
    assert response.status_code == 404


async def test_demo_session_uses_only_seeded_members(
    demo_client: AsyncClient,
) -> None:
    response = await demo_client.post(
        "/api/v1/demo/session", json={"role": "operator"}
    )
    assert response.status_code == 201
    assert response.json()["role"] == "operator"
```

- [ ] **步骤 5：实现路由并注册到应用**

路由先调用 `demo_enabled`，未启用时返回 404；随后使用 `DEMO_TENANT_ID` 和 `DEMO_USERS[role]` 查询 active 成员，缺少数据返回 409，存在时调用 `issue_demo_token`。在 `create_app()` 中注册 `demo_router`。

- [ ] **步骤 6：运行认证测试和现有身份测试**

运行：`cd apps/api; .\.venv\Scripts\python.exe -m pytest tests/unit/test_demo_auth.py tests/integration/test_demo_session.py tests/unit/test_rbac.py tests/integration/test_members_api.py -q`

预期：全部通过。

- [ ] **步骤 7：提交认证任务**

```powershell
git add apps/api/src/fruit_agent/config.py apps/api/src/fruit_agent/app.py apps/api/src/fruit_agent/demo apps/api/tests/unit/test_demo_auth.py apps/api/tests/integration/test_demo_session.py
git commit -m "feat: add development-only demo sessions"
```

---

### 任务 2：幂等完整演示数据初始化

**文件：**
- 修改：`apps/api/src/fruit_agent/demo/constants.py`
- 新建：`apps/api/src/fruit_agent/demo/seed.py`
- 测试：`apps/api/tests/integration/test_demo_seed.py`

**接口：**
- 生成：`async seed_demo(session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> DemoSeedSummary`
- 生成：`python -m fruit_agent.demo.seed`
- 生成固定数量：1 个租户、4 个成员、6 个 SKU、8 条知识、4 条审批、5 个案例及其建议、引用和结果事件。

- [ ] **步骤 1：编写幂等与跨租户保护失败测试**

```python
async def test_seed_is_idempotent_and_preserves_other_tenants(
    migrated_database: None,
) -> None:
    other_tenant_id = uuid4()
    await insert_other_tenant(other_tenant_id, name="不得修改")
    first = await seed_demo(SessionFactory, demo_settings)
    second = await seed_demo(SessionFactory, demo_settings)
    assert first == second
    assert second.members == 4
    assert second.skus == 6
    assert second.knowledge == 8
    assert second.approvals == 4
    assert second.cases == 5
    assert await load_tenant_name(other_tenant_id) == "不得修改"
```

- [ ] **步骤 2：运行测试并确认 `seed_demo` 尚不存在**

运行：`cd apps/api; .\.venv\Scripts\python.exe -m pytest tests/integration/test_demo_seed.py -q`

预期：导入失败。

- [ ] **步骤 3：定义全部固定演示数据**

`constants.py` 使用固定 UUID，并包含以下明确业务内容：

```python
DEMO_SKUS = (
    DemoSku("YNT-APPLE-5KG", "云南昭通丑苹果 5斤装", "39.90", 128, "云南昭通"),
    DemoSku("XJ-POMELO-2", "福建平和红心蜜柚 2枚", "49.90", 64, "福建平和"),
    DemoSku("SC-KIWI-24", "四川红心猕猴桃 24枚", "59.00", 92, "四川蒲江"),
    DemoSku("HN-MANGO-5", "海南贵妃芒 5斤装", "69.90", 37, "海南三亚"),
    DemoSku("YN-BLUEBERRY-6", "云南蓝莓 6盒装", "89.00", 45, "云南澄江"),
    DemoSku("SX-PEAR-9", "山西玉露香梨 9枚", "45.90", 0, "山西隰县"),
)
```

知识数据必须包含 4 条 approved、1 条 draft、1 条 rejected、1 条 expired，以及 1 组对同一 SKU 形成来源冲突的事实。客服案例必须包含商品咨询、投诉、退款、冲突和已脱敏敏感信息五类情境。

- [ ] **步骤 4：实现单事务 upsert 初始化**

使用 PostgreSQL `insert(...).on_conflict_do_update(...)` 按固定主键或领域唯一键写入；每张表的 `WHERE tenant_id = DEMO_TENANT_ID` 约束必须显式存在。初始化前确认 `settings.environment == "development"`，否则抛出 `DemoSeedRefused`。整个流程由一个 `async with session.begin()` 包裹。

- [ ] **步骤 5：实现密钥生成和命令入口**

使用 `cryptography.hazmat.primitives.asymmetric.rsa.generate_private_key(public_exponent=65537, key_size=2048)` 生成本地密钥；以 PEM 写入 `.demo/rs256-private.pem` 和 `.demo/rs256-public.pem`，已存在则复用。命令先调用 Alembic `upgrade head`，再调用 `seed_demo`，最后只输出数量和访问地址。

- [ ] **步骤 6：连续运行测试两次并核对固定数量**

运行：`cd apps/api; .\.venv\Scripts\python.exe -m pytest tests/integration/test_demo_seed.py -q`

预期：通过，第二次不会增加任何记录。

- [ ] **步骤 7：运行数据、安全和客服副驾回归测试**

运行：`cd apps/api; .\.venv\Scripts\python.exe -m pytest tests/integration tests/security tests/unit/test_copilot_safety.py tests/unit/test_redaction.py -q`

预期：全部通过。

- [ ] **步骤 8：提交初始化任务**

```powershell
git add apps/api/src/fruit_agent/demo/constants.py apps/api/src/fruit_agent/demo/seed.py apps/api/tests/integration/test_demo_seed.py
git commit -m "feat: seed a complete fruit merchant demo"
```

---

### 任务 3：前端演示入口与动态身份

**文件：**
- 新建：`apps/web/components/demo-entry.tsx`
- 修改：`apps/web/lib/api.ts`
- 修改：`apps/web/lib/types.ts`
- 修改：`apps/web/app/page.tsx`
- 修改：`apps/web/components/app-shell.tsx`
- 测试：`apps/web/tests/demo-entry.test.tsx`
- 测试：`apps/web/tests/app-shell.test.tsx`

**接口：**
- 生成：`createDemoSession(role: DemoRole): Promise<DemoSession>`
- 生成：`DemoEntry` 组件，属性 `enabled: boolean`
- 复用：localStorage 键 `fruit-agent-access-token`

- [ ] **步骤 1：编写角色选择、令牌存储和失败重试测试**

```tsx
it("enters the real workspace with the selected demo role", async () => {
  vi.mocked(createDemoSession).mockResolvedValue({
    access_token: "short-lived-token",
    role: "operator",
    expires_at: "2026-07-21T12:30:00Z",
  });
  render(<DemoEntry enabled />);
  await userEvent.selectOptions(screen.getByLabelText("演示角色"), "operator");
  await userEvent.click(screen.getByRole("button", { name: "进入完整演示" }));
  expect(localStorage.getItem("fruit-agent-access-token")).toBe("short-lived-token");
});
```

另写一个 503 场景，断言中文错误可见且按钮可再次点击；`enabled={false}` 时断言入口不渲染。

- [ ] **步骤 2：运行测试并确认组件尚不存在**

运行：`cd apps/web; node_modules\.bin\vitest.cmd run tests/demo-entry.test.tsx`

预期：导入失败。

- [ ] **步骤 3：实现类型与 API**

```ts
export type DemoRole = "owner" | "operator" | "support" | "implementer";
export type DemoSession = {
  access_token: string;
  expires_at: string;
  role: DemoRole;
};

export function createDemoSession(role: DemoRole): Promise<DemoSession> {
  return api<DemoSession>("/api/v1/demo/session", jsonInit("POST", { role }));
}
```

- [ ] **步骤 4：实现演示入口组件**

组件包含开发演示说明、4 个中文角色名称、提交状态和可重试错误。成功后写入现有 localStorage 键并调用 `window.location.assign("/")`，不得把令牌渲染到 DOM 或日志。

- [ ] **步骤 5：把入口和动态身份接入页面**

概览页读取 `process.env.NEXT_PUBLIC_DEMO_MODE === "true"` 并渲染 `DemoEntry`。`AppShell` 在存在令牌时调用现有 `getSession()`，把硬编码的租户/角色文字替换为演示租户名称和真实角色；请求失败时保留“未建立演示会话”。

- [ ] **步骤 6：运行前端相关测试**

运行：`cd apps/web; node_modules\.bin\vitest.cmd run tests/demo-entry.test.tsx tests/app-shell.test.tsx`

预期：全部通过。

- [ ] **步骤 7：提交前端入口**

```powershell
git add apps/web/components/demo-entry.tsx apps/web/lib/api.ts apps/web/lib/types.ts apps/web/app/page.tsx apps/web/components/app-shell.tsx apps/web/tests/demo-entry.test.tsx apps/web/tests/app-shell.test.tsx
git commit -m "feat(web): add guided demo entry"
```

---

### 任务 4：全功能展示引导与示例导入文件

**文件：**
- 新建：`apps/web/public/demo-products.csv`
- 修改：`apps/web/app/page.tsx`
- 修改：`apps/web/app/imports/page.tsx`
- 修改：`apps/web/app/globals.css`
- 测试：`apps/web/tests/demo-entry.test.tsx`

**接口：**
- 生成：从 `/demo-products.csv` 下载的 UTF-8 CSV。
- 生成：6 个现有模块的中文演示说明和建议浏览顺序。

- [ ] **步骤 1：编写展示入口和 CSV 下载测试**

```tsx
it("shows the complete six-step showcase after demo mode is enabled", () => {
  render(<OverviewPage />);
  expect(screen.getByText("完整功能演示路线")).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: /查看/ })).toHaveLength(6);
});
```

导入页测试断言存在 `href="/demo-products.csv"` 且下载名称为 `果序生鲜演示商品.csv`。

- [ ] **步骤 2：运行测试并确认展示路线尚不存在**

运行：`cd apps/web; node_modules\.bin\vitest.cmd run tests/demo-entry.test.tsx tests/csv-import-form.test.tsx`

预期：因缺少演示路线或下载链接而失败。

- [ ] **步骤 3：创建 CSV 和展示路线**

CSV 表头必须严格为：

```csv
sku_code,name,price,inventory,valid_until
DEMO-APPLE-NEW,演示冰糖心苹果,42.90,80,2030-12-31T00:00:00Z
DEMO-INVALID,库存错误演示,19.90,-1,2030-12-31T00:00:00Z
```

概览页按“成员 → 导入 → 知识 → 审批 → 客服副驾 → 回到概览”的顺序提供 6 个链接，并明确指出哪些状态值得查看。

- [ ] **步骤 4：补充响应式样式并验证键盘焦点**

沿用现有绿色、白色和边框变量；新增 `.demo-entry`、`.demo-route`、`.demo-badge`，不引入新动画。按钮和链接继续使用全局 `:focus-visible` 样式，在 640px 以下改为单列。

- [ ] **步骤 5：运行全部前端测试、Lint 和构建**

```powershell
cd apps/web
node_modules\.bin\vitest.cmd run
node_modules\.bin\eslint.cmd .
node_modules\.bin\next.cmd build
```

预期：37 个现有测试加新增测试全部通过；ESLint 无输出；Next.js 生成 `/`、`/members`、`/imports`、`/knowledge`、`/approvals`、`/copilot`。

- [ ] **步骤 6：提交展示引导**

```powershell
git add apps/web/public/demo-products.csv apps/web/app/page.tsx apps/web/app/imports/page.tsx apps/web/app/globals.css apps/web/tests
git commit -m "feat(web): guide the complete demo walkthrough"
```

---

### 任务 5：配置、文档、完整验证和本地启动

**文件：**
- 修改：`.env.example`
- 修改：`.gitignore`
- 修改：`README.md`
- 修改：`docs/runbook.md`
- 新建：`docs/demo-walkthrough.md`

**接口：**
- 生成：`python -m fruit_agent.demo.seed` 初始化命令。
- 生成：管理端 `http://localhost:3000`、API `http://localhost:8000`、API 文档 `http://localhost:8000/docs`。

- [ ] **步骤 1：补全本地配置示例和密钥忽略规则**

`.env.example` 增加：

```dotenv
DEMO_MODE=false
DEMO_PRIVATE_KEY_PATH=.demo/rs256-private.pem
DEMO_PUBLIC_KEY_PATH=.demo/rs256-public.pem
NEXT_PUBLIC_DEMO_MODE=false
NEXT_PUBLIC_API_URL=http://localhost:8000
```

`.gitignore` 增加 `.demo/`，并用 `git check-ignore .demo/rs256-private.pem` 验证私钥被忽略。

- [ ] **步骤 2：写清启动和演示说明**

`README.md` 和 `docs/runbook.md` 写明 Python 3.12、PostgreSQL、迁移、初始化、API 和前端启动顺序。`docs/demo-walkthrough.md` 按页面列出要展示的数据、建议使用角色和安全边界，禁止暗示真实店铺已接入。

- [ ] **步骤 3：建立当前工作树自己的依赖环境**

```powershell
cd apps/api
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
cd ..\web
pnpm install
```

预期：Python 使用 3.12，前后端依赖安装成功。

- [ ] **步骤 4：执行完整后端验证**

```powershell
cd apps/api
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe -m mypy src tests
.\.venv\Scripts\python.exe -m pytest -q
```

预期：Ruff、mypy 和全部后端测试通过。

- [ ] **步骤 5：执行完整前端验证**

```powershell
cd apps/web
node_modules\.bin\vitest.cmd run
node_modules\.bin\eslint.cmd .
node_modules\.bin\next.cmd build
```

预期：全部前端测试、Lint、TypeScript 和生产构建通过。

- [ ] **步骤 6：初始化真实本地演示数据两次**

```powershell
cd apps/api
$env:ENVIRONMENT="development"
$env:DEMO_MODE="true"
.\.venv\Scripts\python.exe -m fruit_agent.demo.seed
.\.venv\Scripts\python.exe -m fruit_agent.demo.seed
```

预期：两次均报告 1 个租户、4 个成员、6 个 SKU、8 条知识、4 条审批、5 个案例；第二次不增加记录。

- [ ] **步骤 7：启动服务并完成 HTTP 冒烟检查**

后台启动 API 和 Web 后依次检查：

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-WebRequest http://localhost:3000/
Invoke-WebRequest http://localhost:3000/members
Invoke-WebRequest http://localhost:3000/imports
Invoke-WebRequest http://localhost:3000/knowledge
Invoke-WebRequest http://localhost:3000/approvals
Invoke-WebRequest http://localhost:3000/copilot
```

预期：健康检查返回 `status=ok`，全部页面返回 200。再通过演示会话获取 operator 令牌，验证 `/api/v1/session`、members、knowledge、approvals 和 copilot cases 均返回演示租户数据。

- [ ] **步骤 8：提交文档和配置**

```powershell
git add .env.example .gitignore README.md docs/runbook.md docs/demo-walkthrough.md
git commit -m "docs: document the complete local demo"
```

- [ ] **步骤 9：记录最终状态**

运行 `git status --short`，确认只保留实施前已经存在且与本任务无关的 `docs/product-plan.md` 换行改动；不得把它纳入任何提交。最终汇报管理端、API 文档地址、演示角色、测试数量和按页面演示顺序。

---

### 任务 6：录制并交付完整操作视频

**文件：**
- 新建：`videos/fruit-growth-agent-demo/DESIGN.md`
- 新建：`videos/fruit-growth-agent-demo/SCRIPT.md`
- 新建：`videos/fruit-growth-agent-demo/STORYBOARD.md`
- 新建：`videos/fruit-growth-agent-demo/scripts/record-tour.mjs`
- 新建：`videos/fruit-growth-agent-demo/index.html`
- 新建：`videos/fruit-growth-agent-demo/compositions/*.html`
- 生成：`videos/fruit-growth-agent-demo/capture/`
- 生成：`videos/fruit-growth-agent-demo/media/*.webm`
- 生成：`videos/fruit-growth-agent-demo/snapshots/*.png`
- 生成：`videos/fruit-growth-agent-demo/renders/果序Agent完整功能演示.mp4`

**接口：**
- 生成：1920×1080、30fps、静音、约 3 分钟的简体中文字幕操作视频。
- 生成：HyperFrames Studio 项目预览地址。
- 依赖：任务 1–5 已完成，API 和管理端正在本地运行，演示数据已经初始化。

- [ ] **步骤 1：检查视频运行环境**

运行：

```powershell
cd videos
npx hyperframes doctor
```

预期：Node.js 22+、Chrome 和 FFmpeg 可用。任何缺项先按 `doctor` 的明确提示修复，不创建合成文件。

- [ ] **步骤 2：初始化 HyperFrames 项目并捕获网站**

```powershell
npx hyperframes init fruit-growth-agent-demo --non-interactive
npx hyperframes capture http://localhost:3000 -o fruit-growth-agent-demo/capture
```

读取并总结 `capture/screenshots/scroll-000.png`、全部滚动截图、`capture/extracted/tokens.json`、`visible-text.txt` 和 `asset-descriptions.md`。站点摘要必须确认主色 `#075f42`、深绿 `#034b34`、浅绿 `#edf7f2`、白色 `#ffffff`，字体为 Inter、苹方或微软雅黑风格，整体为克制的中文运营工作台。

- [ ] **步骤 3：编写品牌设计文件**

`DESIGN.md` 必须包含 Overview、Colors、Typography、Elevation、Components、Do's and Don'ts 六部分，并使用捕获结果中的精确色值。明确禁止深色电影风、霓虹、玻璃拟态、夸张 3D 和小于 20px 的正文字体。

- [ ] **步骤 4：编写无旁白字幕脚本**

`SCRIPT.md` 按以下 9 个场景记录屏幕字幕和目标时长，总时长约 180 秒：

```markdown
1. 片头（0–6s）：果序 Agent｜水果商家 AI 运营工作台
2. 进入演示（6–20s）：选择运营角色，进入真实数据库驱动的本地演示
3. 概览（20–35s）：多租户、权限、知识和人工审批共同构成安全底座
4. 成员（35–50s）：四类封闭角色，各自只拥有必要权限
5. CSV 导入（50–75s）：合法商品写入，错误库存逐行提示且不会污染数据
6. 知识库（75–105s）：只有已审核、未过期、无冲突的知识可以支撑回复
7. 人工审批（105–125s）：退款、改价和发布等高风险动作只记录决定，不自动执行
8. 客服副驾（125–170s）：有依据才建议；投诉、退款、冲突或敏感信息一律安全处理
9. 片尾（170–180s）：真实店铺动作仍由人确认｜演示完成
```

全片不创建 narration、音乐或音效轨道。

- [ ] **步骤 5：编写逐场景故事板**

`STORYBOARD.md` 指定 1920×1080、30fps、静音，以及每场的页面、操作、字幕、鼠标强调、英雄帧和转场。所有场景使用真实操作画面作为主层，字幕为底部安全区卡片；相邻场景使用 300–450ms 的绿色遮罩推移或轻微交叉淡化，不允许突然跳切。

- [ ] **步骤 6：用真实浏览器录制操作素材**

`scripts/record-tour.mjs` 使用 HyperFrames 环境提供的 Playwright/Chromium：

1. 请求 `POST http://localhost:8000/api/v1/demo/session` 获取 operator 演示会话。
2. 打开 1920×1080 浏览器上下文并启用 `recordVideo`，但不得打印令牌。
3. 在首次导航前写入 localStorage 键 `fruit-agent-access-token`。
4. 依次操作 `/`、`/members`、`/imports`、`/knowledge`、`/approvals` 和 `/copilot`。
5. 导入 `public/demo-products.csv`，等待真实接口结果出现。
6. 在客服副驾中创建普通咨询和退款/投诉咨询，等待真实分类、建议或转人工结果。
7. 把每段真实操作保存为 `media/01-entry.webm` 至 `media/08-copilot.webm`。

每个操作使用可访问名称定位控件，等待 API 响应或明确 UI 状态，不用固定长时间 sleep。完整令牌和私钥不得写入录像、控制台或文件名。

- [ ] **步骤 7：构建静态英雄帧和 HyperFrames 合成**

先为每场建立 1920×1080 静态最终布局，再添加 GSAP。每段视频元素必须 `muted playsinline`；没有音频节点。字幕字号至少 32px，标题至少 60px。使用 `gsap.fromTo()` 添加字幕和点击提示的确定性入场；每个多场景边界使用转场，不在转场前提前淡出内容；最后一场可以整体淡出。

根 `index.html` 为 standalone composition，不使用 `<template>`；子合成使用 `<template>`。每个时间片设置唯一 `id`、`data-start`、`data-duration` 和 `data-track-index`，每条时间线以 `{ paused: true }` 创建并注册到 `window.__timelines`。

- [ ] **步骤 8：执行静态、运行时、布局和动画验证**

```powershell
cd videos/fruit-growth-agent-demo
npx hyperframes lint
npx hyperframes validate
npx hyperframes inspect --samples 15
npx hyperframes snapshot . --at 3,13,28,43,63,90,115,148,175
```

预期：lint、validate 和 inspect 零错误。逐张查看 9 张英雄帧，确认字幕无溢出或遮挡、页面主操作清晰、色彩符合 `DESIGN.md`。若动画映射脚本可用，再生成 animation map 并处理所有 offscreen、collision、invisible 和 pacing 标记。

- [ ] **步骤 9：启动 Studio 预览并完整走查**

运行：`npx hyperframes preview --port 3017`

预期项目地址：`http://localhost:3017/#project/fruit-growth-agent-demo`。从头到尾拖动时间线，确认页面操作、字幕、点击提示和转场同步。

- [ ] **步骤 10：渲染用户明确要求的 MP4**

```powershell
npx hyperframes render --output renders/果序Agent完整功能演示.mp4 --fps 30 --quality high
```

预期：生成可播放的 1920×1080 MP4。使用媒体信息检查分辨率、帧率和时长，并确认音轨不存在。

- [ ] **步骤 11：提交可编辑视频源文件**

只提交 DESIGN、SCRIPT、STORYBOARD、脚本、HTML 合成和必要的轻量捕获资产；不提交私钥、完整 JWT、依赖目录或无必要的临时浏览器缓存。最终汇报 Studio 地址和 MP4 的绝对路径。

```powershell
git add videos/fruit-growth-agent-demo
git commit -m "feat(video): add complete product walkthrough"
```
