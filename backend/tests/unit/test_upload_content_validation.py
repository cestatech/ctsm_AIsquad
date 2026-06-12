"""Unit tests for content-based upload type validation."""

from __future__ import annotations

import io
import zipfile

import openpyxl
import pytest
from fastapi import HTTPException

from app.services.upload_service import UploadService


def _xlsx_bytes() -> bytes:
    output = io.BytesIO()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["subject_id", "age"])
    sheet.append(["S001", 45])
    workbook.save(output)
    return output.getvalue()


class TestUploadContentValidation:
    def test_valid_csv_returns_server_canonical_mime(self):
        detected = UploadService._validate_upload_type(
            content=b"subject_id,age\nS001,45\n",
            filename="subjects.csv",
            declared_mime_type="application/vnd.ms-excel",
        )

        assert detected == "text/csv"

    def test_binary_renamed_to_csv_is_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            UploadService._validate_upload_type(
                content=b"\x89PNG\r\n\x1a\n\x00binary",
                filename="subjects.csv",
                declared_mime_type="text/csv",
            )

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["code"] == "FILE_TYPE_MISMATCH"

    def test_declared_mime_must_match_extension(self):
        with pytest.raises(HTTPException) as exc_info:
            UploadService._validate_upload_type(
                content=b"subject_id,age\nS001,45\n",
                filename="subjects.csv",
                declared_mime_type="application/pdf",
            )

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["code"] == "FILE_TYPE_MISMATCH"

    def test_valid_xlsx_is_accepted(self):
        detected = UploadService._validate_upload_type(
            content=_xlsx_bytes(),
            filename="subjects.xlsx",
            declared_mime_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

        assert (
            detected
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_arbitrary_zip_renamed_to_xlsx_is_rejected(self):
        output = io.BytesIO()

        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("payload.txt", "not a workbook")

        with pytest.raises(HTTPException) as exc_info:
            UploadService._validate_upload_type(
                content=output.getvalue(),
                filename="subjects.xlsx",
                declared_mime_type=(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
            )

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["code"] == "FILE_TYPE_MISMATCH"

    def test_unsupported_extension_returns_415(self):
        with pytest.raises(HTTPException) as exc_info:
            UploadService._validate_upload_type(
                content=b"\x89PNG\r\n\x1a\n",
                filename="image.png",
                declared_mime_type="image/png",
            )

        assert exc_info.value.status_code == 415
        assert exc_info.value.detail["code"] == "UNSUPPORTED_MEDIA_TYPE"
