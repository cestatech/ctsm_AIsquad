"""Unit tests for ICH E3 CSR PDF renderer."""

from __future__ import annotations

from app.services.csr_ich_e3_pdf_renderer import render_ich_e3_csr_pdf


def _csr_content() -> dict:
    return {
        "title": "Clinical Study Report — Demo Study",
        "study_identification": {
            "protocol_number": "PROT-001",
            "sponsor": "Demo Sponsor",
        },
        "synopsis": {
            "objectives": "Assess efficacy and safety.",
            "design": "Randomized, double-blind, placebo-controlled.",
            "population": "Adults with Type 2 diabetes.",
        },
        "sections": [
            {
                "number": "9",
                "title": "Introduction",
                "prose": "This study evaluated treatment X in adults with diabetes.",
            },
            {
                "number": "13",
                "title": "Efficacy Evaluation",
                "narrative_summary": "Primary endpoint met with statistical significance.",
                "tlf_references": [
                    {"table_id": "T-14.1.1", "title": "Primary Efficacy Analysis"},
                ],
            },
            {
                "number": "14",
                "title": "Safety Evaluation",
                "content_outline": "Overall safety profile was consistent with known effects.",
            },
        ],
        "tlf_integration": [
            {
                "table_id": "T-14.1.1",
                "csr_section": "13",
                "insertion_note": "Referenced in Section 13; file in tlf/*.rtf",
            },
        ],
    }


class TestCsrIchE3PdfRenderer:
    def test_renders_pdf_bytes(self):
        pdf = render_ich_e3_csr_pdf(
            _csr_content(),
            study_name="Demo Study",
            protocol_number="PROT-001",
        )
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 1000

    def test_renders_multiple_ich_e3_sections_without_error(self):
        content = _csr_content()
        content["sections"].append({
            "number": "15",
            "title": "Discussion and Overall Conclusions",
            "prose": "The benefit-risk profile supports the study conclusions.",
        })
        pdf = render_ich_e3_csr_pdf(content, study_name="Demo Study")
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 2000
