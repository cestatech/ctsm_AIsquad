"""Demo program profile registry for multi-study seeding."""

from __future__ import annotations

from dataclasses import dataclass

import demo_content as demo001
import demo_content_demo2 as demo002

ALL_DOMAINS = demo001.ALL_DOMAINS
DEMO_MARKER = demo001.DEMO_MARKER


@dataclass(frozen=True)
class DemoProfile:
    protocol_number: str
    study_name: str
    study_meta: dict
    intake_conversation: list
    study_brief: dict
    protocol_content: dict
    icf_content: dict
    sap_content: dict
    edc_crf_content: dict
    synthetic_dataset_content: dict
    synthetic_run: dict
    synthetic_assumptions: list


def _profile_from_module(module, *, study_name: str | None = None) -> DemoProfile:
    return DemoProfile(
        protocol_number=getattr(module, "PROTOCOL_NUMBER", None)
        or module.PROTOCOL_CONTENT.get("protocol_number", "DEMO"),
        study_name=study_name
        or getattr(module, "STUDY_NAME", None)
        or module.STUDY_BRIEF.get("study_overview", {}).get("title", "Demo Study"),
        study_meta=module.STUDY_META,
        intake_conversation=module.INTAKE_CONVERSATION,
        study_brief=module.STUDY_BRIEF,
        protocol_content=module.PROTOCOL_CONTENT,
        icf_content=module.ICF_CONTENT,
        sap_content=module.SAP_CONTENT,
        edc_crf_content=module.EDC_CRF_CONTENT,
        synthetic_dataset_content=module.SYNTHETIC_DATASET_CONTENT,
        synthetic_run=module.SYNTHETIC_RUN,
        synthetic_assumptions=module.SYNTHETIC_ASSUMPTIONS,
    )


DEMO_PROFILES: dict[str, DemoProfile] = {
    "DEMO-001": _profile_from_module(
        demo001,
        study_name="Phase II Oncology Pilot Study",
    ),
    "DEMO-002": _profile_from_module(demo002),
}


def get_profile(protocol_number: str) -> DemoProfile:
    key = protocol_number.upper()
    if key not in DEMO_PROFILES:
        known = ", ".join(sorted(DEMO_PROFILES))
        raise ValueError(f"Unknown demo protocol {protocol_number}. Known: {known}")
    return DEMO_PROFILES[key]
