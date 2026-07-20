from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fruit_agent.copilot.models import (
    CopilotCase,
    CopilotCitationSnapshot,
    CopilotSuggestion,
)


class CopilotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_case(self, case: CopilotCase) -> CopilotCase:
        self.session.add(case)
        await self.session.flush()
        return case

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh_suggestion(
        self,
        suggestion: CopilotSuggestion,
    ) -> None:
        await self.session.refresh(
            suggestion,
            attribute_names=["updated_at"],
        )

    async def list_cases(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[CopilotCase]:
        rows = await self.session.scalars(
            select(CopilotCase)
            .where(CopilotCase.tenant_id == tenant_id)
            .options(
                selectinload(CopilotCase.suggestions).selectinload(
                    CopilotSuggestion.citations
                )
            )
            .order_by(CopilotCase.created_at.desc(), CopilotCase.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(rows)

    async def get_case(
        self,
        tenant_id: UUID,
        case_id: UUID,
    ) -> CopilotCase | None:
        rows = await self.session.scalars(
            select(CopilotCase)
            .where(
                CopilotCase.tenant_id == tenant_id,
                CopilotCase.id == case_id,
            )
            .options(
                selectinload(CopilotCase.suggestions).selectinload(
                    CopilotSuggestion.citations
                )
            )
            .execution_options(populate_existing=True)
        )
        return rows.one_or_none()

    async def get_suggestion(
        self,
        tenant_id: UUID,
        case_id: UUID,
        suggestion_id: UUID,
    ) -> CopilotSuggestion | None:
        rows = await self.session.scalars(
            select(CopilotSuggestion)
            .join(
                CopilotCase,
                (CopilotCase.tenant_id == CopilotSuggestion.tenant_id)
                & (CopilotCase.id == CopilotSuggestion.case_id),
            )
            .where(
                CopilotSuggestion.tenant_id == tenant_id,
                CopilotSuggestion.case_id == case_id,
                CopilotSuggestion.id == suggestion_id,
                CopilotCase.tenant_id == tenant_id,
            )
            .options(selectinload(CopilotSuggestion.citations))
        )
        return rows.one_or_none()

    def add_suggestion(self, suggestion: CopilotSuggestion) -> None:
        self.session.add(suggestion)

    def add_citation(self, citation: CopilotCitationSnapshot) -> None:
        self.session.add(citation)
