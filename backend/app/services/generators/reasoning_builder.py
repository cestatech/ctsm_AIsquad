"""
Build audit-grade AI decision reasoning from Study Brief intake answers.

Used by artifact generators to populate AIDecision.reasoning with defensible,
intake-grounded explanations rather than generic one-line summaries.
"""

from __future__ import annotations

from typing import Any

from app.models.artifact import ArtifactType
from app.models.study import Study


def _fmt(value: Any) -> str:
    """Format a brief field value for human-readable reasoning."""
    if value is None:
        return "not specified in intake"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        if not value:
            return "not specified in intake"
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(
                    ", ".join(
                        f"{k}: {_fmt(v)}" for k, v in item.items() if v is not None
                    )
                )
            else:
                parts.append(str(item))
        return "; ".join(parts)
    if isinstance(value, dict):
        parts = [f"{k}: {_fmt(v)}" for k, v in value.items() if v is not None]
        return ", ".join(parts) if parts else "not specified in intake"
    return str(value).strip() or "not specified in intake"


def _section(title: str, body: str) -> str:
    return f"{title}\n{body}"


def build_artifact_reasoning(
    artifact_type: ArtifactType,
    study: Study,
    brief_content: dict[str, Any] | None,
    content: dict[str, Any] | None = None,
) -> str:
    """
    Produce detailed reasoning explaining how intake answers drove artifact generation.

    When brief_content is missing, states which inputs were unavailable rather than
    inventing provenance.
    """
    label = artifact_type.value.replace("_", " ")
    sections: list[str] = []

    if artifact_type == ArtifactType.PROTOCOL:
        sections.extend(_protocol_reasoning(study, brief_content, content))
    elif artifact_type == ArtifactType.ICF:
        sections.extend(_icf_reasoning(study, brief_content))
    elif artifact_type == ArtifactType.SAP:
        sections.extend(_sap_reasoning(study, brief_content))
    elif artifact_type == ArtifactType.EDC_CRF:
        sections.extend(_edc_reasoning(study, brief_content, content))
    else:
        sections.append(
            f"The {label} was generated for study '{study.name}' "
            f"(protocol {study.protocol_number})."
        )
        if brief_content:
            sections.append(
                "Source: compiled Study Brief from sponsor intake "
                f"({len(brief_content)} sections: "
                f"{', '.join(brief_content.keys())})."
            )
        else:
            sections.append(
                "Source: study metadata only — no compiled Study Brief was attached "
                "to this generation job."
            )

    sections.append(
        "Downstream impact: this artifact is DRAFT and requires human review before "
        "use in SDTM mapping, statistical programming, TLF generation, CSR assembly, "
        "or regulatory submission packaging."
    )

    return "\n\n".join(sections)


