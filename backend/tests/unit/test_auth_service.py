"""Unit tests for AuthService.

All dependencies (repos, audit) are mocked — no real DB required.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import AuthenticationError, RateLimitError
from app.schemas.auth import RegisterRequest
from app.services.auth_service import AuthService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def svc(mock_db):
    s = AuthService(mock_db)
    s._users = AsyncMock()
    s._orgs = AsyncMock()
    s._audit = AsyncMock()
    return s


def _make_user(*, is_active=True, locked_until=None, failed_login_count=0):
    u = MagicMock()
    u.id = uuid4()
    u.organization_id = uuid4()
    u.email = f"user-{uuid4().hex[:6]}@test.com"
    u.hashed_password = "hashed"
    u.is_active = is_active
    u.locked_until = locked_until
    u.failed_login_count = failed_login_count
    u.to_audit_dict = MagicMock(return_value={})
    return u


def _make_refresh_token(*, expired=False, revoked=False):
    t = MagicMock()
    t.user_id = uuid4()
    t.expires_at = (
        datetime.now(UTC) - timedelta(hours=1)
        if expired
        else datetime.now(UTC) + timedelta(days=7)
    )
    t.is_revoked = revoked
    return t


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRegister:
    async def test_slug_already_taken_raises_auth_error(self, svc):
        svc._orgs.get_by_slug = AsyncMock(return_value=MagicMock())

        req = RegisterRequest(
            organization_name="Acme",
            organization_slug="acme",
            full_name="Alice",
            email="alice@acme.com",
            password="SecurePass1",
        )
        with pytest.raises(AuthenticationError, match="slug"):
            await svc.register(req)

    async def test_successful_register_returns_user_and_tokens(self, svc):
        svc._orgs.get_by_slug = AsyncMock(return_value=None)
        org = MagicMock()
        org.id = uuid4()
        svc._orgs.create = AsyncMock(return_value=org)
        user = _make_user()
        user.organization_id = org.id
        svc._users.create = AsyncMock(return_value=user)
        svc._users.create_refresh_token = AsyncMock()

        req = RegisterRequest(
            organization_name="Acme",
            organization_slug="acme",
            full_name="Alice",
            email="alice@acme.com",
            password="SecurePass1",
        )
        with patch("app.services.auth_service.create_access_token", return_value="acc"):
            with patch(
                "app.services.auth_service.create_refresh_token_value",
                return_value="ref",
            ):
                result_user, access, refresh = await svc.register(req)

        assert result_user is user
        assert access == "acc"
        assert refresh == "ref"
        svc._audit.log.assert_called_once()

    async def test_audit_logged_on_register(self, svc):
        svc._orgs.get_by_slug = AsyncMock(return_value=None)
        org = MagicMock()
        org.id = uuid4()
        svc._orgs.create = AsyncMock(return_value=org)
        user = _make_user()
        user.organization_id = org.id
        svc._users.create = AsyncMock(return_value=user)
        svc._users.create_refresh_token = AsyncMock()

        req = RegisterRequest(
            organization_name="Acme",
            organization_slug="acme-2",
            full_name="Bob",
            email="bob@acme.com",
            password="SecurePass1",
        )
        with patch("app.services.auth_service.create_access_token", return_value="x"):
            with patch(
                "app.services.auth_service.create_refresh_token_value", return_value="y"
            ):
                await svc.register(req)

        svc._audit.log.assert_called_once()
        call_kwargs = svc._audit.log.call_args.kwargs
        assert call_kwargs["action"].value == "user.created"


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLogin:
    async def test_unknown_email_raises_auth_error(self, svc):
        svc._users.get_by_email_any_org = AsyncMock(return_value=None)

        with pytest.raises(AuthenticationError):
            await svc.login("nobody@test.com", "pass")

    async def test_locked_account_raises_rate_limit_error(self, svc):
        user = _make_user(locked_until=datetime.now(UTC) + timedelta(minutes=5))
        svc._users.get_by_email_any_org = AsyncMock(return_value=user)

        with pytest.raises(RateLimitError):
            await svc.login(user.email, "wrong")

    async def test_wrong_password_raises_auth_error(self, svc, mock_db):
        user = _make_user()
        svc._users.get_by_email_any_org = AsyncMock(return_value=user)
        svc._users.increment_failed_login = AsyncMock()

        with patch("app.services.auth_service.verify_password", return_value=False):
            with pytest.raises(AuthenticationError):
                await svc.login(user.email, "wrong")

        svc._users.increment_failed_login.assert_called_once_with(user)
        svc._audit.log.assert_called_once()

    async def test_wrong_password_audit_action_is_login_failed(self, svc, mock_db):
        user = _make_user()
        svc._users.get_by_email_any_org = AsyncMock(return_value=user)
        svc._users.increment_failed_login = AsyncMock()

        with patch("app.services.auth_service.verify_password", return_value=False):
            with pytest.raises(AuthenticationError):
                await svc.login(user.email, "wrong")

        call_kwargs = svc._audit.log.call_args.kwargs
        assert call_kwargs["action"].value == "user.login_failed"

    async def test_deactivated_user_raises_auth_error(self, svc):
        user = _make_user(is_active=False)
        svc._users.get_by_email_any_org = AsyncMock(return_value=user)
        svc._users.increment_failed_login = AsyncMock()

        with patch("app.services.auth_service.verify_password", return_value=True):
            with pytest.raises(AuthenticationError, match="deactivated"):
                await svc.login(user.email, "pass")

    async def test_successful_login_returns_tokens(self, svc):
        user = _make_user()
        svc._users.get_by_email_any_org = AsyncMock(return_value=user)
        svc._users.reset_failed_login = AsyncMock()
        svc._users.update_last_login = AsyncMock()
        svc._users.create_refresh_token = AsyncMock()

        with patch("app.services.auth_service.verify_password", return_value=True):
            with patch(
                "app.services.auth_service.create_access_token", return_value="acc"
            ):
                with patch(
                    "app.services.auth_service.create_refresh_token_value",
                    return_value="ref",
                ):
                    result_user, access, refresh = await svc.login(user.email, "pass")

        assert result_user is user
        assert access == "acc"
        assert refresh == "ref"

    async def test_successful_login_resets_failed_count(self, svc):
        user = _make_user()
        svc._users.get_by_email_any_org = AsyncMock(return_value=user)
        svc._users.reset_failed_login = AsyncMock()
        svc._users.update_last_login = AsyncMock()
        svc._users.create_refresh_token = AsyncMock()

        with patch("app.services.auth_service.verify_password", return_value=True):
            with patch(
                "app.services.auth_service.create_access_token", return_value="a"
            ):
                with patch(
                    "app.services.auth_service.create_refresh_token_value",
                    return_value="r",
                ):
                    await svc.login(user.email, "pass")

        svc._users.reset_failed_login.assert_called_once_with(user)

    async def test_successful_login_writes_audit(self, svc):
        user = _make_user()
        svc._users.get_by_email_any_org = AsyncMock(return_value=user)
        svc._users.reset_failed_login = AsyncMock()
        svc._users.update_last_login = AsyncMock()
        svc._users.create_refresh_token = AsyncMock()

        with patch("app.services.auth_service.verify_password", return_value=True):
            with patch(
                "app.services.auth_service.create_access_token", return_value="a"
            ):
                with patch(
                    "app.services.auth_service.create_refresh_token_value",
                    return_value="r",
                ):
                    await svc.login(user.email, "pass")

        call_kwargs = svc._audit.log.call_args.kwargs
        assert call_kwargs["action"].value == "user.login"


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRefresh:
    async def test_missing_token_raises_auth_error(self, svc):
        svc._users.get_refresh_token = AsyncMock(return_value=None)

        with pytest.raises(AuthenticationError):
            await svc.refresh("invalid-value")

    async def test_expired_token_raises_auth_error(self, svc):
        token = _make_refresh_token(expired=True)
        svc._users.get_refresh_token = AsyncMock(return_value=token)

        with pytest.raises(AuthenticationError):
            await svc.refresh("some-value")

    async def test_valid_token_rotates_and_returns_new_tokens(self, svc):
        token = _make_refresh_token()
        user = _make_user()
        user.id = token.user_id
        svc._users.get_refresh_token = AsyncMock(return_value=token)
        svc._users.revoke_refresh_token = AsyncMock()
        svc._users.get_by_id = AsyncMock(return_value=user)
        svc._users.create_refresh_token = AsyncMock()

        with patch(
            "app.services.auth_service.create_access_token", return_value="new_acc"
        ):
            with patch(
                "app.services.auth_service.create_refresh_token_value",
                return_value="new_ref",
            ):
                new_access, new_refresh = await svc.refresh("old-value")

        assert new_access == "new_acc"
        assert new_refresh == "new_ref"
        svc._users.revoke_refresh_token.assert_called_once_with(token)

    async def test_refresh_writes_audit(self, svc):
        token = _make_refresh_token()
        user = _make_user()
        user.id = token.user_id
        svc._users.get_refresh_token = AsyncMock(return_value=token)
        svc._users.revoke_refresh_token = AsyncMock()
        svc._users.get_by_id = AsyncMock(return_value=user)
        svc._users.create_refresh_token = AsyncMock()

        with patch("app.services.auth_service.create_access_token", return_value="a"):
            with patch(
                "app.services.auth_service.create_refresh_token_value", return_value="r"
            ):
                await svc.refresh("old")

        call_kwargs = svc._audit.log.call_args.kwargs
        assert call_kwargs["action"].value == "user.token_refreshed"

    async def test_inactive_user_after_valid_token_raises_auth_error(self, svc):
        token = _make_refresh_token()
        user = _make_user(is_active=False)
        user.id = token.user_id
        svc._users.get_refresh_token = AsyncMock(return_value=token)
        svc._users.revoke_refresh_token = AsyncMock()
        svc._users.get_by_id = AsyncMock(return_value=user)

        with pytest.raises(AuthenticationError, match="deactivated"):
            await svc.refresh("some-value")


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLogout:
    async def test_valid_token_is_revoked(self, svc):
        token = _make_refresh_token()
        svc._users.get_refresh_token = AsyncMock(return_value=token)
        svc._users.revoke_refresh_token = AsyncMock()

        await svc.logout("some-value")

        svc._users.revoke_refresh_token.assert_called_once_with(token)

    async def test_unknown_token_is_silently_ignored(self, svc):
        svc._users.get_refresh_token = AsyncMock(return_value=None)
        svc._users.revoke_refresh_token = AsyncMock()

        await svc.logout("nonexistent")

        svc._users.revoke_refresh_token.assert_not_called()
