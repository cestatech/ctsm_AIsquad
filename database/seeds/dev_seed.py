"""
Development seed: one org, one study, three users (Admin / Contributor / Reviewer).

Usage (from backend/):
    .venv/bin/python ../database/seeds/dev_seed.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Allow running from anywhere
sys.path.insert(0, str(Path(__file__).parents[2] / "backend"))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.study import Study, StudyStatus
from app.models.user import User

settings = get_settings()

ORG_ID = uuid4()
ADMIN_ID = uuid4()
CONTRIBUTOR_ID = uuid4()
REVIEWER_ID = uuid4()
STUDY_ID = uuid4()

PASSWORD = "DevPass123!"


async def seed() -> None:
    engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        async with session.begin():
            await _seed(session)

    await engine.dispose()
    print("Seed complete.")
    print(f"  Org:         Demo Pharma Inc  (id={ORG_ID})")
    print(f"  Admin:       admin@demo.dev    (id={ADMIN_ID})  pw={PASSWORD}")
    print(f"  Contributor: contrib@demo.dev  (id={CONTRIBUTOR_ID})  pw={PASSWORD}")
    print(f"  Reviewer:    reviewer@demo.dev (id={REVIEWER_ID})  pw={PASSWORD}")
    print(f"  Study:       DEMO-001          (id={STUDY_ID})")


async def _seed(db: AsyncSession) -> None:
    org = Organization(
        id=ORG_ID,
        name="Demo Pharma Inc",
        slug="demo-pharma",
        description="Development seed organisation",
        is_active=True,
    )
    db.add(org)

    admin = User(
        id=ADMIN_ID,
        organization_id=ORG_ID,
        email="admin@demo.dev",
        full_name="Demo Admin",
        hashed_password=hash_password(PASSWORD),
        is_active=True,
        is_system_admin=True,
        org_role=Role.ADMIN,
    )
    contributor = User(
        id=CONTRIBUTOR_ID,
        organization_id=ORG_ID,
        email="contrib@demo.dev",
        full_name="Demo Contributor",
        hashed_password=hash_password(PASSWORD),
        is_active=True,
        is_system_admin=False,
        org_role=Role.CONTRIBUTOR,
    )
    reviewer = User(
        id=REVIEWER_ID,
        organization_id=ORG_ID,
        email="reviewer@demo.dev",
        full_name="Demo Reviewer",
        hashed_password=hash_password(PASSWORD),
        is_active=True,
        is_system_admin=False,
        org_role=Role.REVIEWER,
    )
    db.add_all([admin, contributor, reviewer])

    study = Study(
        id=STUDY_ID,
        organization_id=ORG_ID,
        protocol_number="DEMO-001",
        name="Phase II Oncology Pilot Study",
        description="Development seed study for smoke testing",
        status=StudyStatus.ACTIVE,
        created_by_id=ADMIN_ID,
    )
    db.add(study)


if __name__ == "__main__":
    asyncio.run(seed())
