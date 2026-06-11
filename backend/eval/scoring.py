"""Automated scoring for generated artifacts.

These metrics are cheap, deterministic, and run on every output. They are
*proxies for review burden*, not a substitute for it — semantic / clinical
correctness still needs a human (see the review template the harness emits).
What they do give you, per model:

- ``json_valid``        : did the real parser return a dict at all.
- ``schema_coverage``   : fraction of the generator's documented top-level keys
                          that are present and non-empty.
- ``cdisc_*``           : conformance from the platform's own rule engine
                          (``run_cdisc_validation``) — the deterministic oracle.
- ``placeholder_rate``  : fraction of leaf values left as stubs ("", null,
                          "To be specified", "<...>"). A high rate means the
                          model returned scaffolding a reviewer must fill in.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.artifact import ArtifactType
from app.services.cdisc_validation_engine import run_cdisc_validation

# Documented top-level keys from each generator's _SYSTEM schema. Used for a
# coarse structural-completeness signal independent of the CDISC rule engine.
EXPECTED_TOP_LEVEL_KEYS: dict[ArtifactType, list[str]] = {
    ArtifactType.SDTM_DATASET: [
        "document_type", "version", "sdtm_ig_version", "domains",
        "supplemental_qualifiers", "define_xml_version", "validation_notes",
        "regulatory_references",
    ],
    ArtifactType.ADAM_DATASET: [
        "document_type", "version", "adam_ig_version", "datasets",
        "traceability_notes", "regulatory_references",
    ],
    ArtifactType.TLF: [
        "document_type", "version", "ich_e3_sections", "tables", "listings",
        "figures", "output_formats", "regulatory_references",
    ],
    ArtifactType.PROTOCOL: [
        "document_type", "version", "title", "protocol_number", "synopsis",
        "objectives", "study_design", "eligibility", "study_procedures",
        "endpoints", "statistical_considerations", "safety_monitoring",
        "regulatory_references",
    ],
    ArtifactType.SAP: [
        "document_type", "version", "title", "study_design_summary",
        "analysis_populations", "estimands", "primary_endpoint_analysis",
        "secondary_endpoints", "subgroup_analyses", "sensitivity_analyses",
        "missing_data", "interim_analyses", "safety_analyses", "software",
        "regulatory_references",
    ],
    ArtifactType.ICF: [
        "document_type", "version", "title", "study_summary", "sections",
        "readability_level", "regulatory_references",
    ],
    ArtifactType.CSR: [
        "document_type", "version", "ich_e3_compliant", "title",
        "study_identification", "synopsis", "sections", "appendices",
        "estimated_total_word_count", "regulatory_references",
    ],
}

# Stub strings the generators themselves use as defaults — if the model echoes
# these back it has not actually produced content for that field.
_PLACEHOLDER_MARKERS = (
    "to be specified",
    "to be determined",
    "not specified",
    "tbd",
    "placeholder",
)


@dataclass
class ArtifactScore:
    json_valid: bool
    schema_coverage: float
    placeholder_rate: float
    leaf_count: int
    cdisc_total: int
    cdisc_passed: int
    cdisc_failed: int
    cdisc_errors: int
    cdisc_warnings: int
    parse_error: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def cdisc_pass_rate(self) -> float:
        return self.cdisc_passed / self.cdisc_total if self.cdisc_total else 0.0


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        s = value.strip().lower()
        if s == "":
            return True
        # Unfilled schema slot like "<title>" or "<note>".
        if s.startswith("<") and s.endswith(">"):
            return True
        return any(marker in s for marker in _PLACEHOLDER_MARKERS)
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _walk_leaves(value: object) -> tuple[int, int]:
    """Return (leaf_count, empty_leaf_count) over a nested JSON structure."""
    if isinstance(value, dict):
        total = empty = 0
        for v in value.values():
            t, e = _walk_leaves(v)
            total += t
            empty += e
        return total, empty
    if isinstance(value, list):
        if not value:
            return 1, 1  # an empty list is itself an unfilled leaf
        total = empty = 0
        for v in value:
            t, e = _walk_leaves(v)
            total += t
            empty += e
        return total, empty
    # Scalar leaf.
    return 1, (1 if _is_empty(value) else 0)


def _schema_coverage(content: dict, expected_keys: list[str]) -> float:
    if not expected_keys:
        return 1.0
    present = sum(
        1 for k in expected_keys if k in content and not _is_empty(content[k])
    )
    return present / len(expected_keys)


def score_artifact(
    *,
    artifact_type: ArtifactType,
    parsed: dict | None,
    parse_error: str | None,
) -> ArtifactScore:
    """Score one generated artifact. ``parsed=None`` means the model never
    produced valid JSON — every quality metric floors to zero."""
    if parsed is None:
        return ArtifactScore(
            json_valid=False,
            schema_coverage=0.0,
            placeholder_rate=1.0,
            leaf_count=0,
            cdisc_total=0,
            cdisc_passed=0,
            cdisc_failed=0,
            cdisc_errors=0,
            cdisc_warnings=0,
            parse_error=parse_error,
            notes=["invalid_json"],
        )

    expected = EXPECTED_TOP_LEVEL_KEYS.get(artifact_type, [])
    coverage = _schema_coverage(parsed, expected)

    leaf_total, leaf_empty = _walk_leaves(parsed)
    placeholder_rate = (leaf_empty / leaf_total) if leaf_total else 1.0

    # Reuse the platform's own CDISC/ICH rule engine as the conformance oracle.
    cdisc = run_cdisc_validation(parsed, artifact_type.value)

    return ArtifactScore(
        json_valid=True,
        schema_coverage=coverage,
        placeholder_rate=placeholder_rate,
        leaf_count=leaf_total,
        cdisc_total=cdisc.get("total_checks", 0),
        cdisc_passed=cdisc.get("passed_checks", 0),
        cdisc_failed=cdisc.get("failed_checks", 0),
        cdisc_errors=cdisc.get("error_count", 0),
        cdisc_warnings=cdisc.get("warning_count", 0),
        parse_error=None,
    )
