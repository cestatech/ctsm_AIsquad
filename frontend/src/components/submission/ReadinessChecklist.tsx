import { ReadinessItem, type ReadinessItemModel } from "./ReadinessItem";

export function ReadinessChecklist({ items }: { items: ReadinessItemModel[] }) {
  return (
    <section className="bg-white border border-slate-200">
      <div className="px-5 py-4 border-b border-slate-100">
        <h2 className="font-display font-semibold text-slate-900 text-sm">
          Readiness Checklist
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Regulatory submission gates across SDTM, ADaM, TLF, CSR, validation, and AI review.
        </p>
      </div>
      <ul className="divide-y divide-slate-100">
        {items.map((item) => (
          <ReadinessItem key={item.id} item={item} />
        ))}
      </ul>
    </section>
  );
}

export function ReadinessChecklistSkeleton() {
  return (
    <section className="bg-white border border-slate-200 animate-pulse">
      <div className="px-5 py-4 border-b border-slate-100">
        <div className="h-4 w-36 bg-slate-200" />
        <div className="mt-2 h-3 w-full max-w-md bg-slate-100" />
      </div>
      <div className="divide-y divide-slate-100">
        {Array.from({ length: 7 }).map((_, index) => (
          <div key={index} className="px-5 py-4">
            <div className="flex gap-3">
              <div className="h-5 w-5 rounded-full bg-slate-200" />
              <div className="flex-1 space-y-2">
                <div className="h-3 w-24 bg-slate-100" />
                <div className="h-4 w-2/3 bg-slate-200" />
                <div className="h-3 w-full bg-slate-100" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export type { ReadinessItemModel, ReadinessStatus } from "./ReadinessItem";
