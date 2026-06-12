"""Internal CDISC conformance validation engine.

Checks artifact content against ~35 CDISC/ICH rules. Runs as a background task
triggered by the validation executor when engine == "internal".

Each rule returns a ValidationFinding dict:
    {
        "rule_id": "SDTM-001",
        "rule_name": "STUDYID present in all domains",
        "severity": "ERROR" | "WARNING" | "INFO",
        "domain": "DM",          # optional
        "variable": "STUDYID",   # optional
        "message": "...",
        "status": "PASS" | "FAIL"
    }
"""

from __future__ import annotations

import re
from typing import Any


Finding = dict[str, Any]

PASS = "PASS"
FAIL = "FAIL"
ERROR = "ERROR"
WARNING = "WARNING"
INFO = "INFO"


def _f(
    rule_id: str,
    rule_name: str,
    status: str,
    severity: str = ERROR,
    message: str = "",
    domain: str | None = None,
    variable: str | None = None,
) -> Finding:
    return {
        "rule_id": rule_id,
        "rule_name": rule_name,
        "severity": severity,
        "domain": domain,
        "variable": variable,
        "message": message,
        "status": status,
    }


# ===========================================================================
# SDTM rules
# ===========================================================================


def _check_sdtm(content: dict) -> list[Finding]:
    findings: list[Finding] = []
    domains: list[dict] = content.get("domains", [])

    if not domains:
        findings.append(
            _f(
                "SDTM-001",
                "At least one SDTM domain must be present",
                FAIL,
                ERROR,
                "No domains found in SDTM specification",
            )
        )
        return findings

    for domain_spec in domains:
        domain_name: str = domain_spec.get(
            "dataset", domain_spec.get("domain", "UNKNOWN")
        )
        variables: list[dict] = domain_spec.get("variables", [])
        var_names: set[str] = {v.get("variable", "") for v in variables}

        # SDTM-002: STUDYID required in every domain
        if "STUDYID" not in var_names:
            findings.append(
                _f(
                    "SDTM-002",
                    "STUDYID required in all domains",
                    FAIL,
                    ERROR,
                    f"STUDYID missing from domain {domain_name}",
                    domain=domain_name,
                    variable="STUDYID",
                )
            )
        else:
            findings.append(
                _f(
                    "SDTM-002",
                    "STUDYID required in all domains",
                    PASS,
                    ERROR,
                    domain=domain_name,
                    variable="STUDYID",
                )
            )

        # SDTM-003: DOMAIN value must be 2-character uppercase
        if domain_name != "UNKNOWN":
            if not re.fullmatch(r"[A-Z]{2}", domain_name[:2]):
                findings.append(
                    _f(
                        "SDTM-003",
                        "DOMAIN must be 2-character uppercase abbreviation",
                        FAIL,
                        ERROR,
                        f"Domain name '{domain_name}' does not conform to 2-char uppercase rule",
                        domain=domain_name,
                    )
                )
            else:
                findings.append(
                    _f(
                        "SDTM-003",
                        "DOMAIN must be 2-character uppercase abbreviation",
                        PASS,
                        ERROR,
                        domain=domain_name,
                    )
                )

        # SDTM-004: USUBJID required in non-trial-design domains
        trial_design_domains = {"TA", "TE", "TV", "TD", "TI", "TS"}
        if domain_name not in trial_design_domains:
            if "USUBJID" not in var_names:
                findings.append(
                    _f(
                        "SDTM-004",
                        "USUBJID required in subject-level domains",
                        FAIL,
                        ERROR,
                        f"USUBJID missing from domain {domain_name}",
                        domain=domain_name,
                        variable="USUBJID",
                    )
                )
            else:
                findings.append(
                    _f(
                        "SDTM-004",
                        "USUBJID required in subject-level domains",
                        PASS,
                        ERROR,
                        domain=domain_name,
                        variable="USUBJID",
                    )
                )

        # SDTM-005: DM domain required variables
        if domain_name == "DM":
            dm_required = {
                "RFSTDTC",
                "RFENDTC",
                "SEX",
                "RACE",
                "ETHNIC",
                "ARMCD",
                "ARM",
                "COUNTRY",
                "AGE",
                "AGEU",
            }
            missing = dm_required - var_names
            if missing:
                findings.append(
                    _f(
                        "SDTM-005",
                        "DM domain required variables",
                        FAIL,
                        ERROR,
                        f"Missing required DM variables: {', '.join(sorted(missing))}",
                        domain="DM",
                    )
                )
            else:
                findings.append(
                    _f(
                        "SDTM-005",
                        "DM domain required variables",
                        PASS,
                        ERROR,
                        domain="DM",
                    )
                )

        # SDTM-006: AE domain required variables
        if domain_name == "AE":
            ae_required = {"AETERM", "AEDECOD", "AEBODSYS", "AESEV", "AESER", "AEOUT"}
            missing = ae_required - var_names
            if missing:
                findings.append(
                    _f(
                        "SDTM-006",
                        "AE domain required variables",
                        FAIL,
                        ERROR,
                        f"Missing required AE variables: {', '.join(sorted(missing))}",
                        domain="AE",
                    )
                )
            else:
                findings.append(
                    _f(
                        "SDTM-006",
                        "AE domain required variables",
                        PASS,
                        ERROR,
                        domain="AE",
                    )
                )

        # SDTM-007: DTC variable naming convention
        for var in variables:
            vname = var.get("variable", "")
            if vname.endswith("DTC"):
                derivation: str = var.get("derivation", "")
                if (
                    derivation
                    and "ISO 8601" not in derivation
                    and "YYYY-MM-DD" not in derivation
                ):
                    findings.append(
                        _f(
                            "SDTM-007",
                            "DTC variables must follow ISO 8601 format",
                            FAIL,
                            WARNING,
                            f"{vname} derivation does not reference ISO 8601 format",
                            domain=domain_name,
                            variable=vname,
                        )
                    )
                else:
                    findings.append(
                        _f(
                            "SDTM-007",
                            "DTC variables must follow ISO 8601 format",
                            PASS,
                            WARNING,
                            domain=domain_name,
                            variable=vname,
                        )
                    )

        # SDTM-008: Controlled terminology documented
        for var in variables:
            vname = var.get("variable", "")
            ct = var.get("controlled_terminology")
            if vname in {"SEX", "RACE", "ETHNIC", "AESER", "AESEV"} and ct is None:
                findings.append(
                    _f(
                        "SDTM-008",
                        "Controlled terminology required for standard variables",
                        FAIL,
                        ERROR,
                        f"Controlled terminology not documented for {vname}",
                        domain=domain_name,
                        variable=vname,
                    )
                )
            elif vname in {"SEX", "RACE", "ETHNIC", "AESER", "AESEV"}:
                findings.append(
                    _f(
                        "SDTM-008",
                        "Controlled terminology required for standard variables",
                        PASS,
                        ERROR,
                        domain=domain_name,
                        variable=vname,
                    )
                )

    # SDTM-009: define.xml version documented
    define_version = content.get("define_xml_version")
    if not define_version:
        findings.append(
            _f(
                "SDTM-009",
                "define.xml version must be documented",
                FAIL,
                WARNING,
                "define_xml_version not specified in SDTM specification",
            )
        )
    else:
        findings.append(
            _f("SDTM-009", "define.xml version must be documented", PASS, WARNING)
        )

    # SDTM-010: Regulatory references present
    reg_refs = content.get("regulatory_references", [])
    if not any("SDTM" in r for r in reg_refs):
        findings.append(
            _f(
                "SDTM-010",
                "CDISC SDTM IG reference required",
                FAIL,
                ERROR,
                "No CDISC SDTM IG reference found in regulatory_references",
            )
        )
    else:
        findings.append(_f("SDTM-010", "CDISC SDTM IG reference required", PASS, ERROR))

    return findings


