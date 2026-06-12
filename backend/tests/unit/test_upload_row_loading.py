"""Unit tests for raw row loading helpers used in SDTM derivation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock


from app.services.storage.filesystem import FilesystemStorageBackend
from app.services.storage_service import StorageService
from app.services.upload_service import UploadService


class TestReconstructRowsFromFields:
    def test_builds_rows_from_sample_values(self):
        age = MagicMock()
        age.column_name = "AGE"
        age.column_index = 0
        age.sample_values = ["45", "52"]

        sex = MagicMock()
        sex.column_name = "SEX"
        sex.column_index = 1
        sex.sample_values = ["M", "F"]

        rows = UploadService.reconstruct_rows_from_fields([age, sex], row_count=2)
        assert len(rows) == 2
        assert rows[0] == {"AGE": "45", "SEX": "M"}
        assert rows[1] == {"AGE": "52", "SEX": "F"}


class TestReadJsonEdcRows:
    def test_reads_matching_form_dataset(self):
        payload = {
            "document_type": "RAW_CLINICAL_DATA",
            "datasets": {
                "demographics": {
                    "form_id": "DM",
                    "form_name": "Demographics",
                    "columns": ["SUBJECT_ID", "SEX"],
                    "sample_rows": [
                        {"SUBJECT_ID": "001", "SEX": "F"},
                        {"SUBJECT_ID": "002", "SEX": "M"},
                    ],
                }
            },
        }
        rows = UploadService.read_json_edc_rows(
            json.dumps(payload).encode(),
            "DM — Demographics",
        )
        assert len(rows) == 2
        assert rows[0]["SUBJECT_ID"] == "001"


class TestReadTabularRows:
    def test_reads_csv_from_resolved_relative_path(self, tmp_path: Path):
        storage_root = tmp_path / "storage"
        rel = Path("org") / "demo" / "studies" / "uploads" / "sample.csv"
        full = storage_root / rel
        full.parent.mkdir(parents=True)
        full.write_text("SUBJECT_ID,SEX\n001,F\n002,M\n", encoding="utf-8")

        storage = StorageService(FilesystemStorageBackend(storage_root))
        storage.put_bytes(str(rel), full.read_bytes())
        rows = UploadService.read_tabular_rows(
            file_path=str(rel),
            mime_type="text/csv",
            filename="sample.csv",
            dataset_name="sample.csv",
            storage_root=str(storage_root),
            storage=storage,
        )
        assert len(rows) == 2
        assert rows[0]["SUBJECT_ID"] == "001"
