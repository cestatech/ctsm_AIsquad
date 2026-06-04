"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { authApi } from "@/lib/api/auth";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", alwaysShow: true, group: "main" },
  { label: "Studies", href: "/studies", alwaysShow: true, group: "main" },
  { label: "Approvals", href: "/approvals", permission: "canApproveArtifact" as const, group: "main" },
  { label: "Validation", href: "/validation", permission: "canRunValidation" as const, group: "main" },
  { label: "AI Generation", href: "/generation", permission: "canTriggerGeneration" as const, group: "main" },
  { label: "Audit Log", href: "/audit", permission: "canViewAuditLog" as const, group: "main" },
  { label: "Users", href: "/users", permission: "canManageUsers" as const, group: "main" },
  { label: "Settings", href: "/settings", alwaysShow: true, group: "main" },
];

const INTELLIGENCE_NAV_ITEMS = [
  { label: "Overview", href: "/intelligence", alwaysShow: true },
  { label: "Context Graph", href: "/intelligence/graph", alwaysShow: true },
  { label: "Traceability", href: "/intelligence/traceability", alwaysShow: true },
  { label: "AI Decisions", href: "/intelligence/decisions", alwaysShow: true },
  { label: "Human Overrides", href: "/intelligence/overrides", alwaysShow: true },
  { label: "Lineage", href: "/intelligence/lineage", alwaysShow: true },
  { label: "Validation", href: "/intelligence/validation", permission: "canRunValidation" as const },
  { label: "Synthetic Data", href: "/intelligence/synthetic", alwaysShow: true },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, role, clearAuth } = useAuthStore();
  const perms = usePermissions(role);

  async function handleLogout() {
    await authApi.logout().catch(() => null);
    clearAuth();
    router.push("/");
  }

  if (!user) return null;

  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.alwaysShow) return true;
    if (item.permission) return perms[item.permission];
    return false;
  });

  const visibleIntelligenceItems = INTELLIGENCE_NAV_ITEMS.filter((item) => {
    if ("alwaysShow" in item && item.alwaysShow) return true;
    if (item.permission) return perms[item.permission];
    return false;
  });

  const isIntelligence = pathname.startsWith("/intelligence");

  const initials = user.full_name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <aside className="w-60 bg-brand-950 flex flex-col flex-shrink-0 h-screen sticky top-0">
      <div className="px-5 py-4 border-b border-white/10">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 bg-brand-500 flex items-center justify-center">
            <span className="text-white text-[10px] font-bold font-display">TG</span>
          </div>
          <span className="text-white font-semibold text-sm font-display">TrialGenesis</span>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {visibleItems.map((item) => {
          const isActive =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : !pathname.startsWith("/intelligence") && pathname.startsWith(item.href);
          return (
            <Link
              key={item.label}
              href={item.href}
              className={`w-full flex items-center px-3 py-2 text-sm transition-colors text-left rounded-sm ${
                isActive
                  ? "bg-brand-500/20 text-white border-l-2 border-brand-400"
                  : "text-slate-400 hover:text-white hover:bg-white/5 border-l-2 border-transparent"
              }`}
            >
              {item.label}
            </Link>
          );
        })}

        <div className="pt-3 pb-1">
          <div className="px-3 mb-1">
            <span className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold">
              Intelligence
            </span>
          </div>
          {visibleIntelligenceItems.map((item) => {
            const isActive =
              item.href === "/intelligence"
                ? pathname === "/intelligence"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.label}
                href={item.href}
                className={`w-full flex items-center px-3 py-1.5 text-sm transition-colors text-left rounded-sm ${
                  isActive
                    ? "bg-brand-500/20 text-white border-l-2 border-brand-400"
                    : isIntelligence
                    ? "text-slate-400 hover:text-white hover:bg-white/5 border-l-2 border-transparent"
                    : "text-slate-500 hover:text-white hover:bg-white/5 border-l-2 border-transparent"
                }`}
              >
                <span className="text-xs">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="px-3 py-4 border-t border-white/10">
        <div className="flex items-center gap-3 px-3 py-2 mb-1">
          <div className="w-7 h-7 bg-brand-600 flex items-center justify-center flex-shrink-0 rounded-sm">
            <span className="text-white text-xs font-semibold font-display">{initials}</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white text-xs font-medium truncate font-display">{user.full_name}</p>
            <p className="text-slate-400 text-[11px] truncate font-mono">{user.email}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="w-full text-left px-3 py-2 text-slate-400 hover:text-white text-xs hover:bg-white/5 transition-colors rounded-sm"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
