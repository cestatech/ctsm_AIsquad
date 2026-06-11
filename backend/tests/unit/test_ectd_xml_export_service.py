"""Unit tests for eCTD backbone XML export."""

from __future__ import annotations

import zipfile
import io
import xml.etree.ElementTree as ET

from app.services.ectd_xml_export_service import (
    generate_ectd_xml_zip,
    generate_index_md5,
    generate_index_xml,
)


def _sample_manifest() -> dict:
    return {
        "files": [
            {
                "path": "m5/define.xml",
                "sha256": "a" * 64,
                "grade": "generated",
            },
            {
                "path": "m5/datasets/tabulation/sdtm/dm.xpt",
                "sha256": "b" * 64,
                "grade": "generated",
            },
            {
                "path": "m5/clinical-study-reports/csr.pdf",
                "sha256": "c" * 64,
                "grade": "placeholder",
            },
        ],
        "data_classification": "SYNTHETIC_DEMO",
    }


class TestEctdXmlExportService:
    def test_generate_index_xml_contains_leaves(self):
        xml_bytes = generate_index_xml(_sample_manifest(), study_id="study-123")
        assert xml_bytes.startswith(b"<?xml")
        root = ET.fromstring(xml_bytes)
        leaves = [e for e in root.iter() if e.tag.endswith("leaf")]
        assert len(leaves) == 3

    def test_generate_index_md5_lists_files(self):
        index_xml = generate_index_xml(_sample_manifest(), study_id="study-123")
        md5_text = generate_index_md5(
            index_xml,
            _sample_manifest()["files"],
        ).decode()
        assert "index.xml" in md5_text
        assert "dm.xpt" in md5_text

    def test_generate_ectd_zip_has_backbone_files(self):
        zbytes = generate_ectd_xml_zip(_sample_manifest(), study_id="study-123")
        with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
            names = zf.namelist()
        assert "index.xml" in names
        assert "index-md5.txt" in names
