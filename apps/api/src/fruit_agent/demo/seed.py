from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fruit_agent.approvals.models import ApprovalRequest
from fruit_agent.config import Settings
from fruit_agent.copilot.models import (
    CopilotCase,
    CopilotCitationSnapshot,
    CopilotSuggestion,
)
from fruit_agent.copilot.outcomes import CopilotOutcomeEvent
from fruit_agent.db import SessionFactory
from fruit_agent.demo.constants import (
    DEMO_APPROVAL_IDS,
    DEMO_CASE_IDS,
    DEMO_CITATION_IDS,
    DEMO_KNOWLEDGE_IDS,
    DEMO_KNOWLEDGE_SOURCE_IDS,
    DEMO_MEMBERSHIPS,
    DEMO_OUTCOME_IDS,
    DEMO_SKU_IDS,
    DEMO_SKU_SOURCE_IDS,
    DEMO_SKUS,
    DEMO_SUGGESTION_IDS,
    DEMO_TENANT_ID,
    DEMO_USERS,
)
from fruit_agent.identity.models import Membership, Role, Tenant, User
from fruit_agent.knowledge.embeddings import DeterministicEmbeddingProvider
from fruit_agent.knowledge.models import MerchantKnowledge, ProductSKU


class DemoSeedRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class DemoSeedSummary:
    tenants: int
    members: int
    skus: int
    knowledge: int
    approvals: int
    cases: int


def ensure_demo_keys(settings: Settings) -> None:
    private_path = Path(settings.demo_private_key_path)
    public_path = Path(settings.demo_public_key_path)
    if private_path.is_file() and public_path.is_file():
        return
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


async def _upsert(
    session: AsyncSession,
    model: type[Any],
    values: dict[str, Any],
    update_fields: tuple[str, ...],
) -> None:
    statement = insert(model).values(**values)
    if update_fields:
        statement = statement.on_conflict_do_update(
            index_elements=[model.id],
            set_={field: getattr(statement.excluded, field) for field in update_fields},
        )
    else:
        statement = statement.on_conflict_do_nothing(index_elements=[model.id])
    await session.execute(statement)


def _knowledge_rows(now: datetime) -> list[dict[str, Any]]:
    provider = DeterministicEmbeddingProvider()
    future = datetime(2030, 12, 31, tzinfo=UTC)
    expired = datetime(2025, 1, 1, tzinfo=UTC)
    records = (
        ("faq", "approved", "苹果收到后冷藏可保存约两周，食用前回温口感更好。", "售后知识手册", future),
        ("talking_point", "approved", "云南昭通丑苹果昼夜温差大，口感脆甜微酸。", "产地采访记录", future),
        ("origin_story", "approved", "高原合作果园采用人工疏果和分批采收。", "果园溯源档案", future),
        ("faq", "approved", "蓝莓到货后请立即冷藏，并在三天内食用。", "冷链操作规范", future),
        ("faq", "draft", "贵妃芒可常温密封催熟。", "运营草稿", future),
        ("talking_point", "rejected", "所有水果都保证绝对无农残。", "未验证营销文案", future),
        ("faq", "approved", "旧版配送承诺为全国次日达。", "2025 配送政策", expired),
        ("product_fact", "approved", "玉露香梨补货日期存在两个来源冲突，需人工确认。", "供应链冲突提示", future),
    )
    rows: list[dict[str, Any]] = []
    for index, (kind, status, content, source_name, valid_until) in enumerate(records):
        rows.append(
            {
                "id": DEMO_KNOWLEDGE_IDS[index],
                "tenant_id": DEMO_TENANT_ID,
                "knowledge_type": kind,
                "review_status": status,
                "content": content,
                "source_id": DEMO_KNOWLEDGE_SOURCE_IDS[index],
                "source_name": source_name,
                "responsible_user_id": DEMO_USERS[Role.implementer],
                "embedding": provider.embed(content),
                "embedding_model": provider.model_name,
                "embedding_version": provider.model_version,
                "valid_until": valid_until,
                "audit_log": [],
            }
        )
    return rows