def _protocol_reasoning(
    study: Study,
    brief: dict[str, Any] | None,
    content: dict[str, Any] | None,
) -> list[str]:
    sections: list[str] = []

    if not brief:
        sections.append(
            _section(
                "Summary",
                f"The protocol for '{study.name}' was generated from study metadata only. "
                "No compiled Study Brief was available, so intake-specific design, "
                "endpoint, population, safety, and statistical rationale could not be "
                "cited. Reviewers should verify all sections against sponsor source "
                "documents.",
            )
        )
        return sections

    overview = brief.get("study_overview") or {}
    design = brief.get("study_design") or {}
    population = brief.get("population") or {}
    endpoints = brief.get("endpoints") or {}
    drug = brief.get("drug_treatment") or {}
    safety = brief.get("safety") or {}
    statistical = brief.get("statistical") or {}
    regulatory = brief.get("regulatory") or {}

    phase = _fmt(overview.get("phase") or getattr(study, "phase", None))
    indication = _fmt(overview.get("indication"))
    design_type = _fmt(design.get("design_type"))
    blinding = _fmt(design.get("blinding"))
    randomization = _fmt(design.get("randomization"))
    comparator = _fmt(design.get("comparator"))
    duration = _fmt(design.get("treatment_duration"))
    sample_size = _fmt(population.get("estimated_sample_size"))
    inclusion = _fmt(
        population.get("inclusion_criteria") or population.get("description")
    )
    exclusion = _fmt(population.get("exclusion_criteria"))

    primary_eps = endpoints.get("primary") or []
    primary_ep = primary_eps[0] if primary_eps else {}
    primary_name = _fmt(
        primary_ep.get("name") if isinstance(primary_ep, dict) else primary_ep
    )
    primary_timepoint = _fmt(
        primary_ep.get("timepoint") if isinstance(primary_ep, dict) else None
    )

    inn_name = _fmt(drug.get("inn_name"))
    regimen = _fmt(drug.get("regimen"))
    safety_concerns = _fmt(safety.get("key_concerns"))
    monitoring = _fmt(safety.get("monitoring_approach"))
    analysis_method = _fmt(statistical.get("primary_analysis_method"))
    alpha = _fmt(statistical.get("alpha_level"))
    regions = _fmt(regulatory.get("regions"))

    sections.append(
        _section(
            "Summary",
            f"The protocol was generated as a {phase} study for {indication} because "
            f"the intake Study Brief specified these characteristics in study_overview. "
            f"Study design was set to {design_type} with {blinding} blinding and "
            f"{randomization} randomization"
            + (
                f", using {comparator} as comparator"
                if comparator != "not specified in intake"
                else ""
            )
            + (f", over {duration}" if duration != "not specified in intake" else "")
            + (
                f", targeting {sample_size} subjects"
                if sample_size != "not specified in intake"
                else ""
            )
            + ".",
        )
    )

    sections.append(
        _section(
            "Study design rationale",
            f"Design type ({design_type}), blinding ({blinding}), randomization "
            f"({randomization}), comparator ({comparator}), and treatment duration "
            f"({duration}) were taken from intake domain STUDY_DESIGN "
            f"(brief section: study_design).",
        )
    )

    sections.append(
        _section(
            "Endpoint selection",
            f"The primary endpoint was set to '{primary_name}'"
            + (
                f" at {primary_timepoint}"
                if primary_timepoint != "not specified in intake"
                else ""
            )
            + " because the intake identified this as the primary objective "
            f"(brief section: endpoints). Secondary and safety endpoints were derived "
            f"from the same intake section: secondary={_fmt(endpoints.get('secondary'))}, "
            f"safety={_fmt(endpoints.get('safety'))}.",
        )
    )

    sections.append(
        _section(
            "Population criteria",
            f"Inclusion criteria were based on intake answers: {inclusion}. "
            f"Exclusion criteria: {exclusion}. "
            f"Age range: {_fmt(population.get('age_range'))}. "
            f"Estimated sample size: {sample_size}. "
            f"(brief section: population)",
        )
    )

    sections.append(
        _section(
            "Treatment and investigational product",
            f"Drug/treatment details were sourced from intake domain DRUG_TREATMENT: "
            f"INN/product={inn_name}, regimen={regimen}, doses={_fmt(drug.get('doses'))}, "
            f"route={_fmt(drug.get('route'))}.",
        )
    )

    sections.append(
        _section(
            "Safety monitoring",
            f"Safety monitoring was included based on intake domain SAFETY. "
            f"Key concerns: {safety_concerns}. "
            f"Monitoring approach: {monitoring}. "
            f"Stopping rules: {_fmt(safety.get('stopping_rules'))}.",
        )
    )

    sections.append(
        _section(
            "Statistical approach",
            f"The statistical analysis plan elements were derived from intake domain "
            f"STATISTICAL: primary analysis method={analysis_method}, "
            f"alpha={alpha}, framework={_fmt(statistical.get('framework'))}, "
            f"subgroups={_fmt(statistical.get('key_subgroups'))}.",
        )
    )

    sections.append(
        _section(
            "Regulatory context",
            f"Regulatory regions and submission context from intake domain REGULATORY: "
            f"regions={regions}, IND/CTA status={_fmt(regulatory.get('ind_cta_status'))}, "
            f"GCP standard={_fmt(regulatory.get('gcp_standard'))}.",
        )
    )

    if content:
        generated_design = (content.get("study_design") or {}).get("type")
        if generated_design:
            sections.append(
                _section(
                    "Generated artifact alignment",
                    f"The generated protocol study_design.type is '{generated_design}', "
                    f"consistent with intake design_type '{design_type}'.",
                )
            )

    sections.append(
        _section(
            "Assumptions and missing inputs",
            _missing_inputs_note(brief),
        )
    )

    return sections


