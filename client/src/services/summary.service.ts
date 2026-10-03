/**
 * The patient summary, for both audiences.
 *
 * Two call sites, one response shape. A patient reading their own summary and
 * a doctor reading that patient's summary are reading the same document, so
 * there is one function here rather than a patient copy and a doctor copy
 * that could drift apart.
 *
 * The `patientId` in the doctor paths is attacker-controlled input as far as
 * the browser is concerned, and this module passes it straight through. That
 * is safe only because the server authorizes it on every call — an ungranted
 * or nonexistent patient both come back `403 NO_PATIENT_ACCESS`, and neither
 * this file nor any screen decides what a doctor may read.
 */

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

  /**
   * Force a rebuild, ignoring the staleness check.
   *
   * A POST because there is nothing to edit: every line in a summary is copied
   * from a record, so the only response to a summary that looks wrong is to
   * read the records again.
   */
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
