"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { tlfApi } from "@/lib/api/tlf";
import {
  ListingFigureCatalogSkeleton,
  ListingFigureCatalogViewer,
} from "@/components/tlf/ListingFigureCatalogViewer";

export default function TLFCatalogPage({
  params,
}: {
  params: { id: string; artifactId: string };
}) {
  const studyId = params.id;
  const artifactId = params.artifactId;
  const { token } = useAuthStore();

  const { data: catalog, isLoading, isError } = useQuery({
    queryKey: ["tlf-catalog", studyId, artifactId, token],
    queryFn: () => tlfApi.getCatalog(artifactId, token!),
    enabled: Boolean(token && artifactId),
    staleTime: 30_000,
  });

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-2 mb-2">
          <Link
            href={`/studies/${studyId}/artifacts`}
            className="text-slate-400 hover:text-slate-700 text-sm transition-colors"
          >
            ← Artifacts
          </Link>
          <Link
            href={`/studies/${studyId}/artifacts/${artifactId}`}
            className="text-slate-400 hover:text-slate-700 text-sm transition-colors"
          >
            / TLF detail
          </Link>
        </div>
        <h1 className="font-display text-xl font-bold text-slate-900">
          TLF Catalog
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          SAP traceability mapping for programmed tables, listings, and figures
        </p>
      </div>

      <div className="px-8 py-6">
        {isLoading ? (
          <ListingFigureCatalogSkeleton />
        ) : isError || !catalog ? (
          <div className="bg-white border border-slate-200 px-8 py-14 text-center">
            <p className="font-display font-semibold text-slate-900 mb-1">
              Unable to load catalog
            </p>
            <p className="text-slate-500 text-sm">
              Confirm this artifact is a TLF package and try again.
            </p>
          </div>
        ) : (
          <ListingFigureCatalogViewer
            studyId={studyId}
            artifactId={artifactId}
            catalog={catalog}
          />
        )}
      </div>
    </div>
  );
}
