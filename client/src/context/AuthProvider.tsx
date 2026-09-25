import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { authService } from "../services/auth.service";
import { TOKEN_STORAGE_KEY } from "../services/api";
import { AuthContext, type AuthStatus } from "./authContext";
import type { AuthResponse, AuthUser } from "../types";

export const USER_STORAGE_KEY = "careverse_user";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  const clearSession = useCallback(() => {
    setUser(null);
    setToken(null);
    setStatus("unauthenticated");
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(USER_STORAGE_KEY);
  }, []);

  // Revalidate the stored token once on mount. The role is read back from
  // the server rather than trusted from localStorage, so a tampered value
  // cannot grant a role client-side.
  useEffect(() => {
    let cancelled = false;
    const storedToken = localStorage.getItem(TOKEN_STORAGE_KEY);

    if (!storedToken) {
      setStatus("unauthenticated");
      return;
    }

    setToken(storedToken);
    authService
      .me()
      .then((freshUser) => {
        if (cancelled) return;
        setUser(freshUser);
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(freshUser));
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        // Expired or revoked token: drop the session silently rather than
        // showing an error the user cannot act on.
        clearSession();
      });

    return () => {
      cancelled = true;
    };
  }, [clearSession]);

  const login = useCallback((auth: AuthResponse) => {
    setToken(auth.access_token);
    setUser(auth.user);
    setStatus("authenticated");
    localStorage.setItem(TOKEN_STORAGE_KEY, auth.access_token);
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(auth.user));
  }, []);

  const value = useMemo(
    () => ({ user, token, status, login, logout: clearSession }),
    [user, token, status, login, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
