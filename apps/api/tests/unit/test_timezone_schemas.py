from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fruit_agent.copilot.schemas import CopilotOutcomeEventCreate
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
