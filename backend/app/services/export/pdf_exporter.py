"""PDF export for specification-style clinical artifacts."""

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


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ExportTitle",
            parent=base["Heading1"],
            fontSize=16,
            spaceAfter=12,
        ),
        "heading": ParagraphStyle(
            "ExportHeading",
            parent=base["Heading2"],
            fontSize=12,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "ExportBody",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
        ),
        "small": ParagraphStyle(
            "ExportSmall",
            parent=base["BodyText"],
            fontSize=9,
            textColor=colors.grey,
        ),
    }


def _escape(text: Any) -> str:
    value = str(text or "")
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _paragraphs_from_value(value: Any, style) -> list:
    blocks: list = []
    if value is None:
        return blocks
    if isinstance(value, str):
        for line in value.split("\n"):
            if line.strip():
                blocks.append(Paragraph(_escape(line.strip()), style))
        return blocks
    if isinstance(value, (int, float, bool)):
        blocks.append(Paragraph(_escape(value), style))
        return blocks
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                for key, nested in item.items():
                    blocks.append(
                        Paragraph(
                            f"<b>{_escape(_heading_text(str(key)))}:</b> "
                            f"{_escape(nested)}",
                            style,
                        )
                    )
            else:
                blocks.append(Paragraph(f"• {_escape(item)}", style))
        return blocks
    if isinstance(value, dict):
        for key, nested in value.items():
            blocks.append(
                Paragraph(
                    f"<b>{_escape(_heading_text(str(key)))}:</b> "
                    f"{_escape(nested)}",
                    style,
                )
            )
        return blocks
    blocks.append(Paragraph(_escape(value), style))
    return blocks


