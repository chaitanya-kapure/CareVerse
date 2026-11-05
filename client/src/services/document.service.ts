 /** Medical document endpoints. */

import { api } from "./api";
import type {
  DocumentListResponse,
  DocumentUploadForm,
  MedicalDocumentDetail,
} from "../types";

const BASE = "/patients/me/documents";

export const documentService = {
  async list(): Promise<DocumentListResponse> {
    const { data } = await api.get<DocumentListResponse>(BASE);
    return data;
  },

  async get(documentId: string): Promise<MedicalDocumentDetail> {
    const { data } = await api.get<MedicalDocumentDetail>(`${BASE}/${documentId}`);
    return data;
  },

  async upload(form: DocumentUploadForm): Promise<MedicalDocumentDetail> {
    const body = new FormData();
    body.append("file", fileWithPdfType(form.file));
    // Only the fields the patient actually filled in. Sending empty strings
    // would make the server treat them as provided and reject a blank date.
    if (form.title?.trim()) body.append("title", form.title.trim());
    if (form.category) body.append("category", form.category);
    if (form.document_date) body.append("document_date", form.document_date);

    const { data } = await api.post<MedicalDocumentDetail>(BASE, body, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 120_000, // a 15 MB upload on a slow connection is not an error
    });
    return data;
  },

  async remove(documentId: string): Promise<void> {
    await api.delete(`${BASE}/${documentId}`);
  },

   /** Fetch the original PDF as bytes. */
  async fetchOriginal(documentId: string): Promise<Blob> {
    const { data } = await api.get<Blob>(`${BASE}/${documentId}/file`, {
      responseType: "blob",
      timeout: 120_000,
    });
    return data;
  },
};

 /** Some desktops leave `File.type` empty even for a `.pdf`, which would make */
function fileWithPdfType(file: File): File {
  if (file.type || !file.name.toLowerCase().endsWith(".pdf")) return file;
  return new File([file], file.name, { type: "application/pdf" });
}
