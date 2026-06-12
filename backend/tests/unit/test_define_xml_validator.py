"""Unit tests for define.xml structural and XPT href validation."""

from __future__ import annotations

from app.services.define_xml_validator import (
    validate_define_xpt_alignment,
    validate_define_xml_structure,
)
from app.services.sdtm_define_service import build_define_xml


def _sdtm_content() -> dict:
    return {
        "document_type": "SDTM_DATASET",
        "protocol_number": "PROT-001",
        "study_name": "Demo Study",
        "domains": [
            {
                "domain": "DM",
                "domain_label": "Demographics",
                "class": "Special-Purpose",
                "variables": [
                    {"variable": "STUDYID", "label": "Study ID", "type": "Char"},
                    {
                        "variable": "USUBJID",
                        "label": "Unique Subject ID",
                        "type": "Char",
                    },
                ],
                "observations": [{"STUDYID": "S1", "USUBJID": "S1-001"}],
            }
        ],
    }


class TestDefineXmlValidator:
    def test_generated_define_xml_passes_structure(self):
        define_xml = build_define_xml(_sdtm_content())
        result = validate_define_xml_structure(define_xml)
        assert result.valid is True
        assert any(h.lower().endswith(".xpt") for h in result.leaf_hrefs)
        assert "DM" in result.domain_codes

    def test_alignment_passes_for_matching_domains(self):
        define_xml = build_define_xml(_sdtm_content())
        result = validate_define_xpt_alignment(
            define_xml,
            expected_domain_codes=["DM"],
        )
        assert result.valid is True

    def test_alignment_fails_for_missing_domain(self):
        define_xml = build_define_xml(_sdtm_content())
        result = validate_define_xpt_alignment(
            define_xml,
            expected_domain_codes=["DM", "AE"],
        )
        assert result.valid is False
        assert any("ae.xpt" in i.lower() for i in result.issues)

    def test_malformed_xml_fails(self):
        result = validate_define_xml_structure("<ODM><unclosed>")
        assert result.valid is False
        assert any("parse" in i.lower() for i in result.issues)
