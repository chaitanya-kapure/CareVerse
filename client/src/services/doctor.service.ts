/**
 * Doctor-facing read endpoints.
 *
 * Every path is nested under a patient id, and the server authorizes that id
 * on every single call -- so this module holds no authorization logic of its
 * own and no client-side flag decides what the doctor sees. The 403 the
 * server returns is the enforcement point, not a condition handled here.
 *
 * The response types are the Phase 2 ones. A doctor's view of a record and a
 * patient's view of that same record are the same object, which is why this
 * file reuses `DocumentListResponse` and `MedicalDocumentDetail` instead of
 * declaring doctor-flavoured copies.
 */

import { api } from "./api";
import type {
  DoctorPatientListResponse,
  DocumentListResponse,
  MedicalDocumentDetail,
  PatientProfile,
} from "../types";

const BASE = "/doctor/patients";

export const doctorService = {
  /** The patients who have authorized this doctor. Never a filtered list of all patients. */
  async listPatients(): Promise<DoctorPatientListResponse> {
    const { data } = await api.get<DoctorPatientListResponse>(BASE);
    return data;
  },

  async getPatient(patientId: string): Promise<PatientProfile> {
    const { data } = await api.get<PatientProfile>(`${BASE}/${patientId}`);
    return data;
  },

  async listDocuments(patientId: string): Promise<DocumentListResponse> {
    const { data } = await api.get<DocumentListResponse>(
      `${BASE}/${patientId}/documents`,
    );
    return data;
  },

  async getDocument(
    patientId: string,
    documentId: string,
  ): Promise<MedicalDocumentDetail> {
    const { data } = await api.get<MedicalDocumentDetail>(
      `${BASE}/${patientId}/documents/${documentId}`,
    );
    return data;
  },

  /**
   * Fetch the original PDF as bytes.
   *
   * Fetched rather than linked, because the browser cannot attach a bearer
   * token when a user clicks a plain `<a>` -- the request would be
   * unauthenticated and 401. The caller turns the Blob into an object URL.
   */
  async fetchOriginal(patientId: string, documentId: string): Promise<Blob> {
    const { data } = await api.get<Blob>(
      `${BASE}/${patientId}/documents/${documentId}/file`,
      { responseType: "blob", timeout: 120_000 },
    );
    return data;
  },
};
