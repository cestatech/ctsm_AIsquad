"""Generate CDISC define.xml from SDTM dataset artifact content."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from fastapi import HTTPException, status


def build_define_xml(content: dict) -> str:
    """
    Build a minimal define.xml 2.1 document from SDTM artifact JSON content.

    Suitable for dev/pilot; full regulatory define.xml may require additional
    metadata (Origin, codelists, computational derivations).
    """
    if content.get("document_type") != "SDTM_DATASET":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NOT_SDTM",
                "message": "Artifact content is not an SDTM_DATASET document.",
            },
        )

    study_id = content.get("protocol_number") or content.get("study_name") or "STUDY"
    ig_version = content.get("sdtm_ig_version", "3.3")

    root = ET.Element(
        "Define",
        attrib={
            "xmlns": "http://www.cdisc.org/ns/def/v2.1",
            "xmlns:xlink": "http://www.w3.org/1999/xlink",
        },
    )

    standards = ET.SubElement(root, "Standards")
    ET.SubElement(
        standards,
        "Standard",
        attrib={
            "Name": "SDTM-IG",
            "Version": ig_version,
            "Type": "IG",
            "Status": "Final",
        },
    )

    datasets_el = ET.SubElement(root, "Datasets")
    for domain in content.get("domains", []):
        domain_code = domain.get("domain", "UNK")
        ds = ET.SubElement(
            datasets_el,
            "Dataset",
            attrib={
                "Name": domain_code,
                "Label": domain.get("domain_label", domain_code),
                "Class": domain.get("class", "General"),
            },
        )
        vars_el = ET.SubElement(ds, "Variables")
        for var in domain.get("variables", []):
            ET.SubElement(
                vars_el,
                "Variable",
                attrib={
                    "Name": var,
                    "Label": var,
                    "DataType": "text",
                },
            )

    meta = ET.SubElement(root, "MetaData")
    ET.SubElement(meta, "StudyID").text = str(study_id)
    ET.SubElement(meta, "DefineXMLVersion").text = "2.1"
    ET.SubElement(meta, "ValidationEngine").text = content.get(
        "validation_engine", "internal"
    )

    rough = ET.tostring(root, encoding="unicode")
    return minidom.parseString(rough).toprettyxml(indent="  ")
