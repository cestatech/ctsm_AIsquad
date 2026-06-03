"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { usersApi } from "@/lib/api/users";
import { MOCK_USERS } from "@/lib/mockData";
import type { User } from "@/types";

const ROLE_COLORS: Record<string, string> = {
  ADMIN: "bg-brand-100 text-brand-700",
  CONTRIBUTOR: "bg-teal-100 text-teal-700",
  REVIEWER: "bg-violet-100 text-violet-700",
};

function rel(iso: string | null) {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const hrs = Math.floor(diff / 3_600_000);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function UsersPage() {
  const { token, role, user: currentUser } = useAuthStore();
  const perms = usePermissions(role);
  const queryClient = useQueryClient();

  const [inviteModal, setInviteModal] = useState(false);
  const [inviteForm, setInviteForm] = useState({ email: "", full_name: "", role: "CONTRIBUTOR" });
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["users", token],
    queryFn: async () => {
      try {
        return await usersApi.list({}, token!);
      } catch {
        return { items: MOCK_USERS, total: MOCK_USERS.length, page: 1, page_size: 50, has_next: false, has_prev: false };
      }
    },
    enabled: !!token,
  });

  const deactivateMutation = useMutation({
    mutationFn: (userId: string) => usersApi.deactivate(userId, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err) => setActionError(err instanceof Error ? err.message : "Action failed."),
  });

  const activateMutation = useMutation({
    mutationFn: (userId: string) => usersApi.activate(userId, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err) => setActionError(err instanceof Error ? err.message : "Action failed."),
  });

  const inviteMutation = useMutation({
    mutationFn: () => usersApi.invite(inviteForm, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setInviteModal(false);
      setInviteForm({ email: "", full_name: "", role: "CONTRIBUTOR" });
      setInviteError(null);
    },
    onError: (err) => setInviteError(err instanceof Error ? err.message : "Failed to invite user."),
  });

  if (!perms.canManageUsers) {
    return (
      <div className="px-8 py-16 text-center text-slate-500 text-sm">
        Only Admins can manage users.
      </div>
    );
  }

  const users: User[] = data?.items ?? [];

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-bold text-slate-900">Users</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            {data?.total ?? MOCK_USERS.length} members in your organization
          </p>
        </div>
        <button
          onClick={() => { setInviteModal(true); setInviteError(null); }}
          className="bg-brand-600 hover:bg-brand-500 text-white text-sm font-semibold font-display px-5 py-2.5 transition-colors"
        >
          Invite user
        </button>
      </div>

      {actionError && (
        <div className="mx-8 mt-4 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3">
          {actionError}
        </div>
      )}

      <div className="px-8 py-6">
        <div className="bg-white border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">User</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Title</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Last Login</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Member Since</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-400 text-sm">Loading…</td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-slate-400 text-sm">No users found.</td>
                </tr>
              ) : (
                users.map((user) => {
                  const isSelf = user.id === currentUser?.id;
                  return (
                    <tr key={user.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 bg-slate-200 flex items-center justify-center flex-shrink-0">
                            <span className="text-slate-600 text-xs font-semibold">
                              {user.full_name.charAt(0).toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <p className="font-medium text-slate-900">
                              {user.full_name}
                              {isSelf && (
                                <span className="ml-2 text-[10px] text-slate-400 font-normal">(you)</span>
                              )}
                            </p>
                            <p className="text-xs text-slate-400">{user.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">{user.title ?? "—"}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs px-2 py-0.5 font-medium ${
                            user.is_active
                              ? "bg-emerald-100 text-emerald-700"
                              : "bg-slate-100 text-slate-500"
                          }`}
                        >
                          {user.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400">{rel(user.last_login_at)}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">
                        {new Date(user.created_at).toLocaleDateString("en-US", {
                          month: "short", day: "numeric", year: "numeric",
                        })}
                      </td>
                      <td className="px-4 py-3">
                        {!isSelf && (
                          <button
                            onClick={() => {
                              setActionError(null);
                              if (user.is_active) {
                                deactivateMutation.mutate(user.id);
                              } else {
                                activateMutation.mutate(user.id);
                              }
                            }}
                            disabled={deactivateMutation.isPending || activateMutation.isPending}
                            className={`text-xs font-medium px-3 py-1.5 border transition-colors disabled:opacity-50 ${
                              user.is_active
                                ? "border-red-200 text-red-700 hover:bg-red-50"
                                : "border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                            }`}
                          >
                            {user.is_active ? "Deactivate" : "Activate"}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Invite Modal */}
      {inviteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white w-full max-w-md border border-slate-200 shadow-xl">
            <div className="px-6 py-4 border-b border-slate-100">
              <h2 className="font-display font-semibold text-slate-900">Invite Team Member</h2>
            </div>
            <div className="px-6 py-5 space-y-4">
              {inviteError && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">{inviteError}</div>
              )}
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">
                  Full Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={inviteForm.full_name}
                  onChange={(e) => setInviteForm((f) => ({ ...f, full_name: e.target.value }))}
                  placeholder="Dr. Jane Smith"
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">
                  Email <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  value={inviteForm.email}
                  onChange={(e) => setInviteForm((f) => ({ ...f, email: e.target.value }))}
                  placeholder="jane.smith@org.com"
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Default Role</label>
                <select
                  value={inviteForm.role}
                  onChange={(e) => setInviteForm((f) => ({ ...f, role: e.target.value }))}
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 bg-white"
                >
                  <option value="CONTRIBUTOR">Contributor — can create and edit artifacts</option>
                  <option value="REVIEWER">Reviewer — can approve and reject artifacts</option>
                  <option value="ADMIN">Admin — full access including user management</option>
                </select>
              </div>

              <div className="bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700">
                An invite email will be sent when the email service is configured. For now, share login credentials directly.
              </div>
            </div>
            <div className="px-6 py-4 border-t border-slate-100 flex gap-3">
              <button
                onClick={() => inviteMutation.mutate()}
                disabled={inviteMutation.isPending || !inviteForm.email.trim() || !inviteForm.full_name.trim()}
                className="bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-semibold font-display px-5 py-2 transition-colors"
              >
                {inviteMutation.isPending ? "Inviting…" : "Send invite"}
              </button>
              <button
                onClick={() => { setInviteModal(false); setInviteError(null); }}
                className="text-slate-500 hover:text-slate-700 text-sm transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
