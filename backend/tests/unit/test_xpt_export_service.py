"""Unit tests for SAS XPT export service."""

from __future__ import annotations

import pytest

from app.services.xpt_export_service import (
    XptExportError,
    bundle_xpt_zip,
    export_sdtm_domain_xpt,
    export_sdtm_study_xpt,
    xpt_filename_for_domain,
)

pytest.importorskip("pyreadstat")
pytest.importorskip("pandas")


def _dm_domain() -> dict:
    return {
        "domain": "DM",
        "variables": [
            {"variable": "STUDYID"},
            {"variable": "USUBJID"},
            {"variable": "SEX"},
        ],
        "observations": [
            {"STUDYID": "DEMO-01", "USUBJID": "DEMO-01-001", "SEX": "M"},
            {"STUDYID": "DEMO-01", "USUBJID": "DEMO-01-002", "SEX": "F"},
        ],
    }


class TestXptExportService:
    def test_export_sdtm_domain_produces_xpt_bytes(self):
        data = export_sdtm_domain_xpt(_dm_domain())
        assert isinstance(data, bytes)
        assert len(data) > 80
        assert data.startswith(b"HEADER")

    def test_export_sdtm_study_returns_all_domains(self):
        content = {
            "document_type": "SDTM_DATASET",
            "domains": [_dm_domain()],
        }
        files = export_sdtm_study_xpt(content)
        assert "DM" in files
        assert files["DM"].startswith(b"HEADER")

    def test_rejects_non_sdtm_document(self):
        with pytest.raises(XptExportError, match="SDTM_DATASET"):
            export_sdtm_study_xpt({"document_type": "PROTOCOL", "domains": []})

    def test_xpt_filename_convention(self):
        assert xpt_filename_for_domain("DM") == "dm.xpt"

    def test_bundle_xpt_zip_contains_files(self):
        import zipfile
        import io

        zbytes = bundle_xpt_zip({"DM": export_sdtm_domain_xpt(_dm_domain())})
        with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
            names = zf.namelist()
        assert "dm.xpt" in names