def _heading_text(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _table_from_rows(
    headers: list[str],
    rows: list[list[str]],
) -> Table | None:
    if not headers:
        return None
    data = [headers] + rows
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    return table


def _render_edc_sections(content: dict, styles) -> list:
    story: list = []

    visit_schedule = content.get("visit_schedule") or []
    if visit_schedule:
        story.append(Paragraph("Schedule of Assessments", styles["heading"]))
        headers = ["Visit ID", "Label", "Day", "Window"]
        rows = [
            [
                str(v.get("visit_id", "")),
                str(v.get("label", "")),
                str(v.get("day", "")),
                str(v.get("window_days", "")),
            ]
            for v in visit_schedule
            if isinstance(v, dict)
        ]
        table = _table_from_rows(headers, rows)
        if table:
            story.append(table)
            story.append(Spacer(1, 0.15 * inch))

    forms = content.get("forms") or []
    if forms:
        story.append(Paragraph("Forms", styles["heading"]))
        headers = ["Form ID", "Form Name", "Visits"]
        rows = [
            [
                str(f.get("form_id", "")),
                str(f.get("form_name", "")),
                ", ".join(str(v) for v in (f.get("visit_ids") or [])),
            ]
            for f in forms
            if isinstance(f, dict)
        ]
        table = _table_from_rows(headers, rows)
        if table:
            story.append(table)
            story.append(Spacer(1, 0.15 * inch))

    fields = content.get("fields") or []
    if fields:
        story.append(Paragraph("Fields", styles["heading"]))
        headers = ["Field ID", "Label", "Type", "SDTM Variable"]
        rows = [
            [
                str(f.get("field_id", "")),
                str(f.get("label", "")),
                str(f.get("type", "")),
                str(f.get("sdtm_variable", "")),
            ]
            for f in fields
            if isinstance(f, dict)
        ]
        table = _table_from_rows(headers, rows[:80])
        if table:
            story.append(table)
            if len(fields) > 80:
                story.append(
                    Paragraph(
                        f"Showing first 80 of {len(fields)} fields.",
                        styles["small"],
                    )
                )
            story.append(Spacer(1, 0.15 * inch))

    edit_checks = content.get("edit_checks") or []
    if edit_checks:
        story.append(Paragraph("Edit Checks", styles["heading"]))
        for check in edit_checks[:40]:
            if isinstance(check, dict):
                story.extend(
                    _paragraphs_from_value(
                        {
                            "rule": check.get("rule_id") or check.get("id"),
                            "description": check.get("description"),
                            "severity": check.get("severity"),
                        },
                        styles["body"],
                    )
                )
        story.append(Spacer(1, 0.1 * inch))

    mock_screens = content.get("mock_screens") or content.get("screens") or []
    if mock_screens:
        story.append(Paragraph("Mock Screen Summaries", styles["heading"]))
        for screen in mock_screens[:20]:
            story.extend(_paragraphs_from_value(screen, styles["body"]))
        story.append(Spacer(1, 0.1 * inch))

    return story


def _render_tlf_sections(content: dict, styles) -> list:
    story: list = []
    for section_name in ("tables", "listings", "figures"):
        items = content.get(section_name) or []
        if not items:
            continue
        story.append(Paragraph(_heading_text(section_name), styles["heading"]))
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("id") or section_name
            story.append(Paragraph(_escape(title), styles["body"]))
            rows = item.get("rows") or []
            columns = item.get("columns") or []
            if rows and columns:
                headers = [
                    c.get("label") or c.get("key") or str(c)
                    if isinstance(c, dict)
                    else str(c)
                    for c in columns
                ]
                table_rows = []
                for row in rows[:30]:
                    if isinstance(row, dict):
                        keys = [
                            c.get("key") if isinstance(c, dict) else str(c)
                            for c in columns
                        ]
                        table_rows.append([str(row.get(k, "")) for k in keys])
                    elif isinstance(row, list):
                        table_rows.append([str(cell) for cell in row])
                table = _table_from_rows(headers, table_rows)
                if table:
                    story.append(table)
            story.append(Spacer(1, 0.1 * inch))
    return story


def export_pdf(
    content: dict,
    *,
    title: str,
    study_name: str,
    version_number: int,
    document_label: str,
    artifact_type: str,
) -> bytes:
    """Render structured artifact JSON as a readable PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = _styles()
    story: list = [
        Spacer(1, 1.5 * inch),
        Paragraph(_escape(title), styles["title"]),
        Spacer(1, 0.3 * inch),
        Paragraph(f"Study: {_escape(study_name)}", styles["body"]),
        Paragraph(f"Document: {_escape(document_label)}", styles["body"]),
        Paragraph(f"Version: {version_number}", styles["body"]),
        Paragraph(
            f"Exported: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
            styles["small"],
        ),
        PageBreak(),
    ]

    if artifact_type == "EDC_CRF":
        story.extend(_render_edc_sections(content, styles))
    elif artifact_type == "TLF":
        story.extend(_render_tlf_sections(content, styles))
    else:
        sections = content.get("sections")
        if isinstance(sections, dict):
            for key, value in sections.items():
                story.append(Paragraph(_heading_text(str(key)), styles["heading"]))
                story.extend(_paragraphs_from_value(value, styles["body"]))
                story.append(Spacer(1, 0.08 * inch))
        elif isinstance(sections, list):
            for section in sections:
                if isinstance(section, dict):
                    heading = section.get("title") or section.get("number") or "Section"
                    story.append(Paragraph(_escape(heading), styles["heading"]))
                    story.extend(
                        _paragraphs_from_value(
                            section.get("content")
                            or section.get("content_outline")
                            or section,
                            styles["body"],
                        )
                    )
                    story.append(Spacer(1, 0.08 * inch))
        else:
            skip_keys = {"document_type", "csv_files", "datasets", "primary_csv_filename"}
            for key, value in content.items():
                if key in skip_keys or value in (None, "", [], {}):
                    continue
                story.append(Paragraph(_heading_text(str(key)), styles["heading"]))
                story.extend(_paragraphs_from_value(value, styles["body"]))
                story.append(Spacer(1, 0.08 * inch))

    doc.build(story)
    return buffer.getvalue()
