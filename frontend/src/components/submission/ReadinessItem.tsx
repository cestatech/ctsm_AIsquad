import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

export type ReadinessStatus = "complete" | "warning" | "missing";

export interface ReadinessItemModel {
  id: string;
  category: string;
  label: string;
  description: string;
  status: ReadinessStatus;
  resolution: string;
}

const STATUS_CONFIG: Record<
  ReadinessStatus,
  {
    icon: typeof CheckCircle2;
    label: string;
    className: string;
    iconClassName: string;
  }
> = {
  complete: {
    icon: CheckCircle2,
    label: "Complete",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
    iconClassName: "text-emerald-600",
  },
  warning: {
    icon: AlertTriangle,
    label: "Warning",
    className: "bg-amber-50 text-amber-700 border-amber-200",
    iconClassName: "text-amber-600",
  },
  missing: {
    icon: XCircle,
    label: "Missing",
    className: "bg-red-50 text-red-700 border-red-200",
    iconClassName: "text-red-600",
  },
};

export function ReadinessItem({ item }: { item: ReadinessItemModel }) {
  const config = STATUS_CONFIG[item.status];
  const StatusIcon = config.icon;

  return (
    <li className="bg-white border border-slate-200 px-4 py-4 sm:px-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex gap-3">
          <StatusIcon className={`mt-0.5 h-5 w-5 flex-shrink-0 ${config.iconClassName}`} />
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                {item.category}
              </span>
              <span className={`text-[11px] px-2 py-0.5 font-medium border ${config.className}`}>
                {config.label}
              </span>
            </div>
            <p className="mt-1 text-sm font-semibold text-slate-900">{item.label}</p>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">{item.description}</p>
          </div>
        </div>
        <p className="sm:max-w-xs text-xs leading-relaxed text-slate-500 sm:text-right">
          {item.resolution}
        </p>
      </div>
    </li>
  );
}
