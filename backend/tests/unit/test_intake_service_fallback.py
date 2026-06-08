"""Unit tests for intake deterministic fallback (no Anthropic API key)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.intake_service import IntakeService


class TestIntakeFallback:
    def test_start_response(self):
        parsed = IntakeService._fallback_conversation_response(
            study_name="Demo Study",
            current_domain=None,
            domains_completed=[],
            is_start=True,
        )
        assert parsed["domain"] == "STUDY_OVERVIEW"
        assert parsed["ready_to_compile"] is False
        assert "Demo Study" in parsed["message"]

    def test_advances_domain_after_answer(self):
        parsed = IntakeService._fallback_conversation_response(
            study_name="Demo Study",
            current_domain="STUDY_OVERVIEW",
            domains_completed=[],
            is_start=False,
        )
        assert "STUDY_OVERVIEW" in parsed["domains_completed"]
        assert parsed["domain"] == "STUDY_DESIGN"

    def test_all_domains_complete(self):
        parsed = IntakeService._fallback_conversation_response(
            study_name="Demo Study",
            current_domain="SITES",
            domains_completed=[
                "STUDY_OVERVIEW",
                "STUDY_DESIGN",
                "POPULATION",
                "ENDPOINTS",
                "DRUG_TREATMENT",
                "SAFETY",
                "REGULATORY",
                "STATISTICAL",
            ],
            is_start=False,
        )
        assert parsed["ready_to_compile"] is True
        assert len(parsed["domains_completed"]) == 9

    def test_fallback_brief_uses_study_name(self):
        study = MagicMock()
        study.name = "Phase II Oncology Pilot Study"
        study.protocol_number = "DEMO-001"
        study.phase = None
        brief = IntakeService._fallback_brief_content(
            study,
            {"STUDY_OVERVIEW": "Oncology phase 2 trial"},
        )
        assert brief["study_overview"]["title"] == "Phase II Oncology Pilot Study"
        assert brief["study_overview"]["compound_code"] == "DEMO-001"
