"""Pydantic schemas for Context Graph API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.graph import GraphEdgeType, GraphNodeType


class GraphNodeResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID | None
    node_type: GraphNodeType
    external_id: UUID | None
    external_type: str | None
    label: str
    description: str | None
    properties: dict
    is_active: bool
    created_by_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GraphEdgeResponse(BaseModel):
    id: UUID
    organization_id: UUID
    study_id: UUID | None
    source_node_id: UUID
    target_node_id: UUID
    edge_type: GraphEdgeType
    label: str | None
    properties: dict
    confidence: float | None
    is_ai_generated: bool
    ai_decision_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GraphNodeListResponse(BaseModel):
    items: list[GraphNodeResponse]
    total: int
    page: int
    page_size: int


class GraphNeighborsResponse(BaseModel):
    node: GraphNodeResponse
    outgoing: list[GraphEdgeResponse]
    incoming: list[GraphEdgeResponse]


class GraphLineageResponse(BaseModel):
    node_id: UUID
    upstream: list[dict]
    downstream: list[dict]


class RegisterNodeRequest(BaseModel):
    node_type: GraphNodeType
    external_id: UUID
    external_type: str
    label: str = Field(max_length=512)
    study_id: UUID | None = None
    description: str | None = None
    properties: dict = Field(default_factory=dict)


class CreateEdgeRequest(BaseModel):
    source_node_id: UUID
    target_node_id: UUID
    edge_type: GraphEdgeType
    study_id: UUID | None = None
    label: str | None = Field(None, max_length=256)
    properties: dict = Field(default_factory=dict)
    confidence: float | None = Field(None, ge=0.0, le=1.0)
