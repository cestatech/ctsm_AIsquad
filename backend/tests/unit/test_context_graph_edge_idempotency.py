"""Unit tests for graph edge idempotency key hashing (Issue #10)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.graph import GraphEdgeType
from app.repositories.graph_repository import GraphRepository
from app.services.context_graph_service import (
    ContextGraphService,
    edge_idempotency_key_hash,
    edge_idempotency_raw_key,
)


class TestEdgeIdempotencyKeyHelpers:
    def test_short_key_returns_no_hash(self):
        source_id = uuid4()
        target_id = uuid4()
        raw = edge_idempotency_raw_key(source_id, "PART_OF", target_id)
        assert edge_idempotency_key_hash(raw) is None

    def test_long_key_returns_sha256_hexdigest(self):
        source_id = uuid4()
        target_id = uuid4()
        long_type = "OBJECTIVE_MAPS_TO_PRIMARY_ENDPOINT_VIA_PROTOCOL_SECTION" + (
            "X" * 200
        )
        raw = edge_idempotency_raw_key(source_id, long_type, target_id)
        assert len(raw) > 200
        digest = edge_idempotency_key_hash(raw)
        assert digest is not None
        assert len(digest) == 64
        assert digest == edge_idempotency_key_hash(raw)


@pytest.mark.asyncio
class TestContextGraphServiceEdgeIdempotency:
    async def test_create_relationship_short_key_passes_no_hash(self):
        db = AsyncMock()
        svc = ContextGraphService(db)
        existing_edge = MagicMock()
        svc._repo.upsert_edge = AsyncMock(return_value=(existing_edge, True))
        svc._events.write = AsyncMock()

        org_id = uuid4()
        source_id = uuid4()
        target_id = uuid4()

        await svc.create_relationship(
            organization_id=org_id,
            source_node_id=source_id,
            target_node_id=target_id,
            edge_type=GraphEdgeType.PART_OF,
        )

        call_kwargs = svc._repo.upsert_edge.await_args.kwargs
        assert call_kwargs["idempotency_key_hash"] is None

    async def test_create_relationship_long_key_passes_hash(self):
        db = AsyncMock()
        svc = ContextGraphService(db)
        existing_edge = MagicMock()
        svc._repo.upsert_edge = AsyncMock(return_value=(existing_edge, True))
        svc._events.write = AsyncMock()

        org_id = uuid4()
        source_id = uuid4()
        target_id = uuid4()
        long_edge_type = MagicMock()
        long_edge_type.value = "A" * 250

        await svc.create_relationship(
            organization_id=org_id,
            source_node_id=source_id,
            target_node_id=target_id,
            edge_type=long_edge_type,
        )

        raw = edge_idempotency_raw_key(source_id, long_edge_type.value, target_id)
        expected_hash = edge_idempotency_key_hash(raw)
        call_kwargs = svc._repo.upsert_edge.await_args.kwargs
        assert call_kwargs["idempotency_key_hash"] == expected_hash
        assert expected_hash is not None


@pytest.mark.asyncio
class TestGraphRepositoryEdgeIdempotency:
    async def test_upsert_edge_duplicate_long_key_is_idempotent(self):
        db = AsyncMock()
        repo = GraphRepository(db)
        org_id = uuid4()
        source_id = uuid4()
        target_id = uuid4()
        key_hash = "a" * 64
        existing = MagicMock()

        repo.find_edge_by_idempotency_hash = AsyncMock(return_value=existing)
        repo.find_edge = AsyncMock()

        edge, created = await repo.upsert_edge(
            organization_id=org_id,
            study_id=None,
            source_node_id=source_id,
            target_node_id=target_id,
            edge_type=GraphEdgeType.PART_OF,
            idempotency_key_hash=key_hash,
        )

        assert edge is existing
        assert created is False
        repo.find_edge.assert_not_called()
        db.add.assert_not_called()
