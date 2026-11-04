# CAREVERSE — Centralized Health Records & AI Clinical Summarization Platform

> **Academic & Technical Project Specification / Engineering Report Guide**  
> *Centralized, patient-governed health records with traceable, verifiable, AI-assisted clinical summaries.*

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement & Academic Context](#2-problem-statement--academic-context)
3. [Core Principles & Medical-Safety Guardrails](#3-core-principles--medical-safety-guardrails)
4. [System Architecture](#4-system-architecture)
   - [Architectural Topology](#architectural-topology)
   - [Technology Stack Justification](#technology-stack-justification)
   - [Design Patterns Employed](#design-patterns-employed)
5. [End-to-End System Workflows](#5-end-to-end-system-workflows)
   - [User Authentication & Session Lifecycle](#workflow-1-authentication--session-lifecycle)
   - [Document Upload, Validation & Extraction Pipeline](#workflow-2-document-upload-validation--extraction-pipeline)
   - [Doctor-Patient Access Control & Authorization](#workflow-3-doctor-patient-access-control--authorization)
   - [Clinical Summarization & Provenance Linking](#workflow-4-clinical-summarization--provenance-linking)
6. [Database Architecture & Data Dictionary](#6-database-architecture--data-dictionary)
   - [Collections & Schemas](#collections--schemas)
   - [Indexing Strategy](#indexing-strategy)
7. [Comprehensive API Reference](#7-comprehensive-api-reference)
   - [Authentication & Recovery Endpoints](#public-authentication--recovery)
   - [Patient Endpoints](#patient-endpoints)
   - [Doctor Endpoints](#doctor-endpoints)
   - [Standard Error Envelope](#standard-error-envelope)
8. [Security, Privacy & Defensive Engineering](#8-security-privacy--defensive-engineering)
9. [Project Directory Layout](#9-project-directory-layout)
10. [Installation & Execution Guide](#10-installation--execution-guide)
11. [Verification & Testing Strategy](#11-verification--testing-strategy)
12. [Project Roadmap & Future Scope](#12-project-roadmap--future-scope)

---

## 1. Executive Summary

In contemporary healthcare ecosystems, a patient's medical history is fragmented across disparate diagnostic laboratories, multi-specialty hospitals, local clinics, and pharmacy receipts. When consulting a new healthcare provider, patients typically present an unorganized assortment of paper files or digital PDFs. Doctors are forced to expend valuable clinical consultation time manually scanning pages of unstructured reports instead of diagnosing and treating the patient.

**CAREVERSE** is an enterprise-grade, student-analyzed web platform designed to solve medical record fragmentation. It provides:
1. **Patient-Governed Centralization:** A unified portal where patients upload, manage, and securely store their diagnostic PDFs (lab reports, discharge summaries, prescriptions).
2. **Deterministic Information Extraction:** Automatic, offline extraction of clinical text and structured data (dates, lab markers, reference ranges, dosages, stated diagnoses).
3. **Traceable AI Summaries:** A consolidated 8-section clinical briefing synthesized for doctors, where **every single clinical assertion carries a verifiable citation (`source_document_id` and exact source quote)** pointing back to the patient's original record.
4. **Zero-Hallucination & Non-Diagnostic Guarantee:** The platform explicitly avoids medical diagnosis, treatment suggestions, or risk calculations. If a clinical data point is not in the uploaded documents, the system reports *"Not found in the uploaded records."*

---

## 2. Problem Statement & Academic Context

### The Healthcare Challenge
- **Information Fragmentation:** Patients rarely possess a continuous, consolidated Electronic Health Record (EHR). When moving across healthcare facilities, longitudinal history is frequently lost.
- **Cognitive Overload for Physicians:** A standard medical consultation lasts 15–20 minutes. Parsing 30–50 pages of unstructured PDF test reports consumes 50–70% of this time, increasing physician burnout and the risk of overlooked anomalies.
- **Consent & Privacy Deficits:** Conventional file-sharing mechanisms (emailing PDFs, messaging apps) lack granular consent mechanisms, audit trails, or instant access revocation.

### Project Objectives
| Objective | Engineering Implementation |
|---|---|
| **Consolidated Profile** | Strict 1:1 mapping between patient user accounts and medical profiles. |
| **Strict Consent Control** | Zero doctor access by default; access requires an active, patient-initiated authorization grant. |
| **Complete Traceability** | Bidirectional provenance: click any summary point in the UI to highlight the underlying source PDF line. |
| **Safe AI Integration** | Decoupled "Provider Seam" pattern: runs offline and deterministically by default; falls back gracefully during external API failure. |

---

## 3. Core Principles & Medical-Safety Guardrails

> [!IMPORTANT]
> **CAREVERSE is an administrative and summarization assistant, NOT a Medical Device or Diagnostic Decision Support System (CDSS).**

To satisfy ethical computing standards and medical safety regulations, CAREVERSE strictly enforces the following rules at both code and prompt levels:

1. **Summarization, Not Interpretation:** The system restates documented facts. It never predicts progression, checks drug interactions, or infers undiagnosed illnesses from isolated laboratory markers.
2. **Grounded Provenance (Anti-Hallucination):** No summary statement can exist without a verifiable link to an existing document owned by that specific patient. Statements without proof are discarded.
3. **Explicit Absence of Data:** Rather than hallucinating or leaving gaps, empty summary sections explicitly declare: `"Not found in the uploaded records."`
4. **Untrusted Input Hygiene:** Patient PDFs and user notes are treated as untrusted clinical data payloads, never as prompt instructions (protecting against Prompt Injection attacks).
5. **No Medical Copy in Component Logic:** All safety disclaimers and notices are centralized in [`client/src/utils/disclaimers.ts`](client/src/utils/disclaimers.ts) and [`server/app/config.py`](server/app/config.py).

---

## 4. System Architecture

CAREVERSE is structured around a decoupled, layered client-server architecture with strict separation of concerns.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER (SPA)                              │
│             React 18 · TypeScript · Vite · Tailwind CSS                │
│   Pages (Patient/Doctor) → Contexts (Auth) → TanStack Query → Axios    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTPS + Bearer JWT
                                    │ Vite Proxy (/api/* → :8000)
┌───────────────────────────────────▼────────────────────────────────────┐
│                       SERVER LAYER (FASTAPI)                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Middlewares: JWT Auth · Role Enforcement · Error Envelopes       │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ Routes & Schemas: Pydantic Validation & Route Handlers           │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ Controllers: Thin orchestration & HTTP status dispatch           │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ Services (Business Logic):                                       │  │
│  │   • AuthService (Bcrypt, JWT)     • DocumentService (Validation) │  │
│  │   • AccessService (Grants/RBAC)   • StructuredExtractionService  │  │
│  │   • SummaryService (Provider Seam)                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└───────────────────────┬───────────────────────────────┬────────────────┘
                        │                               │
             ┌──────────▼──────────┐         ┌──────────▼──────────┐
             │   MongoDB (PyMongo) │         │  Local Disk Storage │
             │  • users            │         │  (Opaque UUID filenames,
             │  • patient_profiles │         │   MIME validated)   │
             │  • medical_documents│         └─────────────────────┘
             │  • patient_access   │         ┌─────────────────────┐
             │  • patient_summaries│         │  AI Provider Seam   │
             │  • password_resets  │◄───────►│  • Mock (Default)   │
             └─────────────────────┘         │  • OpenAI Endpoint  │
                                             └─────────────────────┘
```

### Technology Stack Justification

| Layer | Chosen Technology | Engineering Rationale |
|---|---|---|
| **Frontend Framework** | **React 18 + TypeScript** | Component-driven reactivity, strict compile-time type safety across API contracts, and robust state management. |
| **Build Tool** | **Vite 5** | Lightning-fast Hot Module Replacement (HMR) and optimized ES module bundling. |
| **Styling** | **Tailwind CSS** | Utility-first CSS ensuring lightweight styles, standard UI tokens, and high accessibility consistency. |
| **Client State** | **TanStack Query (React Query)** | Automatic caching, background refetching, query invalidation, and declarative loading/error states. |
| **Backend Framework** | **FastAPI (Python 3.11+)** | High-performance asynchronous API execution, native Python medical/PDF processing support, and automatic OpenAPI/Swagger generation. |
| **Data Validation** | **Pydantic v2** | Blazing-fast Rust-based data validation and strict serialization envelopes for all request/response models. |
| **Database** | **MongoDB (via PyMongo)** | Schema flexibility for dynamic clinical reports, nested laboratory arrays, and native TTL indexing for transient OTPs. |
| **PDF Extraction** | **pypdf** | Pure Python, memory-efficient PDF text parser without heavy external runtime dependencies. |
| **Authentication** | **PyJWT + Bcrypt** | Cryptographically salted password hashing combined with stateless HS256 JSON Web Tokens. |

### Design Patterns Employed

1. **Provider Seam Pattern (AI Summarization & Email):**
   - Summarization logic sits behind an abstract provider interface.
   - `MockSummaryProvider`: Default engine. Deterministic, runs 100% offline, costs zero dollars, reproducible for student evaluations.
   - `OpenAISummaryProvider`: Pluggable LLM provider for live demonstrations. If the external provider experiences network latency, rate limits, or outages, the system automatically falls back to the deterministic mock engine without disrupting the user.
2. **Storage Driver Interface:**
   - File persistence is decoupled behind a storage contract (`StorageDriver`), allowing switching between local disk storage and cloud object stores (AWS S3, Azure Blob) without changing core service logic.
3. **Single Authorization Boundary:**
   - Instead of duplicating permission checks inside individual controllers, access validation is centralized in `assert_patient_access`. This middleware acts as a single gatekeeper enforcing explicit ownership or active grants.

---

## 5. End-to-End System Workflows

### Workflow 1: Authentication & Session Lifecycle
```
User Enters Credentials 
       │
       ▼
POST /auth/login
       │
       ├──► Normalize Email (lowercase, strip)
       ├──► Execute constant-time bcrypt verification (dummy hash on miss to prevent timing attacks)
       └──► Issue signed JWT: { sub: user_id, role: "patient"|"doctor", exp: +60m }
```
- **Password Reset Sub-System:**
  - `POST /auth/forgot-password` generates a cryptographically secure 6-digit OTP.
  - The OTP is hashed using slow **Bcrypt** (`$2b$12$...`) before storing in `password_reset_otps` (protecting against brute-force attacks).
  - MongoDB automatically deletes expired OTPs via a **TTL index** on `expires_at`.
  - Once verified, the OTP is exchanged for a single-use 256-bit URL-safe reset token (hashed with unsalted SHA-256 for fast O(1) indexed lookup).

### Workflow 2: Document Upload, Validation & Extraction Pipeline
```
Patient selects PDF 
       │
       ▼
Client (FormData) ──► POST /patients/me/documents
                            │
                            ├──► 1. Magic Byte Validation: verifies first bytes match `%PDF-`
                            ├──► 2. MIME Type Verification: ensures application/pdf
                            ├──► 3. File Size Guard: enforces MAX_UPLOAD_MB (10 MB cap)
                            ├──► 4. Storage Quarantine: saves file with randomized UUID
                            ├──► 5. Text Extraction (pypdf): parses character streams
                            └──► 6. Deterministic Structured Extraction:
                                      • Date detection (ISO YYYY-MM-DD)
                                      • Laboratory values, units, reference flags
                                      • Prescriptions & dosages
                                      • Stated medical diagnoses
```
> **Honest Failure Resilience:** If a PDF is image-based or encrypted, upload still succeeds (`201 Created`), marking `extraction_status = "needs_ocr"` or `"failed"`. The system never misreports an unparsed PDF as a server crash.

### Workflow 3: Doctor-Patient Access Control & Authorization
```
Patient Dashboard                    Doctor Dashboard
       │                                    │
       ▼                                    ▼
Grants Access (POST /patients/me/access)    Logs in & calls GET /doctor/patients
       │                                    │
       ▼                                    ▼
Writes to `patient_access` collection       DB returns ONLY patients with active grants
(Indexed by doctor_id + patient_id)         │
                                            ▼
                                     Doctor views records:
                                     GET /doctor/patients/{id}/documents
                                            │
                                            ▼
                                     assert_patient_access() checks:
                                     1. Is caller's role == "doctor"?
                                     2. Does active grant exist in DB?
                                     (If No: HTTP 403 NO_PATIENT_ACCESS)
```

### Workflow 4: Clinical Summarization & Provenance Linking
```
Doctor requests summary: GET /doctor/patients/{id}/summary
                            │
                            ▼
             Check Cache in `patient_summaries`
             ├──► Cache Hit & Fresh? ──► Return stored summary
             └──► Missing or Stale?
                       │
                       ▼
             Fetch all completed documents for patient
                       │
                       ▼
             Summary Engine (Mock or OpenAI via Provider Seam)
                       │
                       ├──► Generates 8 Standard Clinical Sections:
                       │    1. Demographics & Overview
                       │    2. Chronic Conditions
                       │    3. Active Medications & Dosages
                       │    4. Critical Laboratory Results
                       │    5. Surgical & Hospitalization History
                       │    6. Allergies & Known Adverse Reactions
                       │    7. Immunization & Preventive Care
                       │    8. Recent Clinical Observations
                       │
                       ├──► Provenance Enforcement:
                       │    Every item MUST cite an authentic source_document_id
                       │    and quote the exact source text.
                       └──► Cache result in MongoDB & stream response
```

---

## 6. Database Architecture & Data Dictionary

CAREVERSE utilizes **MongoDB** with strict schema patterns defined via Pydantic models.

### Collections & Schemas

#### 1. `users`
Stores system accounts for authentication and role-based permissions.
```jsonc
{
  "_id": ObjectId("..."),
  "name": "Jane Doe",
  "email": "jane@example.com",       // Lowercased, UNIQUE index
  "password_hash": "$2b$12$...",     // Salted bcrypt hash
  "role": "patient",                 // Enum: "patient" | "doctor"
  "status": "active",                // Enum: "active" | "suspended"
  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

#### 2. `patient_profiles`
Maintains demographic details. Created automatically upon patient registration.
```jsonc
{
  "_id": ObjectId("..."),
  "patient_id": "67a3...",           // Foreign key -> users._id (UNIQUE)
  "full_name": "Jane Doe",
  "date_of_birth": "1994-06-15",     // YYYY-MM-DD
  "gender": "female",                // "male" | "female" | "other" | "unspecified"
  "phone": "+1-555-0199",
  "address": "42 Health Ave",
  "notes": "Penicillin allergy noted in 2021", // Patient's personal notes
  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

#### 3. `medical_documents`
Represents uploaded clinical PDFs, extraction metadata, and structured clinical findings.
```jsonc
{
  "_id": ObjectId("..."),
  "patient_id": "67a3...",           // Owner ID
  "original_filename": "blood_panel.pdf",
  "stored_filename": "a8f3...pdf",   // Sanitized UUID on disk
  "storage_driver": "local",
  "storage_key": "a8f3...pdf",
  "mime_type": "application/pdf",
  "size_bytes": 245100,
  "title": "Complete Metabolic Panel",
  "category": "lab_report",          // lab_report | prescription | discharge_summary | imaging | other
  "document_date": "2025-10-12",
  "extraction_status": "completed",  // pending | processing | completed | needs_ocr | failed
  "extraction_error": null,
  "page_count": 2,
  "character_count": 3410,
  "extracted_text": "...",           // Raw parsed text
  "extracted_data": {
    "report_title": "Metabolic Panel",
    "document_date": "2025-10-12",
    "lab_values": [
      {
        "name": "Fasting Blood Sugar",
        "value": "135",
        "unit": "mg/dL",
        "reference_range": "70-99",
        "flag": "high",
        "source_text": "Fasting Blood Sugar: 135 mg/dL (Normal: 70-99)"
      }
    ],
    "medications": [
      {
        "name": "Metformin",
        "dosage": "500 mg",
        "frequency": "Once daily",
        "source_text": "Rx: Metformin 500mg daily"
      }
    ],
    "stated_conditions": [
      { "text": "Impaired Fasting Glucose", "source_text": "Impression: Impaired Fasting Glucose" }
    ]
  },
  "uploaded_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

#### 4. `patient_access`
Explicit authorization grants issued by patients to doctors.
```jsonc
{
  "_id": ObjectId("..."),
  "patient_id": "67a3...",           // Grantor
  "doctor_id": "67b9...",            // Grantee
  "status": "active",                // "active" | "revoked"
  "granted_at": ISODate("..."),
  "revoked_at": null,
  "note": "Consultation for endocrinology"
}
```

#### 5. `patient_summaries`
Cached clinical summaries generated on-demand.
```jsonc
{
  "_id": ObjectId("..."),
  "patient_id": "67a3...",           // UNIQUE (one summary per patient)
  "provider": "mock",                // "mock" | "openai"
  "is_mock": true,                   // Flag to display visual badge in UI
  "model": null,
  "disclaimer": "AI-generated summary of available records...",
  "overview": "30-year-old female with documented metabolic records...",
  "sections": [
    {
      "key": "lab_values",
      "title": "Important Lab Values",
      "items": [
        {
          "text": "Elevated Fasting Blood Glucose (135 mg/dL)",
          "source_document_id": "67c1...",
          "source_text": "Fasting Blood Sugar: 135 mg/dL (Normal: 70-99)"
        }
      ],
      "empty_note": "Not found in the uploaded records."
    }
  ],
  "source_document_ids": ["67c1..."],
  "source_document_count": 1,
  "unreadable_document_count": 0,
  "generated_at": ISODate("...")
}
```

#### 6. `password_reset_otps`
Ephemeral collection for handling self-service account recovery.
```jsonc
{
  "_id": ObjectId("..."),
  "user_id": "67a3...",
  "email": "jane@example.com",
  "otp_hash": "$2b$12$...",          // Salted Bcrypt hash of 6 digits
  "attempts": 0,                     // Max 5 attempts
  "max_attempts": 5,
  "expires_at": ISODate("..."),      // Automatically purged by Mongo TTL
  "reset_token_hash": "...",         // Unsalted SHA-256 of 256-bit token
  "reset_token_expires_at": ISODate("..."),
  "created_at": ISODate("..."),
  "verified_at": null,
  "consumed_at": null
}
```

### Indexing Strategy

| Collection | Indexed Fields | Index Type | Purpose |
|---|---|---|---|
| `users` | `email` | Unique | Enforces single account per email address |
| `patient_profiles` | `patient_id` | Unique | Enforces 1:1 user-to-profile relationship |
| `medical_documents` | `(patient_id, uploaded_at DESC)` | Compound | Fast retrieval of patient's documents newest-first |
| `patient_access` | `(doctor_id, patient_id)` | Compound | Accelerates doctor patient-list lookups |
| `patient_access` | `(doctor_id, patient_id)` where `status == "active"` | Partial Unique | Guarantees no duplicate active grants concurrently |
| `patient_summaries` | `patient_id` | Unique | One cached summary record per patient |
| `password_reset_otps` | `expires_at` | TTL (`expireAfterSeconds: 0`) | Automatic background database cleanup |
| `password_reset_otps` | `reset_token_hash` | Sparse / Single | O(1) password reset token resolution |

---

## 7. Comprehensive API Reference

Base URL in local development: `http://localhost:8000`  
Client proxy prefix: `http://localhost:5173/api`

### Public Authentication & Recovery

| Method | Endpoint | Description | Status Codes |
|---|---|---|---|
| `GET` | `/health` | Server status, DB connection & AI provider info | `200` OK, `503` Degraded |
| `POST` | `/auth/register` | Register new user (`patient` or `doctor`) | `201` Created, `409` Conflict |
| `POST` | `/auth/login` | Authenticate and obtain JWT access token | `200` OK, `401` Unauthorized |
| `GET` | `/auth/me` | Retrieve profile and role of authenticated caller | `200` OK, `401` Unauthorized |
| `POST` | `/auth/logout` | Client logout acknowledgement | `200` OK |
| `POST` | `/auth/forgot-password` | Request 6-digit password recovery OTP | `200` OK |
| `POST` | `/auth/verify-reset-otp` | Submit OTP to receive single-use reset token | `200` OK, `400` Invalid OTP |
| `POST` | `/auth/reset-password` | Submit reset token and new password | `200` OK, `400` Expired/Invalid |

### Patient Endpoints
*Requires `Authorization: Bearer <JWT>` with role `patient`.*

| Method | Endpoint | Description | Status Codes |
|---|---|---|---|
| `GET` | `/patients/me` | View authenticated patient's profile | `200` OK |
| `PATCH` | `/patients/me` | Update demographic fields (`full_name`, `dob`, `gender`, etc.) | `200` OK, `422` Validation |
| `GET` | `/patients/me/documents` | List patient's uploaded documents | `200` OK |
| `POST` | `/patients/me/documents` | Upload new medical document (Multipart Form PDF) | `201` Created, `415` Bad File |
| `GET` | `/patients/me/documents/{docId}` | Get metadata, extracted text & structured data | `200` OK, `404` Not Found |
| `DELETE` | `/patients/me/documents/{docId}` | Permanently delete document and physical file | `200` OK, `404` Not Found |
| `GET` | `/patients/me/documents/{docId}/file`| Stream original PDF file securely | `200` OK, `404` Not Found |
| `GET` | `/patients/me/summary` | View own patient clinical summary | `200` OK |
| `GET` | `/patients/me/access` | List all doctor authorizations (active + revoked) | `200` OK |
| `POST` | `/patients/me/access` | Authorize doctor access (`doctor_id`, `note`) | `201` Created, `409` Exists |
| `DELETE` | `/patients/me/access/{accessId}` | Immediately revoke doctor access grant | `200` OK, `404` Not Found |

### Doctor Endpoints
*Requires `Authorization: Bearer <JWT>` with role `doctor`.*

| Method | Endpoint | Description | Status Codes |
|---|---|---|---|
| `GET` | `/doctor/patients` | List only patients who actively authorized this doctor | `200` OK |
| `GET` | `/doctor/patients/{patientId}` | View authorized patient's demographic profile | `200` OK, `403` Forbidden |
| `GET` | `/doctor/patients/{patientId}/documents` | View authorized patient's document list | `200` OK, `403` Forbidden |
| `GET` | `/doctor/patients/{patientId}/documents/{docId}` | View specific document & extracted findings | `200` OK, `403` Forbidden |
| `GET` | `/doctor/patients/{patientId}/documents/{docId}/file` | Stream authorized patient's original PDF | `200` OK, `403` Forbidden |
| `GET` | `/doctor/patients/{patientId}/summary` | Retrieve or generate patient's clinical summary | `200` OK, `403` Forbidden |
| `POST` | `/doctor/patients/{patientId}/summary/regenerate` | Discard existing summary cache and rebuild | `200` OK, `403` Forbidden |

### Standard Error Envelope

Every application error returns a predictable, standardized JSON envelope:
```json
{
  "detail": "Descriptive, human-readable error explanation.",
  "code": "STANDARD_MACHINE_ERROR_CODE"
}
```

Common error codes:
- `MISSING_TOKEN` / `INVALID_TOKEN` (HTTP 401)
- `INVALID_CREDENTIALS` (HTTP 401)
- `NO_PATIENT_ACCESS` (HTTP 403)
- `ROLE_NOT_ALLOWED` (HTTP 403)
- `NOT_RECORD_OWNER` (HTTP 403)
- `UNSUPPORTED_FILE_TYPE` (HTTP 415)
- `FILE_TOO_LARGE` (HTTP 413)
- `DOCUMENT_NOT_FOUND` (HTTP 404)
- `DATABASE_UNAVAILABLE` (HTTP 503)

---

## 8. Security, Privacy & Defensive Engineering

1. **Insecure Direct Object Reference (IDOR) Mitigation:**
   - Patient routes omit URL identifiers entirely (utilizing `/patients/me/*`), resolving the target ID purely from the authenticated JWT claims.
   - Doctor routes pass through `assert_patient_access`, which verifies database-backed authorization grants before touching records.
2. **Path Traversal & Storage Sanitization:**
   - Uploaded files are renamed using cryptographic UUIDs before being saved to disk.
   - User-supplied filenames (`original_filename`) are stored solely for client-side UI display.
3. **Timing Attack Resistance:**
   - When a login attempt fails for a non-existent email, a dummy Bcrypt hash is computed anyway, preventing attackers from enumerating accounts via response latency differences.
4. **Header Hardening:**
   - All PDF streaming responses include strict defensive headers:
     ```http
     Content-Type: application/pdf
     X-Content-Type-Options: nosniff
     Content-Security-Policy: default-src 'none'
     Cache-Control: private, no-cache, no-store
     ```

---

## 9. Project Directory Layout

```
careverse/
├── package.json               # Root scripts (starts client + server concurrently)
├── README.md                  # Comprehensive project specification & report guide
├── AGENTS.md                  # Repository protocols, git workflow & safety rules
├── docs/
│   └── ARCHITECTURE.md        # Technical specification of record (schemas, rules)
│
├── client/                    # React 18 + Vite frontend
│   ├── src/
│   │   ├── components/        # Reusable UI & medical widgets
│   │   │   ├── ExtractionBadge.tsx      # Visual parser status
│   │   │   ├── ExtractionPanel.tsx      # Dual-pane text viewer
│   │   │   ├── SummarySectionCard.tsx   # Summaries with provenance links
│   │   │   └── ui/                      # Atoms: Button, Card, Modal, Alert
│   │   ├── context/           # Session & Auth state providers
│   │   ├── layouts/           # AppShell (Sidebar/Header) & AuthLayout
│   │   ├── pages/
│   │   │   ├── patient/       # Dashboard, Records, AccessManager, Summary
│   │   │   └── doctor/        # AuthorizedPatients, PatientRecords, Summary
│   │   ├── services/          # Typed Axios API clients (auth, doc, doctor, summary)
│   │   └── utils/
│   │       └── disclaimers.ts # Centralized medical safety copy
│   └── vite.config.ts         # Vite server & reverse proxy configuration
│
└── server/                    # Python FastAPI backend
    ├── dev.py                 # Development server launcher (port 8000)
    ├── requirements.txt       # Dependencies (FastAPI, PyMongo, Pydantic, pypdf)
    ├── app/
    │   ├── main.py            # FastAPI lifespan, CORS & router aggregation
    │   ├── config.py          # Environment settings & medical safety disclaimers
    │   ├── database.py        # PyMongo connection manager & index initializers
    │   ├── routes/            # Thin route definitions (health, auth, patients, doctor)
    │   ├── controllers/       # Orchestration layer
    │   ├── middlewares/       # Security gatekeeper (assert_patient_access)
    │   ├── models/            # MongoDB collection definitions & indexes
    │   ├── schemas/           # Pydantic v2 validation contracts
    │   └── services/          # Core business logic:
    │       ├── auth_service.py              # Salted hashing & token issue
    │       ├── document_service.py          # Storage, validation & streaming
    │       ├── extraction_service.py        # pypdf text extraction
    │       ├── structured_extraction.py     # Deterministic regex parser
    │       ├── access_service.py            # Consent grant controller
    │       └── summary_service.py           # Provider seam (Mock / OpenAI)
    ├── storage/
    │   └── documents/         # Physical PDF storage directory (.gitkeep)
    └── tests/                 # Pytest test suite with isolated test DB
```

---

## 10. Installation & Execution Guide

### Prerequisites
- **Node.js**: `v18.0.0` or higher ([Download Node.js](https://nodejs.org/))
- **Python**: `v3.11` or higher ([Download Python](https://www.python.org/))
- **MongoDB**: Community Server `v7.0+` ([Download MongoDB](https://www.mongodb.com/try/download/community))

### Step 1: Clone & Configure Environments

```bash
# Clone the repository
git clone https://github.com/chaitanya-kapure/CareVerse.git
cd CareVerse

# Initialize environment files from examples
# Windows (PowerShell):
Copy-Item server\.env.example server\.env
Copy-Item client\.env.example client\.env

# macOS / Linux:
cp server/.env.example server/.env
cp client/.env.example client/.env
```

### Step 2: Install Dependencies

```bash
# 1. Install root & client packages
npm install

# 2. Configure Python Virtual Environment for Server
cd server
python -m venv .venv

# Activate Virtual Environment:
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# Install Python requirements
pip install -r requirements.txt
cd ..
```

### Step 3: Start MongoDB
Ensure MongoDB is running locally on port `27017`:
```powershell
# Windows Service check:
Get-Service MongoDB | Start-Service

# Or run mongod directly:
mongod --dbpath "$env:TEMP\mongo-data" --port 27017 --bind_ip 127.0.0.1
```

### Step 4: Run Application

Start both frontend and backend concurrently with one command from the project root:
```bash
npm run dev
```

| Service | Access URL | Description |
|---|---|---|
| **Web Frontend** | `http://localhost:5173` | React 18 Client Application |
| **Backend API** | `http://localhost:8000` | FastAPI RESTful Core |
| **Interactive API Docs** | `http://localhost:8000/docs` | Swagger UI documentation |

---

## 11. Verification & Testing Strategy

### 1. Automated Health Check
Run a quick diagnostic to verify API boot and database connectivity:
```bash
curl http://localhost:8000/health
```
**Expected Response:**
```json
{
  "status": "ok",
  "database": "connected",
  "environment": "development",
  "ai_provider": "mock"
}
```

### 2. Frontend Linting & Typechecking
```bash
npm run typecheck       # Executes TypeScript compiler verification (tsc --noEmit)
npm run lint            # Executes ESLint rule checks
```

### 3. Backend Test Suite (Pytest)
Run backend integration tests using the isolated test database:
```bash
cd server
pytest
```
Test suite coverage includes:
- `test_patient_profile.py`: Profile CRUD and user sync.
- `test_documents.py`: PDF validation, magic bytes, storage, and text extraction.
- `test_doctor_access.py`: Full RBAC permission matrix and grant revocation.
- `test_summary.py`: Traceability links, provenance assertion, and fallback triggers.
- `test_password_reset.py`: OTP rate limiting, hashing, and single-use invalidation.

---

## 12. Project Roadmap & Future Scope

| Milestone | Phase Description | Status |
|---|---|---|
| **Phase 1** | Foundation, JWT auth, MongoDB schemas, password recovery | ✅ Completed |
| **Phase 2** | Patient profile management, secure PDF upload & text extraction | ✅ Completed |
| **Phase 3** | Consent-driven doctor authorization & authorized records view | ✅ Completed |
| **Phase 4A** | Deterministic structured data extraction (labs, meds, diagnoses) | ✅ Completed |
| **Phase 4B** | Traceable clinical summaries with Mock provider | ✅ Completed |
| **Phase 4C** | Pluggable OpenAI provider seam with deterministic fallback | ✅ Completed |
| **Phase 5** | Test seed fixtures, accessibility audit, and demo scripts | 🔄 In Progress |

### Future Research & Extensions (For Capstone / Viva Reports)
1. **Optical Character Recognition (OCR) Engine:** Integrate Tesseract or cloud OCR (AWS Textract) to extract text from scanned, photographic, or handwritten medical documents.
2. **FHIR / HL7 Standardized Interoperability:** Export and import patient summaries according to international Fast Healthcare Interoperability Resources (FHIR) standard JSON resources.
3. **Multi-Factor Authentication (MFA):** Add time-based one-time password (TOTP via Google Authenticator) support for healthcare providers.
4. **Cloud Object Storage Adapter:** Implement Amazon S3 / Google Cloud Storage drivers with pre-signed upload URLs for zero-load server transfers.

---

## License

This project is developed for educational, academic, and evaluation purposes under the **MIT License**.
