"""Type-aware artifact export orchestration."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.artifact import Artifact, ArtifactType
from app.services.data_cut_service import extract_data_cut

DOCX_TYPES = {ArtifactType.PROTOCOL, ArtifactType.SAP, ArtifactType.CSR}
PDF_TYPES = {ArtifactType.ICF, ArtifactType.TLF, ArtifactType.EDC_CRF}
ZIP_TYPES = {ArtifactType.SDTM_DATASET, ArtifactType.ADAM_DATASET}
CSV_TYPES = {ArtifactType.OTHER}

FORMAT_MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "csv": "text/csv",
    "zip": "application/zip",
    "xml": "application/xml",
    "json": "application/json",
}

TYPE_PREFIX: dict[ArtifactType, str] = {
    ArtifactType.PROTOCOL: "protocol",
    ArtifactType.SAP: "sap",
    ArtifactType.CSR: "csr",
    ArtifactType.ICF: "icf",
    ArtifactType.TLF: "tlf",
    ArtifactType.EDC_CRF: "edc_ecrf",
    ArtifactType.SDTM_DATASET: "sdtm",
    ArtifactType.ADAM_DATASET: "adam",
    ArtifactType.OTHER: "synthetic_raw",
    ArtifactType.VALIDATION_REPORT: "validation_report",
    ArtifactType.TRACEABILITY_MATRIX: "traceability_matrix",
    ArtifactType.SUBMISSION_PACKAGE: "submission_package",
}


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "study"


def _safe_basename(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_") or "export"


@dataclass(frozen=True)
class ExportResult:
    """Binary export payload with HTTP response metadata."""

    filename: str
    content: bytes
    media_type: str
    export_format: str


class ArtifactExportService:
    """Resolve artifact type to the correct user-facing download format."""

    @classmethod
    def default_format(cls, artifact_type: ArtifactType) -> str | None:
        """Return the primary download format for an artifact type."""
        if artifact_type in DOCX_TYPES:
            return "docx"
        if artifact_type in PDF_TYPES:
            return "pdf"
        if artifact_type in ZIP_TYPES:
            return "zip"
        if artifact_type in CSV_TYPES:
            return "csv"
        return None

    @classmethod
    def supported_formats(cls, artifact_type: ArtifactType) -> list[str]:
        """Return supported export formats for an artifact type."""
        formats: list[str] = []
        default = cls.default_format(artifact_type)
        if default:
            formats.append(default)
        if artifact_type == ArtifactType.SDTM_DATASET:
            formats.append("xml")
        return formats

    @classmethod
    def build_filename(
        cls,
        artifact_type: ArtifactType,
        study_slug: str,
        version_number: int,
        export_format: str,
        content: dict | None = None,
        artifact_name: str | None = None,
        artifact_metadata: dict | None = None,
    ) -> str:
        """Build a descriptive, type-specific download filename."""
        if (
            artifact_type == ArtifactType.OTHER
            and export_format == "csv"
            and content
        ):
            primary = content.get("primary_csv_filename")
            if isinstance(primary, str) and primary.strip():
                return _safe_basename(primary)

        cut = extract_data_cut(artifact_metadata, content)
        prefix = TYPE_PREFIX.get(artifact_type, _slugify(artifact_type.value))

        if artifact_type == ArtifactType.CSR and cut:
            if cut.data_source_type.value == "LIVE_INTERIM":
                prefix = "interim_csr"
            elif cut.is_synthetic:
                prefix = "csr_synthetic"

        if cut:
            slug = cut.download_slug(study_slug)
        else:
            slug = _slugify(study_slug) or _slugify(artifact_name or "study")

        version_suffix = f"_v{version_number}"
        if export_format == "xml" and artifact_type == ArtifactType.SDTM_DATASET:
            return f"{prefix}_{slug}{version_suffix}_define.xml"
        if export_format == "json":
            return f"{prefix}_{slug}{version_suffix}.json"
        return f"{prefix}_{slug}{version_suffix}.{export_format}"

    @classmethod
    def export_artifact(
        cls,
        artifact: Artifact,
        content: dict,
        *,
        study_name: str,
        study_slug: str,
        export_format: str,
    ) -> ExportResult:
        """Generate a user-facing export for the artifact."""
        if not content:
            raise ValueError("Artifact has no content to export.")

        version_number = artifact.current_version_number or 1
        artifact_type = artifact.artifact_type

        if export_format == "docx":
            if artifact_type not in DOCX_TYPES:
                raise ValueError(
                    f"DOCX export is not supported for {artifact_type.value}."
                )
            body = export_docx(
                content,
                title=artifact.name,
                study_name=study_name,
                version_number=version_number,
                document_label=artifact_type.value.replace("_", " "),
            )
        elif export_format == "pdf":
            if artifact_type not in PDF_TYPES:
                raise ValueError(
                    f"PDF export is not supported for {artifact_type.value}."
                )
            body = export_pdf(
                content,
                title=artifact.name,
                study_name=study_name,
                version_number=version_number,
                document_label=artifact_type.value.replace("_", " "),
                artifact_type=artifact_type.value,
            )
        elif export_format == "zip":
            if artifact_type == ArtifactType.SDTM_DATASET:
                define_xml = build_define_xml(content)
                body = export_sdtm_zip(content, include_define_xml=define_xml)
            elif artifact_type == ArtifactType.ADAM_DATASET:
                body = export_adam_zip(content)
            else:
                raise ValueError(
                    f"ZIP export is not supported for {artifact_type.value}."
                )
        elif export_format == "xml":
            if artifact_type != ArtifactType.SDTM_DATASET:
                raise ValueError(
                    "XML export is only supported for SDTM datasets."
                )
            body = build_define_xml(content).encode("utf-8")
        elif export_format == "csv":
            if artifact_type == ArtifactType.OTHER:
                from app.services.synthetic_data_service import SyntheticDataService

                _, csv_body = SyntheticDataService.csv_from_content(
                    content, artifact.name
                )
                body = csv_body.encode("utf-8")
            else:
                raise ValueError(
                    f"CSV export is not supported for {artifact_type.value}. "
                    "Use ZIP for SDTM/ADaM datasets."
                )
        else:
            raise ValueError(f"Unsupported export format: {export_format}")

        filename = cls.build_filename(
            artifact_type,
            study_slug,
            version_number,
            export_format,
            content=content,
            artifact_name=artifact.name,
            artifact_metadata=artifact.extra_data,
        )
        media_type = FORMAT_MEDIA_TYPES.get(export_format, "application/octet-stream")
        return ExportResult(
            filename=filename,
            content=body,
            media_type=media_type,
            export_format=export_format,
        )


# Late imports — export helpers pull in reportlab/docx only when used.
from app.services.export.docx_exporter import export_docx  # noqa: E402
from app.services.export.pdf_exporter import export_pdf  # noqa: E402
from app.services.export.zip_exporter import export_adam_zip, export_sdtm_zip  # noqa: E402
from app.services.sdtm_define_service import build_define_xml  # noqa: E402
