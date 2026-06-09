"""Unit tests for data cut classification and CSR readiness helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.models.data_source import DataSourceType
from app.services.data_cut_service import (
    DataCutContext,
    assert_compatible_data_cuts,
    contains_shell_placeholder,
    prepare_pipeline_artifact,
)
from app.services.r_program_runner import compare_csv_files_semantic as runner_compare
from pathlib import Path


class TestDataCutContext:
    def test_synthetic_label(self):
        study_id = uuid4()
        run_id = uuid4()
        user_id = uuid4()
        ctx = DataCutContext.for_synthetic_run(
            study_id=study_id,
            created_by=user_id,
            run_id=run_id,
            version_number=2,
        )
        assert ctx.data_source_type == DataSourceType.SYNTHETIC
        assert ctx.data_cut_label == "Synthetic Data Version 2"
        assert ctx.is_synthetic is True
        assert ctx.data_cut_id == run_id

    def test_pipeline_artifact_naming(self):
        ctx = DataCutContext(
            data_source_type=DataSourceType.LIVE_INTERIM,
            data_cut_label="Week 8 Interim Data Cut",
            data_cut_date=date(2026, 8, 15),
            is_synthetic=False,
            study_id=uuid4(),
            created_by=uuid4(),
            created_at=datetime.now(UTC),
            source_upload_id=uuid4(),
        )
        name, desc, content, meta = prepare_pipeline_artifact(
            study_name="Clarity50",
            package_label="SDTM Package",
            data_cut=ctx,
            content={"domains": []},
            base_description="derived SDTM",
        )
        assert "Week 8" in name
        assert "Live Interim" in desc
        assert content["data_source"]["data_cut_label"] == "Week 8 Interim Data Cut"
        assert meta["data_cut"]["is_synthetic"] is False


class TestDataCutCompatibility:
    def test_blocks_mixed_sources(self):
        a = DataCutContext.for_synthetic_run(
            study_id=uuid4(), created_by=uuid4(), run_id=uuid4()
        )
        b = DataCutContext.for_live_upload(
            study_id=a.study_id,
            created_by=a.created_by,
            upload_id=uuid4(),
            data_source_type=DataSourceType.LIVE_FINAL,
            data_cut_label="Final Data Cut",
            data_cut_date=date.today(),
        )
        with pytest.raises(Exception) as exc:
            assert_compatible_data_cuts(a, b, operation="ADaM")
        assert exc.value.status_code == 422


class TestShellDetection:
    def test_detects_placeholder(self):
        assert contains_shell_placeholder("Table placeholder for efficacy")
        assert not contains_shell_placeholder("Integrated TLF evidence: T-01")


class TestSemanticCsvCompare:
    def test_tolerates_column_order(self, tmp_path: Path):
        p = tmp_path / "p.csv"
        q = tmp_path / "q.csv"
        p.write_text("STUDYID,USUBJID,AGE\nS1,S1-001,45\n")
        q.write_text("AGE,USUBJID,STUDYID\n45,S1-001,S1\n")
        result = runner_compare(p, q)
        assert result["status"] == "MATCH"
