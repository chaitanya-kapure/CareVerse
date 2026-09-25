/**
 * Axios instance and error normalization.
 *
 * In development, Vite proxies `/api/*` to the FastAPI server (see
 * `vite.config.ts`), so the client and the deployed app use the same URL
 * shape. `VITE_API_URL` only needs to be set when the API is not proxied.
 */

import axios, { AxiosError } from "axios";
import type { ApiErrorBody } from "../types";

export const TOKEN_STORAGE_KEY = "careverse_token";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "/api",
  timeout: 20_000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Turns any failure into a readable sentence.
 *
 * The backend always answers with `{ detail, code }`, but a network failure
 * or a proxy error has no body at all, so every layer has to be handled
 * before the UI can show something useful.
 */
export function getErrorMessage(error: unknown, fallback = "Something went wrong"): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorBody>;
    const detail = axiosError.response?.data?.detail;
    if (typeof detail === "string" && detail.length > 0) {
      return detail;
    }
    if (axiosError.code === "ECONNABORTED") {
      return "The request timed out. Please try again.";
    }
    if (!axiosError.response) {
      return "Cannot reach the CAREVERSE server. Is the API running?";
    }
  }
  return fallback;
}

/** Machine-readable error code, used to branch on specific failures. */
export function getErrorCode(error: unknown): string | undefined {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorBody>;
    return axiosError.response?.data?.code;
  }
  return undefined;
}

export function isUnauthorized(error: unknown): boolean {
  const status = axios.isAxiosError(error)
    ? (error as AxiosError).response?.status
    : undefined;
  return status === 401;
}
