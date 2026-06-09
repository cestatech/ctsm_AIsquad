"""Unit tests for TLF generation graph registration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.artifact import ArtifactType
from app.services.tlf_generation_service import TLFGenerationService


@pytest.mark.asyncio
async def test_register_cip_links_creates_adam_to_tlf_edge():
    db = AsyncMock()
    svc = TLFGenerationService(db)
    svc._graph = AsyncMock()
    svc._lineage = AsyncMock()
    svc._artifact_repo = AsyncMock()

    actor = MagicMock()
    actor.id = uuid4()
    actor.organization_id = uuid4()

    adam_id = uuid4()
    tlf_id = uuid4()
    sdtm_id = uuid4()
    study_id = uuid4()
    decision_id = uuid4()

    adam_artifact = MagicMock()
    adam_artifact.id = adam_id
    adam_artifact.name = "ADaM Package"
    adam_artifact.study_id = study_id

    tlf_artifact = MagicMock()
    tlf_artifact.id = tlf_id
    tlf_artifact.name = "TLF Package"
    tlf_artifact.study_id = study_id

    sdtm_artifact = MagicMock()
    sdtm_artifact.id = sdtm_id
    sdtm_artifact.name = "SDTM Package"
    sdtm_artifact.study_id = study_id
    svc._artifact_repo.get_by_id.return_value = sdtm_artifact

    tlf_node = MagicMock(id=uuid4())
    adam_node = MagicMock(id=uuid4())
    sdtm_node = MagicMock(id=uuid4())

    svc._graph.register_domain_record = AsyncMock(return_value=(tlf_node, True))
    svc._graph.find_node_for_domain_record = AsyncMock(return_value=None)
    svc._resolve_graph_node = AsyncMock(side_effect=[adam_node, sdtm_node])
    svc._graph.link_adam_to_tlf = AsyncMock()
    svc._graph.link_sdtm_to_adam = AsyncMock()

    await svc._register_cip_links(
        adam_artifact=adam_artifact,
        tlf_artifact=tlf_artifact,
        tlf_content={
            "tables": [{
                "id": "T-01",
                "title": "Demographics",
                "source_dataset": "ADSL",
            }],
        },
        adam_content={"source_sdtm_artifact_ids": [str(sdtm_id)]},
        actor=actor,
        ai_decision_id=decision_id,
    )

    svc._graph.link_adam_to_tlf.assert_awaited_once()
    svc._graph.link_sdtm_to_adam.assert_awaited_once()
    svc._lineage.record_field_lineage.assert_awaited_once()
