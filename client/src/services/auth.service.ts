/** Auth endpoints. Thin wrapper so components never call axios directly. */

import { api } from "./api";
import type { AuthResponse, AuthUser, LoginPayload, RegisterPayload } from "../types";

export const authService = {
  async register(payload: RegisterPayload): Promise<AuthUser> {
    const { data } = await api.post<AuthUser>("/auth/register", payload);
    return data;
  },

  async login(payload: LoginPayload): Promise<AuthResponse> {
    const { data } = await api.post<AuthResponse>("/auth/login", payload);
    return data;
  },

  /** Validates a stored token on app start. */
  async me(): Promise<AuthUser> {
    const { data } = await api.get<AuthUser>("/auth/me");
    return data;
  },

  async logout(): Promise<void> {
    await api.post("/auth/logout");
  },
};
