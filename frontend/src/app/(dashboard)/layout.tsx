"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { Sidebar } from "@/components/layout/Sidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { token, isBootstrapped } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (isBootstrapped && !token) {
      router.replace("/login");
    }
  }, [token, isBootstrapped, router]);

  if (!isBootstrapped) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-sm text-slate-400">Loading session…</p>
      </div>
    );
  }

  if (!token) return null;

  return (
    <div className="flex h-screen bg-slate-50 font-sans overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
