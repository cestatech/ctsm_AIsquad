"""Build listing/figure catalogs from SAP traceability graph edges."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import Artifact, ArtifactType
from app.models.graph import GraphEdge, GraphNode
from app.repositories.artifact_repository import ArtifactRepository
from app.services.context_graph_service import ContextGraphService

OutputType = Literal["table", "listing", "figure"]


@dataclass(frozen=True)
class ListingFigureEntry:
    sap_section: str
    output_title: str
    output_type: OutputType
    tlf_index: int
    status: str = "programmed"


@dataclass(frozen=True)
class ListingFigureCatalog:
    sap_artifact_id: UUID | None
    entries: list[ListingFigureEntry]


class ListingFigureCatalogService:
    """Traverse SAP→TLF graph links and build a structured output catalog."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._artifact_repo = ArtifactRepository(db)
        self._graph = ContextGraphService(db)

    async def build_catalog(
        self,
        *,
        tlf_artifact_id: UUID,
        organization_id: UUID,
    ) -> ListingFigureCatalog:
        artifact, content = await self._load_tlf_artifact(
            tlf_artifact_id, organization_id
        )
        tlf_node = await self._resolve_tlf_graph_node(artifact, organization_id)
        if tlf_node is None:
            return ListingFigureCatalog(sap_artifact_id=None, entries=[])

        sap_artifact_id, trace_edges = await self._find_sap_traceability(
            tlf_node=tlf_node,
            organization_id=organization_id,
            study_id=artifact.study_id,
        )
        if sap_artifact_id is None:
            return ListingFigureCatalog(sap_artifact_id=None, entries=[])

        sap_content = await self._load_artifact_content(
            sap_artifact_id, organization_id
        )
        entries = _build_entries_from_trace(
            tlf_content=content,
            sap_content=sap_content,
            trace_edges=trace_edges,
        )
        return ListingFigureCatalog(
            sap_artifact_id=sap_artifact_id,
            entries=entries,
        )

    async def _load_tlf_artifact(
        self, artifact_id: UUID, organization_id: UUID
    ) -> tuple[Artifact, dict]:
        artifact = await self._artifact_repo.get_by_id(artifact_id, organization_id)
        if artifact.artifact_type != ArtifactType.TLF:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "NOT_TLF", "message": "Artifact must be TLF."},
            )
        if artifact.current_version_id is None:
            return artifact, {}
        version = await self._artifact_repo.get_version(artifact.current_version_id)
        return artifact, version.content or {}

    async def _load_artifact_content(
        self, artifact_id: UUID, organization_id: UUID
    ) -> dict:
        artifact = await self._artifact_repo.get_by_id(artifact_id, organization_id)
        if artifact.current_version_id is None:
            return {}
        version = await self._artifact_repo.get_version(artifact.current_version_id)
        return version.content or {}

    async def _resolve_tlf_graph_node(
        self, artifact: Artifact, organization_id: UUID
    ) -> GraphNode | None:
        for external_type in ("tlf_artifact", "artifact"):
            node = await self._graph.find_node_for_domain_record(
                artifact.id, external_type, organization_id
            )
            if node is not None:
                return node
        return None

    async def _find_sap_traceability(
        self,
        *,
        tlf_node: GraphNode,
        organization_id: UUID,
        study_id: UUID,
    ) -> tuple[UUID | None, list[GraphEdge]]:
        trace_edges: list[GraphEdge] = []
        sap_ids: set[UUID] = set()

        incoming = await self._graph.get_neighbors(
            tlf_node.id, organization_id, direction="incoming"
        )
        for edge in incoming["incoming"]:
            source = await self._graph.get_node(edge.source_node_id, organization_id)
            sap_id = _sap_artifact_id_from_node(source)
            if sap_id is not None:
                sap_ids.add(sap_id)
                trace_edges.append(edge)

        outgoing = await self._graph.get_neighbors(
            tlf_node.id, organization_id, direction="outgoing"
        )
        for edge in outgoing["outgoing"]:
            target = await self._graph.get_node(edge.target_node_id, organization_id)
            sap_id = _sap_artifact_id_from_node(target)
            if sap_id is not None:
                sap_ids.add(sap_id)
                trace_edges.append(edge)

        if not sap_ids:
            sap_ids = await self._find_sap_linked_via_study(
                tlf_node=tlf_node,
                organization_id=organization_id,
                study_id=study_id,
                trace_edges=trace_edges,
            )

        if not sap_ids:
            return None, []

        sap_artifact_id = sorted(sap_ids)[0]
        return sap_artifact_id, trace_edges

    async def _find_sap_linked_via_study(
        self,
        *,
        tlf_node: GraphNode,
        organization_id: UUID,
        study_id: UUID,
        trace_edges: list[GraphEdge],
    ) -> set[UUID]:
        """Find SAP nodes in the study with any edge connecting to the TLF node."""
        sap_ids: set[UUID] = set()
        nodes, _ = await self._graph.list_nodes(
            organization_id=organization_id,
            study_id=study_id,
            limit=500,
        )
        for node in nodes:
            sap_id = _sap_artifact_id_from_node(node)
            if sap_id is None:
                continue
            neighbors = await self._graph.get_neighbors(
                node.id, organization_id, direction="both"
            )
            for edge in [*neighbors["outgoing"], *neighbors["incoming"]]:
                if (
                    edge.source_node_id == node.id
                    and edge.target_node_id == tlf_node.id
                ):
                    sap_ids.add(sap_id)
                    trace_edges.append(edge)
                elif (
                    edge.target_node_id == node.id
                    and edge.source_node_id == tlf_node.id
                ):
                    sap_ids.add(sap_id)
                    trace_edges.append(edge)
        return sap_ids


