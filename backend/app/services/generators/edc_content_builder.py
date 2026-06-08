"""
Build structured EDC/eCRF specification JSON from Study Brief and protocol context.

Architecture:
  Protocol / Study Brief → Schedule of Assessments → Visit Schedule →
  eCRF Forms → eCRF Fields → Edit Checks → Controlled Terminology → Mock Screens
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


DEFAULT_VISITS = [
    {"visit_id": "SCR", "label": "Screening", "day": -14, "window_days": 7},
    {"visit_id": "BL", "label": "Baseline", "day": 0, "window_days": 0},
    {"visit_id": "W4", "label": "Week 4", "day": 28, "window_days": 3},
    {"visit_id": "W8", "label": "Week 8", "day": 56, "window_days": 3},
    {"visit_id": "W12", "label": "Week 12", "day": 84, "window_days": 3},
    {"visit_id": "ET", "label": "Early Termination", "day": None, "window_days": 7},
]

DEFAULT_FORMS = [
    "Demographics",
    "Inclusion/Exclusion",
    "Medical History",
    "Vital Signs",
    "Laboratory Assessments",
    "Adverse Events",
    "Concomitant Medications",
    "Drug Accountability",
    "Compliance",
    "End of Study",
]

FORM_ID_MAP = {
    "Demographics": "DM",
    "Inclusion/Exclusion": "IE",
    "Medical History": "MH",
    "Vital Signs": "VS",
    "Laboratory Assessments": "LB",
    "Adverse Events": "AE",
    "Concomitant Medications": "CM",
    "Drug Accountability": "DA",
    "Compliance": "COMP",
    "End of Study": "DS",
}


def _primary_endpoint_hint(brief: dict[str, Any] | None, protocol: dict[str, Any] | None) -> str:
    if brief:
        eps = (brief.get("endpoints") or {}).get("primary") or []
        if eps and isinstance(eps[0], dict):
            return eps[0].get("name") or "primary endpoint"
        if eps:
            return str(eps[0])
    if protocol:
        ep = (protocol.get("endpoints") or {}).get("primary") or {}
        return ep.get("name") or ep.get("measure") or "primary endpoint"
    return "primary endpoint"


def _visit_ids_for_form(form_name: str) -> list[str]:
    if form_name in ("Demographics", "Inclusion/Exclusion", "Medical History"):
        return ["SCR", "BL"]
    if form_name == "End of Study":
        return ["ET", "W12"]
    if form_name == "Adverse Events":
        return ["BL", "W4", "W8", "W12", "ET"]
    return ["BL", "W4", "W8", "W12"]


def _field_definitions(
    primary_endpoint: str,
) -> list[dict[str, Any]]:
    """Core field catalog with SDTM hints and context graph rationale."""
    return [
        {
            "field_id": "SUBJECT_ID",
            "form_id": "DM",
            "visit_ids": ["SCR"],
            "label": "Subject Identifier",
            "data_type": "text",
            "required": True,
            "controlled_terminology": None,
            "edit_checks": ["Required", "Unique per study"],
            "sdtm_mapping": "DM.USUBJID",
            "context_graph_hint": "SUBJECT_ID is required for subject tracking across all visits.",
        },
        {
            "field_id": "VISIT_DATE",
            "form_id": "DM",
            "visit_ids": ["SCR", "BL", "W4", "W8", "W12", "ET"],
            "label": "Visit Date",
            "data_type": "date",
            "required": True,
            "controlled_terminology": None,
            "edit_checks": ["Required", "Must be within visit window"],
            "sdtm_mapping": "SV.SVSTDTC",
            "context_graph_hint": "VISIT_DATE anchors the visit schedule derived from protocol assessments.",
        },
        {
            "field_id": "SEX",
            "form_id": "DM",
            "visit_ids": ["SCR"],
            "label": "Sex",
            "data_type": "select",
            "required": True,
            "controlled_terminology": "C66731",
            "edit_checks": ["Required"],
            "sdtm_mapping": "DM.SEX",
            "context_graph_hint": "SEX collected at screening per standard demographics.",
        },
        {
            "field_id": "RACE",
            "form_id": "DM",
            "visit_ids": ["SCR"],
            "label": "Race",
            "data_type": "multiselect",
            "required": True,
            "controlled_terminology": "C74457",
            "edit_checks": ["Required"],
            "sdtm_mapping": "DM.RACE",
            "context_graph_hint": "RACE supports demographic subgroup analyses in the SAP.",
        },
        {
            "field_id": "ETHNICITY",
            "form_id": "DM",
            "visit_ids": ["SCR"],
            "label": "Ethnicity",
            "data_type": "select",
            "required": True,
            "controlled_terminology": "C66790",
            "edit_checks": ["Required"],
            "sdtm_mapping": "DM.ETHNIC",
            "context_graph_hint": "ETHNICITY collected for regulatory reporting.",
        },
        {
            "field_id": "AGE",
            "form_id": "DM",
            "visit_ids": ["SCR"],
            "label": "Age (years)",
            "data_type": "number",
            "required": True,
            "controlled_terminology": None,
            "edit_checks": ["Required", "Must match inclusion age range"],
            "sdtm_mapping": "DM.AGE",
            "context_graph_hint": "AGE enforces population inclusion criteria from intake.",
        },
        {
            "field_id": "BMI",
            "form_id": "VS",
            "visit_ids": ["BL", "W12"],
            "label": "Body Mass Index (kg/m²)",
            "data_type": "number",
            "required": False,
            "controlled_terminology": None,
            "edit_checks": ["Range 10–60"],
            "sdtm_mapping": "VS.VSSTRESN",
            "context_graph_hint": "BMI supports metabolic endpoint covariate adjustment.",
        },
        {
            "field_id": "HBA1C",
            "form_id": "LB",
            "visit_ids": ["BL", "W4", "W8", "W12"],
            "label": "HbA1c (%)",
            "data_type": "number",
            "required": True,
            "controlled_terminology": None,
            "edit_checks": ["Required at BL and W12", "Range 4.0–15.0"],
            "sdtm_mapping": "LB.LBSTRESN",
            "context_graph_hint": (
                f"LAB_HBA1C exists because the primary endpoint is change in "
                f"{primary_endpoint} from baseline to Week 12."
            ),
        },
        {
            "field_id": "FASTING_GLUCOSE",
            "form_id": "LB",
            "visit_ids": ["BL", "W12"],
            "label": "Fasting Glucose (mg/dL)",
            "data_type": "number",
            "required": True,
            "controlled_terminology": None,
            "edit_checks": ["Required at BL", "Range 70–400"],
            "sdtm_mapping": "LB.LBSTRESN",
            "context_graph_hint": "FASTING_GLUCOSE supports prediabetes eligibility and glycemic endpoints.",
        },
        {
            "field_id": "SYSBP",
            "form_id": "VS",
            "visit_ids": ["BL", "W4", "W8", "W12"],
            "label": "Systolic Blood Pressure (mmHg)",
            "data_type": "number",
            "required": True,
            "controlled_terminology": None,
            "edit_checks": ["Range 70–220"],
            "sdtm_mapping": "VS.VSSTRESN",
            "context_graph_hint": "SYSBP monitored per safety monitoring plan in intake.",
        },
        {
            "field_id": "DIABP",
            "form_id": "VS",
            "visit_ids": ["BL", "W4", "W8", "W12"],
            "label": "Diastolic Blood Pressure (mmHg)",
            "data_type": "number",
            "required": True,
            "controlled_terminology": None,
            "edit_checks": ["Range 40–130"],
            "sdtm_mapping": "VS.VSSTRESN",
            "context_graph_hint": "DIABP collected with vitals at scheduled safety visits.",
        },
        {
            "field_id": "HR",
            "form_id": "VS",
            "visit_ids": ["BL", "W4", "W8", "W12"],
            "label": "Heart Rate (bpm)",
            "data_type": "number",
            "required": True,
            "controlled_terminology": None,
            "edit_checks": ["Range 40–150"],
            "sdtm_mapping": "VS.VSSTRESN",
            "context_graph_hint": "HR collected as part of routine safety vitals.",
        },
        {
            "field_id": "AE_TERM",
            "form_id": "AE",
            "visit_ids": ["BL", "W4", "W8", "W12", "ET"],
            "label": "Adverse Event Term",
            "data_type": "text",
            "required": False,
            "controlled_terminology": "MedDRA",
            "edit_checks": ["Required if AE reported"],
            "sdtm_mapping": "AE.AETERM",
            "context_graph_hint": "AE_TERM captures safety events listed in intake safety concerns.",
        },
        {
            "field_id": "AE_SEVERITY",
            "form_id": "AE",
            "visit_ids": ["BL", "W4", "W8", "W12", "ET"],
            "label": "AE Severity (CTCAE)",
            "data_type": "select",
            "required": False,
            "controlled_terminology": "C66769",
            "edit_checks": ["Required if AE reported"],
            "sdtm_mapping": "AE.AESEV",
            "context_graph_hint": "AE_SEVERITY graded per SAP safety analysis conventions.",
        },
        {
            "field_id": "AE_RELATIONSHIP",
            "form_id": "AE",
            "visit_ids": ["BL", "W4", "W8", "W12", "ET"],
            "label": "Relationship to Study Drug",
            "data_type": "select",
            "required": False,
            "controlled_terminology": "C66742",
            "edit_checks": ["Required if AE reported"],
            "sdtm_mapping": "AE.AEREL",
            "context_graph_hint": "AE_RELATIONSHIP supports causality assessment in CSR safety section.",
        },
        {
            "field_id": "AE_OUTCOME",
            "form_id": "AE",
            "visit_ids": ["BL", "W4", "W8", "W12", "ET"],
            "label": "AE Outcome",
            "data_type": "select",
            "required": False,
            "controlled_terminology": "C66742",
            "edit_checks": ["Required if AE reported"],
            "sdtm_mapping": "AE.AEOUT",
            "context_graph_hint": "AE_OUTCOME tracks resolution status for safety listings.",
        },
        {
            "field_id": "COMPLIANCE_PERCENT",
            "form_id": "COMP",
            "visit_ids": ["W4", "W8", "W12"],
            "label": "Treatment Compliance (%)",
            "data_type": "number",
            "required": True,
            "controlled_terminology": None,
            "edit_checks": ["Range 0–100"],
            "sdtm_mapping": "EX.EXDOSFRQ",
            "context_graph_hint": "COMPLIANCE_PERCENT supports exposure-adjusted safety analyses.",
        },
    ]


def build_edc_content(
    *,
    study_id: UUID,
    study_name: str,
    protocol_number: str,
    brief_content: dict[str, Any] | None = None,
    protocol_content: dict[str, Any] | None = None,
    source_artifact_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Build full EDC/eCRF specification JSON."""
    primary_ep = _primary_endpoint_hint(brief_content, protocol_content)
    fields = _field_definitions(primary_ep)

    visit_schedule = list(DEFAULT_VISITS)
    safety = (brief_content or {}).get("safety") or {}
    monitoring = safety.get("monitoring_approach")
    if monitoring and isinstance(monitoring, str) and "week" in monitoring.lower():
        pass  # default visits already align

    schedule_of_assessments = []
    for visit in visit_schedule:
        assessments = []
        for field in fields:
            if visit["visit_id"] in field["visit_ids"]:
                assessments.append({
                    "assessment_id": f"{visit['visit_id']}_{field['field_id']}",
                    "field_id": field["field_id"],
                    "form_id": field["form_id"],
                    "label": field["label"],
                })
        schedule_of_assessments.append({
            "visit_id": visit["visit_id"],
            "visit_label": visit["label"],
            "assessments": assessments,
        })

    forms = []
    for form_name in DEFAULT_FORMS:
        form_id = FORM_ID_MAP[form_name]
        form_fields = [f for f in fields if f["form_id"] == form_id]
        forms.append({
            "form_id": form_id,
            "form_name": form_name,
            "visit_ids": _visit_ids_for_form(form_name),
            "status": "DRAFT",
            "fields": [
                {
                    "field_id": f["field_id"],
                    "label": f["label"],
                    "type": f["data_type"],
                    "required": f["required"],
                }
                for f in form_fields
            ],
        })

    edit_checks = []
    for field in fields:
        for check in field.get("edit_checks") or []:
            edit_checks.append({
                "check_id": f"EC_{field['field_id']}_{check[:12].upper().replace(' ', '_')}",
                "field_id": field["field_id"],
                "form_id": field["form_id"],
                "rule": check,
                "severity": "ERROR",
            })

    controlled_terminology = []
    seen_ct: set[str] = set()
    for field in fields:
        ct = field.get("controlled_terminology")
        if ct and ct not in seen_ct:
            seen_ct.add(ct)
            controlled_terminology.append({
                "codelist_id": ct,
                "name": ct,
                "used_by_fields": [f["field_id"] for f in fields if f.get("controlled_terminology") == ct],
            })

    mock_screens = []
    for form in forms:
        mock_screens.append({
            "screen_id": f"MOCK_{form['form_id']}",
            "form_id": form["form_id"],
            "form_name": form["form_name"],
            "visit_ids": form["visit_ids"],
            "field_ids": [f["field_id"] for f in fields if f["form_id"] == form["form_id"]],
            "preview_subject": "SUBJ-001",
        })

    return {
        "document_type": "EDC_CRF",
        "version": "1.0",
        "title": f"{study_name} — EDC/eCRF Specification",
        "study_id": str(study_id),
        "protocol_number": protocol_number,
        "edc_vendor": "Celerius Mock EDC",
        "build_status": "DRAFT",
        "source_artifacts": source_artifact_ids or [],
        "schedule_of_assessments": schedule_of_assessments,
        "visit_schedule": visit_schedule,
        "forms": forms,
        "fields": fields,
        "edit_checks": edit_checks,
        "controlled_terminology": controlled_terminology,
        "mock_screens": mock_screens,
        # Legacy compatibility for seeded viewer format
        "legacy_forms": [
            {
                "form_id": f["form_id"],
                "form_name": f["form_name"],
                "visit": f["visit_ids"][0] if f["visit_ids"] else "All",
                "status": "DRAFT",
                "fields": f["fields"],
            }
            for f in forms
        ],
    }
