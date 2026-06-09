"""Unit tests for CSR generation service."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.data_cut_service import DataCutContext
from fastapi import HTTPException

from app.services.csr_generation_service import CSRGenerationService


class TestAssertTlfReady:
    def test_rejects_empty_tables(self):
        with pytest.raises(HTTPException) as exc:
            CSRGenerationService._assert_tlf_ready({}, "Test TLF")
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "TLF_NOT_READY"

    def test_passes_with_tables(self):
        CSRGenerationService._assert_tlf_ready(
            {"tables": [{"id": "T-01"}]}, "Test TLF"
        )


class TestDeterministicCsr:
    def test_builds_ich_e3_sections(self):
        study = MagicMock()
        study.name = "Test Study"
        study.protocol_number = "PROT-001"
        study.sponsor = "Sponsor Inc"
        study.phase = "PHASE_3"
        study.indication = "Diabetes"

        tables = [
            {
                "id": "T-01",
                "title": "Summary of Demographics",
                "section": "14.1",
                "population": "ITT",
            },
            {
                "id": "T-02",
                "title": "Summary of Treatment Exposure",
                "section": "14.2",
                "population": "Safety",
            },
        ]

        svc = CSRGenerationService(MagicMock())
        upstream = {
            "sdtm_content": {
                "domains": [{
                    "domain": "DM",
                    "observations": [{"USUBJID": "S1-001"}, {"USUBJID": "S1-002"}],
                }],
            },
            "adam_content": {"datasets": [{"dataset": "ADSL"}]},
        }
        data_cut = DataCutContext.for_synthetic_run(
            study_id=uuid4(),
            created_by=uuid4(),
            run_id=uuid4(),
        )
        content = svc._deterministic_csr(
            study=study,
            merged_tables=tables,
            protocol_content={
                "objectives": {"primary": [{"description": "HbA1c change"}]},
                "design": {"summary": "Randomized double-blind"},
            },
            sap_content={"primary_endpoint": "Change in HbA1c at Week 12"},
            tlf_artifact_ids=[],
            upstream=upstream,
            data_cut=data_cut,
        )

        assert content["document_type"] == "CSR"
        assert content.get("shell_only") is False
        assert content["ich_e3_compliant"] is True
        assert content["data_source"]["is_synthetic"] is True
        section_nums = {s["number"] for s in content["sections"]}
        assert "13" in section_nums
        assert "14" in section_nums
        assert content["synopsis"]["objectives"]
        assert len(content["tlf_integration"]) == 2
        assert content["ectd_module_5"]["folder_structure"]

    def test_merge_tlf_tables_deduplicates(self):
        merged = CSRGenerationService._merge_tlf_tables([
            {"tables": [{"id": "T-01", "title": "A"}]},
            {"tables": [{"id": "T-01", "title": "A duplicate"}, {"id": "T-02"}]},
        ])
        assert len(merged) == 2
        assert merged[0]["id"] == "T-01"
