"""Unit tests for eCTD backbone XML export."""

from __future__ import annotations

import hashlib
import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from lxml import etree

from app.services.ectd_xml_export_service import (
    generate_ectd_xml_zip,
    generate_index_md5,
    generate_index_xml,
)

_DTD_PATH = Path(__file__).parent.parent / "fixtures" / "ectd-3-2-2-subset.dtd"


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

    def test_index_xml_validates_against_ectd_dtd(self):
        dtd = etree.DTD(str(_DTD_PATH))
        xml_bytes = generate_index_xml(_sample_manifest(), study_id="study-123")
        doc = etree.fromstring(xml_bytes)
        assert dtd.validate(doc), dtd.error_log.filter_from_errors()

    def test_leaf_checksums_are_manifest_sha256(self):
        xml_bytes = generate_index_xml(_sample_manifest(), study_id="study-123")
        root = ET.fromstring(xml_bytes)
        leaves = [e for e in root.iter() if e.tag.endswith("leaf")]
        checksums = {leaf.get("checksum") for leaf in leaves}
        assert checksums == {"a" * 64, "b" * 64, "c" * 64}
        assert all(leaf.get("checksum-type") == "SHA256" for leaf in leaves)

    def test_leaf_hrefs_reference_manifest_paths(self):
        xml_bytes = generate_index_xml(_sample_manifest(), study_id="study-123")
        root = ET.fromstring(xml_bytes)
        hrefs = {
            leaf.get("{http://www.w3.org/1999/xlink}href")
            for leaf in root.iter()
            if leaf.tag.endswith("leaf")
        }
        assert hrefs == {
            "m5/define.xml",
            "m5/datasets/tabulation/sdtm/dm.xpt",
            "m5/clinical-study-reports/csr.pdf",
        }

    def test_generate_index_md5_lists_every_file_with_sha256(self):
        index_xml = generate_index_xml(_sample_manifest(), study_id="study-123")
        md5_text = generate_index_md5(
            index_xml,
            _sample_manifest()["files"],
        ).decode()
        lines = md5_text.strip().splitlines()

        # First line: real MD5 of the index.xml bytes.
        assert lines[0] == f"{hashlib.md5(index_xml).hexdigest()}  index.xml"

        # Every package file listed with its manifest SHA-256, explicitly typed.
        assert f"SHA256:{'a' * 64}  m5/define.xml" in lines
        assert f"SHA256:{'b' * 64}  m5/datasets/tabulation/sdtm/dm.xpt" in lines
        assert f"SHA256:{'c' * 64}  m5/clinical-study-reports/csr.pdf" in lines
        assert len(lines) == 4

    def test_generate_ectd_zip_has_backbone_files(self):
        zbytes = generate_ectd_xml_zip(_sample_manifest(), study_id="study-123")
        with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
            names = zf.namelist()
            index_xml = zf.read("index.xml")
            index_md5 = zf.read("index-md5.txt")
        assert sorted(names) == ["index-md5.txt", "index.xml"]
        # The MD5 recorded in the archive matches the index.xml actually shipped.
        assert index_md5.decode().splitlines()[0].split()[0] == hashlib.md5(
            index_xml
        ).hexdigest()

    def test_manifest_json_entry_excluded_from_backbone(self):
        manifest = _sample_manifest()
        manifest["files"].append({"path": "manifest.json", "sha256": "d" * 64})
        xml_bytes = generate_index_xml(manifest, study_id="study-123")
        root = ET.fromstring(xml_bytes)
        hrefs = {
            leaf.get("{http://www.w3.org/1999/xlink}href")
            for leaf in root.iter()
            if leaf.tag.endswith("leaf")
        }
        assert "manifest.json" not in hrefs
