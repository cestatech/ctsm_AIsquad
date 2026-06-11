"""Generate FDA eCTD 3.2.2 backbone files (index.xml, index-md5.txt) from a package manifest.

Stateless utility: receives the submission package manifest dict produced by
``SubmissionService`` and returns bytes. It never touches the database or the
filesystem, so checksums are taken from the manifest as recorded at assembly
time (SHA-256). The index.xml leaf checksums are therefore declared with
``checksum-type="SHA256"`` — we do not fabricate MD5 values for file contents
we cannot read here. The only MD5 actually computed is the eCTD-required MD5
of index.xml itself, which this module generates and can hash honestly.

The emitted grammar is a documented subset of the eCTD 3.2.2 backbone
(`tests/fixtures/ectd-3-2-2-subset.dtd`); full regional STF metadata is
Phase 2.3 scope.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from xml.etree.ElementTree import Element, SubElement, tostring


def _leaf_path_to_ectd_href(logical_path: str) -> str:
    """Map manifest logical path to eCTD-relative href within the submission unit."""
    return logical_path.lstrip("/")


def generate_index_xml(manifest: dict, *, study_id: str) -> bytes:
    """
    Build an eCTD 3.2.2 backbone index.xml from a submission manifest dict.

    Produces a valid XML document with one ``leaf`` element per manifest file
    entry under Module 5, carrying the file's SHA-256 checksum as recorded in
    the manifest. Full STF/regulatory-activity metadata is Phase 2.3 scope.
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
                "ID": f"leaf-{hashlib.sha256(path.encode()).hexdigest()[:16]}",
                "operation": "new",
                "xlink:href": _leaf_path_to_ectd_href(path),
                "checksum-type": "SHA256",
                "checksum": entry.get("sha256", ""),
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
    Build index-md5.txt: the MD5 of index.xml (computed from the actual bytes,
    per eCTD convention), followed by the SHA-256 checksum of every package
    file as recorded in the manifest.

    Format, one entry per line: ``<checksum>  <relative/path>``. File lines are
    prefixed with ``SHA256:`` to make the digest type unambiguous to reviewers.
    """
    lines = [f"{hashlib.md5(index_xml).hexdigest()}  index.xml"]
    for entry in sorted(file_entries, key=lambda e: e.get("path", "")):
        path = entry.get("path", "")
        if not path:
            continue
        sha = entry.get("sha256", "")
        lines.append(f"SHA256:{sha}  {path}")
    return "\n".join(lines).encode("utf-8") + b"\n"


def generate_ectd_xml_zip(manifest: dict, *, study_id: str) -> bytes:
    """Return a zip archive containing index.xml and index-md5.txt."""
    index_xml = generate_index_xml(manifest, study_id=study_id)
    index_md5 = generate_index_md5(index_xml, manifest.get("files", []))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.xml", index_xml)
        zf.writestr("index-md5.txt", index_md5)
    return buffer.getvalue()
