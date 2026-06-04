"""Integration tests for GET /api/v1/audit.

RBAC: Admin and Reviewer can read audit logs. Contributor cannot.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio(loop_scope="session")
class TestAuditList:
    async def test_unauthenticated_returns_401(self, iclient: AsyncClient):
        resp = await iclient.get("/api/v1/audit")
        assert resp.status_code == 401

    async def test_admin_can_list_audit_logs(
        self, iclient: AsyncClient, admin_tok: str
    ):
        resp = await iclient.get(
            "/api/v1/audit", headers={"Authorization": f"Bearer {admin_tok}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    async def test_contributor_cannot_read_audit(
        self, iclient: AsyncClient, contributor_tok: str
    ):
        """Contributor lacks AUDIT_READ permission — must get 403."""
        resp = await iclient.get(
            "/api/v1/audit", headers={"Authorization": f"Bearer {contributor_tok}"}
        )
        assert resp.status_code == 403

    async def test_pagination_params_accepted(
        self, iclient: AsyncClient, admin_tok: str
    ):
        resp = await iclient.get(
            "/api/v1/audit",
            params={"page": 1, "page_size": 5},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 5
