"""CSV export helpers for tabular clinical artifacts."""

from __future__ import annotations

import csv
import io
from typing import Any


def rows_to_csv(columns: list[str], rows: list[dict[str, Any]]) -> str:
    """Serialize rows to RFC 4180 CSV text."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def export_sdtm_domain_csv(domain_name: str, observations: list[dict[str, Any]]) -> str:
    """Export a single SDTM domain observation set to CSV."""
    if not observations:
        raise ValueError(f"Domain {domain_name} has no observations.")

    columns: list[str] = []
    for obs in observations:
        if isinstance(obs, dict):
            for key in obs:
                if key not in columns:
                    columns.append(key)

    return rows_to_csv(columns, observations)


def export_adam_dataset_csv(dataset: dict[str, Any]) -> str:
    """Export one ADaM dataset as CSV (variables catalog or observations)."""
    dataset_name = dataset.get("dataset") or dataset.get("name") or "UNKNOWN"
    variables = dataset.get("variables") or []
    observations = dataset.get("observations") or []

    if observations:
        columns: list[str] = []
        for obs in observations:
            if isinstance(obs, dict):
                for key in obs:
                    if key not in columns:
                        columns.append(key)
        return rows_to_csv(columns, observations)

    if variables:
        columns = ["dataset", "variable", "label", "type", "derivation", "origin"]
        rows = [
            {
                "dataset": dataset_name,
                "variable": var.get("variable") or var.get("name") or "",
                "label": var.get("label") or "",
                "type": var.get("type") or "",
                "derivation": var.get("derivation") or "",
                "origin": var.get("origin") or "",
            }
            for var in variables
            if isinstance(var, dict)
        ]
        return rows_to_csv(columns, rows)

    raise ValueError(f"Dataset {dataset_name} has no exportable rows.")
