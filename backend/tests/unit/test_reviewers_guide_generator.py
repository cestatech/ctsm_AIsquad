"""Unit tests for the Reviewer's Guide (SDRG) PDF generator."""

from __future__ import annotations

import zlib

from app.services.reviewers_guide_generator import (
    build_reviewers_guide_filename,
    generate_reviewers_guide_pdf,
)


def _fixture_csr_content() -> dict:
    return {
        "document_type": "CSR",
        "title": "CEL-220 Resistant Hypertension CSR",
        "study_identification": {
            "sponsor": "Celerius Therapeutics",
            "phase": "Phase 3",
            "indication": "Resistant hypertension",
        },
        "synopsis": {
            "design": "Randomized, double-blind, placebo-controlled",
            "objectives": "Demonstrate superiority of CEL-220 over placebo",
        },
        "sections": [
            {"number": "1", "title": "Title Page"},
            {"number": "2", "title": "Synopsis"},
            {"number": "9", "title": "Introduction"},
        ],
    }


def _fixture_adam_datasets() -> list[dict]:
    return [
        {
            "name": "ADSL",
            "label": "Subject Level Analysis Dataset",
            "record_count": 480,
        },
        {
            "name": "ADAE",
            "label": "Adverse Events Analysis Dataset",
            "record_count": 1322,
        },
        {
            "name": "ADBP",
            "label": "Blood Pressure Analysis Dataset",
            "record_count": None,
        },
    ]


def _pdf_text(pdf_bytes: bytes) -> bytes:
    """Concatenate the PDF's text-bearing content streams (compression off)."""
    # Page compression is disabled in the generator, so content streams are
    # plain; fall back to inflating any compressed streams defensively.
    text = pdf_bytes
    out = b""
    start = 0
    while True:
        idx = text.find(b"stream", start)
        if idx == -1:
            break
        end = text.find(b"endstream", idx)
        if end == -1:
            break
        chunk = text[idx + len(b"stream") : end].strip(b"\r\n")
        try:
            out += zlib.decompress(chunk)
        except zlib.error:
            out += chunk
        start = end + len(b"endstream")
    return out


class TestReviewersGuideGenerator:
    def test_generates_nonempty_pdf(self):
        pdf = generate_reviewers_guide_pdf(
            study_title="Phase 3 Trial of CEL-220 for Resistant Hypertension",
            protocol_number="CEL-220-301",
            csr_content=_fixture_csr_content(),
            adam_datasets=_fixture_adam_datasets(),
            validation_summary={"PASS": 41, "FAIL": 2, "WARNING": 5},
        )
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 1000

    def test_first_page_contains_study_title(self):
        pdf = generate_reviewers_guide_pdf(
            study_title="Phase 3 Trial of CEL-220 for Resistant Hypertension",
            protocol_number="CEL-220-301",
            csr_content=_fixture_csr_content(),
            adam_datasets=_fixture_adam_datasets(),
            validation_summary={"PASS": 41},
        )
        text = _pdf_text(pdf)
        assert b"Phase 3 Trial of CEL-220 for Resistant Hypertension" in text
        assert b"Study Data Reviewer's Guide" in text

    def test_all_four_sections_present(self):
        pdf = generate_reviewers_guide_pdf(
            study_title="Study X",
            protocol_number="X-001",
            csr_content=_fixture_csr_content(),
            adam_datasets=_fixture_adam_datasets(),
            validation_summary={"PASS": 1, "FAIL": 1},
        )
        text = _pdf_text(pdf)
        assert b"1. Study Overview" in text
        assert b"2. Dataset Inventory" in text
        assert b"3. Validation Summary" in text
        assert b"4. Navigational Guide" in text

    def test_dataset_inventory_lists_each_adam_dataset(self):
        pdf = generate_reviewers_guide_pdf(
            study_title="Study X",
            protocol_number="X-001",
            csr_content=_fixture_csr_content(),
            adam_datasets=_fixture_adam_datasets(),
            validation_summary={},
        )
        text = _pdf_text(pdf)
        assert b"ADSL" in text
        assert b"ADAE" in text
        assert b"480" in text
        # Missing record count renders as n/a, never a fabricated number.
        assert b"n/a" in text

    def test_validation_summary_counts_rendered(self):
        pdf = generate_reviewers_guide_pdf(
            study_title="Study X",
            protocol_number="X-001",
            csr_content=_fixture_csr_content(),
            adam_datasets=[],
            validation_summary={"PASS": 41, "FAIL": 2, "WARNING": 5},
        )
        text = _pdf_text(pdf)
        assert b"PASS: 41" in text
        assert b"FAIL: 2" in text
        assert b"WARNING: 5" in text

    def test_synthetic_banner_always_present(self):
        pdf = generate_reviewers_guide_pdf(
            study_title="Study X",
            protocol_number="X-001",
            csr_content={},
            adam_datasets=[],
            validation_summary={},
        )
        text = _pdf_text(pdf)
        assert b"SYNTHETIC" in text

    def test_filename_sanitized(self):
        assert (
            build_reviewers_guide_filename("CEL 220/301")
            == "reviewers_guide_CEL_220-301.pdf"
        )
        assert build_reviewers_guide_filename(None) == "reviewers_guide_study.pdf"
