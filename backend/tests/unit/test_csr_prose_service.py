"""Unit tests for CSR prose context assembly."""

from __future__ import annotations

from app.services.csr_prose_service import assemble_context


def test_assemble_context_returns_expected_keys():
    context = assemble_context(
        section_id="13",
        study={
            "name": "Phase II Oncology Pilot Study",
            "protocol_number": "DEMO-001",
            "sponsor": "Demo Pharma",
            "phase": "PHASE_2",
            "indication": "Oncology",
        },
        protocol_content={
            "title": "Protocol",
            "objectives": {"primary": [{"description": "Improve PFS"}]},
            "design": {"summary": "Randomized double-blind"},
        },
        sap_content={
            "title": "SAP",
            "primary_endpoint": "Progression-free survival",
            "analysis_populations": ["ITT"],
        },
        merged_tables=[
            {
                "id": "T-13-01",
                "title": "Primary efficacy endpoint analysis",
                "section": "13.1",
            }
        ],
        tlf_content={"tables": [{"id": "T-13-01"}], "listings": [], "figures": []},
        section_entry={"number": "13", "title": "Efficacy Evaluation"},
    )

    assert context["section_id"] == "13"
    assert context["study_name"] == "Phase II Oncology Pilot Study"
    assert context["protocol_number"] == "DEMO-001"
    assert "protocol_excerpt" in context
    assert "sap_excerpt" in context
    assert "tlf_tables" in context
    assert "tlf_summary" in context
    assert context["protocol_excerpt"]["objectives_primary"] == ["Improve PFS"]
    assert context["sap_excerpt"]["primary_endpoint"] == "Progression-free survival"
    assert context["tlf_tables"][0]["id"] == "T-13-01"


def test_assemble_context_includes_optional_instructions():
    context = assemble_context(
        section_id="14",
        study={"name": "Study", "protocol_number": "P-001"},
        protocol_content={},
        sap_content={},
        merged_tables=[],
        instructions="Emphasize treatment-emergent adverse events.",
    )

    assert context["instructions"] == "Emphasize treatment-emergent adverse events."