# ===========================================================================
# ADaM rules
# ===========================================================================


def _check_adam(content: dict) -> list[Finding]:
    findings: list[Finding] = []
    datasets: list[dict] = content.get("datasets", [])

    if not datasets:
        findings.append(
            _f(
                "ADAM-001",
                "At least one ADaM dataset must be present",
                FAIL,
                ERROR,
                "No datasets found in ADaM specification",
            )
        )
        return findings

    has_adsl = any(d.get("dataset") == "ADSL" for d in datasets)
    if not has_adsl:
        findings.append(
            _f(
                "ADAM-002",
                "ADSL dataset required in ADaM submission",
                FAIL,
                ERROR,
                "ADSL (Subject Level Analysis Dataset) not found",
            )
        )
    else:
        findings.append(
            _f("ADAM-002", "ADSL dataset required in ADaM submission", PASS, ERROR)
        )

    for ds in datasets:
        ds_name: str = ds.get("dataset", "UNKNOWN")
        variables: list[dict] = ds.get("variables", [])
        var_names: set[str] = {v.get("variable", "") for v in variables}

        # ADAM-003: ADSL required variables
        if ds_name == "ADSL":
            adsl_required = {"USUBJID", "SUBJID", "STUDYID"}
            missing = adsl_required - var_names
            if missing:
                findings.append(
                    _f(
                        "ADAM-003",
                        "ADSL required variables",
                        FAIL,
                        ERROR,
                        f"Missing required ADSL variables: {', '.join(sorted(missing))}",
                        domain=ds_name,
                    )
                )
            else:
                findings.append(
                    _f(
                        "ADAM-003",
                        "ADSL required variables",
                        PASS,
                        ERROR,
                        domain=ds_name,
                    )
                )

        # ADAM-004: Population flags must be in ADSL
        if ds_name == "ADSL":
            pop_flags = ds.get("population_flags", [])
            if not pop_flags:
                findings.append(
                    _f(
                        "ADAM-004",
                        "Population flags required in ADSL",
                        FAIL,
                        ERROR,
                        "No population flags (ITTFL, SAFFL, etc.) defined in ADSL",
                        domain="ADSL",
                    )
                )
            else:
                flag_vars = {f.get("variable", "") for f in pop_flags}
                findings.append(
                    _f(
                        "ADAM-004",
                        "Population flags required in ADSL",
                        PASS,
                        ERROR,
                        domain="ADSL",
                    )
                )

                # ADAM-005: ITTFL must be present
                if "ITTFL" not in flag_vars:
                    findings.append(
                        _f(
                            "ADAM-005",
                            "ITTFL (Intent-to-Treat flag) required in ADSL",
                            FAIL,
                            ERROR,
                            "ITTFL not found in ADSL population_flags",
                            domain="ADSL",
                            variable="ITTFL",
                        )
                    )
                else:
                    findings.append(
                        _f(
                            "ADAM-005",
                            "ITTFL required in ADSL",
                            PASS,
                            ERROR,
                            domain="ADSL",
                            variable="ITTFL",
                        )
                    )

        # ADAM-006: All variables must have derivation documented
        for var in variables:
            vname = var.get("variable", "")
            derivation = var.get("derivation", "")
            if not derivation or derivation.strip() == "":
                findings.append(
                    _f(
                        "ADAM-006",
                        "All ADaM variables must have derivation documented",
                        FAIL,
                        ERROR,
                        f"{vname} in {ds_name} has no derivation algorithm",
                        domain=ds_name,
                        variable=vname,
                    )
                )

        # ADAM-007: BDS datasets require PARAM, PARAMCD, AVAL
        bds_indicators = {"ADLB", "ADVS", "ADEFF", "ADRS", "ADPC"}
        is_bds = (
            ds_name in bds_indicators or ds_name.startswith("AD") and ds_name != "ADSL"
        )
        if is_bds and ds_name not in ("ADSL", "ADAE"):
            bds_required = {"PARAM", "PARAMCD", "AVAL"}
            missing = bds_required - var_names
            if missing:
                findings.append(
                    _f(
                        "ADAM-007",
                        "BDS datasets require PARAM, PARAMCD, AVAL",
                        FAIL,
                        ERROR,
                        f"Missing BDS required variables in {ds_name}: {', '.join(sorted(missing))}",
                        domain=ds_name,
                    )
                )
            else:
                findings.append(
                    _f(
                        "ADAM-007",
                        "BDS datasets require PARAM, PARAMCD, AVAL",
                        PASS,
                        ERROR,
                        domain=ds_name,
                    )
                )

        # ADAM-008: ADAE required variables
        if ds_name == "ADAE":
            adae_required = {"USUBJID", "AEDECOD", "AESEV", "AESER"}
            missing = adae_required - var_names
            if missing:
                findings.append(
                    _f(
                        "ADAM-008",
                        "ADAE required variables",
                        FAIL,
                        ERROR,
                        f"Missing required ADAE variables: {', '.join(sorted(missing))}",
                        domain="ADAE",
                    )
                )
            else:
                findings.append(
                    _f(
                        "ADAM-008",
                        "ADAE required variables",
                        PASS,
                        ERROR,
                        domain="ADAE",
                    )
                )

    # ADAM-009: ADaM IG version documented
    ig_version = content.get("adam_ig_version")
    if not ig_version:
        findings.append(
            _f(
                "ADAM-009",
                "ADaM IG version must be documented",
                FAIL,
                WARNING,
                "adam_ig_version not specified",
            )
        )
    else:
        findings.append(
            _f("ADAM-009", "ADaM IG version must be documented", PASS, WARNING)
        )

    # ADAM-010: Traceability notes present
    trace_notes = content.get("traceability_notes", [])
    if not trace_notes:
        findings.append(
            _f(
                "ADAM-010",
                "Traceability notes required in ADaM specification",
                FAIL,
                WARNING,
                "No traceability_notes found linking ADaM variables to SDTM source",
            )
        )
    else:
        findings.append(_f("ADAM-010", "Traceability notes required", PASS, WARNING))

    return findings


