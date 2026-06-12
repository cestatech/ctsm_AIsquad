"""Render TLF artifact specifications as Word-compatible RTF documents."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class TLFRenderer:
    """Stateless renderer for TLF JSON specs."""

    def render_to_rtf(self, tlf_content: dict) -> bytes:
        """Render TLF JSON content to RTF bytes."""
        parts = [
            r"{\rtf1\ansi\deff0",
            r"{\fonttbl{\f0 Arial;}{\f1 Courier New;}}",
            r"\margl1440\margr1440\margt1440\margb1440",
            r"\fs20",
            self._paragraph("TLF Rendering Output", bold=True, size=28, align="center"),
        ]

        study_name = tlf_content.get("study_name")
        protocol_number = tlf_content.get("protocol_number")
        if study_name:
            parts.append(self._paragraph(f"Study: {study_name}", bold=True))
        if protocol_number:
            parts.append(self._paragraph(f"Protocol: {protocol_number}", bold=True))

        tables = self._as_list(tlf_content.get("tables"))
        listings = self._as_list(tlf_content.get("listings"))
        figures = self._as_list(tlf_content.get("figures"))

        if not tables and not listings and not figures:
            parts.append(
                self._paragraph("No TLF tables, listings, or figures were provided.")
            )

        for table in tables:
            parts.append(self._render_table(table))
        for listing in listings:
            parts.append(self._render_listing(listing))
        for figure in figures:
            parts.append(self._render_figure(figure))

        parts.append("}")
        return "\n".join(parts).encode("utf-8")

    def _render_table(self, table: Any) -> str:
        if not isinstance(table, dict):
            return self._paragraph(str(table))

        title = (
            table.get("title")
            or table.get("name")
            or table.get("id")
            or "Untitled Table"
        )
        rows = self._as_list(table.get("rows") or table.get("data"))
        columns = self._normalize_columns(table.get("columns"), rows)
        parts = [
            self._paragraph(str(title), bold=True, size=24),
        ]

        if table.get("section"):
            parts.append(self._paragraph(f"Section: {table['section']}"))
        if table.get("population"):
            parts.append(self._paragraph(f"Population: {table['population']}"))

        if columns:
            parts.append(
                self._table_row(
                    [column["label"] for column in columns],
                    [column["align"] for column in columns],
                    header=True,
                )
            )
            for row in rows:
                parts.append(
                    self._table_row(
                        [
                            self._value_for_column(row, column["key"])
                            for column in columns
                        ],
                        [column["align"] for column in columns],
                    )
                )
        else:
            metadata = self._metadata_lines(
                table,
                [
                    "source_dataset",
                    "key_variables",
                    "row_definition",
                    "column_definition",
                    "statistical_summary",
                    "program_name",
                ],
            )
            parts.extend(self._paragraph(line) for line in metadata)
            if not metadata:
                parts.append(self._paragraph("No table rows were provided."))

        for footnote in self._as_list(table.get("footnotes")):
            parts.append(self._paragraph(f"Footnote: {footnote}", size=18))
        parts.append(self._paragraph(""))
        return "\n".join(parts)

    def _render_listing(self, listing: Any) -> str:
        if not isinstance(listing, dict):
            return self._paragraph(str(listing), bold=False)

        title = (
            listing.get("title")
            or listing.get("name")
            or listing.get("id")
            or "Untitled Listing"
        )
        parts = [self._paragraph(str(title), bold=True, size=24)]
        text = listing.get("text") or listing.get("content") or listing.get("body")
        lines = self._as_list(listing.get("lines"))
        rows = self._as_list(listing.get("rows"))

        if text:
            parts.append(self._paragraph(str(text)))
        for line in lines:
            parts.append(self._paragraph(str(line), font="courier"))
        for row in rows:
            if isinstance(row, dict):
                rendered = " | ".join(f"{key}: {value}" for key, value in row.items())
            elif isinstance(row, list):
                rendered = " | ".join(str(value) for value in row)
            else:
                rendered = str(row)
            parts.append(self._paragraph(rendered, font="courier"))

        if not text and not lines and not rows:
            parts.extend(
                self._paragraph(line)
                for line in self._metadata_lines(listing, ["description"])
            )
        parts.append(self._paragraph(""))
        return "\n".join(parts)

    def _render_figure(self, figure: Any) -> str:
        if isinstance(figure, dict):
            title = (
                figure.get("title")
                or figure.get("name")
                or figure.get("id")
                or "Untitled Figure"
            )
        else:
            title = str(figure)
        return "\n".join(
            [
                self._paragraph(str(title), bold=True, size=24),
                self._paragraph(
                    "[Figure placeholder: chart rendering is out of scope]",
                    align="center",
                ),
                self._paragraph(""),
            ]
        )

    def _table_row(
        self, values: list[Any], alignments: list[str], header: bool = False
    ) -> str:
        width = 9000
        col_width = max(1000, width // max(1, len(values)))
        cell_defs = "".join(
            rf"\cellx{col_width * (idx + 1)}" for idx in range(len(values))
        )
        cells = []
        for value, align in zip(values, alignments, strict=False):
            prefix = r"\qc " if header else f"{self._rtf_alignment(align)} "
            content = self._rtf_escape(value)
            if header:
                content = rf"\b {content}\b0"
            cells.append(rf"\intbl {prefix}{content}\cell")
        return rf"\trowd\trgaph108\trleft0{cell_defs}" + "".join(cells) + r"\row"

    def _normalize_columns(
        self, raw_columns: Any, rows: list[Any]
    ) -> list[dict[str, str]]:
        columns = []
        for index, column in enumerate(self._as_list(raw_columns)):
            if isinstance(column, dict):
                key = str(
                    column.get("key") or column.get("name") or column.get("id") or index
                )
                label = str(column.get("label") or column.get("title") or key)
                align = str(column.get("align") or column.get("alignment") or "left")
            else:
                key = str(column)
                label = str(column)
                align = "left"
            columns.append({"key": key, "label": label, "align": align})

        if columns or not rows:
            return columns

        first_row = rows[0]
        if isinstance(first_row, dict):
            return [
                {"key": str(key), "label": str(key), "align": "left"}
                for key in first_row.keys()
            ]
        if isinstance(first_row, list):
            return [
                {"key": str(index), "label": f"Column {index + 1}", "align": "left"}
                for index in range(len(first_row))
            ]
        return [{"key": "value", "label": "Value", "align": "left"}]

    def _value_for_column(self, row: Any, key: str) -> Any:
        if isinstance(row, dict):
            return row.get(key, "")
        if isinstance(row, list):
            try:
                return row[int(key)]
            except (ValueError, IndexError):
                return ""
        return row if key == "value" else ""

    def _metadata_lines(self, spec: dict, keys: Iterable[str]) -> list[str]:
        lines = []
        for key in keys:
            value = spec.get(key)
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            label = key.replace("_", " ").title()
            lines.append(f"{label}: {value}")
        return lines

    def _paragraph(
        self,
        text: Any,
        *,
        bold: bool = False,
        size: int | None = None,
        align: str = "left",
        font: str = "arial",
    ) -> str:
        escaped = self._rtf_escape(text)
        font_control = r"\f1" if font == "courier" else r"\f0"
        size_control = rf"\fs{size}" if size else ""
        bold_start = r"\b " if bold else ""
        bold_end = r"\b0 " if bold else ""
        return rf"{self._rtf_alignment(align)} {font_control}{size_control} {bold_start}{escaped}{bold_end}\par"

    @staticmethod
    def _rtf_alignment(align: str) -> str:
        normalized = align.lower()
        if normalized in {"center", "centre", "c"}:
            return r"\qc"
        if normalized in {"right", "r"}:
            return r"\qr"
        return r"\ql"

    @staticmethod
    def _rtf_escape(value: Any) -> str:
        text = "" if value is None else str(value)
        escaped = []
        for char in text:
            if char == "\\":
                escaped.append(r"\\")
            elif char == "{":
                escaped.append(r"\{")
            elif char == "}":
                escaped.append(r"\}")
            elif char in {"\n", "\r"}:
                escaped.append(r"\line ")
            elif ord(char) > 127:
                codepoint = ord(char)
                if codepoint > 32767:
                    codepoint -= 65536
                escaped.append(rf"\u{codepoint}?")
            else:
                escaped.append(char)
        return "".join(escaped)

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]
