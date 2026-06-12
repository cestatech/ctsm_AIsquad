"""Integration tests for Phase 3 graph event and relationship endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphEdgeType, GraphNodeType
from app.services.context_graph_service import ContextGraphService


@pytest.mark.asyncio(loop_scope="session")
class TestGraphEventsEndpoints:
    async def test_unauthenticated_returns_403(self, iclient: AsyncClient):
        resp = await iclient.get("/api/v1/graph/events")
        assert resp.status_code == 403

    async def test_list_events_after_node_registration(
        self,
        iclient: AsyncClient,
        idb: AsyncSession,
        i_org,
        i_study,
        i_admin,
        admin_tok: str,
    ):
        external_id = uuid4()
        svc = ContextGraphService(idb)
        await svc.register_domain_record(
            organization_id=i_org.id,
            node_type=GraphNodeType.ARTIFACT,
            external_id=external_id,
            external_type="artifact",
            label="Graph Test Artifact",
            study_id=i_study.id,
            actor=i_admin,
        )
        await idb.commit()

        resp = await iclient.get(
            "/api/v1/graph/events",
            params={"study_id": str(i_study.id), "action": "created"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 1
        assert any(
            item["payload"].get("entity_type") == "artifact" for item in data["items"]
        )

    async def test_study_summary_returns_counts(
        self,
        iclient: AsyncClient,
        idb: AsyncSession,
        i_org,
        i_study,
        i_admin,
        admin_tok: str,
    ):
        svc = ContextGraphService(idb)
        await svc.register_domain_record(
            organization_id=i_org.id,
            node_type=GraphNodeType.STUDY,
            external_id=i_study.id,
            external_type="study",
            label="Integration Study",
            study_id=i_study.id,
            actor=i_admin,
        )
        await idb.commit()

        resp = await iclient.get(
            "/api/v1/graph/study-summary",
            params={"study_id": str(i_study.id)},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["study_id"] == str(i_study.id)
        assert data["node_count"] >= 1
        assert "nodes_by_type" in data
        assert "recent_events" in data

    async def test_list_edges_for_study(
        self,
        iclient: AsyncClient,
        i_study,
        admin_tok: str,
    ):
        """Static /graph/edges must not be captured by /graph/{node_id} (UUID) routing."""
        resp = await iclient.get(
            "/api/v1/graph/edges",
            params={"study_id": str(i_study.id)},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    async def test_by_entity_returns_relationships(
        self,
        iclient: AsyncClient,
        idb: AsyncSession,
        i_org,
        i_study,
        i_admin,
        admin_tok: str,
    ):
        artifact_id = uuid4()
        svc = ContextGraphService(idb)
        art_node, _ = await svc.register_domain_record(
            organization_id=i_org.id,
            node_type=GraphNodeType.ARTIFACT,
            external_id=artifact_id,
            external_type="artifact",
            label="Relationship Test Artifact",
            study_id=i_study.id,
            actor=i_admin,
        )
        study_node, _ = await svc.register_domain_record(
            organization_id=i_org.id,
            node_type=GraphNodeType.STUDY,
            external_id=i_study.id,
            external_type="study",
            label="Integration Study",
            study_id=i_study.id,
            actor=i_admin,
        )
        await svc.create_relationship(
            organization_id=i_org.id,
            source_node_id=art_node.id,
            target_node_id=study_node.id,
            edge_type=GraphEdgeType.PART_OF,
            study_id=i_study.id,
            actor=i_admin,
        )
        await idb.commit()

        resp = await iclient.get(
            "/api/v1/graph/by-entity",
            params={
                "external_type": "artifact",
                "external_id": str(artifact_id),
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["external_type"] == "artifact"
        assert data["external_id"] == str(artifact_id)
        assert data["node"] is not None
        assert len(data["outgoing"]) >= 1

    async def test_ai_edge_without_decision_rejected(
        self,
        iclient: AsyncClient,
        idb: AsyncSession,
        i_org,
        i_study,
        i_admin,
        contributor_tok: str,
    ):
        svc = ContextGraphService(idb)
        n1, _ = await svc.register_domain_record(
            organization_id=i_org.id,
            node_type=GraphNodeType.OBJECTIVE,
            external_id=uuid4(),
            external_type="objective",
            label="Obj",
            study_id=i_study.id,
            actor=i_admin,
        )
        n2, _ = await svc.register_domain_record(
            organization_id=i_org.id,
            node_type=GraphNodeType.ENDPOINT,
            external_id=uuid4(),
            external_type="endpoint",
            label="Ep",
            study_id=i_study.id,
            actor=i_admin,
        )
        await idb.commit()

        with pytest.raises(HTTPException) as exc:
            await svc.create_relationship(
                organization_id=i_org.id,
                source_node_id=n1.id,
                target_node_id=n2.id,
                edge_type=GraphEdgeType.OBJECTIVE_TO_ENDPOINT,
                study_id=i_study.id,
                is_ai_generated=True,
                ai_decision_id=None,
                actor=i_admin,
            )
        assert exc.value.status_code == 422
