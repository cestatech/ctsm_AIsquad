"""Unit tests for ImpactAnalysisService.get_downstream_impact()."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.graph import GraphNodeType
from app.services.impact_analysis_service import ImpactAnalysisService


def _node(*, node_id, label: str, node_type: GraphNodeType):
    node = MagicMock()
    node.id = node_id
    node.label = label
    node.node_type = node_type
    return node


def _edge(*, source_id, target_id):
    edge = MagicMock()
    edge.target_node_id = target_id
    edge.source_node_id = source_id
    return edge


@pytest.mark.asyncio
async def test_three_hop_chain_returns_all_downstream_nodes():
    db = AsyncMock()
    svc = ImpactAnalysisService(db)

    org_id = uuid4()
    n0, n1, n2, n3 = uuid4(), uuid4(), uuid4(), uuid4()

    svc._graph = AsyncMock()
    svc._graph.get_node = AsyncMock(
        side_effect=lambda node_id, _org: {
            n0: _node(node_id=n0, label="Objective", node_type=GraphNodeType.OBJECTIVE),
            n1: _node(node_id=n1, label="Endpoint", node_type=GraphNodeType.ENDPOINT),
            n2: _node(
                node_id=n2, label="eCRF Field", node_type=GraphNodeType.ECR_FIELD
            ),
            n3: _node(
                node_id=n3, label="SDTM Variable", node_type=GraphNodeType.SDTM_VARIABLE
            ),
        }[node_id]
    )
    svc._graph.get_neighbors = AsyncMock(
        side_effect=lambda node_id, organization_id, direction="both": {
            n0: {"outgoing": [_edge(source_id=n0, target_id=n1)], "incoming": []},
            n1: {"outgoing": [_edge(source_id=n1, target_id=n2)], "incoming": []},
            n2: {"outgoing": [_edge(source_id=n2, target_id=n3)], "incoming": []},
            n3: {"outgoing": [], "incoming": []},
        }[node_id]
    )

    report = await svc.get_downstream_impact(n0, org_id, max_depth=10)

    assert report.node_id == n0
    assert len(report.impacted_nodes) == 3
    assert [node.name for node in report.impacted_nodes] == [
        "Endpoint",
        "eCRF Field",
        "SDTM Variable",
    ]
    assert [node.depth for node in report.impacted_nodes] == [1, 2, 3]


@pytest.mark.asyncio
async def test_max_depth_limits_traversal():
    db = AsyncMock()
    svc = ImpactAnalysisService(db)

    org_id = uuid4()
    n0, n1, n2 = uuid4(), uuid4(), uuid4()

    svc._graph = AsyncMock()
    svc._graph.get_node = AsyncMock(
        side_effect=lambda node_id, _org: {
            n0: _node(node_id=n0, label="A", node_type=GraphNodeType.OBJECTIVE),
            n1: _node(node_id=n1, label="B", node_type=GraphNodeType.ENDPOINT),
            n2: _node(node_id=n2, label="C", node_type=GraphNodeType.ECR_FIELD),
        }[node_id]
    )
    svc._graph.get_neighbors = AsyncMock(
        side_effect=lambda node_id, organization_id, direction="both": {
            n0: {"outgoing": [_edge(source_id=n0, target_id=n1)], "incoming": []},
            n1: {"outgoing": [_edge(source_id=n1, target_id=n2)], "incoming": []},
            n2: {"outgoing": [], "incoming": []},
        }[node_id]
    )

    report = await svc.get_downstream_impact(n0, org_id, max_depth=1)

    assert len(report.impacted_nodes) == 1
    assert report.impacted_nodes[0].name == "B"
    assert report.impacted_nodes[0].depth == 1
