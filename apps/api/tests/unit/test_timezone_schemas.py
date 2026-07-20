from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fruit_agent.copilot.models import CopilotCase, CopilotCitationSnapshot
from fruit_agent.copilot.schemas import (
    CopilotCaseRead,
    CopilotCitationRead,
    CopilotOutcomeEventCreate,
)
from fruit_agent.knowledge.schemas import KnowledgeItemCreate, KnowledgeItemUpdate


def test_knowledge_create_and_update_reject_naive_validity_timestamps() -> None:
    payload = {
        "knowledge_type": "faq",
        "content": "Store apples cold.",
        "source_name": "Handbook",
        "responsible_user_id": uuid4(),
    }

    with pytest.raises(ValidationError, match="timezone"):
        KnowledgeItemCreate.model_validate(
            {**payload, "valid_until": "2030-01-01T12:00:00"}
        )
    with pytest.raises(ValidationError, match="timezone"):
        KnowledgeItemUpdate.model_validate(
            {"valid_until": "2030-01-01T12:00:00"}
        )


def test_knowledge_create_and_renewal_require_future_validity() -> None:
    past = datetime.now(UTC) - timedelta(seconds=1)
    payload = {
        "knowledge_type": "faq",
        "content": "Store apples cold.",
        "source_name": "Handbook",
        "responsible_user_id": uuid4(),
        "valid_until": past,
    }

    with pytest.raises(ValidationError, match="future"):
        KnowledgeItemCreate.model_validate(payload)
    with pytest.raises(ValidationError, match="future"):
        KnowledgeItemUpdate.model_validate({"valid_until": past})


def test_outcome_occurred_at_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        CopilotOutcomeEventCreate.model_validate(
            {
                "event_type": "payment",
                "occurred_at": "2030-01-01T12:00:00",
            }
        )


def test_aware_plus_eight_timestamps_preserve_the_same_instant() -> None:
    item = KnowledgeItemCreate.model_validate(
        {
            "knowledge_type": "faq",
            "content": "Store apples cold.",
            "source_name": "Handbook",
            "responsible_user_id": uuid4(),
            "valid_until": "2030-01-01T12:00:00+08:00",
        }
    )
    outcome = CopilotOutcomeEventCreate.model_validate(
        {
            "event_type": "payment",
            "occurred_at": "2030-01-01T12:00:00+08:00",
        }
    )

    expected = datetime(2030, 1, 1, 4, tzinfo=UTC)
    assert item.valid_until.astimezone(UTC) == expected
    assert outcome.occurred_at is not None
    assert outcome.occurred_at.astimezone(UTC) == expected


def test_0009_orm_metadata_declares_timezone_and_nonnegative_timing() -> None:
    assert CopilotCitationSnapshot.__table__.c.source_updated_at.type.timezone is True
    assert CopilotCitationSnapshot.__table__.c.retrieved_at.type.timezone is True
    constraint_names = {
        constraint.name for constraint in CopilotCase.__table__.constraints
    }
    assert "ck_copilot_cases_response_time_ms" in constraint_names


def test_0009_response_schemas_reject_naive_provenance_and_negative_timing() -> None:
    citation = {
        "id": uuid4(),
        "citation_type": "sku",
        "source_id": uuid4(),
        "source_name": "SKU APPLE-001",
        "snapshot": {},
        "source_updated_at": "2030-01-01T12:00:00",
        "retrieved_at": "2030-01-01T12:00:00Z",
        "created_at": "2030-01-01T12:00:00Z",
    }
    with pytest.raises(ValidationError, match="timezone"):
        CopilotCitationRead.model_validate(citation)

    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        CopilotCaseRead.model_validate(
            {
                "id": uuid4(),
                "tenant_id": uuid4(),
                "created_by_user_id": uuid4(),
                "message": "Where should I store apples?",
                "selected_sku_codes": [],
                "stage": "presale",
                "intent": "storage",
                "risk": "low",
                "status": "suggestions_ready",
                "risk_reasons": [],
                "response_time_ms": -1,
                "handoff_reason": None,
                "conflict_source_ids": [],
                "suggestions": [],
                "created_at": "2030-01-01T12:00:00Z",
                "updated_at": "2030-01-01T12:00:00Z",
            }
        )
