"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuthStore } from "@/store/authStore";
import { authApi } from "@/lib/api/auth";
import { ApiClientError } from "@/lib/api/client";

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [form, setForm] = useState({
    organization_name: "",
    organization_slug: "",
    full_name: "",
    email: "",
    password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function set(field: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setForm((prev) => {
        const next = { ...prev, [field]: value };
        if (field === "organization_name" && !prev.organization_slug) {
          next.organization_slug = value
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-|-$/g, "")
            .slice(0, 50);
        }
        return next;
      });
    };
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const data = await authApi.register(form);
      setAuth(data.access_token, data.user);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiClientError) {
        const detail = err.error.detail;
        if (Array.isArray(detail)) {
          setError(detail[0]?.msg ?? "Validation error.");
        } else if (typeof detail === "string") {
          setError(detail);
        } else {
          setError("Registration failed. Please check your details.");
        }
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-md">
      <div className="bg-white border border-white/20 shadow-2xl shadow-black/30 p-8">
        <div className="mb-8">
          <h1 className="font-display text-2xl font-bold text-slate-900">Create your workspace</h1>
          <p className="text-slate-500 text-sm mt-1">
            Set up your organization and admin account
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="border-b border-slate-100 pb-5">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3 font-mono-dm">
              Organization
            </p>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Organization name
                </label>
                <input
                  type="text"
                  required
                  value={form.organization_name}
                  onChange={set("organization_name")}
                  placeholder="Acme Pharma"
                  className="w-full px-3.5 py-2.5 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all bg-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Workspace URL
                </label>
                <div className="flex items-center border border-slate-200 overflow-hidden focus-within:ring-2 focus-within:ring-brand-500 focus-within:border-transparent">
                  <span className="px-3 py-2.5 bg-slate-50 text-slate-400 text-xs border-r border-slate-200 whitespace-nowrap font-mono-dm">
                    trialgenesis.app/
                  </span>
                  <input
                    type="text"
                    required
                    value={form.organization_slug}
                    onChange={set("organization_slug")}
                    placeholder="acme-pharma"
                    className="flex-1 px-3 py-2.5 text-sm focus:outline-none font-mono-dm"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="pt-1">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3 font-mono-dm">
              Your account
            </p>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Full name
                </label>
                <input
                  type="text"
                  required
                  value={form.full_name}
                  onChange={set("full_name")}
                  placeholder="Dr. Jane Smith"
                  className="w-full px-3.5 py-2.5 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all bg-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Work email
                </label>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={set("email")}
                  placeholder="jane@acmepharma.com"
                  className="w-full px-3.5 py-2.5 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all bg-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Password
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={form.password}
                  onChange={set("password")}
                  placeholder="Min. 8 characters"
                  className="w-full px-3.5 py-2.5 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all bg-white"
                />
              </div>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-brand-600 hover:bg-brand-500 disabled:bg-brand-300 text-white font-semibold font-display py-2.5 text-sm transition-colors mt-2"
          >
            {loading ? "Creating workspace…" : "Create workspace"}
          </button>
        </form>

        <p className="text-center text-sm text-slate-500 mt-6">
          Already have a workspace?{" "}
          <Link href="/login" className="text-brand-600 hover:text-brand-500 font-medium">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
