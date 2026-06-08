"""Unit tests for SDTM define.xml builder."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.sdtm_define_service import build_define_xml


class TestBuildDefineXml:
    def test_builds_xml_for_sdtm_dataset(self):
        content = {
            "document_type": "SDTM_DATASET",
            "sdtm_ig_version": "3.3",
            "protocol_number": "STUDY-001",
            "validation_engine": "internal",
            "domains": [
                {
                    "domain": "DM",
                    "domain_label": "Demographics",
                    "class": "Special-Purpose",
                    "variables": ["STUDYID", "USUBJID", "AGE"],
                }
            ],
        }
        xml = build_define_xml(content)
        assert '<?xml' in xml
        assert "Define" in xml
        assert "DM" in xml
        assert "STUDY-001" in xml
        assert "2.1" in xml

    def test_rejects_non_sdtm_content(self):
        with pytest.raises(HTTPException) as exc:
            build_define_xml({"document_type": "PROTOCOL"})
        assert exc.value.status_code == 422
