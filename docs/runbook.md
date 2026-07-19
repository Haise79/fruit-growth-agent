# 基础能力运行手册

## 环境变量

从 `.env.example` 创建 `.env`。生产环境必须替换数据库口令，并配置：

- `DATABASE_URL`：SQLAlchemy psycopg 连接串。
- `JWT_PUBLIC_KEY`：只包含服务端签发 JWT 对应的 RSA 公钥。
- `JWT_AUDIENCE=fruit-agent-api`。
- `LOG_LEVEL`：建议生产使用 `INFO`。
- `NEXT_PUBLIC_API_URL`：浏览器可访问的 API 地址。

不得把私钥、供应商密钥或真实用户敏感信息提交到仓库。

## 启动、迁移与验证

```powershell
docker compose up -d postgres
cd apps/api
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe fruit_agent.app:app --host 0.0.0.0 --port 8000
```

管理端：

```powershell
cd apps/web
pnpm install
pnpm dev
```

仓库根目录执行 `make verify` 可验证 Compose、后端测试/类型/Lint 和前端测试/Lint/生产构建。

## 首次租户与 owner

首个租户必须通过受控运维事务创建，不提供匿名注册接口。示例 SQL 仅由数据库管理员在维护窗口执行：

```sql
BEGIN;
INSERT INTO tenants (id, name, valid_until, audit_log)
VALUES (:tenant_id, :name, :valid_until, '[]'::jsonb);
INSERT INTO users (id, tenant_id, email, valid_until, audit_log)
VALUES (:user_id, :tenant_id, :email, :valid_until, '[]'::jsonb);
INSERT INTO memberships
  (id, tenant_id, user_id, role, status, valid_until, audit_log)
VALUES
  (:membership_id, :tenant_id, :user_id, 'owner', 'active',
   :valid_until, '[]'::jsonb);
COMMIT;
```

签发 JWT 时 `sub` 必须为 user ID，`tenant_id` 必须匹配成员关系，`aud` 必须为 `fruit-agent-api`。

## CSV 商品模板

文件必须为 UTF-8（可带 BOM），表头顺序必须完全一致：

```csv
sku_code,name,price,inventory,valid_until
APPLE-001,红富士苹果,29.90,100,2030-01-01T00:00:00Z
```

价格大于 0、库存为非负整数、有效期必须是未来且带时区。无效行逐项返回行号、字段、原因和建议；同一文件内重复 SKU 只导入首个合法行。

## PostgreSQL 备份与恢复

备份：

```powershell
docker compose exec -T postgres pg_dump -U fruit_agent -Fc fruit_agent > fruit_agent.dump
```

恢复前停止 API 写流量并创建恢复演练数据库：

```powershell
docker compose exec -T postgres createdb -U fruit_agent fruit_agent_restore
Get-Content -AsByteStream fruit_agent.dump |
  docker compose exec -T postgres pg_restore -U fruit_agent -d fruit_agent_restore
```

恢复后必须运行迁移版本、RLS 策略、审计触发器和跨租户安全测试，再切换连接串。不得在未验证备份上直接覆盖生产库。

## 模型供应商故障

网关对主模型执行 8 秒超时和最多 3 次尝试；超时或不可用后调用备用合格模型一次并返回 `degraded=true`。排障顺序：

1. 查询 `model_provider_attempt_failed` 和 `model_call_completed` 日志。
2. 核对模型质量档案是否仍满足 `<2%` 事实错误率和 `>=95%` 高风险召回。
3. 检查供应商网络、配额和延迟。
4. 若所有合格供应商不可用，API 返回 503，不得临时选择不合格模型。

日志不得记录原始 prompt。

## 审计查询

运维查询也必须设置租户上下文：

```sql
BEGIN;
SELECT set_config('app.tenant_id', :tenant_id, true);
SELECT request_id, actor_id, action, entity_type, entity_id,
       before, after, created_at
FROM audit_events
WHERE tenant_id = :tenant_id
ORDER BY created_at DESC
LIMIT 200;
COMMIT;
```

审计事件不可更新或删除。异常调查以 `X-Request-ID` 关联 API 响应与日志。

## 租户数据导出与删除

导出必须在审批工单中记录 tenant ID、请求人、范围和保留策略。使用只读事务设置 `app.tenant_id` 后，按表显式添加 `WHERE tenant_id = :tenant_id` 导出；禁止全库导出后在应用层过滤。

删除属于高影响运维动作，本阶段没有 API。流程为：

1. owner 提交并由第二名授权人员确认。
2. 完成加密备份并验证可恢复。
3. 暂停该租户令牌和写流量。
4. 在维护事务中按 tenant ID 删除，保留合规要求允许保留的审计归档。
5. 运行跨租户测试，确认未影响其他租户。
6. 在外部合规工单记录执行人、request ID、备份位置和验证证据。

严禁让 Agent 或普通审批接口自动执行租户删除。
