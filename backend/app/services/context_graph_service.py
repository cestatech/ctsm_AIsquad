"""Context Graph service — writes and reads the intelligence graph.

This service is the single entry point for registering entities, creating
relationships, and querying the graph. Every AI agent and every domain
service that wants to participate in traceability calls this service.

The graph never replaces the domain tables — it indexes them. A node's
authoritative data lives in the domain table; the node here is a lightweight
pointer with a node_type label and a JSONB properties bag for denormalized
display data.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphEdge, GraphEdgeType, GraphNode, GraphNodeType
from app.models.user import User
from app.repositories.graph_repository import GraphRepository


class ContextGraphService:
    """
    Manages the Context Graph. Call from domain services and AI agents.

    Example — when an artifact is created:
        await context_graph.register_artifact(artifact, user)

    Example — when the SDTM agent maps an ECR field to a SDTM variable:
        await context_graph.link_ecr_to_sdtm(
            ecr_node_id, sdtm_node_id, confidence=0.92,
            ai_decision_id=decision.id, actor=None
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = GraphRepository(db)

    # ------------------------------------------------------------------
    # Domain record registration
    # ------------------------------------------------------------------

    async def register_domain_record(
        self,
        organization_id: UUID,
        node_type: GraphNodeType,
        external_id: UUID,
        external_type: str,
        label: str,
        study_id: UUID | None = None,
        description: str | None = None,
        properties: dict | None = None,
        actor: User | None = None,
        actor_agent_id: str | None = None,
    ) -> tuple[GraphNode, bool]:
        """
        Register or update a domain record as a graph node.

        Returns (node, created: bool). Emits a graph event.
        This is idempotent — calling it twice for the same external_id/type
        will update the label and properties without creating a duplicate node.
        """
        node, created = await self._repo.upsert_node_for_domain_record(
            organization_id=organization_id,
            study_id=study_id,
            node_type=node_type,
            external_id=external_id,
            external_type=external_type,
            label=label,
            description=description,
            properties=properties,
            created_by_id=actor.id if actor else None,
        )

        await self._repo.append_event(
            organization_id=organization_id,
            study_id=study_id,
            event_type="NODE_CREATED" if created else "NODE_UPDATED",
            payload={
                "node_type": node_type.value,
                "external_type": external_type,
                "external_id": str(external_id),
                "label": label,
            },
            node_id=node.id,
            actor_user_id=actor.id if actor else None,
            actor_agent_id=actor_agent_id,
        )

        return node, created

    # ------------------------------------------------------------------
    # Relationship creation
    # ------------------------------------------------------------------

    async def create_relationship(
        self,
        organization_id: UUID,
        source_node_id: UUID,
        target_node_id: UUID,
        edge_type: GraphEdgeType,
        study_id: UUID | None = None,
        label: str | None = None,
        properties: dict | None = None,
        confidence: float | None = None,
        is_ai_generated: bool = False,
        ai_decision_id: UUID | None = None,
        actor: User | None = None,
        actor_agent_id: str | None = None,
    ) -> tuple[GraphEdge, bool]:
        """
        Create or update a directed edge between two graph nodes.

        Returns (edge, created: bool). Emits a graph event.
        AI-generated edges must supply ai_decision_id and confidence.
        """
        edge, created = await self._repo.upsert_edge(
            organization_id=organization_id,
            study_id=study_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            label=label,
            properties=properties,
            confidence=confidence,
            is_ai_generated=is_ai_generated,
            ai_decision_id=ai_decision_id,
            created_by_id=actor.id if actor else None,
        )

        await self._repo.append_event(
            organization_id=organization_id,
            study_id=study_id,
            event_type="EDGE_CREATED" if created else "EDGE_UPDATED",
            payload={
                "edge_type": edge_type.value,
                "source_node_id": str(source_node_id),
                "target_node_id": str(target_node_id),
                "is_ai_generated": is_ai_generated,
                "confidence": confidence,
                "ai_decision_id": str(ai_decision_id) if ai_decision_id else None,
            },
            edge_id=edge.id,
            actor_user_id=actor.id if actor else None,
            actor_agent_id=actor_agent_id,
        )

        return edge, created

    # ------------------------------------------------------------------
    # Named relationship shortcuts (lineage chain)
    # ------------------------------------------------------------------

    async def link_objective_to_endpoint(
        self,
        org_id: UUID,
        study_id: UUID,
        objective_node_id: UUID,
        endpoint_node_id: UUID,
        confidence: float | None = None,
        is_ai_generated: bool = False,
        ai_decision_id: UUID | None = None,
        actor: User | None = None,
        actor_agent_id: str | None = None,
    ) -> GraphEdge:
        edge, _ = await self.create_relationship(
            organization_id=org_id,
            source_node_id=objective_node_id,
            target_node_id=endpoint_node_id,
            edge_type=GraphEdgeType.OBJECTIVE_TO_ENDPOINT,
            study_id=study_id,
            confidence=confidence,
            is_ai_generated=is_ai_generated,
            ai_decision_id=ai_decision_id,
            actor=actor,
            actor_agent_id=actor_agent_id,
        )
        return edge

    async def link_endpoint_to_ecr(
        self,
        org_id: UUID,
        study_id: UUID,
        endpoint_node_id: UUID,
        ecr_node_id: UUID,
        confidence: float | None = None,
        is_ai_generated: bool = False,
        ai_decision_id: UUID | None = None,
        actor: User | None = None,
        actor_agent_id: str | None = None,
    ) -> GraphEdge:
        edge, _ = await self.create_relationship(
            organization_id=org_id,
            source_node_id=endpoint_node_id,
            target_node_id=ecr_node_id,
            edge_type=GraphEdgeType.ENDPOINT_TO_ECR,
            study_id=study_id,
            confidence=confidence,
            is_ai_generated=is_ai_generated,
            ai_decision_id=ai_decision_id,
            actor=actor,
            actor_agent_id=actor_agent_id,
        )
        return edge

    async def link_ecr_to_sdtm(
        self,
        org_id: UUID,
        study_id: UUID,
        ecr_node_id: UUID,
        sdtm_node_id: UUID,
        confidence: float | None = None,
        is_ai_generated: bool = False,
        ai_decision_id: UUID | None = None,
        actor: User | None = None,
        actor_agent_id: str | None = None,
    ) -> GraphEdge:
        edge, _ = await self.create_relationship(
            organization_id=org_id,
            source_node_id=ecr_node_id,
            target_node_id=sdtm_node_id,
            edge_type=GraphEdgeType.ECR_TO_SDTM,
            study_id=study_id,
            confidence=confidence,
            is_ai_generated=is_ai_generated,
            ai_decision_id=ai_decision_id,
            actor=actor,
            actor_agent_id=actor_agent_id,
        )
        return edge

    async def link_sdtm_to_adam(
        self,
        org_id: UUID,
        study_id: UUID,
        sdtm_node_id: UUID,
        adam_node_id: UUID,
        confidence: float | None = None,
        is_ai_generated: bool = False,
        ai_decision_id: UUID | None = None,
        actor: User | None = None,
        actor_agent_id: str | None = None,
    ) -> GraphEdge:
        edge, _ = await self.create_relationship(
            organization_id=org_id,
            source_node_id=sdtm_node_id,
            target_node_id=adam_node_id,
            edge_type=GraphEdgeType.SDTM_TO_ADAM,
            study_id=study_id,
            confidence=confidence,
            is_ai_generated=is_ai_generated,
            ai_decision_id=ai_decision_id,
            actor=actor,
            actor_agent_id=actor_agent_id,
        )
        return edge

    async def link_adam_to_tlf(
        self,
        org_id: UUID,
        study_id: UUID,
        adam_node_id: UUID,
        tlf_node_id: UUID,
        confidence: float | None = None,
        is_ai_generated: bool = False,
        ai_decision_id: UUID | None = None,
        actor: User | None = None,
        actor_agent_id: str | None = None,
    ) -> GraphEdge:
        edge, _ = await self.create_relationship(
            organization_id=org_id,
            source_node_id=adam_node_id,
            target_node_id=tlf_node_id,
            edge_type=GraphEdgeType.ADAM_TO_TLF,
            study_id=study_id,
            confidence=confidence,
            is_ai_generated=is_ai_generated,
            ai_decision_id=ai_decision_id,
            actor=actor,
            actor_agent_id=actor_agent_id,
        )
        return edge

    async def link_tlf_to_csr(
        self,
        org_id: UUID,
        study_id: UUID,
        tlf_node_id: UUID,
        csr_node_id: UUID,
        confidence: float | None = None,
        is_ai_generated: bool = False,
        ai_decision_id: UUID | None = None,
        actor: User | None = None,
        actor_agent_id: str | None = None,
    ) -> GraphEdge:
        edge, _ = await self.create_relationship(
            organization_id=org_id,
            source_node_id=tlf_node_id,
            target_node_id=csr_node_id,
            edge_type=GraphEdgeType.TLF_TO_CSR,
            study_id=study_id,
            confidence=confidence,
            is_ai_generated=is_ai_generated,
            ai_decision_id=ai_decision_id,
            actor=actor,
            actor_agent_id=actor_agent_id,
        )
        return edge

    # ------------------------------------------------------------------
    # Graph queries
    # ------------------------------------------------------------------

    async def get_node(self, node_id: UUID, organization_id: UUID) -> GraphNode:
        return await self._repo.get_node(node_id, organization_id)

    async def find_node_for_domain_record(
        self, external_id: UUID, external_type: str, organization_id: UUID
    ) -> GraphNode | None:
        return await self._repo.find_node_by_external(
            external_id, external_type, organization_id
        )

    async def list_nodes(
        self,
        organization_id: UUID,
        study_id: UUID | None = None,
        node_type: GraphNodeType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[GraphNode], int]:
        return await self._repo.list_nodes(
            organization_id=organization_id,
            study_id=study_id,
            node_type=node_type,
            limit=limit,
            offset=offset,
        )

    async def get_neighbors(
        self,
        node_id: UUID,
        organization_id: UUID,
        direction: str = "both",
        edge_type: GraphEdgeType | None = None,
    ) -> dict:
        """
        Return all edges adjacent to a node.
        direction: "outgoing", "incoming", or "both"
        """
        result: dict = {"outgoing": [], "incoming": []}
        if direction in ("outgoing", "both"):
            result["outgoing"] = await self._repo.list_edges_from_node(
                node_id, organization_id, edge_type
            )
        if direction in ("incoming", "both"):
            result["incoming"] = await self._repo.list_edges_to_node(
                node_id, organization_id, edge_type
            )
        return result

    async def get_lineage_path(
        self,
        node_id: UUID,
        organization_id: UUID,
        max_depth: int = 10,
    ) -> dict:
        """
        Walk the lineage chain forward and backward from a node, up to max_depth hops.
        Returns a dict with 'upstream' and 'downstream' edge lists.

        This is a simple BFS traversal. For complex graph queries at scale,
        use a dedicated graph query (PostgreSQL recursive CTE or a graph DB).
        """
        visited: set[UUID] = set()
        upstream: list[dict] = []
        downstream: list[dict] = []

        async def walk_upstream(current_id: UUID, depth: int) -> None:
            if depth >= max_depth or current_id in visited:
                return
            visited.add(current_id)
            edges = await self._repo.list_edges_to_node(current_id, organization_id)
            for edge in edges:
                upstream.append(edge.to_dict())
                await walk_upstream(edge.source_node_id, depth + 1)

        async def walk_downstream(current_id: UUID, depth: int) -> None:
            if depth >= max_depth or current_id in visited:
                return
            visited.add(current_id)
            edges = await self._repo.list_edges_from_node(current_id, organization_id)
            for edge in edges:
                downstream.append(edge.to_dict())
                await walk_downstream(edge.target_node_id, depth + 1)

        await walk_upstream(node_id, 0)
        visited.clear()
        await walk_downstream(node_id, 0)

        return {"upstream": upstream, "downstream": downstream}
