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

// --- Password reset -------------------------------------------------------
// Three requests and three responses, one per step. The `reset_token` is
// opaque and single-use: it is not a session and grants nothing but one
// password change.

export interface ForgotPasswordPayload {
  email: string;
}

export interface ForgotPasswordResponse {
  detail: string;
  code: string;
  /** Constant, not a measurement of this request, so it leaks nothing. */
  retry_after_seconds: number;
  /** Configured OTP lifetime, matching the server's own clock. */
  expires_in: number;
}

export interface VerifyOtpPayload {
  email: string;
  otp: string;
}

export interface VerifyOtpResponse {
  reset_token: string;
  expires_in: number;
  detail: string;
}

export interface ResetPasswordPayload {
  reset_token: string;
  new_password: string;
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

/**
 * PATCH body for the profile. Every field is optional and `null` means
 * "clear this" -- omitting a field leaves it untouched, which is why there
 * is no `Partial<>` variant that would make omission and clearing identical.
 */
export interface PatientProfileUpdate {
  full_name?: string | null;
  date_of_birth?: string | null;
  gender?: "male" | "female" | "other" | "unspecified" | null;
  phone?: string | null;
  address?: string | null;
  notes?: string | null;
}

/** Shape of `GET /patients/me/documents`. */
export interface DocumentListResponse {
  items: MedicalDocumentSummary[];
  total: number;
}

/**
 * Fields the upload form collects alongside the file.
 *
 * All optional: a patient who just wants their report filed can drop the PDF
 * in and go. The server derives a title from the filename when it is empty.
 */
export interface DocumentUploadForm {
  file: File;
  title?: string;
  category?: string;
  document_date?: string;
}

// --- Phase 3: doctor access ---------------------------------------------
//
// One row in `patient_access`, as the patient who created it sees it. The
// doctor side of the same relationship is `DoctorPatientSummary` below.

export type AccessStatus = "active" | "revoked";

export interface AccessGrant {
  id: string;
  patient_id: string;
  doctor_id: string;
  doctor_name: string;
  status: AccessStatus;
  granted_at: string | null;
  revoked_at: string | null;
  note: string | null;
}

export interface AccessGrantListResponse {
  items: AccessGrant[];
  total: number;
}

export interface AccessGrantRequest {
  doctor_id: string;
  note?: string;
}

/**
 * One row in the doctor's list of patients they may read.
 *
 * The doctor never receives a grant id, a note, or anything about the
 * relationship's history -- only the patient themselves and what they would
 * already see in their own profile. `document_count` is a count of stored
 * files, not a clinical measure.
 */
export interface DoctorPatientSummary {
  patient_id: string;
  full_name: string;
  date_of_birth: string | null;
  gender: string;
  document_count: number;
  has_profile: boolean;
}

export interface DoctorPatientListResponse {
  items: DoctorPatientSummary[];
  total: number;
}

// --- Phase 4: AI summary (not implemented) ------------------------------
// Declared ahead of the endpoints so the shape is settled. Nothing in the
// app imports these yet, and no screen renders a summary.

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