def _icf_reasoning(study: Study, brief: dict[str, Any] | None) -> list[str]:
    if not brief:
        return [
            _section(
                "Summary",
                f"The ICF for '{study.name}' was generated without a Study Brief. "
                "Population risks, procedures, and treatment details could not be "
                "grounded in intake answers.",
            )
        ]
    population = brief.get("population") or {}
    safety = brief.get("safety") or {}
    drug = brief.get("drug_treatment") or {}
    return [
        _section(
            "Summary",
            "The Informed Consent Form was generated from the compiled Study Brief, "
            "emphasising risks and procedures disclosed during intake.",
        ),
        _section(
            "Intake sources",
            f"Population risks and eligibility language sourced from brief.population: "
            f"{_fmt(population.get('description'))}. "
            f"Treatment description from brief.drug_treatment: {_fmt(drug.get('inn_name'))}. "
            f"Safety concerns from brief.safety: {_fmt(safety.get('key_concerns'))}.",
        ),
    ]


def _edc_reasoning(
    study: Study,
    brief: dict[str, Any] | None,
    content: dict[str, Any] | None,
) -> list[str]:
    if not brief and not content:
        return [
            _section(
                "Summary",
                f"EDC/eCRF specification for '{study.name}' generated from study metadata. "
                "No Study Brief or protocol artifact was attached.",
            )
        ]
    visits = (content or {}).get("visit_schedule") or []
    forms = (content or {}).get("forms") or []
    fields = (content or {}).get("fields") or []
    return [
        _section(
            "Summary",
            "EDC/eCRF specification derived from Protocol/Study Brief via "
            "Schedule of Assessments → Visit Schedule → Forms → Fields → "
            "Edit Checks → Mock Screens pipeline.",
        ),
        _section(
            "Intake and protocol sources",
            f"Visits: {len(visits)} ({', '.join(v['label'] for v in visits[:6])}). "
            f"Forms: {len(forms)}. Fields: {len(fields)}. "
            f"Brief sections used: {', '.join((brief or {}).keys()) or 'protocol artifact'}.",
        ),
        _section(
            "Primary endpoint linkage",
            next(
                (
                    f["context_graph_hint"]
                    for f in fields
                    if f.get("field_id") == "HBA1C"
                ),
                "Endpoint-driven fields linked per intake endpoints section.",
            ),
        ),
    ]


def _sap_reasoning(study: Study, brief: dict[str, Any] | None) -> list[str]:
    if not brief:
        return [
            _section(
                "Summary",
                f"The SAP for '{study.name}' was generated without a Study Brief.",
            )
        ]
    endpoints = brief.get("endpoints") or {}
    statistical = brief.get("statistical") or {}
    return [
        _section(
            "Summary",
            "The Statistical Analysis Plan was generated from intake endpoints and "
            "statistical domains in the Study Brief.",
        ),
        _section(
            "Intake sources",
            f"Primary/secondary endpoints from brief.endpoints: "
            f"primary={_fmt(endpoints.get('primary'))}, "
            f"secondary={_fmt(endpoints.get('secondary'))}. "
            f"Analysis methods from brief.statistical: "
            f"method={_fmt(statistical.get('primary_analysis_method'))}, "
            f"alpha={_fmt(statistical.get('alpha_level'))}.",
        ),
    ]


def _missing_inputs_note(brief: dict[str, Any]) -> str:
    missing: list[str] = []
    checks = [
        ("study_design.design_type", brief.get("study_design", {}).get("design_type")),
        (
            "population.inclusion_criteria",
            brief.get("population", {}).get("inclusion_criteria"),
        ),
        ("endpoints.primary", brief.get("endpoints", {}).get("primary")),
        (
            "safety.monitoring_approach",
            brief.get("safety", {}).get("monitoring_approach"),
        ),
        (
            "statistical.primary_analysis_method",
            brief.get("statistical", {}).get("primary_analysis_method"),
        ),
    ]
    for path, value in checks:
        if value in (None, "", [], "TBD", "not specified in intake"):
            missing.append(path)
    if missing:
        return (
            "The following intake fields were unavailable or marked TBD and required "
            f"assumptions or defaults: {', '.join(missing)}."
        )
    return "All major intake domains contained usable values; no critical fields were missing."
