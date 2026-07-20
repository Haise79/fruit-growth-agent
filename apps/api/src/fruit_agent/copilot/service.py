from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.common.errors import DomainError
from fruit_agent.common.redaction import (
    PII_PLACEHOLDER,
    redact,
)
from fruit_agent.copilot.models import (
    CopilotCase,
    CopilotCitationSnapshot,
    CopilotSuggestion,
)
from fruit_agent.copilot.outcomes import CopilotOutcomeEvent
from fruit_agent.copilot.repository import CopilotRepository
from fruit_agent.copilot.safety import (
    classify_customer_message,
    merge_model_risk,
    merge_safety_classifications,
)
from fruit_agent.copilot.schemas import (
    CopilotCaseCreate,
    CopilotCaseStatus,
    CopilotCitationType,
    CopilotIntent,
    CopilotOutcomeEventCreate,
    CopilotRisk,
    CopilotStage,
)
from fruit_agent.knowledge.embeddings import (
    EmbeddingProvider,
    default_embedding_provider,
    embedding_provider_is_allowed,
)
from fruit_agent.knowledge.models import KnowledgeType, MerchantKnowledge
from fruit_agent.knowledge.repository import KnowledgeRepository
from fruit_agent.knowledge.schemas import ProductSKURead
from fruit_agent.knowledge.service import KnowledgeService
from fruit_agent.model_gateway.schemas import CopilotAgentSuggestion
from fruit_agent.model_gateway.service import (
    InvalidModelOutputError,
    ModelGateway,
    NoQualifiedModelError,
    ProviderBinding,
    ProviderUnavailableError,
)

_TOPIC_ANCHORS: dict[str, tuple[str, ...]] = {
    "storage": (
        "保存",
        "储存",
        "冷藏",
        "保鲜",
        "冰箱",
        "常温",
        "storage",
        "refrigerat",
        "shelf life",
        "shelf-life",
        "keep fresh",
        "freshness",
    ),
    "delivery": (
        "发货",
        "物流",
        "配送",
        "快递",
        "到货",
        "shipping",
        "delivery",
        "courier",
    ),
    "gift": ("送礼", "礼物", "礼盒", "gift"),
    "recommendation": (
        "推荐",
        "选择",
        "哪款",
        "口感",
        "甜度",
        "酸甜",
        "清脆",
        "酥脆",
        "脆甜",
        "爽脆",
        "recommend",
        "choose",
        "taste",
        "sweet",
        "crisp",
    ),
    "product_fact": (
        "产地",
        "品种",
        "规格",
        "重量",
        "价格",
        "库存",
        "果园",
        "来自",
        "origin",
        "variety",
        "specification",
        "weight",
        "price",
        "inventory",
        "orchard",
    ),
    "damage": (
        "破损",
        "压坏",
        "磕碰",
        "腐烂",
        "damage",
        "crush",
        "rotten",
    ),
    "refund": (
        "退款",
        "退货",
        "赔偿",
        "售后",
        "refund",
        "return",
        "compensation",
    ),
    "health_safety": (
        "过敏",
        "疾病",
        "食品安全",
        "食用",
        "能吃",
        "可以吃",
        "allergy",
        "disease",
        "food safety",
        "safe to eat",
    ),
}
_PRODUCT_CONTEXT = re.compile(
    r"苹果|水果|红富士|果品|果实|梨|橙|柑|桃|葡萄|莓|"
    r"\b(?:apples?|fruits?|pears?|oranges?|peaches?|grapes?|"
    r"berries|produce)\b",
    re.IGNORECASE,
)
_IMPERATIVE_STORE_PRODUCT = re.compile(
    r"\bstore\s+(?:(?:the|your|fresh|ripe)\s+){0,3}"
    r"(?:apples?|fruits?|pears?|oranges?|peaches?|grapes?|"
    r"berries|produce)\b",
    re.IGNORECASE,
)
_PRODUCT_AUXILIARY_STORED = re.compile(
    r"\b(?:apples?|fruits?|pears?|oranges?|peaches?|grapes?|"
    r"berries|produce)\b\s+"
    r"(?:(?:should|must|can|may|need|needs|to|is|are|be|best)\s+){1,4}"
    r"stored\b",
    re.IGNORECASE,
)
_PRODUCT_SCOPED_TOPICS = {"recommendation", "storage"}