# ===========================================================================
# Protocol (ICH E6) rules
# ===========================================================================


def _check_protocol(content: dict) -> list[Finding]:
    findings: list[Finding] = []

    # PROT-001: Synopsis present
    synopsis = content.get("synopsis", {})
    if not synopsis:
        findings.append(
            _f(
                "PROT-001",
                "Protocol synopsis required (ICH E6 §6.1)",
                FAIL,
                ERROR,
                "No synopsis section found",
            )
        )
    else:
        findings.append(_f("PROT-001", "Protocol synopsis required", PASS, ERROR))

    # PROT-002: Objectives section present
    objectives = content.get("objectives", {})
    if not objectives or (
        not objectives.get("primary") and not objectives.get("primary_objective")
    ):
        findings.append(
            _f(
                "PROT-002",
                "Primary objective required (ICH E6 §6.2)",
                FAIL,
                ERROR,
                "No primary objective documented",
            )
        )
    else:
        findings.append(_f("PROT-002", "Primary objective required", PASS, ERROR))

    # PROT-003: Study design section
    design = content.get("study_design", {})
    if not design:
        findings.append(
            _f(
                "PROT-003",
                "Study design section required (ICH E6 §6.4)",
                FAIL,
                ERROR,
                "No study_design section found",
            )
        )
    else:
        findings.append(_f("PROT-003", "Study design section required", PASS, ERROR))

    # PROT-004: Eligibility criteria
    eligibility = content.get("eligibility", {})
    has_inclusion = bool(
        eligibility.get("inclusion_criteria") or eligibility.get("inclusion")
    )
    has_exclusion = bool(
        eligibility.get("exclusion_criteria") or eligibility.get("exclusion")
    )
    if not has_inclusion or not has_exclusion:
        findings.append(
            _f(
                "PROT-004",
                "Inclusion and exclusion criteria required (ICH E6 §6.5)",
                FAIL,
                ERROR,
                f"Missing: {'inclusion' if not has_inclusion else ''} "
                f"{'exclusion' if not has_exclusion else ''} criteria".strip(),
            )
        )
    else:
        findings.append(_f("PROT-004", "Eligibility criteria complete", PASS, ERROR))

    # PROT-005: Primary endpoint documented
    endpoints = content.get("endpoints", {})
    primary_endpoint = (
        endpoints.get("primary")
        or endpoints.get("primary_endpoint")
        or content.get("primary_endpoint")
    )
    if not primary_endpoint:
        findings.append(
            _f(
                "PROT-005",
                "Primary endpoint required (ICH E6 §6.6)",
                FAIL,
                ERROR,
                "No primary endpoint found",
            )
        )
    else:
        findings.append(_f("PROT-005", "Primary endpoint documented", PASS, ERROR))

    # PROT-006: Statistical considerations
    stats = (
        content.get("statistical_considerations")
        or content.get("statistics")
        or content.get("statistical_analysis")
    )
    if not stats:
        findings.append(
            _f(
                "PROT-006",
                "Statistical considerations required (ICH E6 §6.9)",
                FAIL,
                ERROR,
                "No statistical_considerations section found",
            )
        )
    else:
        findings.append(
            _f("PROT-006", "Statistical considerations present", PASS, ERROR)
        )

    # PROT-007: Safety monitoring plan
    safety = content.get("safety_monitoring", {})
    if not safety:
        findings.append(
            _f(
                "PROT-007",
                "Safety monitoring section required (ICH E6 §5.18)",
                FAIL,
                WARNING,
                "No safety_monitoring section found",
            )
        )
    else:
        findings.append(_f("PROT-007", "Safety monitoring plan present", PASS, WARNING))

    return findings


