"""Downstream impact analysis via context graph BFS traversal."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.context_graph_service import ContextGraphService

MAX_IMPACT_DEPTH = 10


@dataclass(frozen=True)
class ImpactedNode:
    id: UUID
    node_type: str
    name: str
    depth: int


@dataclass(frozen=True)
class GapImpactReport:
    node_id: UUID
    impacted_nodes: list[ImpactedNode]


class ImpactAnalysisService:
    """Traverse outgoing graph edges to find downstream affected nodes."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._graph = ContextGraphService(db)

    async def get_downstream_impact(
        self,
        node_id: UUID,
        organization_id: UUID,
        *,
        max_depth: int = MAX_IMPACT_DEPTH,
    ) -> GapImpactReport:
        """BFS from node_id along outgoing edges up to max_depth hops."""
        depth_limit = min(max(max_depth, 1), MAX_IMPACT_DEPTH)
        await self._graph.get_node(node_id, organization_id)

        visited: set[UUID] = {node_id}
        queue: deque[tuple[UUID, int]] = deque([(node_id, 0)])
        impacted: list[ImpactedNode] = []

        while queue:
            current_id, depth = queue.popleft()
            if depth >= depth_limit:
                continue

            neighbors = await self._graph.get_neighbors(
                node_id=current_id,
                organization_id=organization_id,
                direction="outgoing",
            )
            for edge in neighbors["outgoing"]:
                target_id = UUID(str(edge.target_node_id))
                if target_id in visited:
                    continue
                visited.add(target_id)
                node = await self._graph.get_node(target_id, organization_id)
                impacted.append(
                    ImpactedNode(
                        id=node.id,
                        node_type=node.node_type.value,
                        name=node.label,
                        depth=depth + 1,
                    )
                )
                queue.append((target_id, depth + 1))

        return GapImpactReport(node_id=node_id, impacted_nodes=impacted)
