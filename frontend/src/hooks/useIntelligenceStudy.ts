"use client";

import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { useIntelligenceStudyStore } from "@/store/intelligenceStudyStore";
import { studiesApi } from "@/lib/api/studies";
import type { Study } from "@/types";

interface UseIntelligenceStudy {
  studyId: string | null;
  setStudyId: (id: string) => void;
  studies: Study[];
  isLoading: boolean;
  selectedStudy: Study | null;
}

export function useIntelligenceStudy(): UseIntelligenceStudy {
  const { token } = useAuthStore();
  const studyId = useIntelligenceStudyStore((s) => s.studyId);
  const setStudyId = useIntelligenceStudyStore((s) => s.setStudyId);

  const { data, isLoading } = useQuery({
    queryKey: ["studies-for-intelligence", token],
    queryFn: () => studiesApi.list({ page_size: 100 }, token!),
    enabled: !!token,
    staleTime: 60_000,
  });

  const studies = useMemo(() => data?.items ?? [], [data]);

  // Auto-select first study if nothing is stored yet
  useEffect(() => {
    if (!studyId && studies.length > 0) {
      setStudyId(studies[0].id);
    }
  }, [studyId, studies, setStudyId]);

  // If stored study no longer exists in this org, select the first available
  useEffect(() => {
    if (studyId && studies.length > 0 && !studies.find((s) => s.id === studyId)) {
      const next = studies[0]?.id;
      if (next) setStudyId(next);
    }
  }, [studyId, studies, setStudyId]);

  const selectedStudy = studies.find((s) => s.id === studyId) ?? null;

  return { studyId, setStudyId, studies, isLoading, selectedStudy };
}
