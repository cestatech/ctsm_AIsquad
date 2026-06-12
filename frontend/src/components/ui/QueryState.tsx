"use client";

import type { ReactNode } from "react";

interface QueryStateProps {
  isLoading?: boolean;
  isError?: boolean;
  error?: Error | null;
  isEmpty?: boolean;
  loadingMessage?: string;
  emptyMessage?: string;
  children: ReactNode;
}

/** Standard loading, error, and empty states for TanStack Query pages. */
export function QueryState({
  isLoading = false,
  isError = false,
  error = null,
  isEmpty = false,
  loadingMessage = "Loading…",
  emptyMessage = "No results found.",
  children,
}: QueryStateProps) {
  if (isLoading) {
    return (
      <div className="px-8 py-14 text-center text-sm text-slate-500">
        {loadingMessage}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="mx-8 my-6 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {error?.message ?? "Something went wrong. Please try again."}
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div className="px-8 py-14 text-center text-sm text-slate-500">
        {emptyMessage}
      </div>
    );
  }

  return <>{children}</>;
}
