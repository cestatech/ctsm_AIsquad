"""Unit tests for R preflight validation."""

from __future__ import annotations

from app.models.statistical_qc import StatisticalQCWorkflow
from app.services.r_preflight import preflight_input_validation


class TestPreflightValidation:
    def test_catches_missing_usubjid(self):
        result = preflight_input_validation(
            {
                "domains": [
                    {
                        "domain": "DM",
                        "observations": [{"AGE": "45"}],
                    }
                ],
            },
            StatisticalQCWorkflow.RAW_TO_SDTM,
        )
        assert result["ok"] is False
        assert any("USUBJID" in e for e in result["errors"])

    def test_passes_with_required_columns(self):
        result = preflight_input_validation(
            {
                "domains": [
                    {
                        "domain": "DM",
                        "observations": [
                            {"STUDYID": "S1", "USUBJID": "S1-001", "AGE": "45"},
                        ],
                    }
                ],
            },
            StatisticalQCWorkflow.RAW_TO_SDTM,
        )
        assert result["ok"] is True
