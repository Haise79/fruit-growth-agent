from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fruit_agent.db import tenant_session
from fruit_agent.identity.models import Membership, Tenant, User

ADMIN_URL = "postgresql+psycopg://fruit_agent:fruit_agent@localhost:5432/fruit_agent"
APP_URL = (
    "postgresql+psycopg://fruit_agent_app:fruit_agent_app@localhost:5432/fruit_agent"
)


@pytest.fixture(scope="module", autouse=True)
def migrated_database() -> Iterator[None]:
    api_root = Path(__file__).parents[2]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "migrations"))
    os.environ["DATABASE_URL"] = ADMIN_URL

    command.upgrade(config, "head")
    with psycopg.connect(
        "postgresql://fruit_agent:fruit_agent@localhost:5432/fruit_agent",
        autocommit=True,
    ) as connection:
        connection.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fruit_agent_app') THEN
                    CREATE ROLE fruit_agent_app
                        LOGIN PASSWORD 'fruit_agent_app'
                        NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
                END IF;
            END
            $$;
            """
        )
        connection.execute("GRANT USAGE ON SCHEMA public TO fruit_agent_app")
        connection.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
            "TO fruit_agent_app"
        )

    yield

    command.downgrade(config, "base")


async def test_rls_hides_other_tenant_memberships() -> None:
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    user_a_id = uuid4()
    membership_a_id = uuid4()
    admin_engine = create_async_engine(ADMIN_URL)

    async with admin_engine.begin() as connection:
        await connection.execute(
            insert(Tenant),
            [
                {"id": tenant_a_id, "name": "Tenant A"},
                {"id": tenant_b_id, "name": "Tenant B"},
            ],
        )
        await connection.execute(
            insert(User),
            {
                "id": user_a_id,
                "tenant_id": tenant_a_id,
                "email": "a@example.com",
            },
        )
        await connection.execute(
            insert(Membership),
            {
                "id": membership_a_id,
                "tenant_id": tenant_a_id,
                "user_id": user_a_id,
                "role": "owner",
                "status": "active",
            },
        )

    app_engine = create_async_engine(APP_URL)
    session_factory = async_sessionmaker(app_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        async with tenant_session(session, tenant_b_id):
            rows = (
                await session.scalars(
                    select(Membership).where(Membership.tenant_id == tenant_b_id)
                )
            ).all()

    await app_engine.dispose()
    await admin_engine.dispose()

    assert rows == []
