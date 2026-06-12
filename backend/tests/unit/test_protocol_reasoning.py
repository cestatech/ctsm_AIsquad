"""Unit tests for detailed protocol generation reasoning from Study Brief intake."""

from __future__ import annotations

from unittest.mock import MagicMock


from app.models.artifact import ArtifactType
from app.services.generators.reasoning_builder import build_artifact_reasoning

PREDIABETES_BRIEF = {
    "study_overview": {
        "title": "CLR-101 Prediabetes Study",
        "therapeutic_area": "Metabolic",
        "indication": "Prediabetes",
        "phase": "Phase II",
        "sponsor": "Celerius Pharma",
        "compound_code": "CLR-101",
    },
    "study_design": {
        "design_type": "randomized, double-blind, placebo-controlled, parallel-group",
        "randomization": "1:1",
        "blinding": "double-blind",
        "comparator": "placebo",
        "treatment_duration": "12 weeks",
        "number_of_periods": 1,
    },
    "population": {
        "description": "Adults with prediabetes",
        "inclusion_criteria": [
            "Adults aged 30–75",
            "HbA1c 5.7%–6.4% and/or fasting glucose 100–125 mg/dL",
        ],
        "exclusion_criteria": ["Type 1 diabetes", "Pregnancy"],
        "age_range": {"min": 30, "max": 75},
        "estimated_sample_size": 50,
    },
    "endpoints": {
        "primary": [
            {
                "name": "Change in HbA1c from baseline to Week 12",
                "timepoint": "Week 12",
                "instrument": "Central laboratory",
            }
        ],
        "secondary": [],
        "safety": [],
    },
    "drug_treatment": {
        "inn_name": "CLR-101",
        "doses": ["100 mg daily"],
        "route": "oral",
        "formulation": "tablet",
        "regimen": "once daily",
    },
    "safety": {
        "key_concerns": [
            "GI effects",
            "dizziness",
            "headache",
            "weight loss",
            "hypoglycemia",
            "lab abnormalities",
        ],
        "monitoring_approach": "Baseline, Week 4, Week 8, and Week 12",
        "stopping_rules": [],
        "sae_definitions": None,
        "rems_required": False,
    },
    "regulatory": {
        "regions": ["US"],
        "ind_cta_status": "Pre-IND",
        "submission_type": None,
        "gcp_standard": "ICH E6(R2)",
        "special_designations": [],
    },
    "statistical": {
        "framework": "FREQUENTIST",
        "primary_analysis_method": "ANCOVA on change from baseline",
        "alpha_level": 0.05,
        "multiple_testing_approach": None,
        "key_subgroups": [],
    },
    "sites": {
        "planned_sites": 10,
        "countries": ["US"],
        "estimated_enrollment_rate_per_month": 5,
        "site_selection_criteria": ["Endocrinology clinics"],
    },
}


def _make_study() -> MagicMock:
    study = MagicMock()
    study.name = "CLR-101 Prediabetes Study"
    study.protocol_number = "CLR-101-001"
    study.phase = MagicMock(value="Phase II")
    return study


class TestProtocolReasoning:
    def test_detailed_reasoning_cites_intake_answers(self):
        study = _make_study()
        reasoning = build_artifact_reasoning(
            artifact_type=ArtifactType.PROTOCOL,
            study=study,
            brief_content=PREDIABETES_BRIEF,
            content={"study_design": {"type": "parallel-group"}},
        )

        assert "Phase II" in reasoning
        assert "Prediabetes" in reasoning
        assert "double-blind" in reasoning
        assert "placebo" in reasoning
        assert "50" in reasoning
        assert "HbA1c" in reasoning
        assert "Week 12" in reasoning
        assert "30–75" in reasoning or "30-75" in reasoning
        assert "CLR-101" in reasoning
        assert "GI effects" in reasoning or "GI" in reasoning
        assert "Baseline, Week 4, Week 8" in reasoning
        assert "ANCOVA" in reasoning
        assert "study_design" in reasoning
        assert "endpoints" in reasoning
        assert "population" in reasoning

    def test_reasoning_without_brief_states_missing_inputs(self):
        study = _make_study()
        reasoning = build_artifact_reasoning(
            artifact_type=ArtifactType.PROTOCOL,
            study=study,
            brief_content=None,
        )

        assert "No compiled Study Brief" in reasoning
        assert "study metadata only" in reasoning

    def test_reasoning_includes_downstream_impact_note(self):
        study = _make_study()
        reasoning = build_artifact_reasoning(
            artifact_type=ArtifactType.PROTOCOL,
            study=study,
            brief_content=PREDIABETES_BRIEF,
        )

        assert "Downstream impact" in reasoning
        assert "DRAFT" in reasoning
