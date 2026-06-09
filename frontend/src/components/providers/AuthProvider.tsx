"use client";

import { useEffect, useRef, useState } from "react";
import { bootstrapAuth } from "@/lib/auth/session";
import { useAuthStore } from "@/store/authStore";

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [isReady, setIsReady] = useState(false);
  const bootstrappedRef = useRef(false);

  useEffect(() => {
    const runBootstrap = async () => {
      if (bootstrappedRef.current) return;
      bootstrappedRef.current = true;
      useAuthStore.getState().setHydrated(true);
      try {
        await bootstrapAuth();
      } finally {
        useAuthStore.getState().setBootstrapped(true);
        setIsReady(true);
      }
    };

    const unsub = useAuthStore.persist.onFinishHydration(() => {
      void runBootstrap();
    });

    if (useAuthStore.persist.hasHydrated()) {
      void runBootstrap();
    }

    return unsub;
  }, []);

  if (!isReady) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-sm text-slate-400">Loading session…</p>
      </div>
    );
  }

  return <>{children}</>;
}
