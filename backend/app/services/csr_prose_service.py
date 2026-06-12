"""Stateless helpers to assemble CSR section prose generation context."""

from __future__ import annotations

from typing import Any

_SECTION_TITLES: dict[str, str] = {
    "1": "Title Page",
    "2": "Synopsis",
    "9": "Introduction",
    "10": "Study Objectives",
    "11": "Investigational Plan",
    "12": "Study Patients",
    "13": "Efficacy Evaluation",
    "14": "Safety Evaluation",
    "15": "Discussion and Overall Conclusions",
}

_SECTION_GUIDANCE: dict[str, str] = {
    "1": "Study title, sponsor, protocol number, and report metadata.",
    "2": "Concise tabular-style synopsis of design, population, and key results.",
    "9": "Disease background, unmet need, and study rationale.",
    "10": "Primary and secondary objectives with endpoints.",
    "11": "Overall design, selection criteria, treatments, and procedures.",
    "12": "Disposition, demographics, and protocol deviations.",
    "13": "Primary and secondary efficacy results with TLF references.",
    "14": "Safety findings including AEs, labs, and SAEs with TLF references.",
    "15": "Integrated benefit-risk discussion and overall conclusions.",
}


def _protocol_excerpt(protocol_content: dict) -> dict[str, Any]:
    objectives = protocol_content.get("objectives", {})
    primary: list[str] = []
    if isinstance(objectives, dict):
        for item in objectives.get("primary", [])[:3]:
            if isinstance(item, dict):
                primary.append(
                    str(item.get("description") or item.get("title") or item)
                )
            else:
                primary.append(str(item))
    elif isinstance(objectives, list):
        primary = [str(o) for o in objectives[:3]]

    design = protocol_content.get("design")
    if isinstance(design, dict):
        design_summary = design.get("summary") or design.get("description")
    else:
        design_summary = design

    return {
        "title": protocol_content.get("title"),
        "objectives_primary": primary,
        "design_summary": design_summary,
        "primary_endpoint": protocol_content.get("primary_endpoint"),
        "treatments": protocol_content.get("treatments", []),
    }


def _sap_excerpt(sap_content: dict) -> dict[str, Any]:
    return {
        "title": sap_content.get("title"),
        "primary_endpoint": sap_content.get("primary_endpoint"),
        "analysis_populations": sap_content.get("analysis_populations", []),
        "safety_analyses": sap_content.get("safety_analyses"),
        "primary_endpoint_analysis": sap_content.get("primary_endpoint_analysis"),
    }


def _tables_for_section(section_id: str, merged_tables: list[dict]) -> list[dict]:
    matched: list[dict] = []
    for table in merged_tables:
        section = str(table.get("section", "")).split(".")[0]
        title = str(table.get("title", "")).lower()
        if section_id == "12" and any(
            token in title for token in ("demograph", "disposition", "baseline")
        ):
            matched.append(table)
        elif section_id == "13" and any(
            token in title for token in ("efficacy", "endpoint", "response")
        ):
            matched.append(table)
        elif section_id == "14" and any(
            token in title for token in ("safety", "adverse", "ae", "laboratory")
        ):
            matched.append(table)
        elif section == section_id:
            matched.append(table)
    if matched:
        return matched
    if section_id in {"12", "13", "14"} and merged_tables:
        return merged_tables[:2]
    return []


def assemble_context(
    *,
    section_id: str,
    study: dict[str, Any],
    protocol_content: dict,
    sap_content: dict,
    merged_tables: list[dict],
    tlf_content: dict | None = None,
    section_entry: dict | None = None,
    instructions: str | None = None,
) -> dict[str, Any]:
    """Build a section context dict for CSR prose generation (no DB access)."""
    section_entry = section_entry or {}
    tlf_content = tlf_content or {}
    relevant_tables = section_entry.get("tlf_references") or _tables_for_section(
        section_id, merged_tables
    )

    return {
        "section_id": section_id,
        "section_title": section_entry.get("title")
        or _SECTION_TITLES.get(section_id, f"Section {section_id}"),
        "section_guidance": _SECTION_GUIDANCE.get(section_id, ""),
        "study_name": study.get("name"),
        "protocol_number": study.get("protocol_number"),
        "sponsor": study.get("sponsor"),
        "phase": study.get("phase"),
        "indication": study.get("indication"),
        "protocol_excerpt": _protocol_excerpt(protocol_content),
        "sap_excerpt": _sap_excerpt(sap_content),
        "tlf_tables": relevant_tables,
        "tlf_summary": {
            "table_count": len(tlf_content.get("tables", [])),
            "listing_count": len(tlf_content.get("listings", [])),
            "figure_count": len(tlf_content.get("figures", [])),
        },
        "content_outline": section_entry.get("content_outline"),
        "narrative_summary": section_entry.get("narrative_summary"),
        "instructions": instructions,
    }
