"""Standard Context Graph event contract (Phase 3).

Every major workflow action must emit a graph event using this schema so
events are queryable by study, entity, actor, and action.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class GraphActorType(str, Enum):
    USER = "user"
    AI_AGENT = "ai_agent"
    SYSTEM = "system"


class GraphWorkflowAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    GENERATED = "generated"
    UPLOADED = "uploaded"
    PARSED = "parsed"
    MAPPED = "mapped"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    LOCKED = "locked"
    OVERRIDDEN = "overridden"
    REVIEWED = "reviewed"
    LINKED = "linked"


GRAPH_EVENT_SCHEMA_VERSION = "1.0"


class GraphEventPayload(BaseModel):
    """Canonical payload stored inside GraphEvent.payload JSONB."""

    schema_version: str = GRAPH_EVENT_SCHEMA_VERSION
    actor_type: GraphActorType
    actor_id: str | None = None
    action: GraphWorkflowAction
    entity_type: str
    entity_id: str | None = None
    before_hash: str | None = None
    after_hash: str | None = None
    reason: str | None = None
    metadata: dict = Field(default_factory=dict)


class GraphEventResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID | None
    event_type: str
    node_id: UUID | None
    edge_id: UUID | None
    actor_user_id: UUID | None
    actor_agent_id: str | None
    ai_decision_id: UUID | None
    idempotency_key: str | None
    payload: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class GraphEventListResponse(BaseModel):
    items: list[GraphEventResponse]
    total: int
    page: int
    page_size: int


class GraphStudySummaryResponse(BaseModel):
    study_id: UUID
    node_count: int
    edge_count: int
    event_count: int
    nodes_by_type: dict[str, int]
    recent_events: list[GraphEventResponse]


class GraphEntityRelationshipsResponse(BaseModel):
    external_type: str
    external_id: UUID
    node: dict | None
    outgoing: list[dict]
    incoming: list[dict]


class GraphImpactResponse(BaseModel):
    node_id: UUID
    affected_downstream_count: int
    affected_nodes: list[dict]
    affected_edges: list[dict]


class GraphAIDecisionSummary(BaseModel):
    """AI decision linked to a graph node or edge."""

    id: UUID
    agent_name: str
    decision_type: str
    reasoning: str | None
    confidence: float | None
    status: str
    link_source: str
    edge_type: str | None = None
    edge_id: UUID | None = None


class GraphNodeContextResponse(BaseModel):
    """Full node context including neighbors and linked AI reasoning."""

    node: dict
    outgoing: list[dict]
    incoming: list[dict]
    ai_decisions: list[GraphAIDecisionSummary]
