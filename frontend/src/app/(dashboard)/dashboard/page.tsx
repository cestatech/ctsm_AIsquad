"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuthStore } from "@/store/authStore";
import { authApi } from "@/lib/api/auth";

export default function DashboardPage() {
  const router = useRouter();
  const { user, token, clearAuth } = useAuthStore();

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  async function handleLogout() {
    await authApi.logout().catch(() => null);
    clearAuth();
    router.push("/");
  }

  if (!user) return null;

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      <div className="flex h-screen overflow-hidden">
        {/* Sidebar */}
        <aside className="w-60 bg-brand-950 flex flex-col flex-shrink-0">
          <div className="px-5 py-4 border-b border-white/10">
            <div className="flex items-center gap-2.5">
              <div className="w-6 h-6 bg-brand-500 flex items-center justify-center">
                <span className="text-white text-[10px] font-bold font-display">TG</span>
              </div>
              <span className="text-white font-semibold text-sm font-display">TrialGenesis</span>
            </div>
          </div>

          <nav className="flex-1 px-3 py-4 space-y-0.5">
            {[
              { label: "Dashboard", active: true },
              { label: "Studies" },
              { label: "Artifacts" },
              { label: "Approvals" },
              { label: "Audit Log" },
            ].map((item) => (
              <button
                key={item.label}
                className={`w-full flex items-center px-3 py-2 text-sm transition-colors text-left ${
                  item.active
                    ? "bg-brand-500/20 text-white border-l-2 border-brand-400"
                    : "text-slate-400 hover:text-white hover:bg-white/5 border-l-2 border-transparent"
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>

          <div className="px-3 py-4 border-t border-white/10">
            <div className="flex items-center gap-3 px-3 py-2 mb-1">
              <div className="w-7 h-7 bg-brand-600 flex items-center justify-center flex-shrink-0">
                <span className="text-white text-xs font-semibold font-display">
                  {user.full_name.charAt(0).toUpperCase()}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white text-xs font-medium truncate font-display">{user.full_name}</p>
                <p className="text-slate-400 text-xs truncate font-mono-dm">{user.email}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="w-full text-left px-3 py-2 text-slate-400 hover:text-white text-xs hover:bg-white/5 transition-colors"
            >
              Sign out
            </button>
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 overflow-auto">
          <div className="px-8 py-5 border-b border-slate-200 bg-white">
            <h1 className="font-display text-xl font-bold text-slate-900">Dashboard</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              Welcome back, {user.full_name.split(" ")[0]}
            </p>
          </div>

          <div className="px-8 py-8">
            {/* Stats */}
            <div className="grid grid-cols-4 gap-px bg-slate-200 border border-slate-200 mb-8">
              {[
                { label: "Active Studies", value: "0" },
                { label: "Artifacts", value: "0" },
                { label: "Pending Approvals", value: "0" },
                { label: "AI Jobs", value: "0" },
              ].map((stat) => (
                <div key={stat.label} className="bg-white px-6 py-5">
                  <p className="font-display text-2xl font-bold text-slate-900">{stat.value}</p>
                  <p className="text-slate-500 text-sm mt-1">{stat.label}</p>
                </div>
              ))}
            </div>

            {/* Empty state */}
            <div className="bg-white border border-slate-200 p-16 text-center">
              <div className="w-10 h-10 bg-brand-50 border border-brand-100 mx-auto mb-4" />
              <h3 className="font-display font-semibold text-slate-900 mb-2">
                Create your first study
              </h3>
              <p className="text-slate-500 text-sm max-w-xs mx-auto mb-6">
                Studies are the top-level container for all your clinical trial artifacts.
              </p>
              <button className="bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold font-display px-6 py-2.5 transition-colors">
                New study
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
