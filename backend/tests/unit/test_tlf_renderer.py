"""Unit tests for TLF RTF rendering."""

from __future__ import annotations

from app.services.tlf_renderer import TLFRenderer


class TestTLFRenderer:
    def test_renders_table_headers_alignment_and_rows(self):
        rtf = TLFRenderer().render_to_rtf({
            "tables": [{
                "title": "Demographics",
                "columns": [
                    {"key": "parameter", "label": "Parameter", "align": "left"},
                    {"key": "active", "label": "Active", "align": "right"},
                ],
                "rows": [
                    {"parameter": "Age, mean (SD)", "active": "54.2 (8.1)"},
                ],
            }],
        }).decode("utf-8")

        assert rtf.startswith(r"{\rtf1")
        assert "Demographics" in rtf
        assert r"\b Parameter\b0" in rtf
        assert r"\qr 54.2 (8.1)\cell" in rtf
        assert r"\row" in rtf

    def test_renders_listing_as_formatted_text_block(self):
        rtf = TLFRenderer().render_to_rtf({
            "listings": [{
                "title": "Adverse Event Listing",
                "lines": ["SUBJ001 | Headache | Mild"],
            }],
        }).decode("utf-8")

        assert "Adverse Event Listing" in rtf
        assert "SUBJ001 | Headache | Mild" in rtf
        assert r"\f1" in rtf

    def test_renders_empty_spec(self):
        rtf = TLFRenderer().render_to_rtf({}).decode("utf-8")

        assert r"{\rtf1" in rtf
        assert "No TLF tables, listings, or figures were provided." in rtf
