"""Export SDTM and ADaM artifact JSON content to SAS XPT transport files."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd


class XptExportError(ValueError):
    """Raised when artifact content cannot be converted to XPT."""


def _observations_to_dataframe(
    observations: list[Any],
    variables: list[Any],
) -> pd.DataFrame:
    """Build a pandas DataFrame from domain observations and variable specs."""
    if not observations:
        columns = []
        for var in variables:
            if isinstance(var, dict):
                columns.append(str(var.get("variable", var.get("name", ""))))
            else:
                columns.append(str(var))
        columns = [c for c in columns if c]
        return pd.DataFrame(columns=columns or None)

    if isinstance(observations[0], dict):
        return pd.DataFrame(observations)

    columns = [str(v) for v in variables] if variables else []
    rows = []
    for row in observations:
        if isinstance(row, (list, tuple)):
            rows.append(dict(zip(columns, row, strict=False)))
        else:
            rows.append({"VALUE": row})
    return pd.DataFrame(rows)


def _write_xpt_bytes(df: pd.DataFrame, *, table_name: str) -> bytes:
    """Write a DataFrame to SAS XPT format and return raw bytes."""
    try:
        import pyreadstat
    except ImportError as exc:
        raise XptExportError(
            "pyreadstat is required for XPT export. Install backend requirements."
        ) from exc

    safe_name = (table_name or "DATA")[:8].upper()
    with tempfile.NamedTemporaryFile(suffix=".xpt", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        pyreadstat.write_xport(df, tmp_path, table_name=safe_name)
        return Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def export_sdtm_domain_xpt(domain: dict) -> bytes:
    """
    Export one SDTM domain dict to XPT bytes.

    Expects keys: domain, variables, observations.
    """
    domain_code = domain.get("domain", "UNK")
    variables = domain.get("variables", [])
    observations = domain.get("observations", [])
    df = _observations_to_dataframe(observations, variables)
    if df.empty and not list(df.columns):
        raise XptExportError(f"SDTM domain {domain_code} has no variables or observations.")
    return _write_xpt_bytes(df, table_name=domain_code)


def export_sdtm_study_xpt(content: dict) -> dict[str, bytes]:
    """
    Export all SDTM domains in artifact content to {domain_code: xpt_bytes}.

    Raises XptExportError if document_type is not SDTM_DATASET or no domains exist.
    """
    if content.get("document_type") != "SDTM_DATASET":
        raise XptExportError("Content is not an SDTM_DATASET document.")

    domains = content.get("domains", [])
    if not domains:
        raise XptExportError("SDTM content has no domains.")

    result: dict[str, bytes] = {}
    for domain in domains:
        code = domain.get("domain", "UNK")
        result[str(code).upper()] = export_sdtm_domain_xpt(domain)
    return result


def export_adam_dataset_xpt(dataset: dict) -> bytes:
    """Export one ADaM dataset dict to XPT bytes."""
    ds_name = dataset.get("dataset", "ADAM")
    variables = dataset.get("variables", [])
    observations = dataset.get("observations", [])
    df = _observations_to_dataframe(observations, variables)
    if df.empty and not list(df.columns):
        raise XptExportError(f"ADaM dataset {ds_name} has no variables or observations.")
    return _write_xpt_bytes(df, table_name=ds_name)


def export_adam_study_xpt(content: dict) -> dict[str, bytes]:
    """Export all ADaM datasets in artifact content to {dataset_name: xpt_bytes}."""
    datasets = content.get("datasets", [])
    if not datasets:
        raise XptExportError("ADaM content has no datasets.")

    result: dict[str, bytes] = {}
    for dataset in datasets:
        name = dataset.get("dataset", "ADAM")
        result[str(name).upper()] = export_adam_dataset_xpt(dataset)
    return result


def xpt_filename_for_domain(domain_code: str) -> str:
    """Return canonical XPT filename matching define.xml leaf href convention."""
    return f"{domain_code.lower()}.xpt"


def bundle_xpt_zip(files: dict[str, bytes]) -> bytes:
    """Zip multiple XPT files for dev download."""
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(files.items()):
            filename = name if name.endswith(".xpt") else xpt_filename_for_domain(name)
            zf.writestr(filename, data)
    return buffer.getvalue()
