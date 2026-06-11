import type { SubmissionFileGrade, SubmissionPackageStatus } from "@/types";

export interface SubmissionPackageLike {
  status: SubmissionPackageStatus;
  error_message: string | null;
}

export type PackageDisplayState = "idle" | "packaging" | "ready" | "failed";

const PLACEHOLDER_PATH_PATTERNS = [
  /^m5\/reviewers-guide\.pdf$/,
  /^csr\/.+\.pdf$/,
];

/** Whether the client should poll package status until terminal. */
export function shouldPollPackage(pkg: SubmissionPackageLike): boolean {
  if (pkg.error_message) {
    return false;
  }
  return pkg.status === "PACKAGING" || pkg.status === "DRAFT";
}

/** Map backend package record to a UI display state. */
export function derivePackageDisplayState(
  pkg: SubmissionPackageLike | null | undefined
): PackageDisplayState {
  if (!pkg) {
    return "idle";
  }
  if (pkg.error_message) {
    return "failed";
  }
  if (pkg.status === "READY") {
    return "ready";
  }
  if (pkg.status === "PACKAGING" || pkg.status === "DRAFT") {
    return "packaging";
  }
  return "idle";
}

/** Resolve per-file grade from API value or legacy path heuristics. */
export function deriveFileGrade(file: {
  path: string;
  grade?: SubmissionFileGrade;
}): SubmissionFileGrade {
  if (file.grade === "generated" || file.grade === "placeholder") {
    return file.grade;
  }
  if (PLACEHOLDER_PATH_PATTERNS.some((pattern) => pattern.test(file.path))) {
    return "placeholder";
  }
  return "generated";
}
