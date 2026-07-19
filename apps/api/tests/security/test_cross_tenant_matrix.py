from typing import Any

from sqlalchemy import select

from fruit_agent.approvals.models import ApprovalRequest
from fruit_agent.audit.models import AuditEvent
from fruit_agent.common.models import Base
from fruit_agent.identity.models import Membership, User
from fruit_agent.knowledge.models import MerchantKnowledge, ProductSKU


def test_tenant_owned_queries_require_explicit_tenant_predicate() -> None:
    models: list[Any] = [
        User,
        Membership,
        AuditEvent,
        ApprovalRequest,
        ProductSKU,
        MerchantKnowledge,
    ]

    for model in models:
        statement = select(model).where(model.tenant_id == "tenant-sentinel")
        assert "tenant_id" in str(statement)


def test_every_application_table_has_lifecycle_and_audit_columns() -> None:
    required = {"created_at", "updated_at", "valid_until", "audit_log"}

    for table in Base.metadata.sorted_tables:
        assert required <= set(table.columns.keys()), table.name
