import { authApi } from "@/lib/api/auth";
import { useAuthStore } from "@/store/authStore";

let refreshPromise: Promise<string | null> | null = null;

/**
 * Exchange the httpOnly refresh cookie for a new access token.
 * Deduplicates concurrent refresh attempts.
 */
export async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = authApi
      .refresh()
      .then((res) => {
        useAuthStore.getState().updateToken(res.access_token);
        return res.access_token;
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

/**
 * Validate the current session and restore from refresh cookie when needed.
 */
export async function bootstrapAuth(): Promise<void> {
  const { token, user, setAuth, updateToken, clearAuth } = useAuthStore.getState();

  try {
    if (token) {
      try {
        const me = await authApi.me(token);
        if (!user || user.id !== me.id) {
          setAuth(token, me);
        }
        return;
      } catch {
        const newToken = await refreshAccessToken();
        if (!newToken) {
          clearAuth();
          return;
        }
        const me = await authApi.me(newToken);
        setAuth(newToken, me);
        return;
      }
    }

    const newToken = await refreshAccessToken();
    if (!newToken) {
      clearAuth();
      return;
    }
    const me = await authApi.me(newToken);
    setAuth(newToken, me);
  } catch {
    clearAuth();
  }
}
