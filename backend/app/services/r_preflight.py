"""Preflight validation for R statistical programming workflows."""

from __future__ import annotations

from typing import Any

from app.models.statistical_qc import StatisticalQCWorkflow

_REQUIRED_RAW_COLUMNS = {"USUBJID", "STUDYID"}
_OPTIONAL_RAW_ALIASES = {
    "USUBJID": {"usubjid", "subject_id", "SUBJECT_ID", "subjid"},
    "STUDYID": {"studyid", "study_id", "STUDY"},
    "AGE": {"age"},
}

_WORKFLOW_REQUIRED_OUTPUTS: dict[StatisticalQCWorkflow, list[str]] = {
    StatisticalQCWorkflow.RAW_TO_SDTM: ["dm.csv"],
    StatisticalQCWorkflow.SDTM_TO_ADAM: ["adsl.csv"],
    StatisticalQCWorkflow.ADAM_TO_TLF: ["t_demog.csv"],
}


def _normalize_col(name: str) -> str:
    return name.strip().upper().replace(" ", "_")


def _columns_from_payload(input_payload: dict) -> set[str]:
    cols: set[str] = set()
    for domain in input_payload.get("domains", []):
        for row in domain.get("observations", [])[:1]:
            cols.update(_normalize_col(k) for k in row.keys())
    for ds in input_payload.get("datasets", []):
        for var in ds.get("variables", []):
            if isinstance(var, dict) and var.get("variable"):
                cols.add(_normalize_col(str(var["variable"])))
    return cols


def _resolve_column(cols: set[str], canonical: str) -> str | None:
    if canonical in cols:
        return canonical
    for alias in _OPTIONAL_RAW_ALIASES.get(canonical, set()):
        if _normalize_col(alias) in cols:
            return _normalize_col(alias)
    return None


def preflight_input_validation(
    input_payload: dict,
    workflow_step: StatisticalQCWorkflow,
) -> dict[str, Any]:
    """
    Validate input payload before generating or executing R programs.

    Returns dict with ok=True or ok=False and structured errors.
    """
    errors: list[str] = []
    warnings: list[str] = []
    cols = _columns_from_payload(input_payload)

    if workflow_step == StatisticalQCWorkflow.RAW_TO_SDTM:
        if not input_payload.get("domains"):
            errors.append("No SDTM domain observations in input payload.")
        missing = []
        for req in _REQUIRED_RAW_COLUMNS:
            if _resolve_column(cols, req) is None:
                missing.append(req)
        if missing:
            errors.append(
                f"Missing required raw columns: {', '.join(missing)}. "
                f"Available columns: {', '.join(sorted(cols)) or 'none'}."
            )

    if workflow_step == StatisticalQCWorkflow.SDTM_TO_ADAM:
        domains = input_payload.get("domains", [])
        if not domains:
            errors.append("No SDTM domains provided for ADaM derivation.")
        dm = next(
            (d for d in domains if str(d.get("domain", "")).upper() == "DM"), None
        )
        if dm is None:
            warnings.append("DM domain not found — ADSL derivation may fail.")

    if workflow_step == StatisticalQCWorkflow.ADAM_TO_TLF:
        datasets = input_payload.get("datasets", [])
        if not datasets:
            errors.append("No ADaM datasets provided for TLF generation.")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "available_columns": sorted(cols),
        "expected_outputs": _WORKFLOW_REQUIRED_OUTPUTS.get(workflow_step, []),
    }
