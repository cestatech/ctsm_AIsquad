"""Repository for Context Graph nodes, edges, and events.

All queries are scoped to organization_id from the caller's JWT. This class
never accepts organization_id from user input — it must always come from
the authenticated user's session.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import (
    GraphEdge,
    GraphEdgeType,
    GraphEvent,
    GraphNode,
    GraphNodeType,
)


class GraphRepository:
    """Database access layer for the Context Graph."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    async def get_node(self, node_id: UUID, organization_id: UUID) -> GraphNode:
        """Fetch a node by ID, org-scoped."""
        result = await self._db.execute(
            select(GraphNode).where(
                GraphNode.id == node_id,
                GraphNode.organization_id == organization_id,
            )
        )
        node = result.scalar_one_or_none()
        if node is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Graph node not found."},
            )
        return node

    async def find_node_by_external(
        self,
        external_id: UUID,
        external_type: str,
        organization_id: UUID,
    ) -> GraphNode | None:
        """Find the graph node that indexes a specific domain record."""
        result = await self._db.execute(
            select(GraphNode).where(
                GraphNode.external_id == external_id,
                GraphNode.external_type == external_type,
                GraphNode.organization_id == organization_id,
                GraphNode.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_nodes(
        self,
        organization_id: UUID,
        study_id: UUID | None = None,
        node_type: GraphNodeType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[GraphNode], int]:
        """List graph nodes with optional filters. Returns (items, total_count)."""
        filters = [
            GraphNode.organization_id == organization_id,
            GraphNode.is_active.is_(True),
        ]
        if study_id is not None:
            filters.append(GraphNode.study_id == study_id)
        if node_type is not None:
            filters.append(GraphNode.node_type == node_type)

        count_result = await self._db.execute(select(GraphNode).where(and_(*filters)))
        total = len(count_result.scalars().all())

        result = await self._db.execute(
            select(GraphNode)
            .where(and_(*filters))
            .order_by(GraphNode.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def create_node(self, node: GraphNode) -> GraphNode:
        """Persist a new graph node."""
        self._db.add(node)
        await self._db.flush()
        await self._db.refresh(node)
        return node

    async def upsert_node_for_domain_record(
        self,
        organization_id: UUID,
        study_id: UUID | None,
        node_type: GraphNodeType,
        external_id: UUID,
        external_type: str,
        label: str,
        description: str | None = None,
        properties: dict | None = None,
        created_by_id: UUID | None = None,
    ) -> tuple[GraphNode, bool]:
        """
        Create or update the graph node that indexes a domain record.
        Returns (node, created: bool).
        """
        existing = await self.find_node_by_external(
            external_id, external_type, organization_id
        )
        if existing is not None:
            existing.label = label
            if description is not None:
                existing.description = description
            if properties is not None:
                existing.properties = properties
            await self._db.flush()
            return existing, False

        node = GraphNode(
            organization_id=organization_id,
            study_id=study_id,
            node_type=node_type,
            external_id=external_id,
            external_type=external_type,
            label=label,
            description=description,
            properties=properties or {},
            created_by_id=created_by_id,
        )
        self._db.add(node)
        await self._db.flush()
        await self._db.refresh(node)
        return node, True

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------

    async def get_edge(self, edge_id: UUID, organization_id: UUID) -> GraphEdge:
        """Fetch an edge by ID, org-scoped."""
        result = await self._db.execute(
            select(GraphEdge).where(
                GraphEdge.id == edge_id,
                GraphEdge.organization_id == organization_id,
            )
        )
        edge = result.scalar_one_or_none()
        if edge is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Graph edge not found."},
            )
        return edge

    async def find_edge(
        self,
        source_node_id: UUID,
        target_node_id: UUID,
        edge_type: GraphEdgeType,
        organization_id: UUID,
    ) -> GraphEdge | None:
        """Find a specific directed edge between two nodes."""
        result = await self._db.execute(
            select(GraphEdge).where(
                GraphEdge.source_node_id == source_node_id,
                GraphEdge.target_node_id == target_node_id,
                GraphEdge.edge_type == edge_type,
                GraphEdge.organization_id == organization_id,
                GraphEdge.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def find_edge_by_idempotency_hash(
        self,
        organization_id: UUID,
        idempotency_key_hash: str,
    ) -> GraphEdge | None:
        """Find an active edge by its hashed idempotency key."""
        result = await self._db.execute(
            select(GraphEdge).where(
                GraphEdge.organization_id == organization_id,
                GraphEdge.idempotency_key_hash == idempotency_key_hash,
                GraphEdge.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_edges_from_node(
        self,
        node_id: UUID,
        organization_id: UUID,
        edge_type: GraphEdgeType | None = None,
    ) -> list[GraphEdge]:
        """All active outgoing edges from a node."""
        filters = [
            GraphEdge.source_node_id == node_id,
            GraphEdge.organization_id == organization_id,
            GraphEdge.is_active.is_(True),
        ]
        if edge_type is not None:
            filters.append(GraphEdge.edge_type == edge_type)

        result = await self._db.execute(
            select(GraphEdge).where(and_(*filters)).order_by(GraphEdge.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_edges_to_node(
        self,
        node_id: UUID,
        organization_id: UUID,
        edge_type: GraphEdgeType | None = None,
    ) -> list[GraphEdge]:
        """All active incoming edges to a node."""
        filters = [
            GraphEdge.target_node_id == node_id,
            GraphEdge.organization_id == organization_id,
            GraphEdge.is_active.is_(True),
        ]
        if edge_type is not None:
            filters.append(GraphEdge.edge_type == edge_type)

        result = await self._db.execute(
            select(GraphEdge).where(and_(*filters)).order_by(GraphEdge.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_edges_for_study(
        self,
        organization_id: UUID,
        study_id: UUID,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[GraphEdge], int]:
        """List all active edges scoped to a study. Returns (items, total_count)."""
        from sqlalchemy import func

        filters = [
            GraphEdge.organization_id == organization_id,
            GraphEdge.study_id == study_id,
            GraphEdge.is_active.is_(True),
        ]

        count_result = await self._db.execute(
            select(func.count()).select_from(GraphEdge).where(and_(*filters))
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(GraphEdge)
            .where(and_(*filters))
            .order_by(GraphEdge.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def create_edge(self, edge: GraphEdge) -> GraphEdge:
        """Persist a new graph edge."""
        self._db.add(edge)
        await self._db.flush()
        await self._db.refresh(edge)
        return edge

    async def upsert_edge(
        self,
        organization_id: UUID,
        study_id: UUID | None,
        source_node_id: UUID,
        target_node_id: UUID,
        edge_type: GraphEdgeType,
        label: str | None = None,
        properties: dict | None = None,
        confidence: float | None = None,
        is_ai_generated: bool = False,
        ai_decision_id: UUID | None = None,
        created_by_id: UUID | None = None,
        idempotency_key_hash: str | None = None,
    ) -> tuple[GraphEdge, bool]:
        """Create or update a directed edge. Returns (edge, created: bool)."""
        if idempotency_key_hash:
            existing = await self.find_edge_by_idempotency_hash(
                organization_id, idempotency_key_hash
            )
        else:
            existing = await self.find_edge(
                source_node_id, target_node_id, edge_type, organization_id
            )
        if existing is not None:
            if confidence is not None:
                existing.confidence = confidence
            if properties is not None:
                existing.properties = properties
            if ai_decision_id is not None:
                existing.ai_decision_id = str(ai_decision_id)
            await self._db.flush()
            return existing, False

        edge = GraphEdge(
            organization_id=organization_id,
            study_id=study_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            label=label,
            properties=properties or {},
            confidence=confidence,
            is_ai_generated=is_ai_generated,
            ai_decision_id=ai_decision_id,
            created_by_id=created_by_id,
            idempotency_key_hash=idempotency_key_hash,
        )
        self._db.add(edge)
        await self._db.flush()
        await self._db.refresh(edge)
        return edge, True

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def append_event(
        self,
        organization_id: UUID,
        study_id: UUID | None,
        event_type: str,
        payload: dict,
        node_id: UUID | None = None,
        edge_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        actor_agent_id: str | None = None,
        ai_decision_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> GraphEvent:
        """Append an immutable event to the graph event log."""
        event = GraphEvent(
            organization_id=organization_id,
            study_id=study_id,
            event_type=event_type,
            node_id=node_id,
            edge_id=edge_id,
            actor_user_id=actor_user_id,
            actor_agent_id=actor_agent_id,
            ai_decision_id=ai_decision_id,
            idempotency_key=idempotency_key,
            payload=payload,
        )
        self._db.add(event)
        await self._db.flush()
        return event

    async def find_event_by_idempotency_key(
        self,
        organization_id: UUID,
        idempotency_key: str,
    ) -> GraphEvent | None:
        """Return an existing event for a given idempotency key, if any."""
        result = await self._db.execute(
            select(GraphEvent).where(
                GraphEvent.organization_id == organization_id,
                GraphEvent.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def list_events(
        self,
        organization_id: UUID,
        study_id: UUID | None = None,
        node_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[GraphEvent], int]:
        """List graph events with optional filters. Returns (items, total)."""
        filters = [GraphEvent.organization_id == organization_id]
        if study_id is not None:
            filters.append(GraphEvent.study_id == study_id)
        if node_id is not None:
            filters.append(GraphEvent.node_id == node_id)
        if actor_user_id is not None:
            filters.append(GraphEvent.actor_user_id == actor_user_id)
        if event_type is not None:
            filters.append(GraphEvent.event_type == event_type)
        if action is not None:
            filters.append(GraphEvent.payload["action"].astext == action)
        if entity_type is not None:
            filters.append(GraphEvent.payload["entity_type"].astext == entity_type)

        count_result = await self._db.execute(
            select(func.count()).select_from(GraphEvent).where(and_(*filters))
        )
        total = count_result.scalar_one()

        result = await self._db.execute(
            select(GraphEvent)
            .where(and_(*filters))
            .order_by(GraphEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def count_nodes_for_study(self, organization_id: UUID, study_id: UUID) -> int:
        result = await self._db.execute(
            select(func.count())
            .select_from(GraphNode)
            .where(
                GraphNode.organization_id == organization_id,
                GraphNode.study_id == study_id,
                GraphNode.is_active.is_(True),
            )
        )
        return result.scalar_one()

    async def count_edges_for_study(self, organization_id: UUID, study_id: UUID) -> int:
        result = await self._db.execute(
            select(func.count())
            .select_from(GraphEdge)
            .where(
                GraphEdge.organization_id == organization_id,
                GraphEdge.study_id == study_id,
                GraphEdge.is_active.is_(True),
            )
        )
        return result.scalar_one()

    async def count_nodes_by_type(
        self, organization_id: UUID, study_id: UUID
    ) -> dict[str, int]:
        result = await self._db.execute(
            select(GraphNode.node_type, func.count())
            .where(
                GraphNode.organization_id == organization_id,
                GraphNode.study_id == study_id,
                GraphNode.is_active.is_(True),
            )
            .group_by(GraphNode.node_type)
        )
        return {
            (row[0].value if hasattr(row[0], "value") else str(row[0])): row[1]
            for row in result.all()
        }