def _sap_artifact_id_from_node(node: GraphNode) -> UUID | None:
    props = node.properties or {}
    artifact_type = str(props.get("artifact_type", "")).upper()
    if artifact_type != ArtifactType.SAP.value:
        return None
    if not node.external_id:
        return None
    try:
        return UUID(str(node.external_id))
    except ValueError:
        return None


def _build_entries_from_trace(
    *,
    tlf_content: dict,
    sap_content: dict,
    trace_edges: list[GraphEdge],
) -> list[ListingFigureEntry]:
    edge_entries = _entries_from_edge_properties(trace_edges)
    if edge_entries:
        return _sort_entries(edge_entries)

    section_labels = _sap_section_labels(sap_content)
    outputs = _iter_tlf_outputs(tlf_content)
    entries: list[ListingFigureEntry] = []
    for index, output in enumerate(outputs):
        section = output.get("section") or _infer_section(output, section_labels)
        entries.append(
            ListingFigureEntry(
                sap_section=section,
                output_title=str(
                    output.get("title")
                    or output.get("id")
                    or output.get("table_id")
                    or "Output"
                ),
                output_type=output["output_type"],
                tlf_index=index,
                status="programmed",
            )
        )
    return _sort_entries(entries)


def _entries_from_edge_properties(
    trace_edges: list[GraphEdge],
) -> list[ListingFigureEntry]:
    entries: list[ListingFigureEntry] = []
    for edge in trace_edges:
        props = edge.properties or {}
        if not props.get("output_title") and not props.get("sap_section"):
            continue
        output_type = str(props.get("output_type", "table")).lower()
        if output_type not in {"table", "listing", "figure"}:
            output_type = "table"
        entries.append(
            ListingFigureEntry(
                sap_section=str(props.get("sap_section") or "unspecified"),
                output_title=str(props.get("output_title") or edge.label or "Output"),
                output_type=output_type,  # type: ignore[arg-type]
                tlf_index=int(props.get("tlf_index", len(entries))),
                status=str(props.get("status") or "specified"),
            )
        )
    return entries


def _iter_tlf_outputs(tlf_content: dict) -> list[dict]:
    outputs: list[dict] = []
    for output_type in ("table", "listing", "figure"):
        key = f"{output_type}s"
        for item in tlf_content.get(key, []) or []:
            if not isinstance(item, dict):
                continue
            outputs.append({**item, "output_type": output_type})
    return outputs


def _sap_section_labels(sap_content: dict) -> dict[str, str]:
    labels: dict[str, str] = {}
    for key, value in (sap_content.get("ich_e3_sections") or {}).items():
        labels[str(key)] = str(value)
    for spec in sap_content.get("tlf_outputs") or []:
        if isinstance(spec, dict) and spec.get("section"):
            labels[str(spec["section"])] = str(
                spec.get("title") or spec.get("section_label") or spec["section"]
            )
    if sap_content.get("primary_endpoint_analysis"):
        labels.setdefault("14.3", "Primary efficacy analyses")
    if sap_content.get("safety_analyses"):
        labels.setdefault("14.4", "Safety analyses")
    return labels


def _infer_section(output: dict, section_labels: dict[str, str]) -> str:
    explicit = output.get("section")
    if explicit:
        return str(explicit)
    title = str(output.get("title") or "").lower()
    for section, label in section_labels.items():
        if label.lower() in title:
            return section
    if "demograph" in title or "baseline" in title:
        return "14.1"
    if "exposure" in title or "compliance" in title:
        return "14.2"
    if "efficacy" in title or "response" in title:
        return "14.3"
    if "adverse" in title or "safety" in title or "ae" in title:
        return "14.4"
    return "14.1"


def _sort_entries(entries: list[ListingFigureEntry]) -> list[ListingFigureEntry]:
    return sorted(
        entries,
        key=lambda entry: (_section_sort_key(entry.sap_section), entry.tlf_index),
    )


def _section_sort_key(section: str) -> tuple[int, ...]:
    numbers = [int(part) for part in re.findall(r"\d+", section)]
    if not numbers:
        return (999, 0)
    return tuple(numbers)