# ===========================================================================
# ICF rules (21 CFR Part 50, ICH E6)
# ===========================================================================


def _check_icf(content: dict) -> list[Finding]:
    findings: list[Finding] = []
    sections = {
        s.get("section", s.get("title", "")): s for s in content.get("sections", [])
    }

    required_elements = {
        "purpose": ["purpose", "introduction", "study_purpose"],
        "procedures": ["procedures", "study_procedures"],
        "risks": ["risks", "risk"],
        "benefits": ["benefits", "benefit"],
        "alternatives": ["alternatives"],
        "confidentiality": ["confidentiality"],
        "voluntary_participation": ["voluntary_participation", "voluntary"],
        "contact_information": ["contact_information", "contacts"],
    }

    rule_map = {
        "purpose": "ICF-001",
        "procedures": "ICF-002",
        "risks": "ICF-003",
        "benefits": "ICF-004",
        "alternatives": "ICF-005",
        "confidentiality": "ICF-006",
        "voluntary_participation": "ICF-007",
        "contact_information": "ICF-008",
    }

    section_keys_lower = {k.lower() for k in sections}

    for element, aliases in required_elements.items():
        found = any(alias in section_keys_lower for alias in aliases)
        # also check top-level content keys
        if not found:
            found = any(alias in content for alias in aliases)
        rule_id = rule_map[element]
        rule_name = f"ICF must include {element.replace('_', ' ')} (21 CFR 50.25)"
        if found:
            findings.append(_f(rule_id, rule_name, PASS, ERROR))
        else:
            findings.append(
                _f(
                    rule_id,
                    rule_name,
                    FAIL,
                    ERROR,
                    f"ICF missing required element: {element}",
                )
            )

    # ICF-009: Reading level
    reading_level = content.get("reading_level") or content.get(
        "target_reading_level", ""
    )
    if (
        reading_level
        and "8th" not in str(reading_level)
        and "6th" not in str(reading_level)
    ):
        findings.append(
            _f(
                "ICF-009",
                "ICF reading level should be 8th grade or lower",
                FAIL,
                WARNING,
                f"Reading level specified as '{reading_level}' — verify ≤ 8th grade",
            )
        )
    else:
        findings.append(_f("ICF-009", "ICF reading level check", PASS, WARNING))

    return findings


