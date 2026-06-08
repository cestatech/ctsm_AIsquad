"""Unit tests for notification email template rendering."""

from __future__ import annotations

from app.services.notification_service import NotificationService


def _service() -> NotificationService:
    return NotificationService(db=None)  # type: ignore[arg-type]


class TestNotificationEmailTemplates:
    def test_renders_user_invite_template(self):
        html = _service()._render_template(
            "user_invite.html",
            {
                "subject": "You have been invited",
                "org_name": "Example Pharma",
                "recipient_name": "Taylor",
                "inviter_name": "Morgan",
                "temporary_password": "TempPass123!",
                "app_url": "https://app.example.test",
            },
        )

        assert "You have been invited to Example Pharma" in html
        assert "Taylor" in html
        assert "Morgan" in html
        assert "TempPass123!" in html
        assert "https://app.example.test/login" in html

    def test_renders_artifact_review_request_template(self):
        html = _service()._render_template(
            "artifact_review_request.html",
            {
                "subject": "Artifact ready for review",
                "org_name": "Example Pharma",
                "recipient_name": "Reviewer",
                "submitted_by": "Casey",
                "artifact_title": "Protocol v2",
                "study_name": "Study Alpha",
                "artifact_id": "artifact-123",
                "app_url": "https://app.example.test",
            },
        )

        assert "Artifact ready for review" in html
        assert "Protocol v2" in html
        assert "Casey" in html
        assert "Study Alpha" in html
        assert "https://app.example.test/artifacts/artifact-123" in html

    def test_renders_artifact_approved_template(self):
        html = _service()._render_template(
            "artifact_approved.html",
            {
                "subject": "Artifact approved",
                "org_name": "Example Pharma",
                "recipient_name": "Author",
                "approved_by": "Reviewer",
                "artifact_title": "CSR Draft",
                "study_name": "Study Beta",
                "artifact_id": "artifact-456",
                "app_url": "https://app.example.test",
            },
        )

        assert "Artifact approved" in html
        assert "CSR Draft" in html
        assert "Reviewer" in html
        assert "Study Beta" in html
        assert "https://app.example.test/artifacts/artifact-456" in html

    def test_renders_artifact_rejected_template(self):
        html = _service()._render_template(
            "artifact_rejected.html",
            {
                "subject": "Artifact rejected",
                "org_name": "Example Pharma",
                "recipient_name": "Author",
                "rejected_by": "Reviewer",
                "artifact_title": "SAP Draft",
                "rejection_notes": "Please update the endpoint definition.",
                "artifact_id": "artifact-789",
                "app_url": "https://app.example.test",
            },
        )

        assert "Artifact rejected" in html
        assert "SAP Draft" in html
        assert "Reviewer notes" in html
        assert "Please update the endpoint definition." in html
        assert "https://app.example.test/artifacts/artifact-789" in html

    def test_renders_password_reset_template(self):
        html = _service()._render_template(
            "password_reset.html",
            {
                "subject": "Reset your password",
                "org_name": "Example Pharma",
                "recipient_name": "Taylor",
                "reset_token": "reset-token-123",
                "app_url": "https://app.example.test",
            },
        )

        assert "Reset your password" in html
        assert "Taylor" in html
        assert "https://app.example.test/reset-password?token=reset-token-123" in html
        assert "This message was sent by Example Pharma" in html
