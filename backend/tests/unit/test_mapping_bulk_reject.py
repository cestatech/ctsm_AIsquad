"""Unit tests for bulk mapping rejection helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.repositories.raw_data_repository import RawFieldRepository


@pytest.mark.asyncio
class TestGetMappingsByIds:
    async def test_different_organization_returns_403(self):
        db = AsyncMock()
        repo = RawFieldRepository(db)
        org_id = uuid4()
        other_org_id = uuid4()
        dataset_id = uuid4()
        field_id = uuid4()

        field = MagicMock()
        field.id = field_id
        field.organization_id = other_org_id
        field.raw_dataset_id = dataset_id

        result = MagicMock()
        result.scalars.return_value.all.return_value = [field]
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(HTTPException) as exc:
            await repo.get_mappings_by_ids([field_id], dataset_id, org_id)

        assert exc.value.status_code == 403
