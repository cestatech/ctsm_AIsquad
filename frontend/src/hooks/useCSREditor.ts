"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { csrApi, type CSRSection } from "@/lib/api/csr";
import type { Artifact } from "@/types";

const AUTOSAVE_DEBOUNCE_MS = 2000;

export function useCSREditor(studyId: string, artifactId: string) {
  const { token } = useAuthStore();
  const queryClient = useQueryClient();
  const editorKey = ["csr-editor", studyId, artifactId, token];

  const [activeSectionId, setActiveSectionId] = useState<string | null>(null);
  const [draftSections, setDraftSections] = useState<CSRSection[]>([]);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved">(
    "idle"
  );
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingContentRef = useRef<Record<string, unknown> | null>(null);

  const editorQuery = useQuery({
    queryKey: editorKey,
    queryFn: () => csrApi.loadEditorBundle(artifactId, token!),
    enabled: Boolean(token && studyId && artifactId),
    staleTime: 30_000,
  });

  useEffect(() => {
    const sections = editorQuery.data?.content.sections ?? [];
    if (sections.length === 0) return;
    setDraftSections(sections);
    setActiveSectionId((current) => current ?? sections[0]?.number ?? null);
  }, [editorQuery.data?.content.sections]);

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: editorKey });
    queryClient.invalidateQueries({ queryKey: ["artifact", artifactId] });
    queryClient.invalidateQueries({ queryKey: ["artifact-versions", artifactId] });
    queryClient.invalidateQueries({ queryKey: ["artifacts", studyId] });
  }, [artifactId, editorKey, queryClient, studyId]);

  const saveMutation = useMutation({
    mutationFn: (content: Record<string, unknown>) =>
      csrApi.saveContent(
        artifactId,
        content,
        token!,
        "CSR section editor autosave"
      ),
    onMutate: () => {
      setSaveStatus("saving");
      setSaveError(null);
    },
    onSuccess: () => {
      setSaveStatus("saved");
      invalidate();
      window.setTimeout(() => setSaveStatus("idle"), 2000);
    },
    onError: (error: Error) => {
      setSaveStatus("idle");
      setSaveError(error.message);
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: ({
      sectionId,
      instructions,
    }: {
      sectionId: string;
      instructions?: string;
    }) =>
      csrApi.regenerateSection(artifactId, sectionId, token!, { instructions }),
    onSuccess: (response) => {
      setDraftSections((current) =>
        current.map((section) =>
          section.number === response.section_id
            ? { ...section, prose: response.prose, ai_decision_id: response.ai_decision_id }
            : section
        )
      );
      invalidate();
    },
  });

  const flushPendingSave = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    const pending = pendingContentRef.current;
    if (!pending) return;
    pendingContentRef.current = null;
    saveMutation.mutate(pending);
  }, [saveMutation]);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, []);

  const scheduleSave = useCallback(
    (content: Record<string, unknown>) => {
      pendingContentRef.current = content;
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
      saveTimerRef.current = setTimeout(() => {
        saveTimerRef.current = null;
        const pending = pendingContentRef.current;
        if (!pending) return;
        pendingContentRef.current = null;
        saveMutation.mutate(pending);
      }, AUTOSAVE_DEBOUNCE_MS);
    },
    [saveMutation]
  );

  const updateSectionProse = useCallback(
    (sectionId: string, prose: string) => {
      setDraftSections((current) => {
        const nextSections = current.map((section) =>
          section.number === sectionId ? { ...section, prose } : section
        );
        const rawContent = editorQuery.data?.rawContent;
        if (rawContent) {
          scheduleSave({ ...rawContent, sections: nextSections });
        }
        return nextSections;
      });
    },
    [editorQuery.data?.rawContent, scheduleSave]
  );

  const handleSectionBlur = useCallback(() => {
    flushPendingSave();
  }, [flushPendingSave]);

  return {
    artifact: editorQuery.data?.artifact,
    content: editorQuery.data?.content,
    sections: draftSections,
    activeSectionId,
    setActiveSectionId,
    isLoading: editorQuery.isLoading,
    isError: editorQuery.isError,
    error: editorQuery.error,
    refetch: editorQuery.refetch,
    updateSectionProse,
    handleSectionBlur,
    regenerateSection: regenerateMutation.mutateAsync,
    isRegenerating: regenerateMutation.isPending,
    regeneratingSectionId: regenerateMutation.isPending
      ? regenerateMutation.variables?.sectionId ?? null
      : null,
    regenerateError: regenerateMutation.error,
    saveError,
    saveStatus,
    isSaving: saveMutation.isPending,
  };
}

export function useCSRArtifactGuard(
  artifact: Artifact | undefined,
  isLoading: boolean
): { ready: boolean; message: string | null } {
  if (isLoading) {
    return { ready: false, message: null };
  }
  if (!artifact) {
    return { ready: false, message: "Artifact not found." };
  }
  if (artifact.artifact_type !== "CSR") {
    return {
      ready: false,
      message: "This editor is only available for CSR artifacts.",
    };
  }
  return { ready: true, message: null };
}
