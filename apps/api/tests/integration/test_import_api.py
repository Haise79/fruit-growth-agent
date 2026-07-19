from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fruit_agent.app import app
from fruit_agent.db import SessionFactory, engine, get_session
from fruit_agent.identity.dependencies import get_principal
from fruit_agent.identity.models import Role, Tenant, User
from fruit_agent.identity.schemas import TenantPrincipal
from fruit_agent.knowledge.models import ProductSKU


@pytest.fixture
async def import_database() -> AsyncIterator[None]:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    try:
        yield
    finally:
        await engine.dispose()
        command.downgrade(config, "base")


@pytest.mark.asyncio
async def test_import_api_writes_only_valid_rows_for_principal_tenant(
    import_database: None,
) -> None:
    del import_database
    tenant_id = uuid4()
    user_id = uuid4()
    future = datetime.now(UTC) + timedelta(days=30)
    async with SessionFactory() as seed:
        seed.add(Tenant(id=tenant_id, name="Import Tenant", valid_until=future))
        await seed.flush()
        seed.add(
            User(
                id=user_id,
                tenant_id=tenant_id,
                email="importer@example.com",
                valid_until=future,
            )
        )
        await seed.commit()

    principal = TenantPrincipal(
        tenant_id=tenant_id,
        user_id=user_id,
        role=Role.operator,
    )
    session: AsyncSession = SessionFactory()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_principal] = lambda: principal
    csv_content = (
        Path(__file__).parents[1] / "fixtures" / "products_mixed.csv"
    ).read_bytes()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/imports/products",
                files={"file": ("products.csv", csv_content, "text/csv")},
            )
        rows = list(
            await session.scalars(
                select(ProductSKU).where(
                    ProductSKU.tenant_id == tenant_id,
                    ProductSKU.sku_code == "A1",
                )
            )
        )
    finally:
        app.dependency_overrides.clear()
        await session.close()

    assert response.status_code == 200
    assert response.json()["imported_rows"] == 1
    assert response.json()["failed_rows"] == 1
    assert len(rows) == 1
    assert rows[0].tenant_id == tenant_id