async def _seed_identity(session: AsyncSession, future: datetime) -> None:
    await _upsert(
        session,
        Tenant,
        {
            "id": DEMO_TENANT_ID,
            "name": "果序生鲜（华东）",
            "valid_until": future,
            "audit_log": [],
        },
        ("name", "valid_until"),
    )
    names = {
        Role.owner: "owner@demo.fruit-agent.local",
        Role.operator: "operator@demo.fruit-agent.local",
        Role.support: "support@demo.fruit-agent.local",
        Role.implementer: "implementer@demo.fruit-agent.local",
    }
    for role, user_id in DEMO_USERS.items():
        await _upsert(
            session,
            User,
            {
                "id": user_id,
                "tenant_id": DEMO_TENANT_ID,
                "email": names[role],
                "valid_until": future,
                "audit_log": [],
            },
            ("email", "valid_until"),
        )
        await _upsert(
            session,
            Membership,
            {
                "id": DEMO_MEMBERSHIPS[role],
                "tenant_id": DEMO_TENANT_ID,
                "user_id": user_id,
                "role": role.value,
                "status": "active",
                "valid_until": future,
                "audit_log": [],
            },
            ("role", "status", "valid_until"),
        )


async def _seed_products_and_knowledge(
    session: AsyncSession,
    now: datetime,
    future: datetime,
) -> None:
    for index, sku in enumerate(DEMO_SKUS):
        await _upsert(
            session,
            ProductSKU,
            {
                "id": DEMO_SKU_IDS[index],
                "tenant_id": DEMO_TENANT_ID,
                "sku_code": sku.sku_code,
                "name": sku.name,
                "price": Decimal(sku.price),
                "inventory": sku.inventory,
                "source_id": DEMO_SKU_SOURCE_IDS[index],
                "variety": sku.variety,
                "origin": sku.origin,
                "orchard": sku.orchard,
                "taste": sku.taste,
                "ripeness": sku.ripeness,
                "specification": sku.specification,
                "net_weight_grams": sku.net_weight_grams,
                "sales_regions": list(sku.sales_regions),
                "shipping_eta": sku.shipping_eta,
                "valid_until": future,
                "audit_log": [],
            },
            (
                "name",
                "price",
                "inventory",
                "variety",
                "origin",
                "orchard",
                "taste",
                "ripeness",
                "specification",
                "net_weight_grams",
                "sales_regions",
                "shipping_eta",
                "valid_until",
            ),
        )
    for row in _knowledge_rows(now):
        await _upsert(
            session,
            MerchantKnowledge,
            row,
            (
                "knowledge_type",
                "review_status",
                "content",
                "source_name",
                "responsible_user_id",
                "embedding",
                "embedding_model",
                "embedding_version",
                "valid_until",
            ),
        )


async def _seed_approvals(session: AsyncSession, now: datetime, future: datetime) -> None:
    rows: tuple[tuple[Any, ...], ...] = (
        ("refund", "pending", {"order_no": "DEMO-1001", "amount": "39.90"}, None),
        ("change_inventory", "approved", {"sku_code": "YN-APPLE-5", "inventory": 128}, now),
        ("publish_douyin", "rejected", {"title": "夏日蓝莓开箱"}, now),
        ("change_price", "pending", {"sku_code": "HN-MANGO-5", "price": "65.90"}, None),
    )
    for index, (action, status, payload, decided_at) in enumerate(rows):
        await _upsert(
            session,
            ApprovalRequest,
            {
                "id": DEMO_APPROVAL_IDS[index],
                "tenant_id": DEMO_TENANT_ID,
                "requested_by": DEMO_USERS[Role.operator],
                "action": action,
                "payload": payload,
                "requires_approval": True,
                "status": status,
                "decided_by": DEMO_USERS[Role.owner] if decided_at else None,
                "decided_at": decided_at,
                "valid_until": future,
                "audit_log": [],
            },
            ("payload", "status", "decided_by", "decided_at", "valid_until"),
        )


