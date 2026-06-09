"""Data cut context — classification, propagation, and pipeline validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.models.data_source import DataSourceType

_PLACEHOLDER_PHRASES = (
    "table placeholder",
    "results to be inserted",
    "pending analysis",
    "csr shell",
    "populate after",
    "not submission-ready",
    "draft — pending",
)


@dataclass
class DataCutContext:
    """Canonical metadata carried across uploads, runs, and pipeline artifacts."""

    data_source_type: DataSourceType
    data_cut_label: str
    data_cut_date: date | None
    is_synthetic: bool
    study_id: UUID
    created_by: UUID
    created_at: datetime
    source_upload_id: UUID | None = None
    synthetic_data_run_id: UUID | None = None
    data_cut_id: UUID | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.data_cut_id is None:
            self.data_cut_id = self.synthetic_data_run_id or self.source_upload_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_source_type": self.data_source_type.value,
            "data_cut_label": self.data_cut_label,
            "data_cut_date": self.data_cut_date.isoformat() if self.data_cut_date else None,
            "is_synthetic": self.is_synthetic,
            "source_upload_id": str(self.source_upload_id) if self.source_upload_id else None,
            "synthetic_data_run_id": (
                str(self.synthetic_data_run_id) if self.synthetic_data_run_id else None
            ),
            "data_cut_id": str(self.data_cut_id) if self.data_cut_id else None,
            "study_id": str(self.study_id),
            "created_by": str(self.created_by),
            "created_at": self.created_at.isoformat(),
            "notes": self.notes,
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> DataCutContext | None:
        if not data:
            return None
        source = data.get("data_source") or data.get("data_cut") or data
        if not source.get("data_source_type"):
            return None
        try:
            dst = DataSourceType(str(source["data_source_type"]))
        except ValueError:
            return None
        cut_date = source.get("data_cut_date")
        parsed_date: date | None = None
        if isinstance(cut_date, date):
            parsed_date = cut_date
        elif isinstance(cut_date, str) and cut_date:
            parsed_date = date.fromisoformat(cut_date[:10])
        created_at_raw = source.get("created_at")
        if isinstance(created_at_raw, datetime):
            created_at = created_at_raw
        elif isinstance(created_at_raw, str) and created_at_raw:
            created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
        else:
            created_at = datetime.now().astimezone()
        return cls(
            data_source_type=dst,
            data_cut_label=str(source.get("data_cut_label") or "Data Cut"),
            data_cut_date=parsed_date,
            is_synthetic=bool(source.get("is_synthetic", dst == DataSourceType.SYNTHETIC)),
            study_id=UUID(str(source["study_id"])),
            created_by=UUID(str(source["created_by"])),
            created_at=created_at,
            source_upload_id=(
                UUID(str(source["source_upload_id"]))
                if source.get("source_upload_id")
                else None
            ),
            synthetic_data_run_id=(
                UUID(str(source["synthetic_data_run_id"]))
                if source.get("synthetic_data_run_id")
                else None
            ),
            data_cut_id=UUID(str(source["data_cut_id"])) if source.get("data_cut_id") else None,
            notes=source.get("notes"),
        )

    @classmethod
    def for_synthetic_run(
        cls,
        *,
        study_id: UUID,
        created_by: UUID,
        run_id: UUID,
        version_number: int = 1,
        created_at: datetime | None = None,
    ) -> DataCutContext:
        now = created_at or datetime.now().astimezone()
        return cls(
            data_source_type=DataSourceType.SYNTHETIC,
            data_cut_label=f"Synthetic Data Version {version_number}",
            data_cut_date=now.date(),
            is_synthetic=True,
            study_id=study_id,
            created_by=created_by,
            created_at=now,
            synthetic_data_run_id=run_id,
            data_cut_id=run_id,
        )

    @classmethod
    def for_live_upload(
        cls,
        *,
        study_id: UUID,
        created_by: UUID,
        upload_id: UUID,
        data_source_type: DataSourceType,
        data_cut_label: str,
        data_cut_date: date | None,
        notes: str | None = None,
        created_at: datetime | None = None,
    ) -> DataCutContext:
        if data_source_type == DataSourceType.SYNTHETIC:
            raise ValueError("Use for_synthetic_run for synthetic data.")
        now = created_at or datetime.now().astimezone()
        return cls(
            data_source_type=data_source_type,
            data_cut_label=data_cut_label,
            data_cut_date=data_cut_date or now.date(),
            is_synthetic=False,
            study_id=study_id,
            created_by=created_by,
            created_at=now,
            source_upload_id=upload_id,
            data_cut_id=upload_id,
            notes=notes,
        )

    def embed_in_content(self, content: dict) -> dict:
        merged = dict(content)
        merged["data_source"] = self.to_dict()
        return merged

    def csr_kind(self) -> str:
        if self.data_source_type == DataSourceType.SYNTHETIC:
            return "SYNTHETIC_CSR"
        if self.data_source_type == DataSourceType.LIVE_INTERIM:
            return "INTERIM_CSR"
        return "FINAL_CSR"

    def artifact_type_label(self, package: str) -> str:
        if self.data_source_type == DataSourceType.SYNTHETIC:
            return f"{package} — {self.data_cut_label}"
        if self.data_source_type == DataSourceType.LIVE_INTERIM:
            return f"{package} — {self.data_cut_label}"
        return f"{package} — {self.data_cut_label}"

    def csr_title(self, study_name: str) -> str:
        if self.data_source_type == DataSourceType.LIVE_INTERIM:
            return f"Interim CSR — {self.data_cut_label}"
        if self.data_source_type == DataSourceType.SYNTHETIC:
            return f"CSR — {self.data_cut_label}"
        return f"Clinical Study Report — {self.data_cut_label}"

    def download_slug(self, study_slug: str) -> str:
        slug = _slugify(study_slug)
        if self.data_source_type == DataSourceType.SYNTHETIC:
            ver = re.search(r"(\d+)$", self.data_cut_label)
            v = ver.group(1) if ver else "1"
            return f"{slug}_synthetic_v{v}"
        if self.data_source_type == DataSourceType.LIVE_INTERIM:
            cut = _slugify(self.data_cut_label)
            date_part = self.data_cut_date.isoformat() if self.data_cut_date else "cut"
            return f"{slug}_{cut}_{date_part}"
        return f"{slug}_final"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "study"


def extract_data_cut(
    artifact_extra: dict | None,
    content: dict | None,
) -> DataCutContext | None:
    if content:
        ctx = DataCutContext.from_mapping(content.get("data_source"))
        if ctx:
            return ctx
    if artifact_extra:
        return DataCutContext.from_mapping(artifact_extra.get("data_cut"))
    return None


def assert_compatible_data_cuts(
    upstream: DataCutContext | None,
    downstream: DataCutContext | None,
    *,
    operation: str,
) -> None:
    if upstream is None or downstream is None:
        return
    if upstream.study_id != downstream.study_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "DATA_CUT_MISMATCH",
                "message": f"{operation}: study_id mismatch between upstream and downstream.",
            },
        )
    if upstream.data_source_type != downstream.data_source_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "DATA_SOURCE_MISMATCH",
                "message": (
                    f"{operation}: cannot mix {upstream.data_source_type.value} "
                    f"with {downstream.data_source_type.value}."
                ),
            },
        )
    if upstream.data_cut_id and downstream.data_cut_id and upstream.data_cut_id != downstream.data_cut_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "DATA_CUT_MISMATCH",
                "message": (
                    f"{operation}: data cut '{upstream.data_cut_label}' does not match "
                    f"'{downstream.data_cut_label}'."
                ),
            },
        )


def artifacts_share_data_cut(
    artifacts: list[tuple[Any, dict]],
) -> DataCutContext | None:
    """Return shared data cut when all artifacts agree; else None."""
    cuts: list[DataCutContext] = []
    for artifact, content in artifacts:
        cut = extract_data_cut(getattr(artifact, "extra_data", None), content)
        if cut:
            cuts.append(cut)
    if not cuts:
        return None
    first = cuts[0]
    for other in cuts[1:]:
        if (
            other.data_source_type != first.data_source_type
            or other.data_cut_id != first.data_cut_id
        ):
            return None
    return first


def data_cut_from_dataset(
    dataset: Any,
    upload: Any,
    actor_id: UUID,
) -> DataCutContext:
    """Build data cut context from a parsed raw dataset and its upload."""
    return DataCutContext(
        data_source_type=dataset.data_source_type,
        data_cut_label=dataset.data_cut_label or upload.data_cut_label or "Data Cut",
        data_cut_date=dataset.data_cut_date or upload.data_cut_date,
        is_synthetic=bool(dataset.is_synthetic or upload.is_synthetic),
        study_id=dataset.study_id,
        created_by=actor_id,
        created_at=getattr(dataset, "created_at", datetime.now().astimezone()),
        source_upload_id=upload.id,
        data_cut_id=dataset.data_cut_id or upload.data_cut_id or upload.id,
        notes=upload.description,
    )


def prepare_pipeline_artifact(
    *,
    study_name: str,
    package_label: str,
    data_cut: DataCutContext,
    content: dict,
    base_description: str,
) -> tuple[str, str, dict, dict]:
    """Return artifact name, description, content, and extra metadata."""
    name = f"{study_name} — {data_cut.artifact_type_label(package_label)}"
    if data_cut.is_synthetic:
        description = f"SYNTHETIC — {base_description} ({data_cut.data_cut_label})"
    elif data_cut.data_source_type == DataSourceType.LIVE_INTERIM:
        description = f"Live Interim Data — {base_description} ({data_cut.data_cut_label})"
    else:
        description = f"Live Final Data — {base_description} ({data_cut.data_cut_label})"
    enriched = data_cut.embed_in_content(content)
    return name, description, enriched, {"data_cut": data_cut.to_dict()}


def contains_shell_placeholder(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in _PLACEHOLDER_PHRASES)


@dataclass
class CSRRequirement:
    key: str
    label: str
    met: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "met": self.met,
            "detail": self.detail,
        }


@dataclass
class CSRReadinessResult:
    study_id: UUID
    data_cut_id: UUID | None
    data_source_type: str | None
    data_cut_label: str | None
    csr_kind: str | None
    ready: bool
    requirements: list[CSRRequirement] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    protocol_artifact_id: UUID | None = None
    sap_artifact_id: UUID | None = None
    sdtm_artifact_id: UUID | None = None
    adam_artifact_id: UUID | None = None
    tlf_artifact_id: UUID | None = None
    source_upload_id: UUID | None = None
    synthetic_data_run_id: UUID | None = None

    def to_response_dict(self) -> dict:
        return {
            "study_id": self.study_id,
            "data_cut_id": self.data_cut_id,
            "data_source_type": self.data_source_type,
            "data_cut_label": self.data_cut_label,
            "csr_kind": self.csr_kind,
            "ready": self.ready,
            "requirements": [r.to_dict() for r in self.requirements],
            "issues": self.issues,
            "protocol_artifact_count": 1 if self.protocol_artifact_id else 0,
            "sap_artifact_count": 1 if self.sap_artifact_id else 0,
            "tlf_artifact_count": 1 if self.tlf_artifact_id else 0,
            "tlf_artifacts": (
                [{"artifact_id": str(self.tlf_artifact_id), "ready": True}]
                if self.tlf_artifact_id
                else []
            ),
            "sdtm_artifact_id": str(self.sdtm_artifact_id) if self.sdtm_artifact_id else None,
            "adam_artifact_id": str(self.adam_artifact_id) if self.adam_artifact_id else None,
            "source_upload_id": str(self.source_upload_id) if self.source_upload_id else None,
            "synthetic_data_run_id": (
                str(self.synthetic_data_run_id) if self.synthetic_data_run_id else None
            ),
        }
