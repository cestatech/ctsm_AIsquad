import Link from "next/link";

const STATS = [
  { value: "90%", label: "Reduction in manual artifact linking" },
  { value: "3×", label: "Faster protocol-to-submission cycles" },
  { value: "100%", label: "Audit trail coverage, always" },
];

const VALUE_PROPS = [
  {
    label: "01",
    title: "Accelerate every lifecycle stage",
    desc: "AI drafts protocols, SAPs, and CSR sections in minutes. Human experts review and approve — never auto-publish. Cut cycle time without cutting corners.",
  },
  {
    label: "02",
    title: "Unbreakable traceability",
    desc: "Every objective links to an endpoint, every endpoint to an eCRF, every eCRF to SDTM. Gaps surface instantly. Regulatory inspectors see a clean chain.",
  },
  {
    label: "03",
    title: "Compliance built in, not bolted on",
    desc: "21 CFR Part 11 electronic signatures, immutable audit logs, append-only version history, and role-gated approvals — all enforced at the database level.",
  },
];

const ROLES = [
  {
    title: "Clinical Scientists",
    subtitle: "Drive rigor from hypothesis to CSR",
    desc: "Design studies, define endpoints, and trace every decision from protocol objective through to the final analysis dataset — with AI generating first drafts for your review.",
  },
  {
    title: "Clinical Operations",
    subtitle: "Keep studies on track and on budget",
    desc: "Manage artifact status across studies, assign reviewers, track approvals, and get notified the moment something needs your attention.",
    featured: true,
  },
  {
    title: "Medical Writers",
    subtitle: "Produce compliant documents faster",
    desc: "Work from AI-generated drafts, collaborate with inline comments, and submit for approval — all in one system that maintains full version history.",
  },
  {
    title: "Data Managers",
    subtitle: "Structured data from day one",
    desc: "SDTM and ADaM datasets are first-class artifacts, linked to their source eCRFs and downstream TLFs. No more manual traceability matrices.",
  },
];

const OLD_WAY = [
  "Fragmented Word docs, spreadsheets, and email chains",
  "Manual copy-paste between EDC, SDTM, and ADaM",
  "Traceability matrices maintained by hand",
  "Version control via filename suffixes (_v3_FINAL_2)",
  "No audit trail for who changed what, when",
];

