"""Unit tests for ADaM generation service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import anthropic
import pytest
from fastapi import HTTPException

from app.models.artifact import ArtifactType
from app.services.adam_generation_service import ADAMGenerationService
from app.services.generation_fallback import DUMMY_GENERATION_NOTICE


class TestDeterministicAdam:
    def test_builds_adsl_from_dm_domain(self):
        sdtm_domains = [{
            "domain": "DM",
            "variables": ["STUDYID", "USUBJID", "SUBJID", "AGE"],
            "observations": [
                {"STUDYID": "STUDY-1", "USUBJID": "STUDY-1-001", "AGE": "45"},
            ],
        }]
        result = ADAMGenerationService._deterministic_adam(
            protocol_number="STUDY-1",
            sdtm_domains=sdtm_domains,
        )
        assert len(result["datasets"]) >= 1
        adsl = result["datasets"][0]
        assert adsl["dataset"] == "ADSL"
        var_names = {v["variable"] for v in adsl["variables"]}
        assert "USUBJID" in var_names
        assert "SUBJID" in var_names
        assert any(f["variable"] == "ITTFL" for f in adsl["population_flags"])
        assert result["traceability_notes"]

    def test_adds_adae_when_ae_domain_present(self):
        sdtm_domains = [
            {
                "domain": "DM",
                "variables": ["USUBJID"],
                "observations": [{"USUBJID": "S001"}],
            },
            {
                "domain": "AE",
                "variables": ["USUBJID", "AEDECOD"],
                "observations": [{"USUBJID": "S001", "AEDECOD": "Headache"}],
            },
        ]
        result = ADAMGenerationService._deterministic_adam(
            protocol_number="STUDY-1",
            sdtm_domains=sdtm_domains,
        )
        datasets = {d["dataset"] for d in result["datasets"]}
        assert "ADSL" in datasets
        assert "ADAE" in datasets


class TestBDSDerivation:
    def test_derives_adlb_from_lb_domain(self):
        sdtm_domains = [{
            "domain": "LB",
            "variables": ["USUBJID", "LBTESTCD", "LBSTRESN"],
            "observations": [{
                "USUBJID": "S001",
                "LBTESTCD": "GLUC",
                "LBSTRESN": "95",
            }],
        }]
        adlb = ADAMGenerationService._derive_adlb(sdtm_domains[0])
        assert adlb["dataset"] == "ADLB"
        var_names = {v["variable"] for v in adlb["variables"]}
        assert {"AVAL", "BASE", "CHG", "PCHG", "ANRLO", "ANRHI", "ANL01FL"} <= var_names
        assert len(adlb["observations"]) == 1
        assert adlb["observations"][0]["PARAMCD"] == "GLUC"

    def test_enrich_adds_adlb_advs_adtte(self):
        sdtm_domains = [
            {
                "domain": "DM",
                "variables": ["USUBJID"],
                "observations": [{"USUBJID": "S001"}],
            },
            {
                "domain": "LB",
                "variables": ["USUBJID", "LBTESTCD"],
                "observations": [{"USUBJID": "S001", "LBTESTCD": "HGB"}],
            },
            {
                "domain": "VS",
                "variables": ["USUBJID", "VSTESTCD"],
                "observations": [{"USUBJID": "S001", "VSTESTCD": "SYSBP"}],
            },
            {
                "domain": "AE",
                "variables": ["USUBJID", "AEDECOD"],
                "observations": [{"USUBJID": "S001", "AEDECOD": "Headache"}],
            },
        ]
        base = ADAMGenerationService._deterministic_adam(
            protocol_number="STUDY-1",
            sdtm_domains=sdtm_domains,
        )
        datasets = {d["dataset"] for d in base["datasets"]}
        assert "ADLB" in datasets
        assert "ADVS" in datasets
        assert "ADTTE" in datasets

    def test_derives_advs_with_bds_variables(self):
        vs_domain = {
            "domain": "VS",
            "observations": [{"USUBJID": "S001", "VSTESTCD": "SYSBP", "VSSTRESN": "120"}],
        }
        advs = ADAMGenerationService._derive_advs(vs_domain)
        assert advs["dataset"] == "ADVS"
        assert advs["observations"][0]["PARAMCD"] == "SYSBP"

    def test_derives_adtte_from_ae_domain(self):
        ae_domain = {
            "domain": "AE",
            "observations": [{
                "USUBJID": "S001",
                "AEDECOD": "Nausea",
                "AESTDY": "5",
                "AESER": "N",
            }],
        }
        adtte = ADAMGenerationService._derive_adtte(ae_domain, "AE")
        assert adtte["dataset"] == "ADTTE"
        assert adtte["observations"][0]["EVNTDESC"] == "Nausea"
        assert adtte["observations"][0]["SRCDOM"] == "AE"

    def test_derives_adtte_from_ds_domain(self):
        ds_domain = {
            "domain": "DS",
            "observations": [{
                "USUBJID": "S001",
                "DSDECOD": "COMPLETED",
                "DSDY": "180",
            }],
        }
        adtte = ADAMGenerationService._derive_adtte(ds_domain, "DS")
        assert adtte["dataset"] == "ADTTE"
        assert adtte["observations"][0]["SRCDOM"] == "DS"


class TestAssertSdtmReady:
    def test_rejects_empty_domains(self):
        with pytest.raises(HTTPException) as exc:
            ADAMGenerationService._assert_sdtm_ready({}, "Test SDTM")
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "SDTM_NOT_READY"

    def test_rejects_no_observations(self):
        with pytest.raises(HTTPException) as exc:
            ADAMGenerationService._assert_sdtm_ready(
                {"domains": [{"domain": "DM", "observations": []}]},
                "Test SDTM",
            )
        assert exc.value.status_code == 422


@pytest.mark.asyncio
class TestBuildAdamContentFallback:
    async def test_api_error_uses_deterministic_fallback_labels(self):
        svc = ADAMGenerationService(AsyncMock())
        svc._client = MagicMock()
        svc._settings = MagicMock(ADAM_IG_VERSION="1.3", pinnacle21_configured=False)
        sdtm_domains = [{
            "domain": "DM",
            "variables": ["USUBJID", "AGE"],
            "observations": [{"USUBJID": "S001", "AGE": "30"}],
        }]
        svc._call_claude = AsyncMock(
            side_effect=anthropic.APIError(
                message="rate limit",
                request=MagicMock(),
                body=None,
            )
        )

        content = await svc._build_adam_content(
            study_name="Study",
            protocol_number="PROT-001",
            sdtm_domains=sdtm_domains,
            source_sdtm_artifact_ids=[uuid4()],
        )

        assert content["generation_mode"] == "DUMMY"
        assert content["derivation_method"] == "deterministic_fallback"
        assert content["generation_notice"] == DUMMY_GENERATION_NOTICE
        assert "Anthropic API error" in content["fallback_reason"]
        assert any(d["dataset"] == "ADSL" for d in content["datasets"])

    async def test_no_client_uses_deterministic_fallback_labels(self):
        svc = ADAMGenerationService(AsyncMock())
        svc._client = None
        svc._settings = MagicMock(ADAM_IG_VERSION="1.3", pinnacle21_configured=False)
        sdtm_domains = [{
            "domain": "DM",
            "variables": ["USUBJID"],
            "observations": [{"USUBJID": "S001"}],
        }]

        content = await svc._build_adam_content(
            study_name="Study",
            protocol_number="PROT-001",
            sdtm_domains=sdtm_domains,
            source_sdtm_artifact_ids=[uuid4()],
        )

        assert content["generation_mode"] == "DUMMY"
        assert content["derivation_method"] == "deterministic_fallback"
        assert "No Anthropic API key configured" in content["fallback_reason"]


@pytest.mark.asyncio
class TestGenerateFromSdtmArtifact:
    async def test_generate_creates_adam_artifact(self):
        db = AsyncMock()
        svc = ADAMGenerationService(db)
        org_id = uuid4()
        study_id = uuid4()
        sdtm_id = uuid4()

        actor = MagicMock()
        actor.id = uuid4()
        actor.organization_id = org_id

        sdtm_artifact = MagicMock()
        sdtm_artifact.id = sdtm_id
        sdtm_artifact.study_id = study_id
        sdtm_artifact.name = "SDTM Package"
        sdtm_artifact.artifact_type = ArtifactType.SDTM_DATASET
        sdtm_artifact.current_version_id = uuid4()

        study = MagicMock()
        study.id = study_id
        study.name = "Test Study"
        study.protocol_number = "PROT-001"

        adam_artifact = MagicMock()
        adam_artifact.id = uuid4()
        adam_artifact.current_version_id = uuid4()
        adam_artifact.study_id = study_id
        adam_artifact.name = "ADaM Package"

        decision = MagicMock()
        decision.id = uuid4()

        validation_run = MagicMock()
        validation_run.id = uuid4()
        validation_run.organization_id = org_id

        version = MagicMock()
        version.content = {
            "document_type": "SDTM_DATASET",
            "data_source": {
                "data_source_type": "LIVE_FINAL",
                "data_cut_label": "Final",
                "is_synthetic": False,
                "study_id": str(study_id),
                "created_by": str(actor.id),
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            "domains": [{
                "domain": "DM",
                "variables": ["STUDYID", "USUBJID", "SUBJID", "AGE"],
                "observations": [{"USUBJID": "S001", "AGE": "30"}],
            }],
        }

        svc._artifact_repo.get_by_id = AsyncMock(return_value=sdtm_artifact)
        svc._artifact_repo.get_version = AsyncMock(return_value=version)
        svc._study_repo.get = AsyncMock(return_value=study)
        svc._client = None
        svc._artifact_svc.create_artifact = AsyncMock(return_value=adam_artifact)
        svc._ai_decision.begin_decision = AsyncMock(return_value=decision)
        svc._ai_decision.complete_decision = AsyncMock()
        svc._validation.trigger = AsyncMock(return_value=validation_run)
        svc._audit.log = AsyncMock()
        svc._register_cip_links = AsyncMock()
        svc._graph.link_pipeline_artifact_to_study = AsyncMock()

        with (
            patch(
                "app.services.adam_generation_service.DualProgrammerQCService"
            ) as mock_qc_cls,
            patch(
                "app.services.adam_generation_service.check_permission",
                return_value=None,
            ),
            patch.object(mock_qc_cls.return_value, "run_qc", new_callable=AsyncMock),
        ):
            result = await svc.generate_from_sdtm_artifact(sdtm_id, actor)

        assert result.artifact is adam_artifact
        assert result.dataset_count >= 1
        svc._artifact_svc.create_artifact.assert_called_once()
        svc._validation.trigger.assert_called_once()
