"""ZIP archive export for multi-domain tabular artifacts."""

from __future__ import annotations

import io
import zipfile

from app.services.export.csv_exporter import (
    export_adam_dataset_csv,
    export_sdtm_domain_csv,
)


def _add_to_zip(archive: zipfile.ZipFile, path: str, body: str) -> None:
    archive.writestr(path, body.encode("utf-8"))


def export_sdtm_zip(content: dict, *, include_define_xml: str | None = None) -> bytes:
    """Package each SDTM domain as a separate CSV inside a ZIP archive."""
    domains = content.get("domains") or []
    if not domains:
        raise ValueError("SDTM artifact has no domains to export.")

    buffer = io.BytesIO()
    files_added = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for domain in domains:
            if not isinstance(domain, dict):
                continue
            domain_name = domain.get("domain") or domain.get("name") or "UNKNOWN"
            observations = domain.get("observations") or []
            if not observations:
                continue
            csv_body = export_sdtm_domain_csv(domain_name, observations)
            _add_to_zip(archive, f"{domain_name}.csv", csv_body)
            files_added += 1

        if include_define_xml:
            _add_to_zip(archive, "define.xml", include_define_xml)
            files_added += 1

    if files_added == 0:
        raise ValueError("SDTM artifact has no exportable domain observations.")

    return buffer.getvalue()


def export_adam_zip(content: dict) -> bytes:
    """Package each ADaM dataset as a separate CSV inside a ZIP archive."""
    datasets = content.get("datasets") or []
    if not datasets:
        raise ValueError("ADaM artifact has no datasets to export.")

    buffer = io.BytesIO()
    files_added = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for dataset in datasets:
            if not isinstance(dataset, dict):
                continue
            dataset_name = dataset.get("dataset") or dataset.get("name") or "UNKNOWN"
            csv_body = export_adam_dataset_csv(dataset)
            _add_to_zip(archive, f"{dataset_name}.csv", csv_body)
            files_added += 1

    if files_added == 0:
        raise ValueError("ADaM artifact has no exportable datasets.")

    return buffer.getvalue()
