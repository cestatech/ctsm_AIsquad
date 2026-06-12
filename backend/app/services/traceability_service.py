"""Traceability gap detection service.

Walks the canonical Objective → Endpoint → ECR_FIELD → SDTM_VARIABLE →
ADAM_VARIABLE → TLF → CSR_SECTION chain for a given study and returns every
node that has no incoming edge from the immediately preceding stage.

A gap means a node cannot be traced back to an earlier clinical justification,
which is a regulatory risk. Regulators expect full traceability from objectives
through to the final CSR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphEdge, GraphNode, GraphNodeType
from app.services.impact_analysis_service import ImpactAnalysisService, ImpactedNode

# Canonical lineage chain in order
CHAIN: list[GraphNodeType] = [
    GraphNodeType.OBJECTIVE,
    GraphNodeType.ENDPOINT,
    GraphNodeType.ECR_FIELD,
    GraphNodeType.SDTM_VARIABLE,
    GraphNodeType.ADAM_VARIABLE,
    GraphNodeType.TLF,
    GraphNodeType.CSR_SECTION,
]


@dataclass
class TraceabilityGap:
    """A single missing upstream link detected in the traceability chain."""

    node_id: UUID
    node_label: str
    node_type: str
    stage_index: int
    missing_link_from: str
    message: str
    impacted_nodes: list[ImpactedNode] = field(default_factory=list)


@dataclass
class TraceabilityReport:
    """Full gap report for a study."""

    study_id: UUID
    total_nodes: int
    nodes_with_gaps: int
    chain_coverage_pct: float
    gaps: list[TraceabilityGap]


class TraceabilityService:
    """Compute authoritative traceability gaps from the Context Graph."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def compute_gaps(
        self, study_id: UUID, organization_id: UUID
    ) -> TraceabilityReport:
        """
        Walk the CHAIN for the study and return all nodes missing an upstream link.

        Algorithm:
        1. Fetch all active nodes for the study grouped by node_type.
        2. Fetch all active edges for the study.
        3. For each stage after the first, check every node for at least one
           incoming edge whose source belongs to the previous stage.
        4. Nodes with zero such edges are reported as gaps.
        """
        nodes_by_type = await self._fetch_nodes_by_type(study_id, organization_id)
        edges = await self._fetch_edges(study_id, organization_id)

        # Index edge targets → set of source node IDs for O(1) lookups
        target_to_sources: dict[UUID, set[UUID]] = {}
        for edge in edges:
            target_to_sources.setdefault(edge.target_node_id, set()).add(  # type: ignore[arg-type]
                edge.source_node_id  # type: ignore[arg-type]
            )

        all_node_ids_by_type: dict[GraphNodeType, set[UUID]] = {
            t: {n.id for n in nodes_by_type.get(t, [])} for t in CHAIN
        }

        gaps: list[TraceabilityGap] = []
        total_nodes = sum(len(v) for v in nodes_by_type.values())

        for stage_idx in range(1, len(CHAIN)):
            current_type = CHAIN[stage_idx]
            prev_type = CHAIN[stage_idx - 1]
            prev_ids = all_node_ids_by_type[prev_type]

            for node in nodes_by_type.get(current_type, []):
                sources = target_to_sources.get(node.id, set())
                has_upstream = bool(sources & prev_ids)

                if not has_upstream:
                    gaps.append(
                        TraceabilityGap(
                            node_id=node.id,
                            node_label=node.label,
                            node_type=current_type.value,
                            stage_index=stage_idx,
                            missing_link_from=prev_type.value,
                            message=(
                                f"No {prev_type.value} node links to this "
                                f"{current_type.value} node"
                            ),
                        )
                    )

        impact_svc = ImpactAnalysisService(self._db)
        for gap in gaps:
            impact = await impact_svc.get_downstream_impact(
                gap.node_id, organization_id
            )
            gap.impacted_nodes = impact.impacted_nodes

        nodes_with_gaps = len(gaps)
        coverage = (
            round((1 - nodes_with_gaps / total_nodes) * 100, 1)
            if total_nodes > 0
            else 100.0
        )

        return TraceabilityReport(
            study_id=study_id,
            total_nodes=total_nodes,
            nodes_with_gaps=nodes_with_gaps,
            chain_coverage_pct=coverage,
            gaps=gaps,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_nodes_by_type(
        self, study_id: UUID, organization_id: UUID
    ) -> dict[GraphNodeType, list[GraphNode]]:
        result = await self._db.execute(
            select(GraphNode).where(
                and_(
                    GraphNode.study_id == study_id,
                    GraphNode.organization_id == organization_id,
                    GraphNode.node_type.in_([t.value for t in CHAIN]),
                    GraphNode.is_active.is_(True),
                )
            )
        )
        nodes = list(result.scalars().all())
        grouped: dict[GraphNodeType, list[GraphNode]] = {}
        for node in nodes:
            key = GraphNodeType(node.node_type)
            grouped.setdefault(key, []).append(node)
        return grouped

    async def _fetch_edges(
        self, study_id: UUID, organization_id: UUID
    ) -> list[GraphEdge]:
        result = await self._db.execute(
            select(GraphEdge).where(
                and_(
                    GraphEdge.study_id == study_id,
                    GraphEdge.organization_id == organization_id,
                    GraphEdge.is_active.is_(True),
                )
            )
        )
        return list(result.scalars().all())
