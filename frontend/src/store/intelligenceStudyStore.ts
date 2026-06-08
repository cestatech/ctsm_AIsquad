"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface IntelligenceStudyState {
  studyId: string | null;
  setStudyId: (id: string) => void;
  clearStudyId: () => void;
}

export const useIntelligenceStudyStore = create<IntelligenceStudyState>()(
  persist(
    (set) => ({
      studyId: null,
      setStudyId: (id) => set({ studyId: id }),
      clearStudyId: () => set({ studyId: null }),
    }),
    {
      name: "celerius-intelligence-study-id",
      partialize: (state) => ({ studyId: state.studyId }),
    }
  )
);
