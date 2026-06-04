"use client";

import { useState, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { studiesApi } from "@/lib/api/studies";
import type { Study } from "@/types";

const STORAGE_KEY = "celerius-intelligence-study-id";

interface UseIntelligenceStudy {
  studyId: string | null;
  setStudyId: (id: string) => void;
  studies: Study[];
  isLoading: boolean;
  selectedStudy: Study | null;
}

export function useIntelligenceStudy(): UseIntelligenceStudy {
  const { token } = useAuthStore();

  const [studyId, setStudyIdState] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem(STORAGE_KEY);
    }
    return null;
  });

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
      const id = studies[0].id;
      setStudyIdState(id);
      localStorage.setItem(STORAGE_KEY, id);
    }
  }, [studyId, studies]);

  // If stored study no longer exists in this org, clear it
  useEffect(() => {
    if (studyId && studies.length > 0 && !studies.find((s) => s.id === studyId)) {
      const id = studies[0]?.id ?? null;
      setStudyIdState(id);
      if (id) localStorage.setItem(STORAGE_KEY, id);
      else localStorage.removeItem(STORAGE_KEY);
    }
  }, [studyId, studies]);

  function setStudyId(id: string) {
    setStudyIdState(id);
    localStorage.setItem(STORAGE_KEY, id);
  }

  const selectedStudy = studies.find((s) => s.id === studyId) ?? null;

  return { studyId, setStudyId, studies, isLoading, selectedStudy };
}
