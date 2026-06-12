"""Generate a Study Data Reviewer's Guide (SDRG) PDF for a submission package.

Stateless utility: receives CSR content, ADaM dataset metadata, and a
validation summary, and returns PDF bytes. It never touches the database —
the endpoint layer gathers inputs and handles RBAC and audit logging.

The PDF uses the reportlab canvas API directly (no platypus) so the layout
logic is explicit and the output is deterministic. Page compression is
disabled so the document text is byte-inspectable in tests.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

_PAGE_WIDTH, _PAGE_HEIGHT = letter
_MARGIN_LEFT = 54.0
_MARGIN_TOP = 54.0
_MARGIN_BOTTOM = 54.0
_LINE_HEIGHT = 14.0
_SECTION_GAP = 22.0


class _PdfWriter:
    """Tiny cursor-based line writer over a reportlab canvas with page breaks."""

    def __init__(self, canvas: Canvas) -> None:
        self._canvas = canvas
        self._y = _PAGE_HEIGHT - _MARGIN_TOP

    def _ensure_room(self, needed: float) -> None:
        if self._y - needed < _MARGIN_BOTTOM:
            self._canvas.showPage()
            self._y = _PAGE_HEIGHT - _MARGIN_TOP

    def heading(self, text: str) -> None:
        self._ensure_room(_SECTION_GAP + _LINE_HEIGHT)
        self._y -= _SECTION_GAP
        self._canvas.setFont("Helvetica-Bold", 13)
        self._canvas.drawString(_MARGIN_LEFT, self._y, text)
        self._y -= _LINE_HEIGHT

    def line(self, text: str, *, indent: float = 0.0, bold: bool = False) -> None:
        self._ensure_room(_LINE_HEIGHT)
        self._canvas.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        self._canvas.drawString(_MARGIN_LEFT + indent, self._y, text[:110])
        self._y -= _LINE_HEIGHT

    def title(self, text: str) -> None:
        self._ensure_room(_LINE_HEIGHT * 2)
        self._canvas.setFont("Helvetica-Bold", 16)
        self._canvas.drawString(_MARGIN_LEFT, self._y, text[:90])
        self._y -= _LINE_HEIGHT * 1.5

    def table_row(
        self, columns: list[str], widths: list[float], *, bold: bool = False
    ) -> None:
        self._ensure_room(_LINE_HEIGHT)
        self._canvas.setFont("Helvetica-Bold" if bold else "Helvetica", 9)
        x = _MARGIN_LEFT
        for text, width in zip(columns, widths):
            max_chars = max(int(width / 5.0), 4)
            self._canvas.drawString(x, self._y, str(text)[:max_chars])
            x += width
        self._y -= _LINE_HEIGHT


def generate_reviewers_guide_pdf(
    *,
    study_title: str,
    protocol_number: str,
    csr_content: dict,
    adam_datasets: list[dict],
    validation_summary: dict,
) -> bytes:
    """
    Build the Reviewer's Guide PDF.

    Args:
        study_title: Study name used on the title block.
        protocol_number: Protocol identifier.
        csr_content: Current CSR artifact version content (ICH E3 sections).
        adam_datasets: One entry per ADaM dataset:
            ``{"name": str, "label": str, "record_count": int | None}``.
        validation_summary: Counts keyed by evidence status, e.g.
            ``{"PASS": 41, "FAIL": 2, "WARNING": 5, "WAIVED": 1, "PENDING": 0}``.

    Returns:
        PDF document bytes.
    """
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=letter, pageCompression=0)
    writer = _PdfWriter(canvas)

    writer.title("Study Data Reviewer's Guide")
    writer.line(f"Study: {study_title}", bold=True)
    writer.line(f"Protocol: {protocol_number}")
    writer.line(f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    writer.line("Data classification: SYNTHETIC — not for regulatory submission")

    # ------------------------------------------------------------- 1. Overview
    writer.heading("1. Study Overview")
    ident = csr_content.get("study_identification") or {}
    synopsis = csr_content.get("synopsis") or {}
    overview_rows = [
        ("CSR title", csr_content.get("title") or "—"),
        ("Sponsor", ident.get("sponsor") or "—"),
        ("Phase", ident.get("phase") or "—"),
        ("Indication", ident.get("indication") or "—"),
        ("Design", synopsis.get("design") or "—"),
        ("Objectives", synopsis.get("objectives") or "—"),
    ]
    for label, value in overview_rows:
        writer.line(f"{label}: {value}", indent=8)

    # ---------------------------------------------------- 2. Dataset Inventory
    writer.heading("2. Dataset Inventory (ADaM)")
    col_widths = [110.0, 240.0, 90.0]
    writer.table_row(["Dataset", "Label", "Records"], col_widths, bold=True)
    if adam_datasets:
        for ds in adam_datasets:
            count = ds.get("record_count")
            writer.table_row(
                [
                    ds.get("name") or "—",
                    ds.get("label") or "—",
                    str(count) if count is not None else "n/a",
                ],
                col_widths,
            )
    else:
        writer.line("No ADaM datasets found for this study.", indent=8)

    # --------------------------------------------------- 3. Validation Summary
    writer.heading("3. Validation Summary")
    total = sum(validation_summary.values()) if validation_summary else 0
    writer.line(f"Total validation evidence records: {total}", indent=8)
    for status_name in ("PASS", "FAIL", "WARNING", "WAIVED", "PENDING"):
        count = validation_summary.get(status_name, 0)
        writer.line(f"{status_name}: {count}", indent=16)
    if validation_summary.get("FAIL", 0) > 0:
        writer.line(
            "Unresolved FAIL findings exist — see /intelligence/validation for "
            "rule-level evidence.",
            indent=8,
        )

    # ---------------------------------------------------- 4. Navigational Guide
    writer.heading("4. Navigational Guide")
    writer.line(
        "CSR structure (ICH E3). Datasets are under m5/datasets/; define.xml "
        "documents variable-level metadata.",
        indent=8,
    )
    sections = csr_content.get("sections") or []
    if sections:
        for section in sections:
            number = section.get("number", "")
            title = section.get("title", "")
            writer.line(f"Section {number}: {title}", indent=16)
    else:
        writer.line("CSR has no section outline yet.", indent=16)

    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def build_reviewers_guide_filename(protocol_number: str | None) -> str:
    """Return the download filename for the Reviewer's Guide PDF."""
    stem = (protocol_number or "study").replace("/", "-").replace(" ", "_")
    return f"reviewers_guide_{stem}.pdf"
