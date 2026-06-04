"""Integration tests for /api/v1/auth endpoints.

Register, login, refresh, logout, and /me flows are tested against a real
database via the shared test engine (session-scoped fixtures).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


def _unique_slug() -> str:
    return f"auth-test-{uuid4().hex[:8]}"


def _unique_email() -> str:
    return f"auth-{uuid4().hex[:8]}@example.com"


# ---------------------------------------------------------------------------
# POST /register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
class TestRegister:
    async def test_register_returns_201_with_access_token(self, iclient: AsyncClient):
        resp = await iclient.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Auth Test Org",
                "organization_slug": _unique_slug(),
                "full_name": "Alice Admin",
                "email": _unique_email(),
                "password": "SecurePass1!",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["is_system_admin"] is True

    async def test_register_sets_refresh_cookie(self, iclient: AsyncClient):
        resp = await iclient.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Cookie Test Org",
                "organization_slug": _unique_slug(),
                "full_name": "Bob Admin",
                "email": _unique_email(),
                "password": "SecurePass1!",
            },
        )
        assert resp.status_code == 201
        assert "refresh_token" in resp.cookies

    async def test_duplicate_slug_returns_401(self, iclient: AsyncClient):
        slug = _unique_slug()
        payload = {
            "organization_name": "Dup Org",
            "organization_slug": slug,
            "full_name": "Charlie",
            "email": _unique_email(),
            "password": "SecurePass1!",
        }
        first = await iclient.post("/api/v1/auth/register", json=payload)
        assert first.status_code == 201

        payload["email"] = _unique_email()
        second = await iclient.post("/api/v1/auth/register", json=payload)
        assert second.status_code == 401

    async def test_invalid_slug_format_returns_422(self, iclient: AsyncClient):
        resp = await iclient.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Bad Slug Org",
                "organization_slug": "UPPER_CASE",
                "full_name": "Dave",
                "email": _unique_email(),
                "password": "SecurePass1!",
            },
        )
        assert resp.status_code == 422

    async def test_short_password_returns_422(self, iclient: AsyncClient):
        resp = await iclient.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Short Pass Org",
                "organization_slug": _unique_slug(),
                "full_name": "Eve",
                "email": _unique_email(),
                "password": "short",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
class TestLogin:
    async def _register_user(self, iclient: AsyncClient) -> dict:
        email = _unique_email()
        password = "SecurePass1!"
        resp = await iclient.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Login Test Org",
                "organization_slug": _unique_slug(),
                "full_name": "Login User",
                "email": email,
                "password": password,
            },
        )
        assert resp.status_code == 201
        return {"email": email, "password": password}

    async def test_valid_credentials_returns_200_with_token(self, iclient: AsyncClient):
        creds = await self._register_user(iclient)
        resp = await iclient.post("/api/v1/auth/login", json=creds)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "user" in data

    async def test_login_sets_refresh_cookie(self, iclient: AsyncClient):
        creds = await self._register_user(iclient)
        resp = await iclient.post("/api/v1/auth/login", json=creds)
        assert resp.status_code == 200
        assert "refresh_token" in resp.cookies

    async def test_wrong_password_returns_401(self, iclient: AsyncClient):
        creds = await self._register_user(iclient)
        resp = await iclient.post(
            "/api/v1/auth/login",
            json={"email": creds["email"], "password": "WrongPass999!"},
        )
        assert resp.status_code == 401

    async def test_unknown_email_returns_401(self, iclient: AsyncClient):
        resp = await iclient.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "whatever"},
        )
        assert resp.status_code == 401

    async def test_missing_password_returns_422(self, iclient: AsyncClient):
        resp = await iclient.post(
            "/api/v1/auth/login",
            json={"email": "someone@test.com"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
class TestRefresh:
    async def _get_refresh_cookie(self, iclient: AsyncClient) -> str:
        resp = await iclient.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Refresh Test Org",
                "organization_slug": _unique_slug(),
                "full_name": "Refresh User",
                "email": _unique_email(),
                "password": "SecurePass1!",
            },
        )
        assert resp.status_code == 201
        return resp.cookies["refresh_token"]

    async def test_valid_cookie_returns_200_new_access_token(self, iclient: AsyncClient):
        cookie = await self._get_refresh_cookie(iclient)
        resp = await iclient.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": cookie},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_refresh_rotates_cookie(self, iclient: AsyncClient):
        cookie = await self._get_refresh_cookie(iclient)
        resp = await iclient.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": cookie},
        )
        assert resp.status_code == 200
        assert "refresh_token" in resp.cookies
        assert resp.cookies["refresh_token"] != cookie

    async def test_invalid_cookie_returns_401(self, iclient: AsyncClient):
        # Send a garbage token that won't match any DB record.
        # (session-scoped iclient may carry a real cookie, so we override it.)
        resp = await iclient.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": "this-is-not-a-valid-refresh-token-value"},
        )
        assert resp.status_code == 401

    async def test_used_token_cannot_be_reused(self, iclient: AsyncClient):
        cookie = await self._get_refresh_cookie(iclient)
        first = await iclient.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": cookie},
        )
        assert first.status_code == 200

        second = await iclient.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": cookie},
        )
        assert second.status_code == 401


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
class TestLogout:
    async def _register_and_get_token(self, iclient: AsyncClient) -> str:
        resp = await iclient.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Logout Test Org",
                "organization_slug": _unique_slug(),
                "full_name": "Logout User",
                "email": _unique_email(),
                "password": "SecurePass1!",
            },
        )
        assert resp.status_code == 201
        return resp.json()["access_token"]

    async def test_logout_returns_204(self, iclient: AsyncClient):
        token = await self._register_and_get_token(iclient)
        resp = await iclient.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

    async def test_unauthenticated_logout_returns_403(self, iclient: AsyncClient):
        resp = await iclient.post("/api/v1/auth/logout")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
class TestGetMe:
    async def _register_and_get_token(self, iclient: AsyncClient) -> tuple[str, str]:
        email = _unique_email()
        resp = await iclient.post(
            "/api/v1/auth/register",
            json={
                "organization_name": "Me Test Org",
                "organization_slug": _unique_slug(),
                "full_name": "Me User",
                "email": email,
                "password": "SecurePass1!",
            },
        )
        assert resp.status_code == 201
        return resp.json()["access_token"], email

    async def test_returns_authenticated_user_data(self, iclient: AsyncClient):
        token, email = await self._register_and_get_token(iclient)
        resp = await iclient.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == email

    async def test_unauthenticated_returns_403(self, iclient: AsyncClient):
        resp = await iclient.get("/api/v1/auth/me")
        assert resp.status_code == 403

    async def test_invalid_token_returns_401(self, iclient: AsyncClient):
        resp = await iclient.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert resp.status_code == 401
