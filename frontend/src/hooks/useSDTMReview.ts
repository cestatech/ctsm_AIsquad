"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { sdtmApi } from "@/lib/api/sdtm";
import type { ApprovalDecision, Artifact } from "@/types";

export function useSDTMReview(studyId: string, artifactId: string) {
  const { token } = useAuthStore();
  const queryClient = useQueryClient();

  const reviewKey = ["sdtm-review", studyId, artifactId, token];

  const reviewQuery = useQuery({
    queryKey: reviewKey,
    queryFn: () => sdtmApi.loadReviewBundle(studyId, artifactId, token!),
    enabled: Boolean(token && studyId && artifactId),
    staleTime: 30_000,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: reviewKey });
    queryClient.invalidateQueries({ queryKey: ["artifacts", studyId] });
    queryClient.invalidateQueries({ queryKey: ["artifact", artifactId] });
    queryClient.invalidateQueries({ queryKey: ["approvals-queue"] });
  };

  const submitMutation = useMutation({
    mutationFn: () => sdtmApi.submitForReview(artifactId, token!),
    onSuccess: invalidate,
  });

  const approvalMutation = useMutation({
    mutationFn: ({
      decision,
      comments,
      versionId,
    }: {
      decision: ApprovalDecision;
      comments?: string;
      versionId: string;
    }) =>
      sdtmApi.recordApprovalDecision(
        artifactId,
        versionId,
        decision,
        token!,
        comments
      ),
    onSuccess: invalidate,
  });

  const defineXmlMutation = useMutation({
    mutationFn: () => sdtmApi.downloadDefineXml(artifactId, token!),
    onSuccess: ({ blob, filename }) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
    },
  });

  return {
    artifact: reviewQuery.data?.artifact,
    content: reviewQuery.data?.content,
    validationEvidence: reviewQuery.data?.validationEvidence ?? [],
    isLoading: reviewQuery.isLoading,
    isError: reviewQuery.isError,
    error: reviewQuery.error,
    refetch: reviewQuery.refetch,
    submitForReview: submitMutation.mutateAsync,
    isSubmitting: submitMutation.isPending,
    recordApproval: approvalMutation.mutateAsync,
    isRecordingApproval: approvalMutation.isPending,
    downloadDefineXml: defineXmlMutation.mutateAsync,
    isDownloadingDefineXml: defineXmlMutation.isPending,
  };
}

export function useSDTMArtifactGuard(
  artifact: Artifact | undefined,
  isLoading: boolean
): { ready: boolean; message: string | null } {
  if (isLoading) {
    return { ready: false, message: null };
  }
  if (!artifact) {
    return { ready: false, message: "Artifact not found." };
  }
  if (artifact.artifact_type !== "SDTM_DATASET") {
    return {
      ready: false,
      message: "This review page is only available for SDTM dataset artifacts.",
    };
  }
  return { ready: true, message: null };
}
