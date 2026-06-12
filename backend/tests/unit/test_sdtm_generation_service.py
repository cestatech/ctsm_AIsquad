"""Unit tests for SDTM generation service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.models.raw_data import RawField
from app.services.generation_fallback import DUMMY_GENERATION_NOTICE
from app.services.sdtm_generation_service import SDTMGenerationService


def _make_field(
    *,
    status: str = "APPROVED",
    sdtm: str = "DM.AGE",
    column: str = "AGE",
) -> MagicMock:
    f = MagicMock(spec=RawField)
    f.id = uuid4()
    f.column_name = column
    f.mapping_status = status
    f.mapped_sdtm_variable_id = sdtm
    f.mapped_ecrf_field_id = "AGE"
    f.inferred_type = "number"
    f.study_id = uuid4()
    return f


class TestLoadDatasetRows:
    def test_raises_when_no_rows_available(self):
        svc = SDTMGenerationService(MagicMock())
        svc._settings = MagicMock(STORAGE_LOCAL_PATH="/tmp/celerius-storage")

        upload = MagicMock()
        upload.file_path = "/missing/file.csv"
        upload.mime_type = "text/csv"
        upload.original_filename = "missing.csv"

        dataset = MagicMock()
        dataset.dataset_name = "missing.csv"
        dataset.row_count = 0

        with (
            patch(
                "app.services.sdtm_generation_service.UploadService.read_tabular_rows",
                return_value=[],
            ),
            patch(
                "app.services.sdtm_generation_service.UploadService.reconstruct_rows_from_fields",
                return_value=[],
            ),
            pytest.raises(HTTPException) as exc,
        ):
            svc._load_dataset_rows(upload=upload, dataset=dataset, fields=[])

        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "NO_RAW_ROWS"


class TestAssertReadyForGeneration:
    def test_rejects_unapproved_mappings(self):
        fields = [_make_field(status="PENDING_APPROVAL")]
        with pytest.raises(HTTPException) as exc:
            SDTMGenerationService._assert_ready_for_generation(fields)
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "MAPPINGS_NOT_READY"

    def test_rejects_missing_sdtm_variable(self):
        f = _make_field()
        f.mapped_sdtm_variable_id = None
        with pytest.raises(HTTPException) as exc:
            SDTMGenerationService._assert_ready_for_generation([f])
        assert exc.value.status_code == 422

    def test_passes_when_all_approved_with_sdtm(self):
        SDTMGenerationService._assert_ready_for_generation([_make_field()])


class TestParseAiSpec:
    def test_parses_fenced_json(self):
        raw = '```json\n{"domains": [{"domain": "DM"}], "derived_variables": []}\n```'
        parsed = SDTMGenerationService._parse_ai_spec(raw)
        assert parsed is not None
        assert parsed["domains"][0]["domain"] == "DM"

    def test_returns_none_for_empty_text(self):
        assert SDTMGenerationService._parse_ai_spec("") is None
        assert SDTMGenerationService._parse_ai_spec("   ") is None

    def test_returns_none_for_garbage(self):
        assert SDTMGenerationService._parse_ai_spec("not json at all") is None


class TestMaterializeSdtmDomains:
    def test_materializes_all_rows_from_compact_spec(self):
        ai_spec = {
            "domains": [
                {
                    "domain": "DM",
                    "domain_label": "Demographics",
                    "variables": ["STUDYID", "DOMAIN", "USUBJID", "AGE"],
                    "column_transforms": [
                        {"source_column": "AGE", "target_variable": "AGE", "transform": "direct"}
                    ],
                }
            ],
            "derived_variables": [],
        }
        mapping = [
            {
                "column_name": "AGE",
                "sdtm_variable": "DM.AGE",
                "ecrf_field": "AGE",
                "inferred_type": "number",
            }
        ]
        rows = [{"AGE": "30"}, {"AGE": "45"}]
        result = SDTMGenerationService._materialize_sdtm_domains(
            ai_spec,
            mapping_spec=mapping,
            raw_rows=rows,
            protocol_number="PROT-001",
        )
        assert len(result["domains"]) == 1
        assert len(result["domains"][0]["observations"]) == 2
        assert result["domains"][0]["observations"][1]["AGE"] == "45"


class TestBuildSdtmUserPrompt:
    def test_limits_sample_rows_and_columns(self):
        mapping = [
            {"column_name": "AGE", "sdtm_variable": "DM.AGE"},
            {"column_name": "SEX", "sdtm_variable": "DM.SEX"},
        ]
        rows = [
            {"AGE": "30", "SEX": "M", "IGNORED": "x"} for _ in range(20)
        ]
        prompt = SDTMGenerationService._build_sdtm_user_prompt(
            study_name="Study",
            protocol_number="PROT-001",
            mapping_spec=mapping,
            raw_rows=rows,
        )
        assert "Total source rows to materialize locally: 20" in prompt
        assert "IGNORED" not in prompt
        assert '"AGE":"30"' in prompt.replace(" ", "")


class TestDeterministicDomains:
    def test_builds_domain_observations(self):
        mapping = [
            {
                "column_name": "AGE",
                "sdtm_variable": "DM.AGE",
                "ecrf_field": "AGE",
                "inferred_type": "number",
            }
        ]
        rows = [{"AGE": "45"}, {"AGE": "52"}]
        result = SDTMGenerationService._deterministic_domains(
            mapping_spec=mapping,
            raw_rows=rows,
            protocol_number="STUDY-001",
        )
        assert len(result["domains"]) == 1
        assert result["domains"][0]["domain"] == "DM"
        assert len(result["domains"][0]["observations"]) == 2
        assert result["domains"][0]["observations"][0]["AGE"] == "45"


class TestMergeDomains:
    def test_merges_same_domain_observations(self):
        existing = [
            {
                "domain": "DM",
                "variables": ["STUDYID", "USUBJID"],
                "observations": [{"USUBJID": "S001"}],
            }
        ]
        incoming = [
            {
                "domain": "DM",
                "variables": ["AGE"],
                "observations": [{"USUBJID": "S002", "AGE": "45"}],
            },
            {
                "domain": "AE",
                "variables": ["AETERM"],
                "observations": [{"AETERM": "Headache"}],
            },
        ]
        merged = SDTMGenerationService._merge_domains(existing, incoming)
        by_code = {d["domain"]: d for d in merged}
        assert len(by_code["DM"]["observations"]) == 2
        assert "AGE" in by_code["DM"]["variables"]
        assert by_code["AE"]["domain"] == "AE"


@pytest.mark.asyncio
class TestBuildSdtmContentFallback:
    async def test_call_claude_failure_uses_deterministic_fallback(self):
        svc = SDTMGenerationService(AsyncMock())
        svc._client = MagicMock()
        svc._settings = MagicMock(SDTM_IG_VERSION="3.3", pinnacle21_configured=False)
        dataset = MagicMock()
        dataset.id = uuid4()
        dataset.dataset_name = "demographics"
        field = _make_field()
        rows = [{"AGE": "45"}]
        svc._call_claude = AsyncMock(
            side_effect=HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "AI_PARSE_ERROR",
                    "message": "SDTM agent failed after 3 attempts",
                },
            )
        )

        content = await svc._build_sdtm_content(
            dataset=dataset,
            fields=[field],
            raw_rows=rows,
            study_name="Study",
            protocol_number="PROT-001",
        )

        assert content["generation_mode"] == "DUMMY"
        assert content["derivation_method"] == "deterministic_fallback"
        assert content["generation_notice"] == DUMMY_GENERATION_NOTICE
        assert len(content["domains"]) == 1
        assert len(content["domains"][0]["observations"]) == 1

    async def test_no_client_uses_deterministic_fallback_labels(self):
        svc = SDTMGenerationService(AsyncMock())
        svc._client = None
        svc._settings = MagicMock(SDTM_IG_VERSION="3.3", pinnacle21_configured=False)
        dataset = MagicMock()
        dataset.id = uuid4()
        dataset.dataset_name = "demographics"

        content = await svc._build_sdtm_content(
            dataset=dataset,
            fields=[_make_field()],
            raw_rows=[{"AGE": "30"}],
            study_name="Study",
            protocol_number="PROT-001",
        )

        assert content["generation_mode"] == "DUMMY"
        assert content["derivation_method"] == "deterministic_fallback"
        assert "No Anthropic API key configured" in content["fallback_reason"]


@pytest.mark.asyncio
class TestStudyReadiness:
    async def test_not_ready_when_mappings_pending(self):
        db = AsyncMock()
        svc = SDTMGenerationService(db)
        study_id = uuid4()
        org_id = uuid4()

        ds = MagicMock()
        ds.id = uuid4()
        ds.dataset_name = "data"

        field = _make_field(status="PENDING_APPROVAL")
        svc._ds_repo.list_for_study = AsyncMock(return_value=[ds])
        svc._field_repo.list_for_dataset = AsyncMock(return_value=[field])

        readiness = await svc.get_study_readiness(study_id, org_id)
        assert readiness.ready is False
        assert readiness.dataset_count == 1
        assert readiness.approved_fields == 0


@pytest.mark.asyncio
class TestGenerateFromDataset:
    async def test_generate_creates_artifact_and_validation(self):
        db = AsyncMock()
        svc = SDTMGenerationService(db)
        org_id = uuid4()
        dataset_id = uuid4()
        study_id = uuid4()

        actor = MagicMock()
        actor.id = uuid4()
        actor.organization_id = org_id
        actor.email = "contrib@test.com"

        dataset = MagicMock()
        dataset.id = dataset_id
        dataset.study_id = study_id
        dataset.dataset_name = "Sheet1"
        dataset.uploaded_file_id = uuid4()

        upload = MagicMock()
        upload.file_path = "/tmp/test.csv"
        upload.mime_type = "text/csv"
        upload.original_filename = "data.csv"

        study = MagicMock()
        study.name = "Test Study"
        study.protocol_number = "PROT-001"

        field = _make_field()
        field.study_id = study_id

        artifact = MagicMock()
        artifact.id = uuid4()
        artifact.current_version_id = uuid4()
        artifact.study_id = study_id
        artifact.name = "SDTM"

        decision = MagicMock()
        decision.id = uuid4()

        validation_run = MagicMock()
        validation_run.id = uuid4()
        validation_run.organization_id = org_id

        svc._ds_repo.get = AsyncMock(return_value=dataset)
        svc._field_repo.list_for_dataset = AsyncMock(return_value=[field])
        svc._upload_repo.get_by_id = AsyncMock(return_value=upload)
        svc._study_repo.get = AsyncMock(return_value=study)
        svc._client = None
        svc._artifact_svc.create_artifact = AsyncMock(return_value=artifact)
        svc._artifact_repo.list_by_study = AsyncMock(return_value=([], 0))
        svc._ai_decision.begin_decision = AsyncMock(return_value=decision)
        svc._ai_decision.complete_decision = AsyncMock()
        svc._validation.trigger = AsyncMock(return_value=validation_run)
        svc._audit.log = AsyncMock()
        svc._register_cip_links = AsyncMock()
        svc._graph.link_pipeline_artifact_to_study = AsyncMock()

        with (
            patch(
                "app.services.sdtm_generation_service.DualProgrammerQCService"
            ) as mock_qc_cls,
            patch(
                "app.services.sdtm_generation_service.check_permission",
                return_value=None,
            ),
            patch.object(mock_qc_cls.return_value, "run_qc", new_callable=AsyncMock),
            patch(
                "app.services.sdtm_generation_service.UploadService.read_tabular_rows",
                return_value=[{"AGE": "30"}],
            ),
        ):
            result = await svc.generate_from_dataset(dataset_id, actor)

        assert result.artifact is artifact
        assert result.validation_run is validation_run
        assert result.domain_count >= 1
        svc._artifact_svc.create_artifact.assert_called_once()
        svc._validation.trigger.assert_called_once()
