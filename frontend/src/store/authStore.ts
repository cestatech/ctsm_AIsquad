"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Role, User } from "@/types";

interface AuthState {
  token: string | null;
  user: User | null;
  role: Role;
  isHydrated: boolean;
  isBootstrapped: boolean;
  setAuth: (token: string, user: User, role?: Role) => void;
  updateToken: (token: string) => void;
  clearAuth: () => void;
  setHydrated: (value: boolean) => void;
  setBootstrapped: (value: boolean) => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      role: "ADMIN" as Role,
      isHydrated: false,
      isBootstrapped: false,

      setAuth: (token, user, role = "ADMIN") => set({ token, user, role }),

      updateToken: (token) => set({ token }),

      clearAuth: () =>
        set({ token: null, user: null, role: "ADMIN", isBootstrapped: true }),

      setHydrated: (value) => set({ isHydrated: value }),

      setBootstrapped: (value) => set({ isBootstrapped: value }),

      isAuthenticated: () => !!get().token,
    }),
    {
      name: "trialgenesis-auth",
      partialize: (state) => ({ token: state.token, user: state.user, role: state.role }),
    }
  )
);
