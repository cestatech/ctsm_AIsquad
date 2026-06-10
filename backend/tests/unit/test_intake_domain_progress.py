"""Unit tests for intake domain progression normalization."""

from __future__ import annotations

from app.services.intake_service import IntakeService


class TestIntakeDomainProgress:
    def test_merge_preserves_order_and_existing(self):
        merged = IntakeService._merge_domains_completed(
            ["STUDY_OVERVIEW", "STUDY_DESIGN"],
            ["POPULATION", "STUDY_OVERVIEW"],
        )
        assert merged == ["STUDY_OVERVIEW", "STUDY_DESIGN", "POPULATION"]

    def test_normalize_advances_completed_domain(self):
        parsed = IntakeService._normalize_intake_progress(
            domains_completed=["STUDY_OVERVIEW"],
            parsed={
                "message": "Tell me more about the study title.",
                "domain": "STUDY_OVERVIEW",
                "domains_completed": ["STUDY_OVERVIEW"],
                "ready_to_compile": False,
            },
            current_domain="STUDY_OVERVIEW",
            user_answered=True,
        )
        assert parsed["domain"] == "STUDY_DESIGN"
        assert "STUDY_OVERVIEW" in parsed["domains_completed"]

    def test_normalize_marks_ready_when_all_domains_done(self):
        completed = [
            "STUDY_OVERVIEW",
            "STUDY_DESIGN",
            "POPULATION",
            "ENDPOINTS",
            "DRUG_TREATMENT",
            "SAFETY",
            "REGULATORY",
            "STATISTICAL",
            "SITES",
        ]
        parsed = IntakeService._normalize_intake_progress(
            domains_completed=completed[:-1],
            parsed={
                "message": "Any more sites?",
                "domain": "SITES",
                "domains_completed": completed,
                "ready_to_compile": True,
            },
            current_domain="SITES",
            user_answered=True,
        )
        assert parsed["ready_to_compile"] is True
        assert len(parsed["domains_completed"]) == 9

    def test_current_domain_uses_last_assistant_turn(self):
        from unittest.mock import MagicMock

        assistant = MagicMock(role="assistant", domain="ENDPOINTS")
        user = MagicMock(role="user", domain=None)
        assert IntakeService._current_domain([assistant, user]) == "ENDPOINTS"
