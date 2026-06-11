"""Validate CDISC Define-XML structure and XPT href alignment."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

DEF_NS = "http://www.cdisc.org/ns/def/v2.1"
XLINK_NS = "http://www.w3.org/1999/xlink"


@dataclass
class DefineXmlValidationResult:
    """Result of define.xml structural and href validation."""

    valid: bool
    issues: list[str] = field(default_factory=list)
    leaf_hrefs: list[str] = field(default_factory=list)
    domain_codes: list[str] = field(default_factory=list)


def _strip_xml_declaration(xml_text: str) -> str:
    return re.sub(r"<\?xml[^?]*\?>", "", xml_text, count=1).strip()


def extract_define_leaf_hrefs(define_xml: str) -> list[str]:
    """Parse define.xml and return all def:leaf xlink:href values."""
    root = ET.fromstring(_strip_xml_declaration(define_xml))
    hrefs: list[str] = []
    for elem in root.iter():
        if elem.tag.endswith("leaf"):
            href = elem.attrib.get(f"{{{XLINK_NS}}}href") or elem.attrib.get("href")
            if href:
                hrefs.append(href)
    return hrefs


def extract_item_group_domains(define_xml: str) -> list[str]:
    """Return ItemGroupDef Name attributes (domain codes)."""
    root = ET.fromstring(_strip_xml_declaration(define_xml))
    domains: list[str] = []
    for elem in root.iter():
        if elem.tag.endswith("ItemGroupDef"):
            name = elem.attrib.get("Name")
            if name:
                domains.append(name)
    return domains


def validate_define_xml_structure(define_xml: str) -> DefineXmlValidationResult:
    """
    Validate define.xml is well-formed and contains required Define-XML 2.1 markers.

    Full XSD validation against the official CDISC schema is deferred; this checks
    structure required for FDA submission packaging integration.
    """
    issues: list[str] = []
    try:
        root = ET.fromstring(_strip_xml_declaration(define_xml))
    except ET.ParseError as exc:
        return DefineXmlValidationResult(valid=False, issues=[f"XML parse error: {exc}"])

    if not root.tag.endswith("ODM"):
        issues.append("Root element must be ODM.")

    xml_flat = define_xml
    if "DefineVersion" not in xml_flat and "2.1" not in xml_flat:
        issues.append("Define-XML 2.1 DefineVersion not found.")

    if "ItemGroupDef" not in xml_flat:
        issues.append("No ItemGroupDef elements found.")

    if "ItemDef" not in xml_flat:
        issues.append("No ItemDef elements found.")

    leaf_hrefs = extract_define_leaf_hrefs(define_xml)
    if not leaf_hrefs:
        issues.append("No def:leaf xlink:href entries found.")

    for href in leaf_hrefs:
        if not href.lower().endswith(".xpt"):
            issues.append(
                f"Leaf href '{href}' must reference a .xpt file for FDA submission transport."
            )

    domain_codes = extract_item_group_domains(define_xml)
    return DefineXmlValidationResult(
        valid=len(issues) == 0,
        issues=issues,
        leaf_hrefs=leaf_hrefs,
        domain_codes=domain_codes,
    )


def validate_define_xpt_alignment(
    define_xml: str,
    *,
    expected_domain_codes: list[str] | None = None,
) -> DefineXmlValidationResult:
    """
    Validate define.xml structure and that leaf hrefs align with expected domains.

    Each expected domain code must have a leaf href of `{domain}.xpt` (case-insensitive).
    """
    result = validate_define_xml_structure(define_xml)
    if not result.valid:
        return result

    issues = list(result.issues)
    hrefs_lower = {h.lower() for h in result.leaf_hrefs}

    if expected_domain_codes:
        for code in expected_domain_codes:
            expected_href = f"{code.lower()}.xpt"
            if expected_href not in hrefs_lower:
                issues.append(
                    f"define.xml missing leaf href '{expected_href}' for domain {code}."
                )

    for href in result.leaf_hrefs:
        base = href.rsplit("/", 1)[-1].lower()
        if expected_domain_codes:
            domain_from_href = base.replace(".xpt", "").upper()
            if domain_from_href not in {c.upper() for c in expected_domain_codes}:
                issues.append(
                    f"Leaf href '{href}' references domain {domain_from_href} "
                    "not present in artifact content."
                )

    return DefineXmlValidationResult(
        valid=len(issues) == 0,
        issues=issues,
        leaf_hrefs=result.leaf_hrefs,
        domain_codes=result.domain_codes,
    )
