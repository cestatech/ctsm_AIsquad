"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { authApi } from "@/lib/api/auth";
import { notificationsApi } from "@/lib/api/notifications";
import type { Notification } from "@/types";

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
  { label: "Graph Events", href: "/intelligence/events", alwaysShow: true },
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
  const { user, role, token, clearAuth } = useAuthStore();
  const perms = usePermissions(role);
  const queryClient = useQueryClient();
  const [notifOpen, setNotifOpen] = useState(false);

  const { data: notifData } = useQuery({
    queryKey: ["notifications-count", token],
    queryFn: () => notificationsApi.list({ unread_only: true, page_size: 10 }, token!),
    enabled: !!token,
    refetchInterval: 30_000,
  });

  const markReadMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id, token!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications-count"] }),
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => notificationsApi.markAllRead(token!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications-count"] }),
  });

  async function handleLogout() {
    if (token) {
      await authApi.logout(token).catch(() => null);
    }
    clearAuth();
    router.push("/");
  }

  if (!user) return null;

  const unreadCount = notifData?.unread_count ?? 0;
  const notifications: Notification[] = notifData?.items ?? [];

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
  const studyPathMatch = pathname.match(/^\/studies\/([^/]+)/);
  const activeStudyId =
    studyPathMatch && studyPathMatch[1] !== "new" ? studyPathMatch[1] : null;

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

        {activeStudyId && (
          <div className="pt-3 pb-1">
            <div className="px-3 mb-1">
              <span className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold">
                Study Workspace
              </span>
            </div>
            <Link
              href={`/studies/${activeStudyId}/submission`}
              className={`w-full flex items-center px-3 py-1.5 text-sm transition-colors text-left rounded-sm ${
                pathname === `/studies/${activeStudyId}/submission`
                  ? "bg-brand-500/20 text-white border-l-2 border-brand-400"
                  : "text-slate-500 hover:text-white hover:bg-white/5 border-l-2 border-transparent"
              }`}
            >
              <span className="text-xs">Submission Readiness</span>
            </Link>
          </div>
        )}

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

      <div className="px-3 py-4 border-t border-white/10 space-y-1">
        {/* Notification bell */}
        <div className="relative">
          <button
            onClick={() => setNotifOpen((v) => !v)}
            className="w-full flex items-center justify-between px-3 py-2 text-slate-400 hover:text-white text-xs hover:bg-white/5 transition-colors rounded-sm"
          >
            <span>Notifications</span>
            {unreadCount > 0 && (
              <span className="bg-brand-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </button>

          {notifOpen && (
            <div className="absolute bottom-full left-0 right-0 mb-2 bg-white border border-slate-200 shadow-xl z-50 max-h-80 flex flex-col">
              <div className="px-3 py-2 border-b border-slate-100 flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-700">Notifications</span>
                {unreadCount > 0 && (
                  <button
                    onClick={() => markAllReadMutation.mutate()}
                    disabled={markAllReadMutation.isPending}
                    className="text-[10px] text-brand-600 hover:text-brand-700 font-medium disabled:opacity-40"
                  >
                    Mark all read
                  </button>
                )}
              </div>
              <div className="overflow-y-auto flex-1">
                {notifications.length === 0 ? (
                  <p className="text-xs text-slate-400 px-3 py-4 text-center">No unread notifications.</p>
                ) : (
                  notifications.map((n) => (
                    <button
                      key={n.id}
                      onClick={() => markReadMutation.mutate(n.id)}
                      className="w-full text-left px-3 py-2.5 border-b border-slate-50 hover:bg-slate-50 transition-colors"
                    >
                      <p className="text-xs font-medium text-slate-800 leading-tight">{n.title}</p>
                      <p className="text-[11px] text-slate-500 mt-0.5 leading-snug line-clamp-2">{n.body}</p>
                      <p className="text-[10px] text-slate-400 mt-1">
                        {new Date(n.created_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </p>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 px-3 py-2">
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
