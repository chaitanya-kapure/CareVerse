/**
 * The auth context object and its types, kept separate from the provider.
 *
 * Split out so `AuthProvider.tsx` exports only a component and
 * `hooks/useAuth.ts` can reach the context without importing the provider,
 * which keeps React Fast Refresh working during development.
 */

import { createContext } from "react";
import type { AuthResponse, AuthUser } from "../types";

/**
 * `loading` exists so route guards can wait for the stored token to be
 * validated. Without it, a page refresh would bounce a signed-in user to
 * /login for a frame before the localStorage read completes.
 */
export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  status: AuthStatus;
  login: (auth: AuthResponse) => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
