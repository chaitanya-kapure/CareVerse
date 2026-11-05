 /** The patient summary, for both audiences. */

import { api } from "./api";
import type { PatientSummary } from "../types";

const DOCTOR_BASE = "/doctor/patients";

export const summaryService = {
  /** An authorized doctor's view. Generated on demand when missing or stale. */
  async getForPatient(patientId: string): Promise<PatientSummary> {
    const { data } = await api.get<PatientSummary>(
      `${DOCTOR_BASE}/${patientId}/summary`,
    );
    return data;
  },

   /** Force a rebuild, ignoring the staleness check. */
  async regenerate(patientId: string): Promise<PatientSummary> {
    const { data } = await api.post<PatientSummary>(
      `${DOCTOR_BASE}/${patientId}/summary/regenerate`,
    );
    return data;
  },

  /** The signed-in patient's own summary. There is no id to change. */
  async getOwn(): Promise<PatientSummary> {
    const { data } = await api.get<PatientSummary>("/patients/me/summary");
    return data;
  },
};