def _matching_topics(text: str) -> set[str]:
    normalized = text.casefold()
    topics = {
        topic
        for topic, anchors in _TOPIC_ANCHORS.items()
        if any(anchor in normalized for anchor in anchors)
    }
    if (
        _IMPERATIVE_STORE_PRODUCT.search(text)
        or _PRODUCT_AUXILIARY_STORED.search(text)
    ):
        topics.add("storage")
    return topics


def is_relevant_narrative(message: str, content: str) -> bool:
    message_topics = _matching_topics(message)
    shared_topics = message_topics & _matching_topics(content)
    if not shared_topics:
        return False
    unscoped_topics = shared_topics - _PRODUCT_SCOPED_TOPICS
    if unscoped_topics:
        return True
    return bool(
        _PRODUCT_CONTEXT.search(message)
        and _PRODUCT_CONTEXT.search(content)
    )


class CopilotService:
    def __init__(
        self,
        *,
        repository: CopilotRepository,
        knowledge_repository: KnowledgeRepository,
        providers: list[ProviderBinding],
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.repository = repository
        self.knowledge_repository = knowledge_repository
        self.providers = providers
        resolved_provider = embedding_provider or default_embedding_provider()
        self.embedding_provider = (
            resolved_provider
            if resolved_provider is not None
            and embedding_provider_is_allowed(resolved_provider)
            else None
        )

    async def create_case(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        request: CopilotCaseCreate,
        now: datetime | None = None,
    ) -> CopilotCase:
        checked_at = now or datetime.now(UTC)
        raw_classification = classify_customer_message(request.message)
        redacted_message = cast(str, redact(request.message))
        residual_pii = redacted_message == PII_PLACEHOLDER
        classification = merge_safety_classifications(
            raw_classification,
            classify_customer_message(redacted_message),
        )
        risk = classification.risk
        risk_reasons = list(classification.reasons)
        if residual_pii:
            risk = merge_model_risk(risk, CopilotRisk.medium)
            risk_reasons.append("pii_detected")
        case = CopilotCase(
            tenant_id=tenant_id,
            created_by_user_id=user_id,
            message=redacted_message,
            selected_sku_codes=request.selected_sku_codes,
            stage=classification.stage.value,
            intent=classification.intent.value,
            risk=risk.value,
            status=CopilotCaseStatus.handoff_required.value,
            risk_reasons=risk_reasons,
        )
        await self.repository.add_case(case)

        if classification.requires_handoff or residual_pii:
            return case

        skus, knowledge, evidence_failure = await self._load_evidence(
            tenant_id=tenant_id,
            selected_sku_codes=request.selected_sku_codes,
            message=redacted_message,
            now=checked_at,
        )
        if evidence_failure is not None:
            case.risk = merge_model_risk(
                CopilotRisk(case.risk),
                (
                    CopilotRisk.high
                    if evidence_failure == "knowledge_conflict"
                    else CopilotRisk.medium
                ),
            ).value
            case.risk_reasons = [*case.risk_reasons, evidence_failure]
            await self.repository.flush()
            return case

        if not self.providers:
            case.risk_reasons = [*case.risk_reasons, "model_unavailable"]
            await self.repository.flush()
            return case

        prompt = self._prompt(
            message=redacted_message,
            classification=classification.model_dump(mode="json"),
            skus=skus,
            knowledge=knowledge,
        )
        try:
            output = await ModelGateway(
                session=self.repository.session,
                providers=self.providers,
            ).suggest_copilot(
                tenant_id=tenant_id,
                prompt=prompt,
            )
        except (
            InvalidModelOutputError,
            NoQualifiedModelError,
            ProviderUnavailableError,
        ) as exc:
            case.risk_reasons = [
                *case.risk_reasons,
                f"model_{type(exc).__name__}",
            ]
            await self.repository.flush()
            return case

        merged_risk = merge_model_risk(
            CopilotRisk(case.risk),
            CopilotRisk(output.risk_level),
        )
        case.risk = merged_risk.value
        case.stage = CopilotStage(output.stage).value
        case.intent = CopilotIntent(output.intent).value
        if merged_risk in {CopilotRisk.high, CopilotRisk.critical}:
            case.risk_reasons = [*case.risk_reasons, "model_high_risk"]
            await self.repository.flush()
            return case

        if not output.suggestions or not self._valid_output_context(
            output.suggestions,
            skus=skus,
            knowledge=knowledge,
        ):
            case.risk_reasons = [*case.risk_reasons, "invalid_model_evidence"]
            await self.repository.flush()
            return case

        case.status = (
            CopilotCaseStatus.degraded.value
            if output.degraded
            else CopilotCaseStatus.suggestions_ready.value
        )
        for rank, draft in enumerate(output.suggestions[:3], start=1):
            verified_sku = next(
                sku
                for sku in skus
                if sku.sku_code == draft.recommended_sku_code
            )
            suggestion = CopilotSuggestion(
                tenant_id=tenant_id,
                case_id=case.id,
                original_text=self._render_verified_sku_facts(verified_sku),
                rank=rank,
                recommended_sku_code=draft.recommended_sku_code,
                confidence=draft.confidence_score,
                risk_tip=draft.risk_tip,
                degraded=output.degraded,
                model_name=output.model_name,
            )
            self.repository.add_suggestion(suggestion)
            await self.repository.flush()
            for citation in self._citation_snapshots(
                tenant_id=tenant_id,
                suggestion_id=suggestion.id,
                draft=draft,
                skus=skus,
                knowledge=knowledge,
            ):
                self.repository.add_citation(citation)
            await self.repository.flush()
        return case

    async def _load_evidence(
        self,
        *,
        tenant_id: UUID,
        selected_sku_codes: list[str],
        message: str,
        now: datetime,
    ) -> tuple[list[ProductSKURead], list[MerchantKnowledge], str | None]:
        skus: list[ProductSKURead] = []
        if self.embedding_provider is None:
            return [], [], "embedding_provider_unavailable"
        knowledge_service = KnowledgeService(
            self.knowledge_repository,
            self.embedding_provider,
        )
        for sku_code in selected_sku_codes:
            result = await knowledge_service.get_recommendable_sku(
                tenant_id=tenant_id,
                sku_code=sku_code,
                now=now,
            )
            if result.status != "ok" or result.sku is None:
                reason = (
                    "knowledge_conflict"
                    if result.status == "conflict"
                    else f"sku_evidence_{result.status}"
                )
                return [], [], reason
            skus.append(result.sku)

        try:
            query_embedding = self.embedding_provider.embed(message)
            session = getattr(self.repository, "session", None)
            if isinstance(session, AsyncSession):
                async with session.begin_nested():
                    knowledge = await self.knowledge_repository.search_semantic(
                        tenant_id=tenant_id,
                        query_embedding=query_embedding,
                        knowledge_types=[
                            KnowledgeType.faq,
                            KnowledgeType.talking_point,
                            KnowledgeType.origin_story,
                        ],
                        now=now,
                        limit=5,
                        embedding_model=self.embedding_provider.model_name,
                        embedding_version=self.embedding_provider.model_version,
                    )
            else:
                knowledge = await self.knowledge_repository.search_semantic(
                    tenant_id=tenant_id,
                    query_embedding=query_embedding,
                    knowledge_types=[
                        KnowledgeType.faq,
                        KnowledgeType.talking_point,
                        KnowledgeType.origin_story,
                    ],
                    now=now,
                    limit=5,
                    embedding_model=self.embedding_provider.model_name,
                    embedding_version=self.embedding_provider.model_version,
                )
        except Exception:
            return skus, [], "embedding_provider_error"
        knowledge = [
            item
            for item in knowledge
            if is_relevant_narrative(message, item.content)
        ]
        if not skus and not knowledge:
            return [], [], "missing_evidence"
        return skus, knowledge, None

    @staticmethod
    def _prompt(
        *,
        message: str,
        classification: dict[str, object],
        skus: list[ProductSKURead],
        knowledge: list[MerchantKnowledge],
    ) -> dict[str, object]:
        return {
            "message": message,
            "classification": classification,
            "sku_evidence": [
                {
                    "id": str(sku.id),
                    "sku_code": sku.sku_code,
                    "name": sku.name,
                    "price": str(sku.price),
                    "inventory": sku.inventory,
                    "variety": sku.variety,
                    "origin": sku.origin,
                    "orchard": sku.orchard,
                    "taste": sku.taste,
                    "ripeness": sku.ripeness,
                    "specification": sku.specification,
                    "net_weight_grams": sku.net_weight_grams,
                    "sales_regions": sku.sales_regions,
                    "shipping_eta": sku.shipping_eta,
                    "valid_until": (
                        sku.valid_until.isoformat()
                        if sku.valid_until is not None
                        else None
                    ),
                }
                for sku in skus
            ],
            "knowledge_evidence": [
                {
                    "id": str(item.id),
                    "knowledge_type": item.knowledge_type,
                    "content": item.content,
                    "source_name": item.source_name,
                    "valid_until": (
                        item.valid_until.isoformat()
                        if item.valid_until is not None
                        else None
                    ),
                }
                for item in knowledge
            ],
        }

    @staticmethod
    def _valid_output_context(
        suggestions: list[CopilotAgentSuggestion],
        *,
        skus: list[ProductSKURead],
        knowledge: list[MerchantKnowledge],
    ) -> bool:
        allowed_skus = {sku.sku_code for sku in skus}
        skus_by_code = {sku.sku_code: sku for sku in skus}
        allowed_knowledge = {item.id for item in knowledge}
        for suggestion in suggestions:
            if suggestion.recommended_sku_code is None:
                return False
            if suggestion.recommended_sku_code not in allowed_skus:
                return False
            if not set(suggestion.referenced_knowledge_ids) <= allowed_knowledge:
                return False
            if not CopilotService._valid_sku_facts(
                suggestion,
                skus_by_code[suggestion.recommended_sku_code],
            ):
                return False
        return True

    @staticmethod
    def _valid_sku_facts(
        suggestion: CopilotAgentSuggestion,
        sku: ProductSKURead,
    ) -> bool:
        claims = suggestion.fact_claims
        if claims.price != sku.price:
            return False
        if claims.currency.casefold() not in {"cny", "rmb", "¥", "￥"}:
            return False
        if claims.inventory != sku.inventory:
            return False
        if (
            CopilotService._normalized_fact(claims.origin)
            != CopilotService._normalized_fact(sku.origin)
        ):
            return False
        if (
            claims.net_weight_grams != sku.net_weight_grams
        ):
            return False
        if (
            claims.shipping_eta is not None
            and CopilotService._normalized_fact(claims.shipping_eta)
            != CopilotService._normalized_fact(sku.shipping_eta)
        ):
            return False
        return True

    @staticmethod
    def _normalized_fact(value: str | None) -> str | None:
        if value is None:
            return None
        return re.sub(r"\s+", " ", value).strip().casefold()

    @staticmethod
    def _render_verified_sku_facts(sku: ProductSKURead) -> str:
        origin = sku.origin or "未提供"
        net_weight = (
            f"{sku.net_weight_grams} 克"
            if sku.net_weight_grams is not None
            else "未提供"
        )
        return (
            f"推荐 {sku.name}（SKU {sku.sku_code}）。"
            f"价格 CNY {sku.price:.2f}；库存 {sku.inventory}；"
            f"产地 {origin}；净重 {net_weight}。"
        )

    @staticmethod
    def _citation_snapshots(
        *,
        tenant_id: UUID,
        suggestion_id: UUID,
        draft: CopilotAgentSuggestion,
        skus: list[ProductSKURead],
        knowledge: list[MerchantKnowledge],
    ) -> list[CopilotCitationSnapshot]:
        citations: list[CopilotCitationSnapshot] = []
        if draft.recommended_sku_code is not None:
            sku = next(
                item
                for item in skus
                if item.sku_code == draft.recommended_sku_code
            )
            citations.append(
                CopilotCitationSnapshot(
                    tenant_id=tenant_id,
                    suggestion_id=suggestion_id,
                    citation_type=CopilotCitationType.sku.value,
                    source_id=sku.id,
                    source_name=f"SKU {sku.sku_code}",
                    snapshot={
                        "sku_code": sku.sku_code,
                        "name": sku.name,
                        "price": str(sku.price),
                        "inventory": sku.inventory,
                        "origin": sku.origin,
                        "orchard": sku.orchard,
                        "taste": sku.taste,
                        "ripeness": sku.ripeness,
                        "specification": sku.specification,
                        "net_weight_grams": sku.net_weight_grams,
                        "sales_regions": sku.sales_regions,
                        "shipping_eta": sku.shipping_eta,
                        "source_id": str(sku.source_id),
                        "valid_until": (
                            sku.valid_until.isoformat()
                            if sku.valid_until is not None
                            else None
                        ),
                    },
                )
            )
        by_id = {item.id: item for item in knowledge}
        for knowledge_id in dict.fromkeys(draft.referenced_knowledge_ids):
            item = by_id[knowledge_id]
            citations.append(
                CopilotCitationSnapshot(
                    tenant_id=tenant_id,
                    suggestion_id=suggestion_id,
                    citation_type=CopilotCitationType.knowledge.value,
                    source_id=item.id,
                    source_name=item.source_name,
                    snapshot={
                        "knowledge_type": item.knowledge_type,
                        "content": item.content,
                        "source_id": str(item.source_id),
                        "source_name": item.source_name,
                        "review_status": item.review_status,
                        "valid_until": (
                            item.valid_until.isoformat()
                            if item.valid_until is not None
                            else None
                        ),
                    },
                )
            )
        return citations

    async def list_cases(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[CopilotCase]:
        return await self.repository.list_cases(
            tenant_id,
            limit=limit,
            offset=offset,
        )

    async def get_case(
        self,
        tenant_id: UUID,
        case_id: UUID,
    ) -> CopilotCase | None:
        return await self.repository.get_case(tenant_id, case_id)

    async def edit_suggestion(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        suggestion_id: UUID,
        edited_text: str,
    ) -> CopilotSuggestion | None:
        suggestion = await self.repository.get_suggestion(
            tenant_id,
            case_id,
            suggestion_id,
        )
        if suggestion is None:
            return None
        suggestion.edited_text = cast(str, redact(edited_text))
        await self.repository.flush()
        await self.repository.refresh_suggestion(suggestion)
        return suggestion

    async def record_outcome_event(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        idempotency_key: str,
        request: CopilotOutcomeEventCreate,
    ) -> tuple[CopilotOutcomeEvent, CopilotCase, bool] | None:
        case = await self.repository.get_case_for_update(tenant_id, case_id)
        if case is None:
            return None
        existing = await self.repository.get_outcome_by_idempotency_key(
            tenant_id,
            case_id,
            idempotency_key,
        )
        if existing is not None:
            return existing, case, True

        if case.status == CopilotCaseStatus.closed.value:
            raise DomainError(
                code="copilot_case_closed",
                message="copilot case is closed",
                status_code=409,
            )
        if request.suggestion_id is not None:
            suggestion = await self.repository.get_suggestion(
                tenant_id,
                case_id,
                request.suggestion_id,
            )
            if suggestion is None:
                return None

        redacted_metadata = cast(dict[str, Any], redact(request.metadata or {}))
        try:
            event = await self.repository.add_outcome_event(
                CopilotOutcomeEvent(
                    tenant_id=tenant_id,
                    case_id=case_id,
                    suggestion_id=request.suggestion_id,
                    event_type=request.event_type.value,
                    idempotency_key=idempotency_key,
                    occurred_at=request.occurred_at or datetime.now(UTC),
                    metadata_=redacted_metadata,
                )
            )
        except IntegrityError:
            existing = await self.repository.get_outcome_by_idempotency_key(
                tenant_id,
                case_id,
                idempotency_key,
            )
            if existing is not None:
                return existing, case, True
            raise
        if request.event_type.value == "case_closed":
            case.status = CopilotCaseStatus.closed.value
            await self.repository.flush()
        return event, case, False
