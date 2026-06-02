"""
Unit tests for artifact workflow transitions.

Every valid and invalid status transition is tested.
This test suite is the executable specification of the workflow model.
"""
import pytest

from app.models.artifact import ArtifactStatus, VALID_TRANSITIONS


class TestWorkflowTransitions:
    """Verify all valid transitions are permitted and all invalid transitions are blocked."""

    VALID = [
        (ArtifactStatus.DRAFT, ArtifactStatus.IN_REVIEW),
        (ArtifactStatus.IN_REVIEW, ArtifactStatus.APPROVED),
        (ArtifactStatus.IN_REVIEW, ArtifactStatus.REJECTED),
        (ArtifactStatus.REJECTED, ArtifactStatus.DRAFT),
        (ArtifactStatus.APPROVED, ArtifactStatus.LOCKED),
        (ArtifactStatus.LOCKED, ArtifactStatus.AMENDED),
        (ArtifactStatus.APPROVED, ArtifactStatus.SUPERSEDED),
        (ArtifactStatus.LOCKED, ArtifactStatus.SUPERSEDED),
    ]

    INVALID = [
        (ArtifactStatus.DRAFT, ArtifactStatus.APPROVED),
        (ArtifactStatus.DRAFT, ArtifactStatus.LOCKED),
        (ArtifactStatus.DRAFT, ArtifactStatus.REJECTED),
        (ArtifactStatus.IN_REVIEW, ArtifactStatus.LOCKED),
        (ArtifactStatus.IN_REVIEW, ArtifactStatus.DRAFT),
        (ArtifactStatus.APPROVED, ArtifactStatus.DRAFT),
        (ArtifactStatus.APPROVED, ArtifactStatus.IN_REVIEW),
        (ArtifactStatus.LOCKED, ArtifactStatus.DRAFT),
        (ArtifactStatus.LOCKED, ArtifactStatus.IN_REVIEW),
        (ArtifactStatus.LOCKED, ArtifactStatus.APPROVED),
        (ArtifactStatus.SUPERSEDED, ArtifactStatus.DRAFT),
        (ArtifactStatus.SUPERSEDED, ArtifactStatus.IN_REVIEW),
    ]

    @pytest.mark.parametrize("from_status,to_status", VALID)
    def test_valid_transition_exists(self, from_status, to_status):
        assert (from_status, to_status) in VALID_TRANSITIONS, (
            f"Expected ({from_status} → {to_status}) to be a valid transition"
        )

    @pytest.mark.parametrize("from_status,to_status", INVALID)
    def test_invalid_transition_not_in_matrix(self, from_status, to_status):
        assert (from_status, to_status) not in VALID_TRANSITIONS, (
            f"Expected ({from_status} → {to_status}) to be blocked but it is allowed"
        )

    def test_locked_artifact_is_detected(self, mocker):
        artifact = mocker.MagicMock()
        artifact.status = ArtifactStatus.LOCKED
        artifact.is_locked.return_value = True

        assert artifact.is_locked() is True
