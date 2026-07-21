# Fruit Growth Agent

面向水果商城运营团队的多租户 AI 工作台。当前实现覆盖租户隔离、成员权限、不可变审计、人工审批、商品与知识模型、CSV 导入、运营 Copilot、结果反馈以及 Next.js 管理端。

## 安全原则

- 所有应用查询显式携带 `tenant_id`，PostgreSQL RLS 提供第二层隔离。
- 退款、赔付、改价、改库存和发布抖音内容只创建待审批记录，不存在真实执行器。
- 电话、地址等字段进入模型或审计前递归替换为 `[REDACTED]`。
- 价格和库存只走精确 SQL；FAQ、话术和产地故事才允许 pgvector 检索。
- 过期或冲突事实不进入推荐。

## 本地启动

要求 Python 3.12、Node.js 24、pnpm 11、Docker Desktop（WSL 2）和 GNU Make。

```powershell
Copy-Item .env.example .env
docker compose up -d postgres
cd apps/api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\alembic.exe upgrade head
```

分别启动 API 和管理端：

```powershell
make api-run
make web-install
make web-run
```

完整验证：

```powershell
make verify
```

API 默认地址为 `http://localhost:8000`，管理端默认地址为 `http://localhost:3000`。前端通过 `NEXT_PUBLIC_API_URL` 指向 API。

详细操作见 [运行手册](docs/runbook.md)，设计决策见 [架构说明](docs/architecture.md)。

## 中文完整演示

开发环境可以生成一套可重复执行的“果序生鲜（华东）”演示数据。它包含 4 种角色、6 个商品、8 条知识、4 个审批和 5 个 Copilot 案例。

```powershell
Copy-Item .env.example apps/api/.env
# 将 apps/api/.env 中的 DEMO_MODE 改为 true
cd apps/api
.\.venv\Scripts\python.exe -m fruit_agent.demo.seed
.\.venv\Scripts\uvicorn.exe fruit_agent.app:app --host 127.0.0.1 --port 8000
```

另开终端启动管理端：

```powershell
cd apps/web
Set-Content .env.local "NEXT_PUBLIC_DEMO_MODE=true`nNEXT_PUBLIC_API_URL=http://127.0.0.1:8000"
pnpm dev
```

打开 `http://localhost:3000`，选择角色并按首页六步路线体验。详细脚本见 [中文演示指南](docs/demo-walkthrough.md)。演示开关在生产环境无效，生成的 RSA 私钥也只允许保存在被忽略的 `.demo/` 目录中。
