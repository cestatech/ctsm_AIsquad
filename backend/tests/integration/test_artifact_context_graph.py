from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import Artifact
from app.models.graph import GraphEdge, GraphEdgeType, GraphEvent, GraphNode
from app.models.study import Study
from app.services.artifact_service import ArtifactService


@pytest.mark.asyncio(loop_scope="session")
class TestArtifactContextGraph:
    async def test_manual_create_registers_graph_node_and_study_edge(
        self,
        iclient: AsyncClient,
        idb: AsyncSession,
        i_study: Study,
        admin_tok: str,
    ):
        response = await iclient.post(
            "/api/v1/artifacts",
            json={
                "study_id": str(i_study.id),
                "artifact_type": "PROTOCOL",
                "name": "Manually Created Protocol",
                "description": "Created through the artifact API",
                "content": {"title": "Manual protocol"},
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert response.status_code == 201
        artifact_id = response.json()["id"]

        artifact_result = await idb.execute(
            select(GraphNode).where(
                GraphNode.external_type == "artifact",
                GraphNode.external_id == artifact_id,
            )
        )
        artifact_node = artifact_result.scalar_one()
        assert artifact_node.node_type.value == "PROTOCOL"
        assert artifact_node.study_id == str(i_study.id)
        assert artifact_node.properties["status"] == "DRAFT"

        study_result = await idb.execute(
            select(GraphNode).where(
                GraphNode.external_type == "study",
                GraphNode.external_id == i_study.id,
            )
        )
        study_node = study_result.scalar_one()
        edge_result = await idb.execute(
            select(GraphEdge).where(
                GraphEdge.source_node_id == artifact_node.id,
                GraphEdge.target_node_id == study_node.id,
                GraphEdge.edge_type == GraphEdgeType.PART_OF,
            )
        )
        assert edge_result.scalar_one() is not None

        version_result = await idb.execute(
            select(GraphNode).where(
                GraphNode.external_type == "artifact_version",
                GraphNode.external_id == response.json()["current_version_id"],
            )
        )
        assert version_result.scalar_one() is not None

        event_result = await idb.execute(
            select(GraphEvent).where(
                GraphEvent.event_type == "ARTIFACT_CREATED",
                GraphEvent.node_id == artifact_node.id,
            )
        )
        assert event_result.scalar_one() is not None

        entity = await iclient.get(
            "/api/v1/graph/by-entity",
            params={"external_type": "artifact", "external_id": artifact_id},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert entity.status_code == 200
        assert entity.json()["node"]["id"] == str(artifact_node.id)

        gaps = await iclient.get(
            "/api/v1/graph/traceability-gaps",
            params={"study_id": str(i_study.id)},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert gaps.status_code == 200
        gap_node_ids = {gap["node_id"] for gap in gaps.json()["gaps"]}
        assert str(artifact_node.id) not in gap_node_ids

        artifact_result = await idb.execute(
            select(Artifact).where(Artifact.id == artifact_id)
        )
        artifact = artifact_result.scalar_one()
        service = ArtifactService(idb)
        await service.register_artifact_in_graph(artifact)
        await service.register_artifact_in_graph(artifact)
        await idb.commit()

        node_count = await idb.scalar(
            select(func.count())
            .select_from(GraphNode)
            .where(
                GraphNode.external_type == "artifact",
                GraphNode.external_id == artifact_id,
            )
        )
        edge_count = await idb.scalar(
            select(func.count())
            .select_from(GraphEdge)
            .where(
                GraphEdge.source_node_id == artifact_node.id,
                GraphEdge.target_node_id == study_node.id,
                GraphEdge.edge_type == GraphEdgeType.PART_OF,
            )
        )
        assert node_count == 1
        assert edge_count == 1

        submitted = await iclient.post(
            f"/api/v1/artifacts/{artifact_id}/submit",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "IN_REVIEW"

        await idb.refresh(artifact_node)
        assert artifact_node.properties["status"] == "IN_REVIEW"
        submitted_event = await idb.execute(
            select(GraphEvent).where(
                GraphEvent.event_type == "ARTIFACT_SUBMITTED",
                GraphEvent.node_id == artifact_node.id,
            )
        )
        assert submitted_event.scalar_one() is not None
