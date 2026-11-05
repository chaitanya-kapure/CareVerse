 /** Doctor-facing read endpoints. */

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

   /** Fetch the original PDF as bytes. */
  async fetchOriginal(patientId: string, documentId: string): Promise<Blob> {
    const { data } = await api.get<Blob>(
      `${BASE}/${patientId}/documents/${documentId}/file`,
      { responseType: "blob", timeout: 120_000 },
    );
    return data;
  },
};
