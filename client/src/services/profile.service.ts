/** Patient profile endpoints. Thin wrapper so components never call axios. */

import { api } from "./api";
import type { PatientProfile, PatientProfileUpdate } from "../types";

export const profileService = {
  async get(): Promise<PatientProfile> {
    const { data } = await api.get<PatientProfile>("/patients/me");
    return data;
  },

  /**
   * Partial update. Only the keys present are sent, so a form that does not
   * own a field cannot blank it -- the server treats an omitted key as
   * "leave it alone" and an explicit `null` as "clear it".
   */
  async update(payload: PatientProfileUpdate): Promise<PatientProfile> {
    const { data } = await api.patch<PatientProfile>("/patients/me", payload);
    return data;
  },
};
