from __future__ import annotations

from datetime import UTC, datetime
import re
from uuid import UUID

from fruit_agent.common.redaction import redact_text
from fruit_agent.copilot.models import (
    CopilotCase,
    CopilotCitationSnapshot,
    CopilotSuggestion,
)
from fruit_agent.copilot.repository import CopilotRepository
from fruit_agent.copilot.safety import classify_customer_message, merge_model_risk
from fruit_agent.copilot.schemas import (
    CopilotCaseCreate,
    CopilotCaseStatus,
    CopilotCitationType,
    CopilotIntent,
    CopilotRisk,
    CopilotStage,
)
from fruit_agent.knowledge.embeddings import DeterministicEmbeddingProvider
from fruit_agent.knowledge.models import KnowledgeType, MerchantKnowledge, ProductSKU
from fruit_agent.knowledge.repository import KnowledgeRepository
from fruit_agent.knowledge.service import KnowledgeService
from fruit_agent.model_gateway.schemas import CopilotAgentSuggestion
from fruit_agent.model_gateway.service import (
    InvalidModelOutputError,
    ModelGateway,
    NoQualifiedModelError,
    ProviderBinding,
    ProviderUnavailableError,
)

_IRRELEVANT_TERMS = {
    "一下",
    "什么",
    "你们",
    "可以",
    "应该",
    "怎么",
    "这个",
    "我们",
    "about",
    "could",
    "please",
    "should",
    "that",
    "this",
    "what",
    "with",
    "would",
}


def _relevance_terms(text: str) -> set[str]:
    terms = {
        word
        for word in re.findall(r"[a-z0-9]+", text.casefold())
        if len(word) >= 3 and word not in _IRRELEVANT_TERMS
    }
    for sequence in re.findall(r"[\u3400-\u9fff]+", text):
        terms.update(
            sequence[index : index + 2]
            for index in range(len(sequence) - 1)
        )
    return terms - _IRRELEVANT_TERMS


def is_relevant_narrative(message: str, content: str) -> bool:
    return bool(_relevance_terms(message) & _relevance_terms(content))


class CopilotService:
    def __init__(
        self,
        *,
        repository: CopilotRepository,
        knowledge_repository: KnowledgeRepository,
        providers: list[ProviderBinding],
    ) -> None:
        self.repository = repository
        self.knowledge_repository = knowledge_repository
        self.providers = providers

    async def create_case(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        request: CopilotCaseCreate,
        now: datetime | None = None,
    ) -> CopilotCase:
        checked_at = now or datetime.now(UTC)
        redacted_message = redact_text(request.message)
        classification = classify_customer_message(redacted_message)
        case = CopilotCase(
            tenant_id=tenant_id,
            created_by_user_id=user_id,
            message=redacted_message,
            selected_sku_codes=request.selected_sku_codes,
            stage=classification.stage.value,
            intent=classification.intent.value,
            risk=classification.risk.value,
            status=CopilotCaseStatus.handoff_required.value,
            risk_reasons=list(classification.reasons),
        )
        await self.repository.add_case(case)

        if classification.requires_handoff:
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
            suggestion = CopilotSuggestion(
                tenant_id=tenant_id,
                case_id=case.id,
                original_text=draft.suggestion_text,
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
    ) -> tuple[list[ProductSKU], list[MerchantKnowledge], str | None]:
        skus: list[ProductSKU] = []
        knowledge_service = KnowledgeService(self.knowledge_repository)
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
            rows = await self.knowledge_repository.get_sku_exact(
                tenant_id,
                sku_code,
            )
            skus.append(rows[0])

        knowledge = await self.knowledge_repository.search_semantic(
            tenant_id=tenant_id,
            query_embedding=DeterministicEmbeddingProvider().embed(message),
            knowledge_types=[
                KnowledgeType.faq,
                KnowledgeType.talking_point,
                KnowledgeType.origin_story,
            ],
            now=now,
            limit=5,
        )
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
        skus: list[ProductSKU],
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
                    "origin": sku.origin,
                    "taste": sku.taste,
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
        skus: list[ProductSKU],
        knowledge: list[MerchantKnowledge],
    ) -> bool:
        allowed_skus = {sku.sku_code for sku in skus}
        allowed_knowledge = {item.id for item in knowledge}
        for suggestion in suggestions:
            if (
                suggestion.recommended_sku_code is not None
                and suggestion.recommended_sku_code not in allowed_skus
            ):
                return False
            if not set(suggestion.referenced_knowledge_ids) <= allowed_knowledge:
                return False
            has_sku_citation = suggestion.recommended_sku_code is not None
            has_knowledge_citation = bool(suggestion.referenced_knowledge_ids)
            if not has_sku_citation and not has_knowledge_citation:
                return False
        return True

    @staticmethod
    def _citation_snapshots(
        *,
        tenant_id: UUID,
        suggestion_id: UUID,
        draft: CopilotAgentSuggestion,
        skus: list[ProductSKU],
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
        suggestion.edited_text = redact_text(edited_text)
        await self.repository.flush()
        await self.repository.refresh_suggestion(suggestion)
        return suggestion
