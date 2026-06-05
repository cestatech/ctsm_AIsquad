"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { usePermissions } from "@/hooks/usePermissions";
import { organizationsApi } from "@/lib/api/organizations";
import { authApi } from "@/lib/api/auth";

export default function SettingsPage() {
  const { token, role } = useAuthStore();
  const perms = usePermissions(role);
  const queryClient = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", description: "", logo_url: "" });

  const [pwForm, setPwForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSuccess, setPwSuccess] = useState(false);

  const { data: org, isLoading } = useQuery({
    queryKey: ["org-me", token],
    queryFn: () => organizationsApi.getMe(token!),
    enabled: !!token,
  });

  function startEdit() {
    if (!org) return;
    setForm({ name: org.name, description: org.description ?? "", logo_url: org.logo_url ?? "" });
    setError(null);
    setEditing(true);
  }

  const changePasswordMutation = useMutation({
    mutationFn: () => {
      if (pwForm.new_password !== pwForm.confirm_password) {
        throw new Error("New passwords do not match.");
      }
      if (pwForm.new_password.length < 8) {
        throw new Error("New password must be at least 8 characters.");
      }
      return authApi.changePassword(
        { current_password: pwForm.current_password, new_password: pwForm.new_password },
        token!
      );
    },
    onSuccess: () => {
      setPwForm({ current_password: "", new_password: "", confirm_password: "" });
      setPwError(null);
      setPwSuccess(true);
      setTimeout(() => setPwSuccess(false), 4000);
    },
    onError: (err) => {
      setPwError(err instanceof Error ? err.message : "Password change failed.");
      setPwSuccess(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      organizationsApi.updateMe(
        {
          name: form.name || undefined,
          description: form.description || undefined,
          logo_url: form.logo_url || undefined,
        },
        token!
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData(["org-me", token], updated);
      setEditing(false);
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Update failed."),
  });

  if (isLoading) {
    return <div className="px-8 py-16 text-center text-slate-400 text-sm">Loading…</div>;
  }

  if (!org) {
    return <div className="px-8 py-16 text-center text-slate-400 text-sm">Organization not found.</div>;
  }

  return (
    <div>
      <div className="px-8 py-5 border-b border-slate-200 bg-white">
        <h1 className="font-display text-xl font-bold text-slate-900">Organization Settings</h1>
        <p className="text-slate-500 text-sm mt-0.5">{org.slug}</p>
      </div>

      <div className="px-8 py-6 max-w-2xl space-y-6">
        {/* General info */}
        <div className="bg-white border border-slate-200">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h2 className="font-display font-semibold text-slate-900 text-sm">General</h2>
            {perms.isAdmin && !editing && (
              <button
                onClick={startEdit}
                className="text-xs px-3 py-1.5 border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
              >
                Edit
              </button>
            )}
          </div>

          {editing ? (
            <div className="px-5 py-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Organization Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Description</label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  rows={3}
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-brand-500 resize-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Logo URL</label>
                <input
                  type="url"
                  value={form.logo_url}
                  onChange={(e) => setForm((f) => ({ ...f, logo_url: e.target.value }))}
                  placeholder="https://…"
                  className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 font-mono focus:outline-none focus:border-brand-500"
                />
              </div>
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">{error}</div>
              )}
              <div className="flex gap-3">
                <button
                  onClick={() => updateMutation.mutate()}
                  disabled={updateMutation.isPending || !form.name.trim()}
                  className="text-sm font-semibold px-4 py-2 bg-brand-600 text-white hover:bg-brand-500 transition-colors disabled:opacity-50"
                >
                  {updateMutation.isPending ? "Saving…" : "Save changes"}
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="text-sm text-slate-500 hover:text-slate-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <dl className="divide-y divide-slate-50">
              {[
                { label: "Name", value: org.name },
                { label: "Slug", value: org.slug },
                { label: "Description", value: org.description ?? "—" },
                { label: "Logo URL", value: org.logo_url ?? "—" },
                { label: "Status", value: org.is_active ? "Active" : "Inactive" },
                { label: "Created", value: new Date(org.created_at).toLocaleDateString() },
                { label: "Last updated", value: new Date(org.updated_at).toLocaleDateString() },
              ].map(({ label, value }) => (
                <div key={label} className="px-5 py-3.5 flex gap-4">
                  <dt className="text-xs text-slate-400 w-28 shrink-0 pt-0.5">{label}</dt>
                  <dd className="text-sm text-slate-800 break-all">{value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>

        {/* Tenant ID */}
        <div className="bg-white border border-slate-200 px-5 py-4">
          <h2 className="font-display font-semibold text-slate-900 text-sm mb-3">Tenant ID</h2>
          <p className="text-xs text-slate-500 mb-2">
            This ID is your organization&apos;s immutable identifier. Include it in support requests.
          </p>
          <code className="text-xs font-mono text-slate-700 bg-slate-50 border border-slate-200 px-3 py-2 block">
            {org.id}
          </code>
        </div>

        {/* Settings blob */}
        {Object.keys(org.settings ?? {}).length > 0 && (
          <div className="bg-white border border-slate-200 px-5 py-4">
            <h2 className="font-display font-semibold text-slate-900 text-sm mb-3">Configuration</h2>
            <pre className="text-xs font-mono text-slate-600 bg-slate-50 border border-slate-100 p-4 overflow-auto max-h-48">
              {JSON.stringify(org.settings, null, 2)}
            </pre>
          </div>
        )}

        {!perms.isAdmin && (
          <p className="text-xs text-slate-400">Only Admins can modify organization settings.</p>
        )}

        {/* Change password */}
        <div className="bg-white border border-slate-200">
          <div className="px-5 py-4 border-b border-slate-100">
            <h2 className="font-display font-semibold text-slate-900 text-sm">Change Password</h2>
          </div>
          <div className="px-5 py-5 space-y-4">
            {pwSuccess && (
              <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs px-3 py-2">
                Password changed successfully.
              </div>
            )}
            {pwError && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2">{pwError}</div>
            )}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Current password</label>
              <input
                type="password"
                value={pwForm.current_password}
                onChange={(e) => setPwForm((f) => ({ ...f, current_password: e.target.value }))}
                autoComplete="current-password"
                className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">New password</label>
              <input
                type="password"
                value={pwForm.new_password}
                onChange={(e) => setPwForm((f) => ({ ...f, new_password: e.target.value }))}
                autoComplete="new-password"
                className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Confirm new password</label>
              <input
                type="password"
                value={pwForm.confirm_password}
                onChange={(e) => setPwForm((f) => ({ ...f, confirm_password: e.target.value }))}
                autoComplete="new-password"
                className="w-full border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <button
              onClick={() => changePasswordMutation.mutate()}
              disabled={
                changePasswordMutation.isPending ||
                !pwForm.current_password ||
                !pwForm.new_password ||
                !pwForm.confirm_password
              }
              className="text-sm font-semibold px-4 py-2 bg-brand-600 text-white hover:bg-brand-500 transition-colors disabled:opacity-50"
            >
              {changePasswordMutation.isPending ? "Saving…" : "Update password"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
