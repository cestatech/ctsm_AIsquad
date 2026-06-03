"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Role, User } from "@/types";

interface AuthState {
  token: string | null;
  user: User | null;
  role: Role;
  setAuth: (token: string, user: User, role?: Role) => void;
  clearAuth: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      role: "ADMIN" as Role,

      setAuth: (token, user, role = "ADMIN") => set({ token, user, role }),

      clearAuth: () => set({ token: null, user: null, role: "ADMIN" }),

      isAuthenticated: () => !!get().token,
    }),
    {
      name: "trialgenesis-auth",
      partialize: (state) => ({ token: state.token, user: state.user, role: state.role }),
    }
  )
);
