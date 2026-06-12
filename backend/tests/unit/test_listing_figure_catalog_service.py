"""Unit tests for listing/figure catalog service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.artifact import ArtifactType
from app.services.listing_figure_catalog_service import ListingFigureCatalogService


def _graph_node(*, external_id, artifact_type: str):
    node = MagicMock()
    node.id = uuid4()
    node.external_id = str(external_id)
    node.properties = {"artifact_type": artifact_type}
    return node


def _graph_edge(*, source_id, target_id, properties: dict | None = None):
    edge = MagicMock()
    edge.source_node_id = source_id
    edge.target_node_id = target_id
    edge.properties = properties or {}
    edge.label = None
    return edge


@pytest.mark.asyncio
async def test_build_catalog_maps_sap_sections_from_graph_edges():
    db = AsyncMock()
    svc = ListingFigureCatalogService(db)

    org_id = uuid4()
    study_id = uuid4()
    tlf_id = uuid4()
    sap_id = uuid4()
    version_id = uuid4()

    tlf_artifact = MagicMock()
    tlf_artifact.artifact_type = ArtifactType.TLF
    tlf_artifact.study_id = study_id
    tlf_artifact.current_version_id = version_id

    tlf_version = MagicMock()
    tlf_version.content = {
        "tables": [
            {
                "id": "T-01",
                "title": "Summary of Demographics",
                "section": "14.1",
            }
        ],
        "listings": [],
        "figures": [],
    }

    sap_version = MagicMock()
    sap_version.content = {
        "document_type": "SAP",
        "ich_e3_sections": {"14.1": "Demographics"},
    }

    tlf_node = _graph_node(external_id=tlf_id, artifact_type="TLF")
    sap_node = _graph_node(external_id=sap_id, artifact_type="SAP")
    edge = _graph_edge(
        source_id=sap_node.id,
        target_id=tlf_node.id,
        properties={
            "sap_section": "14.1",
            "output_title": "Summary of Demographics",
            "output_type": "table",
            "tlf_index": 0,
            "status": "specified",
        },
    )

    svc._artifact_repo = AsyncMock()
    svc._artifact_repo.get_by_id.return_value = tlf_artifact
    svc._artifact_repo.get_version.side_effect = [tlf_version, sap_version]

    svc._graph = AsyncMock()
    svc._graph.find_node_for_domain_record = AsyncMock(return_value=tlf_node)
    svc._graph.get_neighbors = AsyncMock(
        return_value={"incoming": [edge], "outgoing": []}
    )
    svc._graph.get_node = AsyncMock(return_value=sap_node)
    svc._graph.list_nodes = AsyncMock(return_value=([], 0))

    catalog = await svc.build_catalog(
        tlf_artifact_id=tlf_id,
        organization_id=org_id,
    )

    assert catalog.sap_artifact_id == sap_id
    assert len(catalog.entries) == 1
    assert catalog.entries[0].sap_section == "14.1"
    assert catalog.entries[0].output_title == "Summary of Demographics"
    assert catalog.entries[0].output_type == "table"


@pytest.mark.asyncio
async def test_build_catalog_returns_empty_entries_without_sap_link():
    db = AsyncMock()
    svc = ListingFigureCatalogService(db)

    org_id = uuid4()
    tlf_id = uuid4()
    version_id = uuid4()

    tlf_artifact = MagicMock()
    tlf_artifact.artifact_type = ArtifactType.TLF
    tlf_artifact.study_id = uuid4()
    tlf_artifact.current_version_id = version_id

    tlf_version = MagicMock()
    tlf_version.content = {
        "tables": [{"id": "T-01", "title": "Demographics", "section": "14.1"}],
        "listings": [],
        "figures": [],
    }

    tlf_node = _graph_node(external_id=tlf_id, artifact_type="TLF")

    svc._artifact_repo = AsyncMock()
    svc._artifact_repo.get_by_id.return_value = tlf_artifact
    svc._artifact_repo.get_version.return_value = tlf_version

    svc._graph = AsyncMock()
    svc._graph.find_node_for_domain_record = AsyncMock(return_value=tlf_node)
    svc._graph.get_neighbors = AsyncMock(return_value={"incoming": [], "outgoing": []})
    svc._graph.list_nodes = AsyncMock(return_value=([], 0))

    catalog = await svc.build_catalog(
        tlf_artifact_id=tlf_id,
        organization_id=org_id,
    )

    assert catalog.sap_artifact_id is None
    assert catalog.entries == []


@pytest.mark.asyncio
async def test_build_catalog_orders_entries_by_sap_section():
    db = AsyncMock()
    svc = ListingFigureCatalogService(db)

    org_id = uuid4()
    study_id = uuid4()
    tlf_id = uuid4()
    sap_id = uuid4()
    version_id = uuid4()

    tlf_artifact = MagicMock()
    tlf_artifact.artifact_type = ArtifactType.TLF
    tlf_artifact.study_id = study_id
    tlf_artifact.current_version_id = version_id

    tlf_version = MagicMock()
    tlf_version.content = {
        "tables": [
            {"id": "T-02", "title": "Exposure", "section": "14.2"},
            {"id": "T-01", "title": "Demographics", "section": "14.1"},
        ],
        "listings": [],
        "figures": [],
    }

    sap_version = MagicMock()
    sap_version.content = {"document_type": "SAP"}

    tlf_node = _graph_node(external_id=tlf_id, artifact_type="TLF")
    sap_node = _graph_node(external_id=sap_id, artifact_type="SAP")
    edge = _graph_edge(source_id=sap_node.id, target_id=tlf_node.id, properties={})

    svc._artifact_repo = AsyncMock()
    svc._artifact_repo.get_by_id.return_value = tlf_artifact
    svc._artifact_repo.get_version.side_effect = [tlf_version, sap_version]

    svc._graph = AsyncMock()
    svc._graph.find_node_for_domain_record = AsyncMock(return_value=tlf_node)
    svc._graph.get_neighbors = AsyncMock(
        return_value={"incoming": [edge], "outgoing": []}
    )
    svc._graph.get_node = AsyncMock(return_value=sap_node)
    svc._graph.list_nodes = AsyncMock(return_value=([], 0))

    catalog = await svc.build_catalog(
        tlf_artifact_id=tlf_id,
        organization_id=org_id,
    )

    assert [entry.sap_section for entry in catalog.entries] == ["14.1", "14.2"]
