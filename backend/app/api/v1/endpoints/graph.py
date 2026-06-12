"""Context Graph API endpoints.

Provides read/write access to the intelligence graph: nodes, edges, lineage
traversal, and graph events. All routes are org-scoped via JWT.

Permissions:
  - GET endpoints: any authenticated user
  - POST endpoints (register node, create edge): ADMIN or CONTRIBUTOR
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.permissions import Permission, check_permission
from app.models.graph import GraphEdgeType, GraphNodeType
from app.models.user import User
from app.repositories.graph_repository import GraphRepository
from app.schemas.graph import (
    CreateEdgeRequest,
    GraphEdgeListResponse,
    GraphEdgeResponse,
    GraphLineageResponse,
    GraphNeighborsResponse,
    GraphNodeListResponse,
    GraphNodeResponse,
    RegisterNodeRequest,
    TraceabilityGapItem,
    TraceabilityGapResponse,
)
from app.schemas.graph_event import (
    GraphEntityRelationshipsResponse,
    GraphEventListResponse,
    GraphEventResponse,
    GraphNodeContextResponse,
    GraphStudySummaryResponse,
)
from app.schemas.traceability import GapImpactReport, ImpactedNode
from app.services.context_graph_service import ContextGraphService
from app.services.impact_analysis_service import ImpactAnalysisService
from app.services.traceability_service import TraceabilityService

router = APIRouter()


@router.get("/events", response_model=GraphEventListResponse, summary="List graph events")
async def list_graph_events(
    study_id: UUID | None = Query(None),
    actor_user_id: UUID | None = Query(None),
    action: str | None = Query(None, description="Workflow action filter (e.g. mapped)"),
    entity_type: str | None = Query(None),
    event_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphEventListResponse:
    """Query standardized graph events by study, user, action, or entity type."""
    svc = ContextGraphService(db)
    offset = (page - 1) * page_size
    items, total = await svc.list_events(
        organization_id=current_user.organization_id,
        study_id=study_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        event_type=event_type,
        limit=page_size,
        offset=offset,
    )
    return GraphEventListResponse(
        items=[GraphEventResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/study-summary",
    response_model=GraphStudySummaryResponse,
    summary="Study graph relationship summary",
)
async def get_study_graph_summary(
    study_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphStudySummaryResponse:
    """Return node/edge counts and recent graph events for a study workspace."""
    svc = ContextGraphService(db)
    summary = await svc.get_study_summary(current_user.organization_id, study_id)
    return GraphStudySummaryResponse(
        study_id=summary["study_id"],
        node_count=summary["node_count"],
        edge_count=summary["edge_count"],
        event_count=summary["event_count"],
        nodes_by_type=summary["nodes_by_type"],
        recent_events=[
            GraphEventResponse.model_validate(e)
            for e in summary["recent_events"]
        ],
    )


@router.get(
    "/by-entity",
    response_model=GraphEntityRelationshipsResponse,
    summary="Graph relationships for a domain entity",
)
async def get_entity_relationships(
    external_type: str = Query(..., description="e.g. artifact, study, raw_field"),
    external_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphEntityRelationshipsResponse:
    """Drilldown: show graph node and adjacent edges for any domain record."""
    svc = ContextGraphService(db)
    data = await svc.get_entity_relationships(
        organization_id=current_user.organization_id,
        external_type=external_type,
        external_id=external_id,
    )
    return GraphEntityRelationshipsResponse.model_validate(data)


@router.get("", response_model=GraphNodeListResponse, summary="List graph nodes")
async def list_nodes(
    study_id: UUID | None = Query(None),
    node_type: GraphNodeType | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphNodeListResponse:
    """
    List graph nodes for the authenticated organization.

    Optionally filter by study_id and/or node_type. Returns paginated results.
    All users (Admin, Contributor, Reviewer) can query the graph.
    """
    svc = ContextGraphService(db)
    offset = (page - 1) * page_size
    nodes, total = await svc.list_nodes(
        organization_id=current_user.organization_id,
        study_id=study_id,
        node_type=node_type,
        limit=page_size,
        offset=offset,
    )
    return GraphNodeListResponse(
        items=[GraphNodeResponse.model_validate(n) for n in nodes],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=GraphNodeResponse,
    status_code=201,
    summary="Register a domain record as a graph node",
)
async def register_node(
    body: RegisterNodeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphNodeResponse:
    """
    Register a domain record as a graph node (idempotent upsert).

    Requires CONTRIBUTOR or ADMIN role. If the node already exists for the
    given external_id + external_type, it will be updated in place.
    """
    check_permission(current_user, Permission.ARTIFACT_CREATE)
    svc = ContextGraphService(db)
    node, _ = await svc.register_domain_record(
        organization_id=current_user.organization_id,
        node_type=body.node_type,
        external_id=body.external_id,
        external_type=body.external_type,
        label=body.label,
        study_id=body.study_id,
        description=body.description,
        properties=body.properties,
        actor=current_user,
    )
    return GraphNodeResponse.model_validate(node)


@router.get(
    "/edges",
    response_model=GraphEdgeListResponse,
    summary="List edges for a study",
)
async def list_edges(
    study_id: UUID = Query(..., description="Study ID to scope the query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphEdgeListResponse:
    """
    List all active graph edges for a study.

    Used by traceability matrix and graph explorer to render relationships
    between nodes without querying each node's neighbors individually.
    """
    repo = GraphRepository(db)
    offset = (page - 1) * page_size
    edges, total = await repo.list_edges_for_study(
        organization_id=current_user.organization_id,
        study_id=study_id,
        limit=page_size,
        offset=offset,
    )
    return GraphEdgeListResponse(
        items=[GraphEdgeResponse.model_validate(e) for e in edges],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/traceability-gaps",
    response_model=TraceabilityGapResponse,
    summary="Compute traceability gaps for a study",
)
async def get_traceability_gaps(
    study_id: UUID = Query(..., description="Study ID to analyse"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TraceabilityGapResponse:
    """
    Walk the Objective → Endpoint → eCRF → SDTM → ADaM → TLF → CSR chain
    and return every node that has no incoming link from the preceding stage.

    A gap indicates a traceability break that would require remediation before
    regulatory submission. The response includes overall chain coverage %.
    """
    svc = TraceabilityService(db)
    report = await svc.compute_gaps(study_id, current_user.organization_id)
    return TraceabilityGapResponse(
        study_id=report.study_id,
        total_nodes=report.total_nodes,
        nodes_with_gaps=report.nodes_with_gaps,
        chain_coverage_pct=report.chain_coverage_pct,
        gaps=[
            TraceabilityGapItem(
                node_id=g.node_id,
                node_label=g.node_label,
                node_type=g.node_type,
                stage_index=g.stage_index,
                missing_link_from=g.missing_link_from,
                message=g.message,
                impacted_nodes=[
                    ImpactedNode(
                        id=node.id,
                        node_type=node.node_type,
                        name=node.name,
                        depth=node.depth,
                    )
                    for node in g.impacted_nodes
                ],
            )
            for g in report.gaps
        ],
    )


@router.post(
    "/edges",
    response_model=GraphEdgeResponse,
    status_code=201,
    summary="Create a relationship between two graph nodes",
)
async def create_edge(
    body: CreateEdgeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphEdgeResponse:
    """
    Create a directed edge between two nodes in the Context Graph.

    Requires CONTRIBUTOR or ADMIN role.
    Human-created edges should not supply ai_decision_id.
    """
    check_permission(current_user, Permission.ARTIFACT_CREATE)
    svc = ContextGraphService(db)
    edge, _ = await svc.create_relationship(
        organization_id=current_user.organization_id,
        source_node_id=body.source_node_id,
        target_node_id=body.target_node_id,
        edge_type=body.edge_type,
        study_id=body.study_id,
        label=body.label,
        properties=body.properties,
        confidence=body.confidence,
        is_ai_generated=False,
        actor=current_user,
    )
    return GraphEdgeResponse.model_validate(edge)


@router.get("/{node_id}", response_model=GraphNodeResponse, summary="Get a graph node")
async def get_node(
    node_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphNodeResponse:
    """Fetch a single graph node by ID, scoped to the authenticated organization."""
    svc = ContextGraphService(db)
    node = await svc.get_node(node_id, current_user.organization_id)
    return GraphNodeResponse.model_validate(node)


@router.get(
    "/{node_id}/neighbors",
    response_model=GraphNeighborsResponse,
    summary="Get a node's adjacent edges and neighbors",
)
async def get_neighbors(
    node_id: UUID,
    direction: str = Query("both", pattern="^(outgoing|incoming|both)$"),
    edge_type: GraphEdgeType | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphNeighborsResponse:
    """
    Return all edges adjacent to a node.

    direction: "outgoing", "incoming", or "both" (default)
    Optionally filter by edge_type.
    """
    svc = ContextGraphService(db)
    node = await svc.get_node(node_id, current_user.organization_id)
    neighbors = await svc.get_neighbors(
        node_id=node_id,
        organization_id=current_user.organization_id,
        direction=direction,
        edge_type=edge_type,
    )
    return GraphNeighborsResponse(
        node=GraphNodeResponse.model_validate(node),
        outgoing=[GraphEdgeResponse.model_validate(e) for e in neighbors["outgoing"]],
        incoming=[GraphEdgeResponse.model_validate(e) for e in neighbors["incoming"]],
    )


@router.get(
    "/{node_id}/context",
    response_model=GraphNodeContextResponse,
    summary="Node context with neighbors and AI reasoning",
)
async def get_node_context(
    node_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphNodeContextResponse:
    """Return adjacent edges and linked AI decision reasoning for a graph node."""
    svc = ContextGraphService(db)
    context = await svc.get_node_context(node_id, current_user.organization_id)
    return GraphNodeContextResponse.model_validate(context)


@router.get(
    "/{node_id}/impact",
    response_model=GapImpactReport,
    summary="Downstream impact analysis for a node",
)
async def get_node_impact(
    node_id: UUID,
    max_depth: int = Query(10, ge=1, le=10),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GapImpactReport:
    """Return downstream nodes affected if this gap node is not remediated."""
    check_permission(current_user, Permission.ARTIFACT_APPROVE)
    svc = ImpactAnalysisService(db)
    impact = await svc.get_downstream_impact(
        node_id=node_id,
        organization_id=current_user.organization_id,
        max_depth=max_depth,
    )
    return GapImpactReport(
        node_id=impact.node_id,
        impacted_nodes=[
            ImpactedNode(
                id=node.id,
                node_type=node.node_type,
                name=node.name,
                depth=node.depth,
            )
            for node in impact.impacted_nodes
        ],
    )


@router.get(
    "/{node_id}/lineage",
    response_model=GraphLineageResponse,
    summary="Walk the lineage path from a node",
)
async def get_lineage(
    node_id: UUID,
    max_depth: int = Query(10, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GraphLineageResponse:
    """
    Walk the lineage path upstream and downstream from a node, up to max_depth hops.

    This traces the Objective → Endpoint → ECR → SDTM → ADaM → TLF → CSR chain
    (or any sub-path) from the given node in both directions.
    """
    svc = ContextGraphService(db)
    lineage = await svc.get_lineage_path(
        node_id=node_id,
        organization_id=current_user.organization_id,
        max_depth=max_depth,
    )
    return GraphLineageResponse(
        node_id=node_id,
        upstream=lineage["upstream"],
        downstream=lineage["downstream"],
    )
