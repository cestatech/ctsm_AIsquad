"""Unit tests for TraceabilityService.compute_gaps().

The service queries GraphNode and GraphEdge via a SQLAlchemy async session.
All DB calls are mocked — no real database required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.graph import GraphNodeType
from app.services.impact_analysis_service import GapImpactReport, ImpactAnalysisService
from app.services.traceability_service import (
    CHAIN,
    TraceabilityService,
)


@pytest.fixture(autouse=True)
def _mock_downstream_impact(monkeypatch):
    async def _empty_impact(self, node_id, organization_id, *, max_depth=10):
        return GapImpactReport(node_id=node_id, impacted_nodes=[])

    monkeypatch.setattr(ImpactAnalysisService, "get_downstream_impact", _empty_impact)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_node(node_type: GraphNodeType, label: str = "node"):
    n = MagicMock()
    n.id = uuid4()
    n.label = label
    n.node_type = node_type.value
    return n


def _make_edge(source_id, target_id):
    e = MagicMock()
    e.source_node_id = source_id
    e.target_node_id = target_id
    return e


def _mock_db(nodes: list, edges: list) -> AsyncMock:
    """Return a mock db session whose execute() returns nodes first, then edges."""
    db = AsyncMock()

    def _scalars_result(items):
        r = MagicMock()
        sc = MagicMock()
        sc.all = MagicMock(return_value=items)
        r.scalars = MagicMock(return_value=sc)
        return r

    nodes_result = _scalars_result(nodes)
    edges_result = _scalars_result(edges)
    db.execute = AsyncMock(side_effect=[nodes_result, edges_result])
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestComputeGaps:
    async def test_empty_graph_returns_zero_gaps(self):
        db = _mock_db([], [])
        svc = TraceabilityService(db)
        report = await svc.compute_gaps(uuid4(), uuid4())

        assert report.total_nodes == 0
        assert report.nodes_with_gaps == 0
        assert report.chain_coverage_pct == 100.0
        assert report.gaps == []

    async def test_objectives_only_have_no_gaps(self):
        """OBJECTIVE is the first stage — it requires no upstream link."""
        obj1 = _make_node(GraphNodeType.OBJECTIVE, "Objective 1")
        obj2 = _make_node(GraphNodeType.OBJECTIVE, "Objective 2")
        db = _mock_db([obj1, obj2], [])
        svc = TraceabilityService(db)
        report = await svc.compute_gaps(uuid4(), uuid4())

        assert report.total_nodes == 2
        assert report.nodes_with_gaps == 0
        assert report.chain_coverage_pct == 100.0

    async def test_endpoint_without_objective_link_is_a_gap(self):
        """An ENDPOINT node with no incoming OBJECTIVE edge is a traceability gap."""
        endpoint = _make_node(GraphNodeType.ENDPOINT, "Primary Endpoint")
        db = _mock_db([endpoint], [])
        svc = TraceabilityService(db)
        report = await svc.compute_gaps(uuid4(), uuid4())

        assert report.nodes_with_gaps == 1
        assert report.gaps[0].node_id == endpoint.id
        assert report.gaps[0].missing_link_from == GraphNodeType.OBJECTIVE.value

    async def test_endpoint_linked_to_objective_has_no_gap(self):
        obj = _make_node(GraphNodeType.OBJECTIVE, "Reduce mortality")
        ep = _make_node(GraphNodeType.ENDPOINT, "OS at 12 months")
        edge = _make_edge(obj.id, ep.id)
        db = _mock_db([obj, ep], [edge])
        svc = TraceabilityService(db)
        report = await svc.compute_gaps(uuid4(), uuid4())

        assert report.nodes_with_gaps == 0
        assert report.chain_coverage_pct == 100.0

    async def test_full_chain_no_gaps(self):
        """All 7 stages linked end-to-end → 0 gaps, 100% coverage."""
        nodes = [_make_node(t, t.value) for t in CHAIN]
        edges = [
            _make_edge(nodes[i].id, nodes[i + 1].id) for i in range(len(CHAIN) - 1)
        ]
        db = _mock_db(nodes, edges)
        svc = TraceabilityService(db)
        report = await svc.compute_gaps(uuid4(), uuid4())

        assert report.nodes_with_gaps == 0
        assert report.total_nodes == len(CHAIN)
        assert report.chain_coverage_pct == 100.0

    async def test_broken_chain_mid_way_creates_gap(self):
        """SDTM_VARIABLE with no ECR_FIELD link is a gap even if chain is otherwise ok."""
        obj = _make_node(GraphNodeType.OBJECTIVE)
        ep = _make_node(GraphNodeType.ENDPOINT)
        ecr = _make_node(GraphNodeType.ECR_FIELD)
        sdtm = _make_node(GraphNodeType.SDTM_VARIABLE)

        # obj→ep, ep→ecr — but NO ecr→sdtm link
        edges = [_make_edge(obj.id, ep.id), _make_edge(ep.id, ecr.id)]
        db = _mock_db([obj, ep, ecr, sdtm], edges)
        svc = TraceabilityService(db)
        report = await svc.compute_gaps(uuid4(), uuid4())

        assert report.nodes_with_gaps == 1
        gap = report.gaps[0]
        assert gap.node_id == sdtm.id
        assert gap.missing_link_from == GraphNodeType.ECR_FIELD.value

    async def test_coverage_pct_calculation(self):
        """With 4 nodes and 1 gap → 75% coverage."""
        obj = _make_node(GraphNodeType.OBJECTIVE)
        ep = _make_node(GraphNodeType.ENDPOINT)
        ecr = _make_node(GraphNodeType.ECR_FIELD)
        sdtm = _make_node(GraphNodeType.SDTM_VARIABLE)

        # ep has obj link, ecr has ep link, sdtm has NO ecr link
        edges = [_make_edge(obj.id, ep.id), _make_edge(ep.id, ecr.id)]
        db = _mock_db([obj, ep, ecr, sdtm], edges)
        svc = TraceabilityService(db)
        report = await svc.compute_gaps(uuid4(), uuid4())

        assert report.total_nodes == 4
        assert report.nodes_with_gaps == 1
        assert report.chain_coverage_pct == 75.0

    async def test_edge_from_wrong_stage_does_not_resolve_gap(self):
        """An edge from OBJECTIVE directly to SDTM_VARIABLE is not a valid upstream
        link for stage SDTM (which requires ECR_FIELD as predecessor)."""
        obj = _make_node(GraphNodeType.OBJECTIVE)
        sdtm = _make_node(GraphNodeType.SDTM_VARIABLE)
        # Direct obj→sdtm edge (skipping ENDPOINT, ECR_FIELD)
        edge = _make_edge(obj.id, sdtm.id)
        db = _mock_db([obj, sdtm], [edge])
        svc = TraceabilityService(db)
        report = await svc.compute_gaps(uuid4(), uuid4())

        # sdtm should still be a gap (no ECR_FIELD predecessor)
        assert report.nodes_with_gaps == 1
        assert report.gaps[0].node_id == sdtm.id

    async def test_multiple_gaps_all_reported(self):
        """Two orphan endpoints → two gap records returned."""
        ep1 = _make_node(GraphNodeType.ENDPOINT, "EP1")
        ep2 = _make_node(GraphNodeType.ENDPOINT, "EP2")
        db = _mock_db([ep1, ep2], [])
        svc = TraceabilityService(db)
        report = await svc.compute_gaps(uuid4(), uuid4())

        assert len(report.gaps) == 2
        gap_ids = {g.node_id for g in report.gaps}
        assert ep1.id in gap_ids
        assert ep2.id in gap_ids

    async def test_gap_message_names_missing_stage(self):
        ep = _make_node(GraphNodeType.ENDPOINT, "My Endpoint")
        db = _mock_db([ep], [])
        svc = TraceabilityService(db)
        report = await svc.compute_gaps(uuid4(), uuid4())

        gap = report.gaps[0]
        assert GraphNodeType.OBJECTIVE.value in gap.message
        assert GraphNodeType.ENDPOINT.value in gap.message

    async def test_report_contains_study_id(self):
        study_id = uuid4()
        db = _mock_db([], [])
        svc = TraceabilityService(db)
        report = await svc.compute_gaps(study_id, uuid4())

        assert report.study_id == study_id
