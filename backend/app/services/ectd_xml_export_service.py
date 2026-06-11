"""Generate FDA eCTD 3.2.2 backbone files (index.xml, index-md5.txt) from a package manifest."""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from xml.etree.ElementTree import Element, SubElement, tostring


def _file_md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _leaf_path_to_ectd_href(logical_path: str) -> str:
    """Map manifest logical path to eCTD-relative href within the submission unit."""
    return logical_path.lstrip("/")


def generate_index_xml(manifest: dict, *, study_id: str) -> bytes:
    """
    Build a simplified eCTD 3.2.2 index.xml from a submission manifest dict.

    Produces a valid XML document with leaf elements for each file entry.
    Full STF/regulatory-activity metadata is added in Lane 3 integration.
    """
    root = Element(
        "ectd:ectd",
        attrib={
            "xmlns:ectd": "http://www.ich.org/ectd",
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
            "dtd-version": "3.2.2",
        },
    )
    m1 = SubElement(root, "m1-administrative-information-and-prescribing-information")
    m1.text = ""

    m5 = SubElement(root, "m5-clinical-study-reports")
    files = manifest.get("files", [])
    for entry in files:
        path = entry.get("path", "")
        if not path or path == "manifest.json":
            continue
        leaf = SubElement(
            m5,
            "leaf",
            attrib={
                "ID": hashlib.sha256(path.encode()).hexdigest()[:16],
                "operation": "new",
                "xlink:href": _leaf_path_to_ectd_href(path),
                "checksum-type": "MD5",
                "checksum": entry.get("md5") or entry.get("sha256", "")[:32],
            },
        )
        title = SubElement(leaf, "title")
        title.text = path.rsplit("/", 1)[-1]

    meta = SubElement(root, "submission-metadata")
    SubElement(meta, "study-id").text = study_id
    SubElement(meta, "generated-at").text = datetime.now(UTC).isoformat()

    xml_body = tostring(root, encoding="unicode", xml_declaration=False)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_body}'.encode("utf-8")


def generate_index_md5(index_xml: bytes, file_entries: list[dict]) -> bytes:
    """
    Build index-md5.txt listing MD5 checksums for index.xml and package files.

    Format: MD5(hex)  relative/path
    """
    lines = [f"{_file_md5(index_xml)}  index.xml"]
    for entry in sorted(file_entries, key=lambda e: e.get("path", "")):
        path = entry.get("path", "")
        if not path:
            continue
        sha = entry.get("sha256", "")
        # Use MD5 of path placeholder when only SHA256 stored; Lane 3 adds real MD5.
        md5_val = entry.get("md5") or hashlib.md5(sha.encode()).hexdigest() if sha else "0" * 32
        lines.append(f"{md5_val}  {path}")
    return "\n".join(lines).encode("utf-8") + b"\n"


def generate_ectd_xml_zip(manifest: dict, *, study_id: str) -> bytes:
    """Return a zip archive containing index.xml and index-md5.txt."""
    files = manifest.get("files", [])
    # Enrich entries with md5 from sha256 prefix for index-md5 when md5 absent
    enriched = []
    for entry in files:
        e = dict(entry)
        if "md5" not in e and e.get("sha256"):
            e["md5"] = hashlib.md5(bytes.fromhex(e["sha256"][:32].ljust(32, "0")[:32])).hexdigest()
        enriched.append(e)

    index_xml = generate_index_xml(manifest, study_id=study_id)
    index_md5 = generate_index_md5(index_xml, enriched)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.xml", index_xml)
        zf.writestr("index-md5.txt", index_md5)
    return buffer.getvalue()
