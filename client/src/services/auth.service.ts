/** Auth endpoints. Thin wrapper so components never call axios directly. */

import { api } from "./api";
import type {
  AuthResponse,
  AuthUser,
  ForgotPasswordPayload,
  ForgotPasswordResponse,
  LoginPayload,
  RegisterPayload,
  ResetPasswordPayload,
  VerifyOtpPayload,
  VerifyOtpResponse,
} from "../types";

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

  // --- Password reset ---------------------------------------------------

  /**
   * Asks for an OTP. The server answers identically whether or not the
   * address is registered, so the UI must not imply that it did.
   */
  async forgotPassword(payload: ForgotPasswordPayload): Promise<ForgotPasswordResponse> {
    const { data } = await api.post<ForgotPasswordResponse>(
      "/auth/forgot-password",
      payload,
    );
    return data;
  },

  async verifyResetOtp(payload: VerifyOtpPayload): Promise<VerifyOtpResponse> {
    const { data } = await api.post<VerifyOtpResponse>("/auth/verify-reset-otp", payload);
    return data;
  },

  async resetPassword(payload: ResetPasswordPayload): Promise<void> {
    await api.post("/auth/reset-password", payload);
  },
};
