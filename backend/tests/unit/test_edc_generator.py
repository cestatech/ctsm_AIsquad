"""Unit tests for EDC/eCRF content builder and generator registration."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4


from app.models.artifact import ArtifactType
from app.services.generation_executor import _GENERATOR_MAP
from app.services.generators.edc_content_builder import build_edc_content
from app.services.generators.edc_generator import EDCGenerator


PREDIABETES_BRIEF = {
    "study_overview": {"indication": "Prediabetes", "phase": "Phase II"},
    "endpoints": {
        "primary": [{"name": "Change in HbA1c from baseline to Week 12", "timepoint": "Week 12"}],
    },
    "safety": {"monitoring_approach": "Baseline, Week 4, Week 8, and Week 12"},
}


class TestEDCContentBuilder:
    def test_builds_required_structure(self):
        study_id = uuid4()
        content = build_edc_content(
            study_id=study_id,
            study_name="CLR-101 Prediabetes",
            protocol_number="CLR-101-001",
            brief_content=PREDIABETES_BRIEF,
        )

        assert content["document_type"] == "EDC_CRF"
        assert content["study_id"] == str(study_id)
        assert len(content["visit_schedule"]) >= 6
        visit_labels = [v["label"] for v in content["visit_schedule"]]
        assert "Screening" in visit_labels
        assert "Week 12" in visit_labels

        form_names = [f["form_name"] for f in content["forms"]]
        assert "Demographics" in form_names
        assert "Laboratory Assessments" in form_names

        field_ids = [f["field_id"] for f in content["fields"]]
        assert "HBA1C" in field_ids
        assert "SUBJECT_ID" in field_ids
        assert "COMPLIANCE_PERCENT" in field_ids

        hba1c = next(f for f in content["fields"] if f["field_id"] == "HBA1C")
        assert "HbA1c" in hba1c["context_graph_hint"]
        assert hba1c["sdtm_mapping"] == "LB.LBSTRESN"

        assert len(content["edit_checks"]) > 0
        assert len(content["mock_screens"]) == len(content["forms"])
        assert len(content["schedule_of_assessments"]) == len(content["visit_schedule"])

    def test_legacy_forms_compatible(self):
        content = build_edc_content(
            study_id=uuid4(),
            study_name="Test Study",
            protocol_number="TST-001",
        )
        assert content["legacy_forms"]
        assert content["legacy_forms"][0]["form_id"] == "DM"


class TestEDCGeneratorRegistration:
    def test_edc_registered_in_executor_map(self):
        assert ArtifactType.EDC_CRF in _GENERATOR_MAP
        assert _GENERATOR_MAP[ArtifactType.EDC_CRF] is EDCGenerator

    def test_agent_name_and_artifact_type(self):
        gen = EDCGenerator(MagicMock())
        assert gen.ARTIFACT_TYPE == ArtifactType.EDC_CRF
        assert gen.AGENT_NAME == "edc-generator"
