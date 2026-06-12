#!/usr/bin/env python
"""Register existing active artifacts and versions in the Context Graph."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.artifact import Artifact
from app.services.artifact_service import ArtifactService


async def backfill(*, dry_run: bool = False) -> int:
    async with async_session_factory() as db:
        result = await db.execute(
            select(Artifact)
            .where(Artifact.deleted_at.is_(None))
            .order_by(Artifact.created_at.asc())
        )
        artifacts = list(result.scalars().all())

        if dry_run:
            return len(artifacts)

        service = ArtifactService(db)
        for artifact in artifacts:
            await service.register_artifact_in_graph(artifact)
        await db.commit()
        return len(artifacts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the number of active artifacts without writing graph records.",
    )
    args = parser.parse_args()
    count = asyncio.run(backfill(dry_run=args.dry_run))
    action = "would register" if args.dry_run else "registered"
    print(f"{action} {count} active artifact(s)")


if __name__ == "__main__":
    main()
