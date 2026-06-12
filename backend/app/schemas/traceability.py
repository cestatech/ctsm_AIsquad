"""Pydantic schemas for traceability gap and impact analysis."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ImpactedNode(BaseModel):
    id: UUID
    node_type: str
    name: str
    depth: int = Field(ge=1)


class GapImpactReport(BaseModel):
    node_id: UUID
    impacted_nodes: list[ImpactedNode] = Field(default_factory=list)
