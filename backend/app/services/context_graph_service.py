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

import hashlib
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphEdge, GraphEdgeType, GraphNode, GraphNodeType
from app.models.user import User
from app.repositories.graph_repository import GraphRepository
from app.schemas.graph_event import GraphActorType, GraphWorkflowAction
from app.services.graph_event_writer import (
    GraphEventWriter,
    require_ai_decision_for_generated_edge,
)

EDGE_IDEMPOTENCY_HASH_THRESHOLD = 200


def edge_idempotency_raw_key(
    source_node_id: UUID,
    edge_type_value: str,
    target_node_id: UUID,
) -> str:
    """Composite idempotency key: source + edge type + target."""
    return f"{source_node_id}:{edge_type_value}:{target_node_id}"


def edge_idempotency_key_hash(raw_key: str) -> str | None:
    """Return SHA-256 hex digest when the raw key exceeds the length threshold."""
    if len(raw_key) <= EDGE_IDEMPOTENCY_HASH_THRESHOLD:
        return None
    return hashlib.sha256(raw_key.encode()).hexdigest()


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
        self._events = GraphEventWriter(db)

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

        await self._events.write(
            organization_id=organization_id,
            study_id=study_id,
            event_type="NODE_CREATED" if created else "NODE_UPDATED",
            action=GraphWorkflowAction.CREATED if created else GraphWorkflowAction.UPDATED,
            entity_type=external_type,
            entity_id=external_id,
            actor_type=(
                GraphActorType.USER
                if actor
                else GraphActorType.AI_AGENT if actor_agent_id else GraphActorType.SYSTEM
            ),
            actor_user_id=actor.id if actor else None,
            actor_agent_id=actor_agent_id,
            node_id=node.id,
            idempotency_key=GraphEventWriter.node_idempotency_key(
                organization_id, external_type, external_id
            )
            if created
            else None,
            extra={
                "node_type": node_type.value,
                "external_type": external_type,
                "external_id": str(external_id),
                "label": label,
            },
            after_state={"label": label, "properties": properties or {}},
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
        require_ai_decision_for_generated_edge(is_ai_generated, ai_decision_id)

        raw_idempotency_key = edge_idempotency_raw_key(
            source_node_id, edge_type.value, target_node_id
        )
        idempotency_key_hash = edge_idempotency_key_hash(raw_idempotency_key)

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
            idempotency_key_hash=idempotency_key_hash,
        )

        await self._events.write(
            organization_id=organization_id,
            study_id=study_id,
            event_type="EDGE_CREATED" if created else "EDGE_UPDATED",
            action=GraphWorkflowAction.LINKED if created else GraphWorkflowAction.UPDATED,
            entity_type="graph_edge",
            entity_id=edge.id,
            actor_type=(
                GraphActorType.USER
                if actor
                else GraphActorType.AI_AGENT if actor_agent_id else GraphActorType.SYSTEM
            ),
            actor_user_id=actor.id if actor else None,
            actor_agent_id=actor_agent_id,
            edge_id=edge.id,
            ai_decision_id=ai_decision_id,
            idempotency_key=GraphEventWriter.edge_idempotency_key(
                organization_id,
                source_node_id,
                target_node_id,
                edge_type.value,
            )
            if created
            else None,
            extra={
                "edge_type": edge_type.value,
                "source_node_id": str(source_node_id),
                "target_node_id": str(target_node_id),
                "is_ai_generated": is_ai_generated,
                "confidence": confidence,
                "ai_decision_id": str(ai_decision_id) if ai_decision_id else None,
            },
            after_state={
                "edge_type": edge_type.value,
                "is_ai_generated": is_ai_generated,
            },
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

    async def link_pipeline_artifact_to_study(
        self,
        *,
        organization_id: UUID,
        study_id: UUID,
        study_name: str,
        artifact_id: UUID,
        artifact_name: str,
        artifact_node_type: GraphNodeType,
        artifact_external_type: str,
        actor: User,
        ai_decision_id: UUID,
        protocol_artifact_id: UUID | None = None,
        protocol_artifact_name: str | None = None,
    ) -> None:
        """Register a pipeline artifact node and link it to the study graph."""
        study_node, _ = await self.register_domain_record(
            organization_id=organization_id,
            node_type=GraphNodeType.STUDY,
            external_id=study_id,
            external_type="study",
            label=study_name,
            study_id=study_id,
            actor=actor,
        )
        artifact_node, _ = await self.register_domain_record(
            organization_id=organization_id,
            node_type=artifact_node_type,
            external_id=artifact_id,
            external_type=artifact_external_type,
            label=artifact_name,
            study_id=study_id,
            properties={"artifact_id": str(artifact_id)},
            actor=actor,
        )
        await self.create_relationship(
            organization_id=organization_id,
            source_node_id=artifact_node.id,
            target_node_id=study_node.id,
            edge_type=GraphEdgeType.PART_OF,
            study_id=study_id,
            is_ai_generated=True,
            ai_decision_id=ai_decision_id,
            actor=actor,
        )

        if protocol_artifact_id is not None and protocol_artifact_name is not None:
            protocol_node, _ = await self.register_domain_record(
                organization_id=organization_id,
                node_type=GraphNodeType.PROTOCOL,
                external_id=protocol_artifact_id,
                external_type="artifact",
                label=protocol_artifact_name,
                study_id=study_id,
                actor=actor,
            )
            await self.create_relationship(
                organization_id=organization_id,
                source_node_id=artifact_node.id,
                target_node_id=protocol_node.id,
                edge_type=GraphEdgeType.DERIVED_FROM,
                study_id=study_id,
                is_ai_generated=True,
                ai_decision_id=ai_decision_id,
                actor=actor,
            )

    # ------------------------------------------------------------------
    # Direct event emission
    # ------------------------------------------------------------------

    async def emit_event(
        self,
        organization_id: UUID,
        event_type: str,
        payload: dict,
        study_id: UUID | None = None,
        node_id: UUID | None = None,
        edge_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        actor_agent_id: str | None = None,
        ai_decision_id: UUID | None = None,
    ) -> None:
        """
        Emit a graph event directly without creating a node or edge.

        Use this for system events (login, logout, validation runs,
        AI decisions, human overrides) that need to be in the event log
        but don't create new graph structure.
        """
        action = self._map_event_type_to_action(event_type)
        entity_type = payload.get("entity_type") or payload.get("context_type") or "system"
        entity_id_raw = payload.get("entity_id") or payload.get("override_id")
        entity_id = UUID(str(entity_id_raw)) if entity_id_raw else None

        await self._events.write(
            organization_id=organization_id,
            study_id=study_id,
            event_type=event_type,
            action=action,
            entity_type=str(entity_type),
            entity_id=entity_id,
            actor_type=(
                GraphActorType.USER
                if actor_user_id
                else GraphActorType.AI_AGENT if actor_agent_id else GraphActorType.SYSTEM
            ),
            actor_user_id=actor_user_id,
            actor_agent_id=actor_agent_id,
            reason=payload.get("reason"),
            node_id=node_id,
            edge_id=edge_id,
            ai_decision_id=ai_decision_id,
            extra=payload,
            after_state=payload,
            idempotency_key=payload.get("idempotency_key"),
        )

    @staticmethod
    def _map_event_type_to_action(event_type: str) -> GraphWorkflowAction:
        mapping = {
            "AI_DECISION_STARTED": GraphWorkflowAction.GENERATED,
            "AI_DECISION_COMPLETED": GraphWorkflowAction.GENERATED,
            "HUMAN_OVERRIDE": GraphWorkflowAction.OVERRIDDEN,
            "STUDY_CREATED": GraphWorkflowAction.CREATED,
            "STUDY_UPDATED": GraphWorkflowAction.UPDATED,
            "STUDY_ARCHIVED": GraphWorkflowAction.LOCKED,
            "MEMBER_ADDED": GraphWorkflowAction.LINKED,
            "MEMBER_REMOVED": GraphWorkflowAction.UPDATED,
            "USER_LOGIN": GraphWorkflowAction.REVIEWED,
            "ARTIFACT_EXPORTED": GraphWorkflowAction.REVIEWED,
        }
        return mapping.get(event_type, GraphWorkflowAction.UPDATED)

    # ------------------------------------------------------------------
    # Graph queries
    # ------------------------------------------------------------------

    async def list_events(
        self,
        organization_id: UUID,
        study_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list, int]:
        return await self._repo.list_events(
            organization_id=organization_id,
            study_id=study_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )

    async def get_study_summary(
        self, organization_id: UUID, study_id: UUID
    ) -> dict:
        node_count = await self._repo.count_nodes_for_study(organization_id, study_id)
        edge_count = await self._repo.count_edges_for_study(organization_id, study_id)
        nodes_by_type = await self._repo.count_nodes_by_type(organization_id, study_id)
        events, event_count = await self._repo.list_events(
            organization_id=organization_id,
            study_id=study_id,
            limit=10,
            offset=0,
        )
        return {
            "study_id": study_id,
            "node_count": node_count,
            "edge_count": edge_count,
            "event_count": event_count,
            "nodes_by_type": nodes_by_type,
            "recent_events": events,
        }

    async def get_entity_relationships(
        self,
        organization_id: UUID,
        external_type: str,
        external_id: UUID,
    ) -> dict:
        node = await self._repo.find_node_by_external(
            external_id, external_type, organization_id
        )
        if node is None:
            return {
                "external_type": external_type,
                "external_id": external_id,
                "node": None,
                "outgoing": [],
                "incoming": [],
            }
        neighbors = await self.get_neighbors(
            node_id=UUID(str(node.id)),
            organization_id=organization_id,
        )
        return {
            "external_type": external_type,
            "external_id": external_id,
            "node": node.to_dict(),
            "outgoing": [e.to_dict() for e in neighbors["outgoing"]],
            "incoming": [e.to_dict() for e in neighbors["incoming"]],
        }

    async def get_impact_analysis(
        self,
        node_id: UUID,
        organization_id: UUID,
        max_depth: int = 5,
    ) -> dict:
        lineage = await self.get_lineage_path(
            node_id=node_id,
            organization_id=organization_id,
            max_depth=max_depth,
        )
        downstream = lineage["downstream"]
        node_ids = {
            UUID(e["target_node_id"])
            for e in downstream
            if e.get("target_node_id")
        }
        affected_nodes = []
        for nid in node_ids:
            try:
                n = await self._repo.get_node(nid, organization_id)
                affected_nodes.append(n.to_dict())
            except Exception:
                continue
        return {
            "node_id": node_id,
            "affected_downstream_count": len(affected_nodes),
            "affected_nodes": affected_nodes,
            "affected_edges": downstream,
        }

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
                await walk_upstream(UUID(edge.source_node_id), depth + 1)

        async def walk_downstream(current_id: UUID, depth: int) -> None:
            if depth >= max_depth or current_id in visited:
                return
            visited.add(current_id)
            edges = await self._repo.list_edges_from_node(current_id, organization_id)
            for edge in edges:
                downstream.append(edge.to_dict())
                await walk_downstream(UUID(edge.target_node_id), depth + 1)

        await walk_upstream(node_id, 0)
        visited.clear()
        await walk_downstream(node_id, 0)

        return {"upstream": upstream, "downstream": downstream}

    async def get_node_context(
        self,
        node_id: UUID,
        organization_id: UUID,
    ) -> dict:
        """
        Return node neighbors plus linked AI decisions with reasoning traces.
        """
        from app.services.intelligence_service import AIDecisionService

        node = await self.get_node(node_id, organization_id)
        neighbors = await self.get_neighbors(node_id, organization_id)
        ai_svc = AIDecisionService(self._db)

        seen: set[UUID] = set()
        ai_decisions: list[dict] = []

        async def _add_decision(
            decision_id: UUID | None,
            link_source: str,
            *,
            edge_type: str | None = None,
            edge_id: UUID | None = None,
        ) -> None:
            if decision_id is None or decision_id in seen:
                return
            seen.add(decision_id)
            try:
                decision = await ai_svc.get_decision(decision_id, organization_id)
            except Exception:
                return
            ai_decisions.append({
                "id": decision.id,
                "agent_name": decision.agent_name,
                "decision_type": decision.decision_type,
                "reasoning": decision.reasoning,
                "confidence": decision.confidence,
                "status": (
                    decision.status.value
                    if hasattr(decision.status, "value")
                    else str(decision.status)
                ),
                "link_source": link_source,
                "edge_type": edge_type,
                "edge_id": edge_id,
            })

        props = node.properties or {}
        raw_decision_id = props.get("ai_decision_id")
        if raw_decision_id:
            await _add_decision(UUID(str(raw_decision_id)), "node_property")

        for edge in [*neighbors["outgoing"], *neighbors["incoming"]]:
            edge_dict = edge.to_dict()
            edge_decision_id = edge_dict.get("ai_decision_id")
            if edge_decision_id:
                await _add_decision(
                    UUID(str(edge_decision_id)),
                    "edge",
                    edge_type=edge_dict.get("edge_type"),
                    edge_id=UUID(str(edge_dict["id"])),
                )

        return {
            "node": node.to_dict(),
            "outgoing": [e.to_dict() for e in neighbors["outgoing"]],
            "incoming": [e.to_dict() for e in neighbors["incoming"]],
            "ai_decisions": ai_decisions,
        }
