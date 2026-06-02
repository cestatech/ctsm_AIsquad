import Link from "next/link";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen mesh-bg dot-grid flex flex-col">
      <header className="px-6 py-4">
        <Link href="/" className="inline-flex items-center gap-2.5">
          <div className="w-7 h-7 bg-brand-500 flex items-center justify-center">
            <span className="text-white text-xs font-bold font-display">TG</span>
          </div>
          <span className="text-white font-semibold tracking-tight font-display">TrialGenesis</span>
        </Link>
      </header>

      <div className="flex-1 flex items-center justify-center px-4 py-12">
        {children}
      </div>

      <footer className="px-6 py-4 text-center">
        <p className="text-slate-400 text-xs font-mono-dm">
          © {new Date().getFullYear()} Celerius — Clinical Trial Lifecycle Platform
        </p>
      </footer>
    </div>
  );
}
