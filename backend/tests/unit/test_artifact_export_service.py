"""Unit tests for artifact export utilities."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import MagicMock

import pytest

from app.models.artifact import ArtifactType
from app.services.export.artifact_export_service import ArtifactExportService
from app.services.export.csv_exporter import export_adam_dataset_csv, export_sdtm_domain_csv
from app.services.export.docx_exporter import export_docx
from app.services.export.pdf_exporter import export_pdf
from app.services.export.zip_exporter import export_adam_zip, export_sdtm_zip


def _artifact(artifact_type: ArtifactType, version: int = 2):
    artifact = MagicMock()
    artifact.artifact_type = artifact_type
    artifact.name = "Test Artifact"
    artifact.current_version_number = version
    return artifact


class TestCsvExporter:
    def test_export_sdtm_domain_csv(self):
        csv_body = export_sdtm_domain_csv(
            "DM",
            [{"USUBJID": "001", "SEX": "M"}, {"USUBJID": "002", "SEX": "F"}],
        )
        assert "USUBJID,SEX" in csv_body
        assert "001,M" in csv_body

    def test_export_adam_dataset_csv(self):
        csv_body = export_adam_dataset_csv(
            {
                "dataset": "ADSL",
                "variables": [
                    {"variable": "STUDYID", "label": "Study", "derivation": "Assigned"},
                ],
            }
        )
        assert "dataset,variable,label,type,derivation,origin" in csv_body
        assert "ADSL,STUDYID,Study" in csv_body


class TestZipExporter:
    def test_export_sdtm_zip_contains_domain_files(self):
        content = {
            "domains": [
                {
                    "domain": "DM",
                    "observations": [{"USUBJID": "001", "SEX": "M"}],
                },
                {
                    "domain": "AE",
                    "observations": [{"USUBJID": "001", "AETERM": "Headache"}],
                },
            ]
        }
        body = export_sdtm_zip(content)
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            names = archive.namelist()
            assert "DM.csv" in names
            assert "AE.csv" in names

    def test_export_adam_zip_contains_dataset_files(self):
        content = {
            "datasets": [
                {
                    "dataset": "ADSL",
                    "variables": [{"variable": "STUDYID", "label": "Study"}],
                }
            ]
        }
        body = export_adam_zip(content)
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            assert "ADSL.csv" in archive.namelist()


class TestDocxExporter:
    def test_export_docx_returns_bytes(self):
        body = export_docx(
            {"synopsis": {"title": "Demo Study", "phase": "II"}},
            title="Protocol",
            study_name="Demo Study",
            version_number=1,
            document_label="Protocol",
        )
        assert isinstance(body, bytes)
        assert len(body) > 100
        assert body[:2] == b"PK"


class TestPdfExporter:
    def test_export_pdf_returns_pdf_header(self):
        body = export_pdf(
            {"sections": {"introduction": "You are invited to participate."}},
            title="ICF",
            study_name="Demo Study",
            version_number=1,
            document_label="ICF",
            artifact_type="ICF",
        )
        assert body.startswith(b"%PDF")


class TestArtifactExportService:
    def test_build_filename_zip(self):
        filename = ArtifactExportService.build_filename(
            ArtifactType.SDTM_DATASET, "CLARITY-50", 3, "zip"
        )
        assert filename == "sdtm_clarity_50_v3.zip"

    def test_build_filename_xml(self):
        filename = ArtifactExportService.build_filename(
            ArtifactType.SDTM_DATASET, "CLARITY-50", 3, "xml"
        )
        assert filename == "sdtm_clarity_50_v3_define.xml"

    def test_build_filename_synthetic_csv_uses_primary_name(self):
        filename = ArtifactExportService.build_filename(
            ArtifactType.OTHER,
            "CLARITY-50",
            2,
            "csv",
            content={"primary_csv_filename": "CLARITY-50_synthetic_demographics.csv"},
        )
        assert filename == "CLARITY-50_synthetic_demographics.csv"

    def test_build_filename_protocol_docx(self):
        filename = ArtifactExportService.build_filename(
            ArtifactType.PROTOCOL, "CLARITY-50", 1, "docx"
        )
        assert filename == "protocol_clarity_50_v1.docx"

    def test_export_protocol_docx(self):
        artifact = _artifact(ArtifactType.PROTOCOL)
        result = ArtifactExportService.export_artifact(
            artifact,
            {"synopsis": {"title": "Demo"}},
            study_name="Demo Study",
            study_slug="DEMO-001",
            export_format="docx",
        )
        assert result.export_format == "docx"
        assert result.filename.endswith(".docx")

    def test_export_sdtm_zip(self):
        artifact = _artifact(ArtifactType.SDTM_DATASET)
        result = ArtifactExportService.export_artifact(
            artifact,
            {
                "document_type": "SDTM_DATASET",
                "domains": [
                    {"domain": "DM", "observations": [{"USUBJID": "001"}]},
                ],
            },
            study_name="Demo Study",
            study_slug="DEMO-001",
            export_format="zip",
        )
        assert result.export_format == "zip"
        assert result.filename.endswith(".zip")
        with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
            assert "DM.csv" in archive.namelist()
            assert "define.xml" in archive.namelist()

    def test_export_sdtm_xml(self):
        artifact = _artifact(ArtifactType.SDTM_DATASET)
        result = ArtifactExportService.export_artifact(
            artifact,
            {
                "document_type": "SDTM_DATASET",
                "domains": [
                    {"domain": "DM", "observations": [{"USUBJID": "001"}]},
                ],
            },
            study_name="Demo Study",
            study_slug="DEMO-001",
            export_format="xml",
        )
        assert result.export_format == "xml"
        assert b"define" in result.content.lower()

    def test_unsupported_format_raises(self):
        artifact = _artifact(ArtifactType.PROTOCOL)
        with pytest.raises(ValueError, match="PDF export is not supported"):
            ArtifactExportService.export_artifact(
                artifact,
                {"synopsis": {}},
                study_name="Demo",
                study_slug="demo",
                export_format="pdf",
            )
