"""PHI masking utilities for safe preview of uploaded clinical data."""

from __future__ import annotations

import re

# Column names that likely contain protected health information.
_PHI_COLUMN_RE = re.compile(
    r"(name|dob|birth|ssn|social|mrn|patient|subject|address|phone|email|zip|postal)",
    re.IGNORECASE,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SSN_RE = re.compile(r"^\d{3}-\d{2}-\d{4}$")
_PHONE_RE = re.compile(r"^\+?[\d\s().-]{7,}$")


def mask_sample_value(column_name: str, value: str | None) -> str:
    """Return a safe preview string, masking values that look like PHI."""
    if value is None or value == "":
        return ""

    text = str(value).strip()
    if _PHI_COLUMN_RE.search(column_name):
        return "[MASKED]"

    if _SSN_RE.match(text) or _EMAIL_RE.match(text) or _PHONE_RE.match(text):
        return "[MASKED]"

    # Truncate long free-text values that may contain narrative PHI.
    if len(text) > 40:
        return f"{text[:20]}…[TRUNCATED]"

    return text


def mask_sample_values(column_name: str, values: list) -> list[str]:
    """Mask and cap sample values for column preview (max 3)."""
    return [mask_sample_value(column_name, v) for v in values[:3]]
