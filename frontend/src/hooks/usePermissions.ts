"use client";

import type { Role } from "@/types";

interface Permissions {
  canCreateArtifact: boolean;
  canEditArtifact: boolean;
  canSubmitArtifact: boolean;
  canApproveArtifact: boolean;
  canRejectArtifact: boolean;
  canLockArtifact: boolean;
  canAmendArtifact: boolean;
  canManageUsers: boolean;
  canManageStudyMembers: boolean;
  canViewAuditLog: boolean;
  canRunValidation: boolean;
  canTriggerGeneration: boolean;
  canDeleteDraftArtifact: boolean;
  isAdmin: boolean;
  isContributor: boolean;
  isReviewer: boolean;
}

const PERMISSION_MAP: Record<Role, Permissions> = {
  ADMIN: {
    canCreateArtifact: true,
    canEditArtifact: true,
    canSubmitArtifact: true,
    canApproveArtifact: true,
    canRejectArtifact: true,
    canLockArtifact: true,
    canAmendArtifact: true,
    canManageUsers: true,
    canManageStudyMembers: true,
    canViewAuditLog: true,
    canRunValidation: true,
    canTriggerGeneration: true,
    canDeleteDraftArtifact: true,
    isAdmin: true,
    isContributor: false,
    isReviewer: false,
  },
  CONTRIBUTOR: {
    canCreateArtifact: true,
    canEditArtifact: true,
    canSubmitArtifact: true,
    canApproveArtifact: false,
    canRejectArtifact: false,
    canLockArtifact: false,
    canAmendArtifact: false,
    canManageUsers: false,
    canManageStudyMembers: false,
    canViewAuditLog: false,
    canRunValidation: true,
    canTriggerGeneration: true,
    canDeleteDraftArtifact: true,
    isAdmin: false,
    isContributor: true,
    isReviewer: false,
  },
  REVIEWER: {
    canCreateArtifact: false,
    canEditArtifact: false,
    canSubmitArtifact: false,
    canApproveArtifact: true,
    canRejectArtifact: true,
    canLockArtifact: false,
    canAmendArtifact: false,
    canManageUsers: false,
    canManageStudyMembers: false,
    canViewAuditLog: true,
    canRunValidation: true,
    canTriggerGeneration: false,
    canDeleteDraftArtifact: false,
    isAdmin: false,
    isContributor: false,
    isReviewer: true,
  },
};

/** Whether the current user may remove a DRAFT artifact from the study. */
export function canRemoveArtifact(
  artifact: { status: string; created_by_id: string },
  userId: string | undefined,
  perms: Permissions
): boolean {
  if (!perms.canDeleteDraftArtifact || artifact.status !== "DRAFT") {
    return false;
  }
  if (perms.isAdmin) {
    return true;
  }
  return !!userId && artifact.created_by_id === userId;
}

/**
 * Returns permission flags for the current user's role.
 * Use the study-level role when operating within a study context.
 *
 * Usage:
 *   const { canApproveArtifact } = usePermissions(studyRole ?? userRole);
 */
export function usePermissions(role: Role): Permissions {
  return PERMISSION_MAP[role];
}