# ===========================================================================
# SAP rules (ICH E9, ICH E9(R1))
# ===========================================================================


def _check_sap(content: dict) -> list[Finding]:
    findings: list[Finding] = []

    # SAP-001: Analysis populations defined
    populations = content.get("analysis_populations", [])
    if not populations:
        findings.append(
            _f(
                "SAP-001",
                "Analysis populations required (ICH E9 §5.2.2)",
                FAIL,
                ERROR,
                "No analysis populations defined",
            )
        )
    else:
        findings.append(_f("SAP-001", "Analysis populations defined", PASS, ERROR))

    # SAP-002: Primary endpoint analysis method
    primary = content.get("primary_endpoint_analysis") or content.get(
        "primary_analysis"
    )
    if not primary:
        findings.append(
            _f(
                "SAP-002",
                "Primary endpoint analysis method required",
                FAIL,
                ERROR,
                "No primary_endpoint_analysis section found",
            )
        )
    else:
        findings.append(
            _f("SAP-002", "Primary endpoint analysis documented", PASS, ERROR)
        )

    # SAP-003: Estimands framework (ICH E9(R1))
    estimands = content.get("estimands", [])
    if not estimands:
        findings.append(
            _f(
                "SAP-003",
                "Estimands framework required (ICH E9(R1))",
                FAIL,
                ERROR,
                "No estimands defined — ICH E9(R1) requires estimand specification",
            )
        )
    else:
        findings.append(_f("SAP-003", "Estimands framework documented", PASS, ERROR))
        # SAP-004: Each estimand must have treatment_condition and population
        for i, est in enumerate(estimands):
            for field in (
                "treatment_condition",
                "population",
                "variable",
                "handling_of_intercurrent_events",
            ):
                if not est.get(field):
                    findings.append(
                        _f(
                            "SAP-004",
                            "Estimand completeness (ICH E9(R1) §A.4)",
                            FAIL,
                            WARNING,
                            f"Estimand {i + 1} missing '{field}' component",
                        )
                    )
                    break
            else:
                findings.append(_f("SAP-004", "Estimand completeness", PASS, WARNING))

    # SAP-005: Missing data strategy
    missing_data = content.get("missing_data") or content.get("missing_data_handling")
    if not missing_data:
        findings.append(
            _f(
                "SAP-005",
                "Missing data strategy required (ICH E9 §5.3.3)",
                FAIL,
                ERROR,
                "No missing data handling strategy documented",
            )
        )
    else:
        findings.append(_f("SAP-005", "Missing data strategy documented", PASS, ERROR))

    # SAP-006: Sensitivity analyses
    sensitivity = content.get("sensitivity_analyses", [])
    if not sensitivity:
        findings.append(
            _f(
                "SAP-006",
                "Sensitivity analyses required (ICH E9(R1))",
                FAIL,
                WARNING,
                "No sensitivity_analyses documented",
            )
        )
    else:
        findings.append(_f("SAP-006", "Sensitivity analyses documented", PASS, WARNING))

    # SAP-007: Secondary endpoints addressed
    secondary = content.get("secondary_endpoints") or content.get("secondary_analyses")
    if not secondary:
        findings.append(
            _f(
                "SAP-007",
                "Secondary endpoints analysis required",
                FAIL,
                WARNING,
                "No secondary endpoint analyses documented",
            )
        )
    else:
        findings.append(
            _f("SAP-007", "Secondary endpoints analysis documented", PASS, WARNING)
        )

    return findings


