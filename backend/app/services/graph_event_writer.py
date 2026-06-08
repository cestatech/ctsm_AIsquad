"""GraphEventWriter — single mandatory entry point for Context Graph events.

Phase 3 contract: all graph mutations emit a standardized, idempotent event
through this writer. ContextGraphService delegates here; services must not
call GraphRepository.append_event() directly.
"""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphEvent
from app.repositories.graph_repository import GraphRepository
from app.schemas.graph_event import (
    GRAPH_EVENT_SCHEMA_VERSION,
    GraphActorType,
    GraphWorkflowAction,
)


class GraphEventWriter:
    """Append-only writer for standardized graph events with idempotency."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = GraphRepository(db)

    async def write(
        self,
        *,
        organization_id: UUID,
        study_id: UUID | None,
        event_type: str,
        action: GraphWorkflowAction,
        entity_type: str,
        entity_id: UUID | None = None,
        actor_type: GraphActorType,
        actor_user_id: UUID | None = None,
        actor_agent_id: str | None = None,
        reason: str | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        metadata: dict | None = None,
        idempotency_key: str | None = None,
        node_id: UUID | None = None,
        edge_id: UUID | None = None,
        ai_decision_id: UUID | None = None,
        extra: dict | None = None,
    ) -> GraphEvent:
        """
        Persist a standardized graph event. Returns existing event when
        idempotency_key was already written for this organization.
        """
        if idempotency_key:
            existing = await self._repo.find_event_by_idempotency_key(
                organization_id, idempotency_key
            )
            if existing is not None:
                return existing

        actor_id = (
            str(actor_user_id) if actor_user_id else actor_agent_id
        )

        payload: dict = {
            "schema_version": GRAPH_EVENT_SCHEMA_VERSION,
            "actor_type": actor_type.value,
            "actor_id": actor_id,
            "action": action.value,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id else None,
            "before_hash": self._hash_state(before_state),
            "after_hash": self._hash_state(after_state),
            "reason": reason,
            "metadata": metadata or {},
        }
        if extra:
            payload.update(extra)

        return await self._repo.append_event(
            organization_id=organization_id,
            study_id=study_id,
            event_type=event_type,
            payload=payload,
            node_id=node_id,
            edge_id=edge_id,
            actor_user_id=actor_user_id,
            actor_agent_id=actor_agent_id,
            ai_decision_id=ai_decision_id,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def node_idempotency_key(
        organization_id: UUID,
        external_type: str,
        external_id: UUID,
    ) -> str:
        return f"node:{organization_id}:{external_type}:{external_id}"

    @staticmethod
    def edge_idempotency_key(
        organization_id: UUID,
        source_node_id: UUID,
        target_node_id: UUID,
        edge_type: str,
    ) -> str:
        raw = (
            f"edge:{organization_id}:{source_node_id}:{target_node_id}:{edge_type}"
        )
        if len(raw) <= 128:
            return raw
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return f"edge:{digest}"

    @staticmethod
    def workflow_idempotency_key(
        organization_id: UUID,
        action: GraphWorkflowAction,
        entity_type: str,
        entity_id: UUID,
    ) -> str:
        return f"wf:{organization_id}:{action.value}:{entity_type}:{entity_id}"

    @staticmethod
    def _hash_state(state: dict | None) -> str | None:
        if state is None:
            return None
        canonical = json.dumps(state, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()


def require_ai_decision_for_generated_edge(
    is_ai_generated: bool,
    ai_decision_id: UUID | None,
) -> None:
    """Enforce Phase 3 rule: AI-generated graph edges require an AIDecision."""
    if is_ai_generated and ai_decision_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "AI_DECISION_REQUIRED",
                "message": "AI-generated graph edges must include ai_decision_id.",
            },
        )
