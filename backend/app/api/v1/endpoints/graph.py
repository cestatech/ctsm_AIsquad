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
from app.schemas.graph import (
    CreateEdgeRequest,
    GraphEdgeResponse,
    GraphLineageResponse,
    GraphNeighborsResponse,
    GraphNodeListResponse,
    GraphNodeResponse,
    RegisterNodeRequest,
)
from app.services.context_graph_service import ContextGraphService

router = APIRouter()


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