async def _seed_cases(session: AsyncSession, now: datetime, future: datetime) -> None:
    rows: tuple[tuple[Any, ...], ...] = (
        ("这款昭通苹果甜不甜，适合送人吗？", ["YN-APPLE-5"], "presale", "gift", "low", "suggestions_ready", [], None, []),
        ("收到的芒果有碰伤，我非常不满意。", ["HN-MANGO-5"], "aftersale", "complaint", "high", "handoff_required", ["complaint"], "投诉需要人工客服处理", []),
        ("我要求马上退款并赔偿。", [], "aftersale", "refund", "critical", "handoff_required", ["refund", "compensation"], "退款与赔付必须转人工审批", []),
        ("玉露香梨什么时候补货？", ["SX-PEAR-9"], "presale", "product_info", "medium", "handoff_required", ["conflicting_sources"], "补货信息来源冲突", [str(DEMO_KNOWLEDGE_SOURCE_IDS[6]), str(DEMO_KNOWLEDGE_SOURCE_IDS[7])]),
        ("请联系我：[REDACTED]，地址：[REDACTED]。", ["YN-BLUEBERRY-6"], "aftersale", "delivery", "medium", "closed", ["pii_redacted"], None, []),
    )
    for index, row in enumerate(rows):
        message, skus, stage, intent, risk, status, reasons, handoff, conflicts = row
        await _upsert(
            session,
            CopilotCase,
            {
                "id": DEMO_CASE_IDS[index],
                "tenant_id": DEMO_TENANT_ID,
                "created_by_user_id": DEMO_USERS[Role.operator],
                "message": message,
                "selected_sku_codes": skus,
                "stage": stage,
                "intent": intent,
                "risk": risk,
                "status": status,
                "risk_reasons": reasons,
                "response_time_ms": 420 + index * 85,
                "handoff_reason": handoff,
                "conflict_source_ids": conflicts,
                "valid_until": future,
                "audit_log": [],
            },
            (
                "message",
                "selected_sku_codes",
                "stage",
                "intent",
                "risk",
                "status",
                "risk_reasons",
                "response_time_ms",
                "handoff_reason",
                "conflict_source_ids",
                "valid_until",
            ),
        )

    suggestions = (
        (DEMO_SUGGESTION_IDS[0], "这款昭通丑苹果脆甜微酸，5斤装也很适合作为家庭分享装。", 1, "YN-APPLE-5", 0.94),
        (DEMO_SUGGESTION_IDS[1], "如果用于送礼，可以搭配礼袋，并提醒收货后冷藏保存。", 2, "YN-APPLE-5", 0.89),
    )
    for suggestion_id, text_value, rank, sku_code, confidence in suggestions:
        await _upsert(
            session,
            CopilotSuggestion,
            {
                "id": suggestion_id,
                "tenant_id": DEMO_TENANT_ID,
                "case_id": DEMO_CASE_IDS[0],
                "original_text": text_value,
                "edited_text": None,
                "rank": rank,
                "recommended_sku_code": sku_code,
                "confidence": confidence,
                "risk_tip": "建议发送前核对库存和配送范围",
                "degraded": False,
                "model_name": "demo-grounded-provider",
                "valid_until": future,
                "audit_log": [],
            },
            (
                "original_text",
                "rank",
                "recommended_sku_code",
                "confidence",
                "risk_tip",
                "valid_until",
            ),
        )

    citations = (
        (DEMO_CITATION_IDS[0], DEMO_SUGGESTION_IDS[0], "sku", DEMO_SKU_IDS[0], "商品主数据", {"sku_code": "YN-APPLE-5", "price": "39.90", "inventory": 128}),
        (DEMO_CITATION_IDS[1], DEMO_SUGGESTION_IDS[1], "knowledge", DEMO_KNOWLEDGE_IDS[0], "售后知识手册", {"content": "苹果收到后冷藏可保存约两周"}),
    )
    for citation_id, suggestion_id, kind, source_id, source_name, snapshot in citations:
        await _upsert(
            session,
            CopilotCitationSnapshot,
            {
                "id": citation_id,
                "tenant_id": DEMO_TENANT_ID,
                "suggestion_id": suggestion_id,
                "citation_type": kind,
                "source_id": source_id,
                "source_name": source_name,
                "snapshot": snapshot,
                "source_updated_at": now,
                "retrieved_at": now,
                "valid_until": future,
                "audit_log": [],
            },
            (),
        )

    outcomes: tuple[
        tuple[UUID, UUID, UUID | None, str, str, dict[str, str]], ...
    ] = (
        (DEMO_OUTCOME_IDS[0], DEMO_CASE_IDS[0], DEMO_SUGGESTION_IDS[0], "suggestion_adopted", "demo-adopt-1", {"channel": "manual_demo"}),
        (DEMO_OUTCOME_IDS[1], DEMO_CASE_IDS[0], None, "payment", "demo-payment-1", {"amount": "39.90"}),
        (DEMO_OUTCOME_IDS[2], DEMO_CASE_IDS[1], None, "complaint", "demo-complaint-1", {"severity": "high"}),
        (DEMO_OUTCOME_IDS[3], DEMO_CASE_IDS[0], DEMO_SUGGESTION_IDS[1], "suggestion_rejected", "demo-reject-1", {"reason": "customer_prefers_short_reply"}),
        (DEMO_OUTCOME_IDS[4], DEMO_CASE_IDS[4], None, "case_closed", "demo-close-1", {"resolution": "manual_followup"}),
    )
    for (
        outcome_id,
        case_id,
        outcome_suggestion_id,
        event_type,
        key,
        metadata,
    ) in outcomes:
        await _upsert(
            session,
            CopilotOutcomeEvent,
            {
                "id": outcome_id,
                "tenant_id": DEMO_TENANT_ID,
                "case_id": case_id,
                "suggestion_id": outcome_suggestion_id,
                "event_type": event_type,
                "idempotency_key": key,
                "occurred_at": now,
                "metadata_": metadata,
                "valid_until": future,
                "audit_log": [],
            },
            (),
        )


