"""Data source classification for clinical data pipeline artifacts."""

from __future__ import annotations

import enum


class DataSourceType(str, enum.Enum):
    """Classification of clinical vs synthetic data across the pipeline."""

    SYNTHETIC = "SYNTHETIC"
    LIVE_INTERIM = "LIVE_INTERIM"
    LIVE_FINAL = "LIVE_FINAL"
