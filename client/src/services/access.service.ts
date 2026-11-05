 /** Patient-side doctor authorization. */

import { api } from "./api";
import type {
  AccessGrant,
  AccessGrantListResponse,
  AccessGrantRequest,
} from "../types";

const BASE = "/patients/me/access";

export const accessService = {
   /** Every grant this patient has issued, including revoked ones. */
  async list(): Promise<AccessGrantListResponse> {
    const { data } = await api.get<AccessGrantListResponse>(BASE);
    return data;
  },

  async grant(payload: AccessGrantRequest): Promise<AccessGrant> {
    const { data } = await api.post<AccessGrant>(BASE, payload);
    return data;
  },

  /** Ends access immediately; the server re-checks the grant on every request. */
  async revoke(accessId: string): Promise<AccessGrant> {
    const { data } = await api.delete<AccessGrant>(`${BASE}/${accessId}`);
    return data;
  },
};