async def _summary(session: AsyncSession) -> DemoSeedSummary:
    async def count(model: type[Any]) -> int:
        value = await session.scalar(
            select(func.count()).select_from(model).where(
                model.tenant_id == DEMO_TENANT_ID
            )
        )
        return int(value or 0)

    tenant_count = await session.scalar(
        select(func.count()).select_from(Tenant).where(Tenant.id == DEMO_TENANT_ID)
    )
    return DemoSeedSummary(
        tenants=int(tenant_count or 0),
        members=await count(Membership),
        skus=await count(ProductSKU),
        knowledge=await count(MerchantKnowledge),
        approvals=await count(ApprovalRequest),
        cases=await count(CopilotCase),
    )


async def seed_demo(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> DemoSeedSummary:
    if settings.environment != "development":
        raise DemoSeedRefused("demo data may only be seeded in development")
    ensure_demo_keys(settings)
    now = datetime.now(UTC)
    future = datetime(2030, 12, 31, tzinfo=UTC)
    async with session_factory() as session:
        async with session.begin():
            await _seed_identity(session, future)
            await _seed_products_and_knowledge(session, now, future)
            await _seed_approvals(session, now, future)
            await _seed_cases(session, now, future)
        return await _summary(session)


async def _main() -> None:
    settings = Settings()
    if settings.environment != "development":
        raise DemoSeedRefused("demo data may only be seeded in development")
    command.upgrade(Config("alembic.ini"), "head")
    summary = await seed_demo(SessionFactory, settings)
    print(
        "Demo ready: "
        f"tenants={summary.tenants}, members={summary.members}, "
        f"skus={summary.skus}, knowledge={summary.knowledge}, "
        f"approvals={summary.approvals}, cases={summary.cases}"
    )
    print("Web: http://localhost:3000")
    print("API docs: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(_main())
