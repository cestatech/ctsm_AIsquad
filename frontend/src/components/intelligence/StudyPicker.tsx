"use client";

import { useIntelligenceStudy } from "@/hooks/useIntelligenceStudy";

interface StudyPickerProps {
  className?: string;
}

export function StudyPicker({ className }: StudyPickerProps) {
  const { studyId, setStudyId, studies, isLoading } = useIntelligenceStudy();

  if (isLoading) {
    return <span className="text-xs text-slate-400">Loading studies…</span>;
  }

  if (studies.length === 0) {
    return (
      <span className="text-xs text-slate-400 italic">No studies available</span>
    );
  }

  return (
    <div className={`flex items-center gap-2 ${className ?? ""}`}>
      <span className="text-xs font-medium text-slate-500 shrink-0">Study:</span>
      <select
        value={studyId ?? ""}
        onChange={(e) => setStudyId(e.target.value)}
        className="text-xs border border-slate-200 px-2 py-1.5 text-slate-700 bg-white focus:outline-none focus:border-brand-500 min-w-52"
      >
        {studies.map((s) => (
          <option key={s.id} value={s.id}>
            {s.protocol_number} — {s.name}
          </option>
        ))}
      </select>
    </div>
  );
}