# ===========================================================================
# CSR rules (ICH E3)
# ===========================================================================


def _check_csr(content: dict) -> list[Finding]:
    findings: list[Finding] = []
    sections = content.get("sections", [])
    section_numbers = {s.get("number", ""): s for s in sections}
    section_titles_lower = {s.get("title", "").lower(): s for s in sections}

    ich_e3_required = {
        "1": "Title Page",
        "2": "Synopsis",
        "9": "Introduction",
        "10": "Study Objectives",
        "11": "Investigational Plan",
        "12": "Study Patients",
        "13": "Efficacy Evaluation",
        "14": "Safety Evaluation",
        "15": "Discussion and Overall Conclusions",
    }

    for num, title in ich_e3_required.items():
        present = num in section_numbers or title.lower() in section_titles_lower
        rule_id = f"CSR-{int(num):03d}"
        rule_name = f"ICH E3 Section {num}: {title}"
        if present:
            findings.append(_f(rule_id, rule_name, PASS, ERROR))
        else:
            findings.append(
                _f(
                    rule_id,
                    rule_name,
                    FAIL,
                    ERROR,
                    f"Missing ICH E3 required section {num}: {title}",
                )
            )

    # CSR-010: Synopsis content completeness
    synopsis = content.get("synopsis", {})
    if synopsis:
        for field in ("objectives", "design", "population"):
            if not synopsis.get(field):
                findings.append(
                    _f(
                        "CSR-010",
                        "Synopsis completeness (ICH E3 §2)",
                        FAIL,
                        WARNING,
                        f"Synopsis missing '{field}' field",
                    )
                )
                break
        else:
            findings.append(_f("CSR-010", "Synopsis completeness", PASS, WARNING))

    # CSR-011: Appendices listed
    appendices = content.get("appendices", [])
    if not appendices:
        findings.append(
            _f(
                "CSR-011",
                "Appendices must be listed (ICH E3 §16)",
                FAIL,
                WARNING,
                "No appendices defined",
            )
        )
    else:
        findings.append(_f("CSR-011", "Appendices listed", PASS, WARNING))

    # CSR-012: ICH E3 compliance flag
    if not content.get("ich_e3_compliant"):
        findings.append(
            _f(
                "CSR-012",
                "ich_e3_compliant must be true",
                FAIL,
                ERROR,
                "CSR document not marked as ICH E3 compliant",
            )
        )
    else:
        findings.append(_f("CSR-012", "ICH E3 compliance marked", PASS, ERROR))

    return findings


