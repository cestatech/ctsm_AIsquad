"""Synthetic study fixtures for the eval sweep.

These are fictional study designs — no patient data, no PHI. They span a few
therapeutic areas and phases so the comparison is not tuned to one shape of
study. Each fixture supplies both the Study-level fields the prompts read and an
``input_context`` (including a compiled ``brief_content`` for the brief-aware
generators: protocol, SAP, ICF).

Add your own fixtures here to evaluate on studies that look like your real book
of work — the more representative the fixtures, the more trustworthy the floor
the harness reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StudyFixture:
    key: str
    study_fields: dict[str, Any]
    input_context: dict[str, Any] = field(default_factory=dict)


FIXTURES: list[StudyFixture] = [
    StudyFixture(
        key="onc-ph2-nsclc",
        study_fields={
            "name": "Phase 2 Study of CEL-101 in Advanced NSCLC",
            "protocol_number": "CEL-101-201",
            "indication": "Advanced non-small cell lung cancer",
            "therapeutic_area": "Oncology",
            "phase": "PHASE_2",
            "sponsor": "Celerius Therapeutics",
        },
        input_context={
            "indication": "Advanced non-small cell lung cancer",
            "phase": "Phase 2",
            "therapeutic_area": "Oncology",
            "primary_endpoint": "Objective response rate (ORR) per RECIST v1.1",
            "secondary_endpoints": "Progression-free survival, overall survival, duration of response",
            "design": "Single-arm, open-label, multicenter",
            "populations": "ITT, Safety, Response-evaluable",
            "treatment_arms": "CEL-101 200 mg PO daily",
            "sample_size": "85 subjects",
            "domains": "DM, DS, AE, CM, VS, LB, EX, MH, TU, TR, RS",
            "adam_datasets": "ADSL, ADAE, ADLB, ADVS, ADTR, ADRS, ADTTE",
            "estimand_framework": "ICH E9(R1) treatment policy estimand",
            "brief_content": {
                "objective": "Evaluate the antitumor activity and safety of CEL-101 monotherapy in patients with advanced NSCLC who have progressed on platinum-based chemotherapy.",
                "population": "Adults with histologically confirmed advanced NSCLC, ECOG 0-1, measurable disease per RECIST v1.1.",
                "primary_endpoint": "ORR per RECIST v1.1 by investigator assessment.",
                "design": "Single-arm, open-label, Phase 2.",
                "duration": "Treatment until progression or unacceptable toxicity; follow-up 12 months.",
            },
        },
    ),
    StudyFixture(
        key="cardio-ph3-htn",
        study_fields={
            "name": "Phase 3 Trial of CEL-220 for Resistant Hypertension",
            "protocol_number": "CEL-220-301",
            "indication": "Resistant hypertension",
            "therapeutic_area": "Cardiology",
            "phase": "PHASE_3",
            "sponsor": "Celerius Therapeutics",
        },
        input_context={
            "indication": "Resistant hypertension",
            "phase": "Phase 3",
            "therapeutic_area": "Cardiology",
            "primary_endpoint": "Change from baseline in mean 24-hour ambulatory systolic blood pressure at Week 12",
            "secondary_endpoints": "Office systolic BP, diastolic BP, proportion achieving BP control",
            "design": "Randomized, double-blind, placebo-controlled, parallel-group",
            "populations": "ITT, mITT, PP, Safety",
            "treatment_arms": "CEL-220 50 mg vs placebo",
            "sample_size": "480 subjects (240 per arm)",
            "domains": "DM, DS, AE, CM, VS, LB, EX, MH, EC, IE",
            "adam_datasets": "ADSL, ADAE, ADLB, ADVS, ADBP, ADEFF",
            "estimand_framework": "ICH E9(R1) treatment policy estimand",
            "stat_methods": "MMRM for continuous endpoints, logistic regression for responder analysis",
            "brief_content": {
                "objective": "Demonstrate superiority of CEL-220 over placebo in lowering 24-hour ambulatory systolic blood pressure in patients with resistant hypertension on three antihypertensives.",
                "population": "Adults with resistant hypertension despite stable doses of three antihypertensive agents including a diuretic.",
                "primary_endpoint": "Change from baseline in 24-hour ambulatory SBP at Week 12.",
                "design": "Randomized 1:1, double-blind, placebo-controlled, parallel-group.",
                "duration": "12-week double-blind period followed by 40-week open-label extension.",
            },
        },
    ),
    StudyFixture(
        key="neuro-ph1-early-ad",
        study_fields={
            "name": "Phase 1 SAD/MAD Study of CEL-330 in Early Alzheimer's Disease",
            "protocol_number": "CEL-330-101",
            "indication": "Early Alzheimer's disease",
            "therapeutic_area": "Neurology",
            "phase": "PHASE_1",
            "sponsor": "Celerius Therapeutics",
        },
        input_context={
            "indication": "Early Alzheimer's disease",
            "phase": "Phase 1",
            "therapeutic_area": "Neurology",
            "primary_endpoint": "Incidence of treatment-emergent adverse events and dose-limiting toxicities",
            "secondary_endpoints": "Pharmacokinetic parameters (Cmax, AUC, t1/2), CSF biomarker change",
            "design": "Randomized, double-blind, placebo-controlled, single- and multiple-ascending-dose",
            "populations": "Safety, PK-evaluable",
            "treatment_arms": "CEL-330 ascending doses vs placebo",
            "sample_size": "64 subjects across cohorts",
            "domains": "DM, DS, AE, CM, VS, LB, EX, MH, PC, PP",
            "adam_datasets": "ADSL, ADAE, ADLB, ADVS, ADPC, ADPP",
            "brief_content": {
                "objective": "Characterize the safety, tolerability, and pharmacokinetics of single and multiple ascending doses of CEL-330 in patients with early Alzheimer's disease.",
                "population": "Adults 55-80 with early Alzheimer's disease confirmed by amyloid PET or CSF biomarkers, MMSE 20-26.",
                "primary_endpoint": "Safety and tolerability (TEAEs, DLTs).",
                "design": "Randomized, double-blind, placebo-controlled SAD/MAD.",
                "duration": "SAD single dose; MAD 28 days; safety follow-up 30 days.",
            },
        },
    ),
]


def get_fixtures(keys: list[str] | None = None) -> list[StudyFixture]:
    """Return all fixtures, or only those whose key is in ``keys``."""
    if not keys:
        return list(FIXTURES)
    wanted = set(keys)
    selected = [f for f in FIXTURES if f.key in wanted]
    missing = wanted - {f.key for f in selected}
    if missing:
        raise ValueError(f"unknown fixture key(s): {sorted(missing)}")
    return selected
