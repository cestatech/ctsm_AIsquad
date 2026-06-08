"""Unit tests for SDTM define.xml builder."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.sdtm_define_service import build_define_xml


def _rich_sdtm_content() -> dict:
    return {
        "document_type": "SDTM_DATASET",
        "sdtm_ig_version": "3.3",
        "protocol_number": "STUDY-001",
        "study_name": "Example Study",
        "validation_engine": "internal",
        "domains": [
            {
                "domain": "DM",
                "domain_label": "Demographics",
                "class": "Special-Purpose",
                "variables": [
                    "STUDYID",
                    "USUBJID",
                    {
                        "variable": "SEX",
                        "label": "Sex",
                        "description": "Sex of the subject",
                        "controlled_terminology": "NCI (C66731)",
                        "origin": "Collected",
                    },
                    {
                        "variable": "RACE",
                        "label": "Race",
                        "description": "Race of the subject",
                    },
                    {
                        "variable": "AGE",
                        "label": "Age",
                        "type": "number",
                        "derivation": "Calculate age at informed consent from RFICDTC and BRTHDTC",
                        "description": "Age in years at informed consent",
                    },
                ],
            },
            {
                "domain": "QS",
                "domain_label": "Questionnaires",
                "class": "Findings",
                "variables": [
                    {
                        "variable": "QVAL",
                        "label": "Finding Value",
                        "description": "Result or finding value",
                        "value_level_metadata": [
                            {
                                "where": {"variable": "QSCAT", "value": "GENERAL"},
                                "data_type": "float",
                                "label": "General Health Score",
                            },
                            {
                                "where": {"variable": "QSCAT", "value": "PAIN"},
                                "data_type": "integer",
                                "label": "Pain Score",
                            },
                        ],
                    }
                ],
            },
        ],
        "derived_variables": [
            {
                "variable": "DM.AGE",
                "logic": "Calculate age at informed consent from RFICDTC and BRTHDTC",
            }
        ],
    }


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


class TestDefineXmlCodelists:
    def test_generates_codelist_elements_for_controlled_terminology(self):
        xml = build_define_xml(_rich_sdtm_content())
        assert "CodeList" in xml
        assert 'OID="CL.SEX"' in xml
        assert 'CodedValue="M"' in xml
        assert "Male" in xml
        assert 'OID="CL.RACE"' in xml
        assert 'def:CodeListOID="CL.SEX"' in xml


class TestDefineXmlOriginsAndMethods:
    def test_origin_and_methoddef_for_derived_variables(self):
        xml = build_define_xml(_rich_sdtm_content())
        assert 'Type="Assigned"' in xml
        assert 'Type="Collected"' in xml
        assert 'Type="Derived"' in xml
        assert "MethodDef" in xml
        assert 'OID="MT.DM.AGE"' in xml
        assert "Calculate age at informed consent" in xml

    def test_comment_from_variable_description(self):
        xml = build_define_xml(_rich_sdtm_content())
        assert 'Comment="Sex of the subject"' in xml
        assert 'Comment="Age in years at informed consent"' in xml


class TestDefineXmlValueLevelMetadata:
    def test_generates_valuelist_and_whereclause_for_vlm(self):
        xml = build_define_xml(_rich_sdtm_content())
        assert "ValueListDef" in xml
        assert 'OID="VL.QS.QVAL"' in xml
        assert "WhereClauseDef" in xml
        assert 'OID="WC.QS.QVAL.1"' in xml
        assert "GENERAL" in xml
        assert "PAIN" in xml


class TestDefineXmlStructure:
    def test_uses_odm_root_with_define_version(self):
        xml = build_define_xml(_rich_sdtm_content())
        assert "<ODM" in xml
        assert "DefineVersion" in xml
        assert "ItemGroupDef" in xml
        assert "ItemDef" in xml

    def test_well_formed_xml(self):
        import xml.etree.ElementTree as ET

        xml = build_define_xml(_rich_sdtm_content())
        ET.fromstring(xml.split("\n", 1)[-1] if xml.startswith("<?xml") else xml)
