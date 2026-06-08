"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { studiesApi } from "@/lib/api/studies";
import { usePermissions } from "@/hooks/usePermissions";
import type { Role } from "@/types";

/**
 * Resolve permissions using study-level role when available,
 * falling back to organization role from the JWT.
 */
export function useStudyPermissions(studyId: string | undefined) {
  const { token, role, user } = useAuthStore();

  const { data: members } = useQuery({
    queryKey: ["study-members", studyId, token],
    queryFn: () => studiesApi.getMembers(studyId!, token!),
    enabled: !!token && !!studyId,
    staleTime: 60_000,
  });

  const studyRole: Role | undefined = members?.find(
    (member) => member.user_id === user?.id
  )?.role;

  return usePermissions(studyRole ?? role);
}
