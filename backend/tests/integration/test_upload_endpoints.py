"""Integration tests for /api/v1/studies/{id}/uploads endpoints."""

from __future__ import annotations


import pytest
from httpx import AsyncClient

from app.models.study import Study


@pytest.mark.asyncio(loop_scope="session")
class TestUploadFile:
    async def test_unauthenticated_returns_403(
        self, iclient: AsyncClient, i_study: Study
    ):
        resp = await iclient.post(
            f"/api/v1/studies/{i_study.id}/uploads",
            files={"file": ("test.csv", b"col1,col2\nval1,val2", "text/csv")},
        )
        assert resp.status_code == 403

    async def test_admin_can_upload_csv(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        csv_content = b"subject_id,age,treatment\nS001,45,A\nS002,52,B\n"
        resp = await iclient.post(
            f"/api/v1/studies/{i_study.id}/uploads",
            files={"file": ("subjects.csv", csv_content, "text/csv")},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["original_filename"] == "subjects.csv"
        assert data["mime_type"] == "text/csv"
        assert data["file_size_bytes"] == len(csv_content)
        assert data["study_id"] == str(i_study.id)
        assert data["extracted_metadata"]["columns"] == [
            "subject_id",
            "age",
            "treatment",
        ]
        assert data["extracted_metadata"]["row_count"] == 2

    async def test_contributor_can_upload(
        self, iclient: AsyncClient, i_study: Study, contributor_tok: str
    ):
        resp = await iclient.post(
            f"/api/v1/studies/{i_study.id}/uploads",
            files={"file": ("data.csv", b"a,b\n1,2", "text/csv")},
            headers={"Authorization": f"Bearer {contributor_tok}"},
        )
        assert resp.status_code == 201

    async def test_synthetic_filename_auto_labeled(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        csv_content = b"subject_id,age\nS001,45\n"
        resp = await iclient.post(
            f"/api/v1/studies/{i_study.id}/uploads",
            files={
                "file": (
                    "CLARITY-50_synthetic_demographics.csv",
                    csv_content,
                    "text/csv",
                )
            },
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["data_source_type"] == "SYNTHETIC"
        assert data["is_synthetic"] is True
        assert "Synthetic" in data["data_cut_label"]

    async def test_explicit_synthetic_upload(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        resp = await iclient.post(
            f"/api/v1/studies/{i_study.id}/uploads",
            files={"file": ("patients.csv", b"id\n1\n", "text/csv")},
            data={"data_source_type": "SYNTHETIC"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["data_source_type"] == "SYNTHETIC"
        assert data["is_synthetic"] is True

    async def test_unsupported_mime_type_returns_415(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        resp = await iclient.post(
            f"/api/v1/studies/{i_study.id}/uploads",
            files={"file": ("image.png", b"\x89PNG...", "image/png")},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 415


@pytest.mark.asyncio(loop_scope="session")
class TestListUploads:
    async def test_unauthenticated_returns_403(
        self, iclient: AsyncClient, i_study: Study
    ):
        resp = await iclient.get(f"/api/v1/studies/{i_study.id}/uploads")
        assert resp.status_code == 403

    async def test_returns_paginated_list(
        self, iclient: AsyncClient, i_study: Study, admin_tok: str
    ):
        resp = await iclient.get(
            f"/api/v1/studies/{i_study.id}/uploads",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 0