const NEW_WAY = [
  "Unified workspace — Protocol to CSR in one platform",
  "Automated linkage: eCRF → SDTM → ADaM → TLF",
  "Real-time traceability gaps surface automatically",
  "Append-only versioning with full diff history",
  "Immutable audit log on every action, always",
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-white font-sans">

      {/* ── Nav ─────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 bg-white border-b border-slate-200">
        <div className="mx-auto max-w-7xl px-6 flex items-center justify-between h-16">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-brand-600 flex items-center justify-center">
              <span className="text-white text-xs font-bold font-display">TG</span>
            </div>
            <span className="text-brand-950 font-bold text-lg tracking-tight font-display">TrialGenesis</span>
          </div>

          <nav className="hidden md:flex items-center gap-8">
            {["Platform", "Solutions", "Compliance", "Pricing"].map((item) => (
              <a key={item} href={`#${item.toLowerCase()}`}
                className="text-sm text-slate-600 hover:text-brand-700 transition-colors">
                {item}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <Link href="/register" className="text-sm text-slate-600 hover:text-slate-900 transition-colors px-3 py-2">
              Register
            </Link>
            <Link href="/login"
              className="text-sm font-semibold font-display bg-brand-950 hover:bg-brand-800 text-white px-5 py-2 transition-colors">
              Login
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero ────────────────────────────────────────────────────── */}
      <section className="bg-brand-950 pt-16 pb-20 overflow-hidden">
        <div className="mx-auto max-w-7xl px-6 flex flex-col lg:flex-row items-center gap-12">

          {/* Left */}
          <div className="flex-1 min-w-0">
            <h1 className="font-display text-4xl md:text-5xl xl:text-6xl font-bold text-white leading-[1.08] mb-6">
              Generate and manage
              <br />
              <span className="text-brand-300">clinical trial artifacts</span>
              <br />
              end to end
            </h1>
            <p className="text-slate-300 text-lg leading-relaxed max-w-lg mb-10">
              From AI-drafted protocols to locked CSRs — TrialGenesis connects every artifact,
              enforces every review, and logs every decision. Built for regulated environments
              from day one.
            </p>

            {/* Stats */}
            <div className="flex flex-wrap gap-10 mb-10">
              {STATS.map((s) => (
                <div key={s.value}>
                  <div className="font-display text-3xl font-bold text-brand-300">{s.value}</div>
                  <div className="text-slate-400 text-xs uppercase tracking-widest mt-1 font-mono-dm max-w-[140px] leading-tight">
                    {s.label}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-4">
              <Link href="/register"
                className="bg-brand-400 hover:bg-brand-300 text-brand-950 font-bold font-display px-8 py-3 text-sm transition-colors">
                Get started free →
              </Link>
              <a href="#platform"
                className="border border-white/30 hover:border-white/60 text-white font-medium px-8 py-3 text-sm transition-colors">
                See how it works
              </a>
            </div>
          </div>

          {/* Right — product UI mockup */}
          <div className="flex-1 min-w-0 w-full max-w-xl lg:max-w-none">
            <div className="bg-white shadow-2xl overflow-hidden text-xs">
              {/* Window chrome */}
              <div className="bg-slate-100 border-b border-slate-200 px-4 py-2.5 flex items-center gap-2">
                <div className="w-2.5 h-2.5 bg-red-400" />
                <div className="w-2.5 h-2.5 bg-yellow-400" />
                <div className="w-2.5 h-2.5 bg-green-400" />
                <span className="ml-3 text-slate-400 font-mono-dm text-[10px]">TrialGenesis — PROTOCOL-2024-001</span>
              </div>
              {/* Artifact list header */}
              <div className="bg-brand-950 text-white px-4 py-2 flex items-center justify-between">
                <span className="font-display font-semibold text-[11px]">Artifacts</span>
                <span className="bg-brand-500 text-white text-[10px] px-2 py-0.5 font-mono-dm">+ New</span>
              </div>
              {/* Artifact rows */}
              {[
                { name: "Phase II Protocol v3.1", type: "PROTOCOL", status: "APPROVED", color: "text-green-600 bg-green-50" },
                { name: "Informed Consent Form", type: "ICF", status: "IN REVIEW", color: "text-yellow-700 bg-yellow-50" },
                { name: "Statistical Analysis Plan", type: "SAP", status: "DRAFT", color: "text-slate-500 bg-slate-100" },
                { name: "eDC Case Report Forms", type: "EDC_CRF", status: "DRAFT", color: "text-slate-500 bg-slate-100" },
                { name: "SDTM Datasets v1.0", type: "SDTM", status: "LOCKED", color: "text-brand-700 bg-brand-50" },
              ].map((row) => (
                <div key={row.name} className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 hover:bg-slate-50">
                  <div>
                    <div className="font-medium text-slate-800 text-[11px]">{row.name}</div>
                    <div className="text-slate-400 font-mono-dm text-[10px]">{row.type}</div>
                  </div>
                  <span className={`text-[10px] font-mono-dm font-medium px-2 py-0.5 ${row.color}`}>
                    {row.status}
                  </span>
                </div>
              ))}
              {/* Traceability bar */}
              <div className="bg-brand-50 border-t border-brand-100 px-4 py-2 flex items-center gap-1 text-[10px] text-brand-600 font-mono-dm">
                <span className="font-semibold">Traceability:</span>
                {["Protocol", "→", "ICF", "→", "SAP", "→", "EDC", "→", "SDTM"].map((s, i) => (
                  <span key={i} className={s === "→" ? "text-brand-300" : ""}>{s}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Value props ──────────────────────────────────────────────── */}
      <section id="platform" className="bg-brand-950 pb-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center mb-14">
            <h2 className="font-display text-3xl md:text-4xl font-bold text-white mb-4">
              Turn compliance overhead into competitive advantage
            </h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              Leading biotech and pharma teams use TrialGenesis to close the gap between
              scientific ambition and regulatory reality.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {VALUE_PROPS.map((v) => (
              <div key={v.title} className="bg-white border-t-4 border-brand-400 p-7">
                <div className="font-mono-dm text-xs text-brand-400 font-semibold tracking-widest mb-5">{v.label}</div>
                <h3 className="font-display font-bold text-brand-950 text-lg mb-3">{v.title}</h3>
                <p className="text-slate-500 text-sm leading-relaxed">{v.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Roles ───────────────────────────────────────────────────── */}
      <section id="solutions" className="py-24 bg-slate-50">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center mb-14">
            <h2 className="font-display text-3xl md:text-4xl font-bold text-brand-950 mb-4">
              Built for your entire clinical development team
            </h2>
            <p className="text-slate-500 max-w-2xl mx-auto">
              Every role gets the tools they need — Contributors draft, Reviewers approve,
              Admins lock. No role can bypass the workflow.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-5">
            {ROLES.map((r) => (
              <div key={r.title}
                className={`bg-white p-7 border ${r.featured ? "border-brand-500 shadow-md" : "border-slate-200"}`}>
                <h3 className={`font-display font-bold text-lg mb-1 ${r.featured ? "text-brand-700" : "text-brand-950"}`}>
                  {r.title}
                </h3>
                <p className="font-semibold text-slate-600 text-xs mb-3">{r.subtitle}</p>
                <p className="text-slate-500 text-sm leading-relaxed">{r.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Comparison ──────────────────────────────────────────────── */}
      <section id="compliance" className="py-24 bg-white">
        <div className="mx-auto max-w-5xl px-6">
          <div className="text-center mb-14">
            <h2 className="font-display text-3xl md:text-4xl font-bold text-brand-950 mb-4">
              The old way vs. TrialGenesis
            </h2>
            <p className="text-slate-500 max-w-xl mx-auto text-sm">
              Traditional clinical development is fragmented, manual, and audit-unfriendly.
              TrialGenesis was built to fix all of that.
            </p>
          </div>

          <div className="border border-slate-200">
            {/* Header */}
            <div className="grid grid-cols-2 border-b border-slate-200">
              <div className="px-8 py-5 border-r border-slate-200">
                <p className="font-display font-bold text-slate-700 text-sm">
                  Traditional approach
                  <span className="font-normal text-slate-400 ml-1">(Word docs &amp; email)</span>
                </p>
              </div>
              <div className="px-8 py-5 bg-brand-50">
                <p className="font-display font-bold text-brand-700 text-sm">TrialGenesis</p>
              </div>
            </div>
            {/* Rows */}
            {OLD_WAY.map((old, i) => (
              <div key={i} className={`grid grid-cols-2 ${i < OLD_WAY.length - 1 ? "border-b border-slate-100" : ""}`}>
                <div className="px-8 py-4 border-r border-slate-100 flex items-start gap-3">
                  <span className="text-red-400 font-mono-dm text-xs font-semibold mt-0.5 flex-shrink-0 uppercase tracking-wide">No</span>
                  <span className="text-slate-500 text-sm">{old}</span>
                </div>
                <div className="px-8 py-4 bg-brand-50/40 flex items-start gap-3">
                  <span className="text-brand-600 font-mono-dm text-xs font-semibold mt-0.5 flex-shrink-0 uppercase tracking-wide">Yes</span>
                  <span className="text-slate-700 text-sm">{NEW_WAY[i]}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────────────────── */}
      <section className="py-20 bg-brand-950 text-center">
        <div className="mx-auto max-w-2xl px-6">
          <h2 className="font-display text-3xl md:text-4xl font-bold text-white mb-4">
            Ready to modernize your trial lifecycle?
          </h2>
          <p className="text-slate-400 mb-10">
            Create your workspace in minutes. No credit card required.
          </p>
          <Link href="/register"
            className="inline-block bg-brand-400 hover:bg-brand-300 text-brand-950 font-bold font-display px-12 py-4 text-sm transition-colors">
            Create your workspace →
          </Link>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────── */}
      <footer className="border-t border-slate-200 py-8 bg-white">
        <div className="mx-auto max-w-7xl px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 bg-brand-600 flex items-center justify-center">
              <span className="text-white text-[10px] font-bold font-display">TG</span>
            </div>
            <span className="text-slate-700 text-sm font-display font-semibold">TrialGenesis</span>
          </div>
          <p className="text-slate-400 text-xs font-mono-dm">
            © {new Date().getFullYear()} TrialGenesis. Clinical Trial Lifecycle Platform.
          </p>
        </div>
      </footer>
    </div>
  );
}
