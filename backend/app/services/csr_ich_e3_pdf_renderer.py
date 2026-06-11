"""Render ICH E3 Clinical Study Report content to submission-grade PDF."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ICH E3 sections rendered in submission CSR PDF (Lane 2; prose from #17 in Lane 3).
ICH_E3_SECTION_ORDER = [
    ("1", "Title Page"),
    ("2", "Synopsis"),
    ("9", "Introduction"),
    ("10", "Study Objectives"),
    ("11", "Investigational Plan"),
    ("12", "Study Patients"),
    ("13", "Efficacy Evaluation"),
    ("14", "Safety Evaluation"),
    ("15", "Discussion and Overall Conclusions"),
]


def _escape(text: Any) -> str:
    value = str(text or "")
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "CSRTitle",
            parent=base["Heading1"],
            fontSize=18,
            spaceAfter=14,
            alignment=1,
        ),
        "heading": ParagraphStyle(
            "CSRHeading",
            parent=base["Heading2"],
            fontSize=13,
            spaceBefore=12,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "CSRBody",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
        ),
        "small": ParagraphStyle(
            "CSRSmall",
            parent=base["BodyText"],
            fontSize=9,
            textColor=colors.grey,
        ),
    }


def _section_text(section: dict) -> str:
    """Prefer prose (from #17), then narrative_summary, then content_outline."""
    for key in ("prose", "narrative_summary", "content_outline", "content"):
        value = section.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _build_synopsis_table(synopsis: dict, styles: dict) -> Table | None:
    if not synopsis:
        return None
    rows = [["Element", "Description"]]
    for key, value in synopsis.items():
        if value is None or value == "":
            continue
        if isinstance(value, (list, dict)):
            value = str(value)
        rows.append([_escape(key.replace("_", " ").title()), _escape(value)])
    if len(rows) <= 1:
        return None
    table = Table(rows, colWidths=[1.8 * inch, 4.5 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _build_tlf_reference_table(tlf_integration: list[dict], styles: dict) -> Table | None:
    if not tlf_integration:
        return None
    rows = [["Table ID", "CSR Section", "Note"]]
    for entry in tlf_integration:
        rows.append(
            [
                _escape(entry.get("table_id", "")),
                _escape(entry.get("csr_section", "")),
                _escape(entry.get("insertion_note", "")),
            ]
        )
    table = Table(rows, colWidths=[1.2 * inch, 1.0 * inch, 4.1 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ]
        )
    )
    return table


def render_ich_e3_csr_pdf(
    content: dict,
    *,
    study_name: str,
    protocol_number: str | None = None,
) -> bytes:
    """
    Render CSR artifact JSON to an ICH E3-structured PDF.

    Expects content with title, study_identification, synopsis, sections[],
    and optional tlf_integration[]. Full prose per section is supplied by #17;
    this renderer falls back to narrative_summary or content_outline for Lane 2 tests.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=content.get("title", "Clinical Study Report"),
    )
    styles = _styles()
    story: list = []

    ident = content.get("study_identification", {})
    title = content.get("title", study_name)
    protocol = protocol_number or ident.get("protocol_number", "N/A")

    # Section 1 — Title Page
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph(_escape(title), styles["title"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(f"Protocol: {_escape(protocol)}", styles["body"]))
    story.append(Paragraph(f"Study: {_escape(study_name)}", styles["body"]))
    story.append(
        Paragraph(
            f"Sponsor: {_escape(ident.get('sponsor', 'Sponsor'))}",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            f"Report date: {datetime.now(UTC).strftime('%Y-%m-%d')}",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "ICH E3 Clinical Study Report — regulatory draft",
            styles["small"],
        )
    )
    story.append(PageBreak())

    # Section 2 — Synopsis
    story.append(Paragraph("2. Synopsis", styles["heading"]))
    synopsis = content.get("synopsis", {})
    syn_table = _build_synopsis_table(synopsis, styles)
    if syn_table:
        story.append(syn_table)
    else:
        story.append(Paragraph("Synopsis not provided.", styles["body"]))
    story.append(PageBreak())

    # Sections 9–15
    sections_by_number: dict[str, dict] = {}
    for section in content.get("sections", []):
        num = str(section.get("number", ""))
        sections_by_number[num] = section

    for num, default_title in ICH_E3_SECTION_ORDER[2:]:
        section = sections_by_number.get(num, {})
        section_title = section.get("title", default_title)
        story.append(
            Paragraph(f"{num}. {_escape(section_title)}", styles["heading"])
        )
        text = _section_text(section)
        if text:
            for para in text.split("\n\n"):
                if para.strip():
                    story.append(Paragraph(_escape(para.strip()), styles["body"]))
                    story.append(Spacer(1, 0.06 * inch))
        else:
            story.append(
                Paragraph(
                    "[Section content pending medical writer review.]",
                    styles["small"],
                )
            )

        refs = section.get("tlf_references", [])
        if refs:
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph("Referenced TLFs:", styles["body"]))
            for ref in refs[:10]:
                tid = ref.get("table_id", "?")
                rtitle = ref.get("title", "")
                story.append(
                    Paragraph(
                        f"• Table { _escape(tid) }: {_escape(rtitle)} (see tlf/*.rtf)",
                        styles["small"],
                    )
                )
        story.append(Spacer(1, 0.15 * inch))

    # TLF integration appendix
    tlf_integration = content.get("tlf_integration", [])
    if tlf_integration:
        story.append(PageBreak())
        story.append(Paragraph("TLF Integration Map", styles["heading"]))
        story.append(
            Paragraph(
                "Tables, listings, and figures are provided as separate RTF files "
                "in the submission package. This map documents CSR section placement.",
                styles["body"],
            )
        )
        story.append(Spacer(1, 0.1 * inch))
        ref_table = _build_tlf_reference_table(tlf_integration, styles)
        if ref_table:
            story.append(ref_table)

    doc.build(story)
    return buffer.getvalue()
