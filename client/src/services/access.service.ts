/**
 * Patient-side doctor authorization.
 *
 * This is the only way access comes into existence. A patient names a doctor
 * and the server records one grant; there is no request from the doctor, no
 * invitation, no approval queue and no way to enumerate the patients in the
 * system. The patient's id is never sent from the browser -- the server
 * derives it from the session -- so this call cannot be aimed at anyone else.
 */

import { api } from "./api";
import type {
  AccessGrant,
  AccessGrantListResponse,
  AccessGrantRequest,
} from "../types";

const BASE = "/patients/me/access";

export const accessService = {
  /**
   * Every grant this patient has issued, including revoked ones.
   *
   * A patient is entitled to see who *used to* have access, so the list is not
   * filtered to live grants.
   */
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
