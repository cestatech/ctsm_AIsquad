"""Unit tests for GraphEventWriter and AI edge enforcement."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.graph_event import GraphActorType, GraphWorkflowAction
from app.services.graph_event_writer import (
    GraphEventWriter,
    require_ai_decision_for_generated_edge,
)


def _make_event(event_id=None):
    event = MagicMock()
    event.id = event_id or uuid4()
    return event


@pytest.mark.asyncio
class TestGraphEventWriter:
    async def test_write_persists_standardized_payload(self):
        db = AsyncMock()
        writer = GraphEventWriter(db)
        writer._repo.append_event = AsyncMock(return_value=_make_event())
        writer._repo.find_event_by_idempotency_key = AsyncMock(return_value=None)

        org_id = uuid4()
        entity_id = uuid4()
        study_id = uuid4()
        user_id = uuid4()

        event = await writer.write(
            organization_id=org_id,
            study_id=study_id,
            event_type="TEST_EVENT",
            action=GraphWorkflowAction.CREATED,
            entity_type="artifact",
            entity_id=entity_id,
            actor_type=GraphActorType.USER,
            actor_user_id=user_id,
            reason="test reason",
            after_state={"status": "DRAFT"},
            metadata={"source": "unit_test"},
        )

        assert event.id is not None
        call_kwargs = writer._repo.append_event.await_args.kwargs
        assert call_kwargs["organization_id"] == org_id
        assert call_kwargs["study_id"] == study_id
        payload = call_kwargs["payload"]
        assert payload["schema_version"] == "1.0"
        assert payload["action"] == "created"
        assert payload["entity_type"] == "artifact"
        assert payload["entity_id"] == str(entity_id)
        assert payload["reason"] == "test reason"
        assert payload["metadata"] == {"source": "unit_test"}
        assert payload["after_hash"] is not None

    async def test_idempotency_key_returns_existing_event(self):
        db = AsyncMock()
        writer = GraphEventWriter(db)
        existing = _make_event()
        writer._repo.find_event_by_idempotency_key = AsyncMock(return_value=existing)
        writer._repo.append_event = AsyncMock()

        org_id = uuid4()
        key = f"test:{uuid4()}"
        kwargs = dict(
            organization_id=org_id,
            study_id=None,
            event_type="NODE_CREATED",
            action=GraphWorkflowAction.CREATED,
            entity_type="artifact",
            entity_id=uuid4(),
            actor_type=GraphActorType.SYSTEM,
            idempotency_key=key,
        )

        result = await writer.write(**kwargs)

        assert result is existing
        writer._repo.append_event.assert_not_called()

    async def test_node_idempotency_key_is_deterministic(self):
        org_id = uuid4()
        external_id = uuid4()
        k1 = GraphEventWriter.node_idempotency_key(org_id, "artifact", external_id)
        k2 = GraphEventWriter.node_idempotency_key(org_id, "artifact", external_id)
        assert k1 == k2
        assert k1.startswith("node:")

    def test_edge_idempotency_key_fits_varchar_128(self):
        org_id = uuid4()
        source_id = uuid4()
        target_id = uuid4()
        key = GraphEventWriter.edge_idempotency_key(
            org_id, source_id, target_id, "GENERATED_FROM"
        )
        assert len(key) <= 128
        assert key.startswith("edge:")


class TestRequireAiDecisionForGeneratedEdge:
    def test_ai_edge_without_decision_raises_422(self):
        with pytest.raises(HTTPException) as exc:
            require_ai_decision_for_generated_edge(True, None)
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "AI_DECISION_REQUIRED"

    def test_ai_edge_with_decision_passes(self):
        require_ai_decision_for_generated_edge(True, uuid4())

    def test_human_edge_without_decision_passes(self):
        require_ai_decision_for_generated_edge(False, None)
