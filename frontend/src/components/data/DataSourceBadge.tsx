interface DataSourceInfo {
  data_source_type?: string | null;
  data_cut_label?: string | null;
  is_synthetic?: boolean;
}

const BADGE_STYLES: Record<string, string> = {
  SYNTHETIC: "bg-amber-100 text-amber-800 border-amber-200",
  LIVE_INTERIM: "bg-sky-100 text-sky-800 border-sky-200",
  LIVE_FINAL: "bg-emerald-100 text-emerald-800 border-emerald-200",
};

const LABELS: Record<string, string> = {
  SYNTHETIC: "Synthetic",
  LIVE_INTERIM: "Live Interim",
  LIVE_FINAL: "Live Final",
};

export function DataSourceBadge({ source }: { source?: DataSourceInfo | null }) {
  if (!source?.data_source_type) return null;
  const type = source.data_source_type;
  const style = BADGE_STYLES[type] ?? "bg-slate-100 text-slate-700 border-slate-200";
  const label = LABELS[type] ?? type;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className={`text-[10px] px-2 py-0.5 font-semibold border ${style}`}>
        {label}
      </span>
      {source.data_cut_label && (
        <span className="text-[10px] text-slate-500">{source.data_cut_label}</span>
      )}
      {source.is_synthetic && type !== "SYNTHETIC" && (
        <span className="text-[10px] text-amber-700 font-medium">SYNTHETIC</span>
      )}
    </div>
  );
}

export function dataSourceFromContent(
  content?: Record<string, unknown> | null
): DataSourceInfo | null {
  if (!content) return null;
  const ds = (content.data_source ?? content.data_cut) as DataSourceInfo | undefined;
  return ds ?? null;
}
