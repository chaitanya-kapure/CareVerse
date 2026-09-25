/**
 * Shared API types.
 *
 * These mirror the Pydantic schemas in `server/app/schemas/`. When a
 * response shape changes, both sides change together.
 */

export type UserRole = "patient" | "doctor";

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  name: string;
  email: string;
  password: string;
  role: UserRole;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface HealthStatus {
  status: "ok" | "degraded";
  database: "connected" | "unavailable";
  environment: string;
  ai_provider: string;
}

/** The single error envelope every CAREVERSE endpoint returns. */
export interface ApiErrorBody {
  detail: string;
  code?: string;
}

// --- Phase 2: patient profile + documents -------------------------------
// Declared now so the API service has a stable target; the endpoints
// arrive with the Phase 2 backend.

export interface PatientProfile {
  id: string;
  patient_id: string;
  full_name: string;
  date_of_birth: string | null;
  gender: "male" | "female" | "other" | "unspecified";
  phone: string | null;
  address: string | null;
  notes: string | null;
}

export type ExtractionStatus =
  | "pending"
  | "processing"
  | "completed"
  | "needs_ocr"
  | "failed";

export interface MedicalDocumentSummary {
  id: string;
  patient_id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  title: string;
  category: string;
  document_date: string | null;
  extraction_status: ExtractionStatus;
  extraction_error: string | null;
  page_count: number | null;
  character_count: number;
  uploaded_at: string;
  has_text: boolean;
}

export interface MedicalDocumentDetail extends MedicalDocumentSummary {
  extracted_text: string | null;
  extracted_data: Record<string, unknown>;
}

// --- Phase 3: authorization + summary -----------------------------------

export interface AuthorizedPatient {
  id: string;
  patient_id: string;
  patient_name: string;
  status: "active" | "revoked";
  granted_at: string;
  revoked_at: string | null;
  note: string | null;
}

export interface SummarySection {
  key: string;
  title: string;
  items: Array<string | Record<string, unknown>>;
  empty_note?: string | null;
}

export interface PatientSummary {
  id: string;
  patient_id: string;
  provider: string;
  is_mock: boolean;
  model: string | null;
  disclaimer: string;
  overview: string;
  sections: SummarySection[];
  source_document_ids: string[];
  source_document_count: number;
  unreadable_document_count: number;
  generated_at: string;
}
