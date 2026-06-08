"use client";

import { useIntelligenceStudy } from "@/hooks/useIntelligenceStudy";
import { useStudyPermissions } from "@/hooks/useStudyPermissions";

/** Permissions scoped to the study selected in intelligence screens. */
export function useIntelligencePermissions() {
  const { studyId } = useIntelligenceStudy();
  return useStudyPermissions(studyId ?? undefined);
}