# ===========================================================================
# Generic rules applied to all artifact types
# ===========================================================================


def _check_generic(content: dict, artifact_type: str) -> list[Finding]:
    findings: list[Finding] = []

    # GEN-001: Content is not empty
    if not content:
        findings.append(
            _f(
                "GEN-001",
                "Artifact content must not be empty",
                FAIL,
                ERROR,
                "Content is empty",
            )
        )
    else:
        findings.append(_f("GEN-001", "Artifact content not empty", PASS, ERROR))

    # GEN-002: document_type matches artifact type
    doc_type = content.get("document_type", "")
    expected_map = {
        "PROTOCOL": "PROTOCOL",
        "ICF": "ICF",
        "SAP": "SAP",
        "SDTM_DATASET": "SDTM_SPECIFICATION",
        "ADAM_DATASET": "ADAM_SPECIFICATION",
        "TLF": "TLF_SPECIFICATION",
        "CSR": "CSR",
    }
    expected = expected_map.get(artifact_type, "")
    if doc_type and expected and doc_type != expected:
        findings.append(
            _f(
                "GEN-002",
                "document_type must match artifact type",
                FAIL,
                WARNING,
                f"Expected document_type '{expected}', found '{doc_type}'",
            )
        )
    else:
        findings.append(
            _f("GEN-002", "document_type consistent with artifact type", PASS, WARNING)
        )

    # GEN-003: Version field present
    if not content.get("version"):
        findings.append(
            _f(
                "GEN-003",
                "Version field required",
                FAIL,
                WARNING,
                "No 'version' field in artifact content",
            )
        )
    else:
        findings.append(_f("GEN-003", "Version field present", PASS, WARNING))

    # GEN-004: Regulatory references present
    reg_refs = content.get("regulatory_references", [])
    if not reg_refs:
        findings.append(
            _f(
                "GEN-004",
                "Regulatory references required",
                FAIL,
                WARNING,
                "No regulatory_references array found",
            )
        )
    else:
        findings.append(
            _f("GEN-004", "Regulatory references documented", PASS, WARNING)
        )

    return findings


# ===========================================================================
# Define-XML / XPT cross-validation (Lane 1c)
# ===========================================================================


def run_define_xpt_cross_validation(
    define_xml: str,
    *,
    xpt_filenames: list[str] | None = None,
    expected_domain_codes: list[str] | None = None,
) -> dict:
    """
    Validate define.xml structure and alignment with XPT transport files.

    Used before submission packaging (Lane 3) and by validation runs that include
    define.xml + exported XPT filenames from ``xpt_export_service``.

    Args:
        define_xml: Raw define.xml text.
        xpt_filenames: Basenames of XPT files present in the package (e.g. ``dm.xpt``).
        expected_domain_codes: SDTM/ADaM domain codes from artifact content.
    """
    from app.services.define_xml_validator import (
        validate_define_xpt_alignment,
        validate_define_xml_structure,
    )

    findings: list[Finding] = []

    struct = validate_define_xml_structure(define_xml)
    if struct.valid:
        findings.append(
            _f(
                "DEF-001",
                "define.xml is well-formed with required Define-XML 2.1 markers",
                PASS,
                ERROR,
            )
        )
    else:
        for issue in struct.issues:
            findings.append(
                _f(
                    "DEF-001",
                    "define.xml is well-formed with required Define-XML 2.1 markers",
                    FAIL,
                    ERROR,
                    issue,
                )
            )

    if struct.leaf_hrefs:
        xpt_hrefs = [h for h in struct.leaf_hrefs if h.lower().endswith(".xpt")]
        if xpt_hrefs:
            findings.append(
                _f(
                    "DEF-002",
                    "define.xml leaf hrefs reference .xpt transport files",
                    PASS,
                    ERROR,
                )
            )
        else:
            findings.append(
                _f(
                    "DEF-002",
                    "define.xml leaf hrefs reference .xpt transport files",
                    FAIL,
                    ERROR,
                    "No .xpt leaf hrefs found in define.xml.",
                )
            )

    if expected_domain_codes is not None:
        align = validate_define_xpt_alignment(
            define_xml,
            expected_domain_codes=expected_domain_codes,
        )
        if align.valid:
            findings.append(
                _f(
                    "DEF-003",
                    "define.xml domains align with artifact domain codes",
                    PASS,
                    ERROR,
                )
            )
        else:
            for issue in align.issues:
                if "missing leaf href" in issue or "not present in artifact" in issue:
                    findings.append(
                        _f(
                            "DEF-003",
                            "define.xml domains align with artifact domain codes",
                            FAIL,
                            ERROR,
                            issue,
                        )
                    )

    if xpt_filenames is not None:
        href_basenames = {h.rsplit("/", 1)[-1].lower() for h in struct.leaf_hrefs}
        xpt_basenames = {
            f.rsplit("/", 1)[-1].lower()
            for f in xpt_filenames
            if f.lower().endswith(".xpt")
        }
        missing_on_disk = href_basenames - xpt_basenames
        extra_on_disk = xpt_basenames - href_basenames

        if not missing_on_disk and not extra_on_disk and href_basenames:
            findings.append(
                _f(
                    "XPT-001",
                    "XPT files match define.xml leaf href basenames",
                    PASS,
                    ERROR,
                )
            )
        else:
            if missing_on_disk:
                findings.append(
                    _f(
                        "XPT-001",
                        "XPT files match define.xml leaf href basenames",
                        FAIL,
                        ERROR,
                        f"Missing XPT files: {', '.join(sorted(missing_on_disk))}",
                    )
                )
            if extra_on_disk:
                findings.append(
                    _f(
                        "XPT-002",
                        "No orphan XPT files without define.xml leaf href",
                        FAIL,
                        WARNING,
                        f"Orphan XPT files: {', '.join(sorted(extra_on_disk))}",
                    )
                )

    total = len(findings)
    passed = sum(1 for f in findings if f["status"] == PASS)
    failed = sum(1 for f in findings if f["status"] == FAIL)
    warnings = sum(
        1 for f in findings if f["status"] == FAIL and f["severity"] == WARNING
    )
    errors = sum(1 for f in findings if f["status"] == FAIL and f["severity"] == ERROR)

    return {
        "total_checks": total,
        "passed_checks": passed,
        "failed_checks": failed,
        "warning_count": warnings,
        "error_count": errors,
        "findings": findings,
        "rule_set": "CDISC-DEFINE-XPT-1.0",
        "artifact_type": "DEFINE_XPT_CROSSCHECK",
    }


# ===========================================================================
# Public entry point
# ===========================================================================

ARTIFACT_TYPE_CHECKERS = {
    "SDTM_DATASET": _check_sdtm,
    "ADAM_DATASET": _check_adam,
    "PROTOCOL": _check_protocol,
    "ICF": _check_icf,
    "SAP": _check_sap,
    "CSR": _check_csr,
}


def run_cdisc_validation(content: dict, artifact_type: str) -> dict:
    """
    Run all applicable CDISC / ICH conformance rules for the given artifact type.

    Returns a results dict suitable for storing in ValidationRun.results.
    """
    findings: list[Finding] = []

    # Generic rules for all types
    findings.extend(_check_generic(content, artifact_type))

    # Type-specific rules
    checker = ARTIFACT_TYPE_CHECKERS.get(artifact_type)
    if checker:
        findings.extend(checker(content))
    else:
        findings.append(
            _f(
                "GEN-005",
                "Artifact type has no specific CDISC rule set",
                "PASS",
                INFO,
                f"No type-specific rules defined for {artifact_type}; generic checks only",
            )
        )

    total = len(findings)
    passed = sum(1 for f in findings if f["status"] == PASS)
    failed = sum(1 for f in findings if f["status"] == FAIL)
    warnings = sum(
        1 for f in findings if f["status"] == FAIL and f["severity"] == WARNING
    )
    errors = sum(1 for f in findings if f["status"] == FAIL and f["severity"] == ERROR)

    return {
        "total_checks": total,
        "passed_checks": passed,
        "failed_checks": failed,
        "warning_count": warnings,
        "error_count": errors,
        "findings": findings,
        "rule_set": "CDISC-INTERNAL-1.0",
        "artifact_type": artifact_type,
    }
