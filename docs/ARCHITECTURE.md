# CAREVERSE — Architecture & Design

**Status:** Phase 1 complete (foundation + password recovery). Phase 2 complete (patient profile & document pipeline). Phase 3 complete (doctor access & authorized records). Phase 4A complete (deterministic structured extraction). Phase 4B complete (summary over a **mock** provider). **No real AI/LLM provider is implemented — that is Phase 4C.**
**Last updated:** Phase 4B

---

## 1. Requirements analysis

CAREVERSE solves one problem: a patient's medical history is fragmented across
many PDFs, so a doctor burns consultation time reading them instead of
treating the patient.

The system is therefore a **centralization + summarization** platform, and
nothing else:

| Requirement | Design consequence |
|---|---|
| One centralized profile per patient | `patient_profiles` is 1:1 with a patient `User`, enforced by a unique index |
| Doctor must not see every patient | A `patient_access` grant is required for *every* doctor read |
| Summary must not invent information | The AI only restates extracted text; empty sections say "not found" explicitly |
| Summary must stay traceable | Every summary item carries a `source_document_id` |
| Never a diagnostic tool | No diagnosis/treatment/drug code paths exist anywhere in the design |
| PDF only, extensible later | MIME allowlist drives validation; storage sits behind a driver interface |

### Deliberate non-goals

No appointments, wearables, billing, chat, prescriptions-as-orders, risk
scoring, or health recommendations. None of these have a data model here, and
adding any of them would require revisiting the medical-safety boundaries in
§9 of the product spec.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  client/  React 18 + Vite + TypeScript + Tailwind           │
│  ─────────────────────────────────────────────────────────    │
│  pages → layouts → components                                 │
│  hooks/useAuth · services/api (axios) · types · utils         │
│  TanStack Query for server state                              │
└───────────────────────────┬──────────────────────────────────┘
│  HTTPS  Authorization: Bearer <JWT>
│  Vite dev proxy: /api/* → :8000
┌───────────────────────────▼──────────────────────────────────┐
│  server/  FastAPI + Pydantic + PyMongo                       │
│  ─────────────────────────────────────────────────────────    │
│  routes/       thin — path, deps, status code, response model │
│  controllers/  orchestration                                  │
│  services/     business logic  ← AI logic lives ONLY here     │
│  models/       collections, document shapes, indexes          │
│  middlewares/  auth + authorization + error envelope          │
│  schemas/      Pydantic validation (the "Zod" of this stack)  │
└───────────────────────────┬──────────────────────────────────┘
│
                 ┌──────────▼──────────┐
│  MongoDB            │
│  storage/ (local FS)│
│  AI provider (opt.) │
                 └─────────────────────┘
```

### Request flow (read a patient's record list)

```
React page
  → services/document.service.ts (axios attaches JWT)
  → GET /api/patients/me/documents
  → routes/documents.py            parse path + deps
  → controllers/document_controller.py
  → middlewares: get_current_user → require_roles("patient")
                 → assert_own_records
  → services/document_service.py   business rules, query scoped by patient_id
  → models/medical_document.py     collection + serializer
  ← JSON
```

### Deviation from the original spec — please read

The written spec (§10) specifies **MERN**: Node.js + Express + TypeScript.
This project was **built on the pre-existing Python FastAPI backend** at your
direction. What that changes:

| Spec item | Reality here | Note |
|---|---|---|
| Express + TypeScript backend | FastAPI + Python 3.13 | Matches the existing code that was already in the repo |
| Zod validation | Pydantic v2 | Same role, same fail-fast semantics |
| Mongoose | PyMongo + `TypedDict` document shapes | Explicit schemas, no runtime ODM |
| `src/` on the server | `app/` | Same layer names inside |
| MERN branding | **Not MERN** | "MERN" is inaccurate for this repo |

**The frontend is unaffected** — it is React + Vite + TypeScript exactly as
specified, with the mandated TanStack Query and Axios.

**The layering was kept deliberately portable.** `services/`, `models/` and
`schemas/` are framework-agnostic in shape, so a later port to Express +
Mongoose is a mechanical translation, not a redesign. Nothing in the data
model or the authorization rules depends on FastAPI.

If you later want to switch to Node/Express, say so — the services and models
are the layer to translate first.

---

## 3. Folder structure

```
careverse/
├── README.md
├── package.json                  # runs client + server together
├── .gitignore
│
├── docs/
│   └── ARCHITECTURE.md           # this file
│
├── client/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── tsconfig.json / .app.json / .node.json
│   ├── .env.example
│   └── src/
│       ├── main.tsx              # QueryClientProvider + mount
│       ├── App.tsx               # route table
│       ├── index.css
│       ├── components/
│       │   ├── auth/RequireAuth.tsx
│       │   ├── ui/               Button, Card, Field, Alert, Badge,
│       │   │                     Spinner, EmptyState, PageHeader
│       │   ├── ExtractionBadge.tsx  # completed / needs_ocr / failed
│       │   ├── ExtractionPanel.tsx  # ★ patient + doctor extracted text
│       │   ├── DocumentFileActions.tsx # ★ view/save original PDF
│       │   ├── DetailRow.tsx     # label/value pair
│       │   ├── SummarySectionCard.tsx # ★ Phase 4B: one section + source links
│       │   ├── SafetyNotice.tsx
│       │   └── PhasePlaceholder.tsx
│       ├── context/
│       │   ├── authContext.ts    # context object + types
│       │   └── AuthProvider.tsx  # provider (session lifecycle)
│       ├── hooks/
│       │   └── useAuth.ts
│       ├── layouts/
│       │   ├── AppShell.tsx      # signed-in: sidebar + topbar
│       │   └── AuthLayout.tsx    # public: centered card
│       ├── pages/
│       │   ├── LandingPage · LoginPage · RegisterPage · ForgotPasswordPage ·
│       │   │   NotFoundPage
│       │   ├── patient/  Dashboard · Profile · MedicalRecords ·
│       │   │             UploadRecord · RecordDetails · DoctorAccessManager
│       │   └── doctor/   Dashboard · AuthorizedPatients ·
│       │                 PatientDetails · PatientRecords ·
│       │                 PatientSummary (★ Phase 4B, real)
│       ├── services/
│       │   ├── api.ts            # axios instance + error normalization
│       │   ├── auth.service.ts
│       │   ├── profile.service.ts   # GET/PATCH /patients/me
│       │   ├── document.service.ts  # list / upload (FormData) / blob fetch
│       │   ├── doctor.service.ts    # ★ authorized patients + their records
│       │   ├── access.service.ts    # ★ patient grants: list/grant/revoke
│       │   └── summary.service.ts   # ★ Phase 4B: read / regenerate / own
│       ├── types/index.ts
│       └── utils/
│           ├── disclaimers.ts    # all medical-safety copy, one place
│           ├── format.ts         # byte + date formatting, timezone-safe
│           ├── navigation.ts     # role → nav items
│           └── query.ts         # retry policy: transient only, never a 4xx
│
└── server/
    ├── requirements.txt
    ├── .env.example
    ├── app/
│   ├── main.py               # app, lifespan, CORS, handlers
│   ├── config.py             # all env access
│   ├── database.py           # MongoManager + get_db()
│   ├── controllers/          # thin orchestration
│   │   ├── auth_controller.py
│   │   ├── patient_controller.py
│   │   ├── document_controller.py
│   │   ├── access_controller.py    # patient grants: list/grant/revoke
│   │   ├── doctor_controller.py    # ★ reads, only after assert_patient_access
│   │   ├── summary_controller.py   # ★ Phase 4B, thin: authorize → SummaryService
│   ├── middlewares/
│   │   ├── auth_middleware.py    # ★ security boundary
│   │   └── error_handler.py
│   ├── models/
│   │   ├── collections.py    # 6 collection names + accessors
│   │   ├── indexes.py        # startup index creation
│   │   ├── user.py
│   │   ├── patient_profile.py
│   │   ├── medical_document.py
│   │   ├── access.py
│   │   ├── patient_summary.py      # summary shape (Phase 4B consumes it)
│   │   └── password_reset.py
│   ├── routes/
│   │   ├── __init__.py       # router registry
│   │   ├── health.py
│   │   ├── auth.py
│   │   ├── patients.py       # /patients/me
│   │   ├── documents.py      # /patients/me/documents
│   │   ├── access.py         # /patients/me/access   (patient role)
│   │   └── doctor.py         # ★ /doctor/patients     (doctor role)
│   ├── schemas/              # Pydantic request/response
│   │   ├── auth.py
│   │   ├── common.py
│   │   ├── profile.py
│   │   ├── documents.py
│   │   ├── access.py         # grants + doctor reads (reuses Phase 2 shapes)
│   │   └── summary.py        # ★ Phase 4B: the one summary response model
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── email_service.py  # provider seam: mock | smtp | gmail
│   │   ├── password_reset_service.py  # OTP issue / verify / reset
│   │   ├── profile_service.py     # read/update, lazy row creation
│   │   ├── document_service.py    # ★ upload / read / delete pipeline
│   │   ├── storage.py             # StorageDriver seam + local driver
│   │   ├── extraction_service.py  # ★ pypdf → text, honest status
│   │   ├── access_service.py      # ★ the only writer of patient_access
│   │   ├── doctor_service.py      # ★ delegates to profile/document services
│   │   ├── structured_extraction.py  # ★ Phase 4A: text → ExtractedData, pure
│   │   └── summary_service.py     # ★ Phase 4B: provider seam + MockSummaryProvider
│   └── utils/
│       ├── security.py       # bcrypt + JWT + OTP/reset-token hashing
│       ├── errors.py         # error envelope helpers
│       └── responses.py      # ★ shared PDF response (patient + doctor)
    ├── tests/                   # pytest; own careverse_test database
│   ├── conftest.py
│   ├── pdf_fixtures.py      # PDFs built in-process, never committed
│       ├── test_password_reset.py
│       ├── test_patient_profile.py
│       ├── test_documents.py
│       ├── test_doctor_access.py  # ★ the authorization matrix
│       └── test_summary.py       # ★ Phase 4B: attribution, staleness, safety
    ├── scripts/                  # seed/demo data (Phase 5)
    └── storage/
        └── documents/            # uploaded PDFs (gitignored)
```

**Not yet created** (arrive with their phase, rather than as empty stubs):
`hooks/useDocuments.ts` and the real AI/LLM summary provider (Phase 4C). Both
summary seams they would sit behind now exist and are exercised by the mock.

---

## 4. MongoDB schemas

Five collections hold clinical and identity data. A sixth,
`password_reset_otps`, holds transient auth state and is reaped by MongoDB
itself. A field that is absent means "not found" — CAREVERSE never writes a
default that could be mistaken for a clinical fact.

### `users`
```jsonc
{
  "_id": ObjectId,
  "name": "Asha Menon",
  "email": "asha@example.com",     // lowercased, UNIQUE index
  "password_hash": "$2b$12$...",   // bcrypt; never serialized
  "role": "patient",               // "patient" | "doctor" only
  "status": "active",
  "created_at": ISODate, "updated_at": ISODate
}
```

### `patient_profiles`
```jsonc
{
  "_id": ObjectId,
  "patient_id": "<users._id>",     // UNIQUE — one profile per patient
  "full_name": "Asha Menon",       // seeded from the user at registration; updating syncs users.name
  "date_of_birth": "1992-04-18",   // ISO date string (YYYY-MM-DD), nullable
  "gender": "unspecified",         // male|female|other|unspecified
  "phone": null,
  "address": null,
  "notes": null,                   // patient's own words, never AI-rewritten
  "created_at": ISODate, "updated_at": ISODate
}
```

### `medical_documents`
```jsonc
{
  "_id": ObjectId,
  "patient_id": "<users._id>",     // owner
  "original_filename": "cbc-report.pdf",   // display only
  "stored_filename": "b3f1...pdf",         // generated, never user input
  "storage_driver": "local",              // "s3" later
  "storage_key": "b3f1...pdf",            // opaque key, path-traversal safe
  "mime_type": "application/pdf",
  "size_bytes": 182340,
  "title": "Complete Blood Count",        // user-supplied, else filename
  "category": "lab_report",        // lab_report|prescription|
                                   // discharge_summary|imaging|other
  "document_date": "2025-11-02",   // date ON the document, not upload date (nullable)
  "extraction_status": "completed", // pending|processing|completed|
                                   // needs_ocr|failed
  "extraction_error": null,
  "extracted_at": ISODate,
  "page_count": 2,
  "character_count": 3140,
  "extracted_text": "…full text…",
  "extracted_data": {
    "report_title": "Complete Blood Count",
    "document_date": "2025-11-02",
    "referring_facility": "…",
    "referring_doctor": "…",
    "lab_values": [
      { "name": "Haemoglobin", "value": "11.2", "unit": "g/dL",
        "reference_range": "12.0-15.0", "flag": "low",
        "source_text": "Haemoglobin 11.2 g/dL (12.0-15.0)" }
    ],
    "medications": [
      { "name": "Metformin", "dosage": "500 mg", "frequency": "BD",
        "source_text": "Tab Metformin 500mg BD" }
    ],
    "abnormal_findings": [
      { "text": "Mildly elevated liver enzymes", "marker": "elevated",
        "source_text": "…" }
    ],
    "stated_conditions": [
      { "text": "Type 2 Diabetes Mellitus", "source_text": "…" }
    ]
  },
  "uploaded_at": ISODate, "updated_at": ISODate
}
```

Every entry in `extracted_data` carries `source_text` — the literal line it
came from. This is what makes the summary auditable and lets the UI deep-link
back into the document.

**As built in Phase 4A**, `extracted_text` is populated by the Phase 2 text
extractor, and `extracted_data` is populated from it by the deterministic
structured pass described in §8. Both are stored on the document at upload time.
There is no AI in this path and no summary is generated from it yet — that is
Phase 4B.

### `patient_access`
```jsonc
{
  "_id": ObjectId,
  "patient_id": "<users._id>",
  "doctor_id":  "<users._id>",
  "status": "active",              // active|revoked (revoked rows are kept)
  "granted_at": ISODate,
  "revoked_at": null,
  "note": null                     // patient's optional reason
}
```
Index: `(doctor_id, patient_id)`. Grants are created by the **patient**
(consent). There is no doctor-initiated request flow in the MVP.

A second index, `uniq_active_doctor_patient`, is **unique over
`(doctor_id, patient_id)` where `status == "active"`**. This is the
database-level guarantee that the same pair cannot be authorized twice —
a read-then-write in the service would not survive two concurrent requests,
both of which would see "no grant yet" and both insert.

It is partial rather than plain-unique on purpose: revoked rows are kept as
an audit trail, so a plain unique index would make it impossible to grant
the same doctor access a second time after a single revoke.

### `patient_summaries`
```jsonc
{
  "_id": ObjectId,
  "patient_id": "<users._id>",     // UNIQUE — one live summary
  "provider": "mock",              // mock today; openai|anthropic are Phase 4C
  "is_mock": true,                 // surfaced in the UI as a demo label
  "model": null,
  "disclaimer": "AI-generated summary of available records. Verify important
                 information with the original medical documents.",
  "overview": "…",
  "sections": [
    { "key": "lab_values", "title": "Important Lab Values",
      "items": [ { "text": "Glucose: 126 mg/dL",
                   "source_document_id": "…",   // REQUIRED, same patient
                   "source_text": "Glucose 126 mg/dL Ref: 70-110 H" } ],
      "empty_note": "Not found in the uploaded records." }
  ],
  "source_document_ids": ["…"],
  "source_document_count": 4,
  "unreadable_document_count": 1,   // needs_ocr + failed + over the doc cap
  "generated_at": ISODate
}
```
`items` are objects, never bare strings: each statement names the document it
came from, and optionally quotes it verbatim. Written on demand — `GET`
regenerates when the readable record set has changed (§9) — so there is no
separate staleness field.
### `password_reset_otps`
```jsonc
{
  "_id": ObjectId,
  "user_id": "<users._id>",           // null while the address is unknown
  "email": "asha@example.com",        // lowercased, for the cooldown lookup
  "otp_hash": "$2b$12$…",            // bcrypt; the digits are never stored
  "attempts": 0,                      // wrong guesses so far
  "max_attempts": 5,                  // frozen at issue time
  "expires_at": ISODate,              // drives the TTL index
  "reset_token_hash": "…",            // unsalted SHA-256 of an opaque 256-bit token
  "reset_token_expires_at": ISODate,
  "created_at": ISODate,
  "verified_at": null,                // set when the OTP is accepted
  "consumed_at": null,                // set when the password is changed
  "request_ip": null                  // abuse triage; never sent to a client
}
```

Indexes: TTL on `expires_at` (`expireAfterSeconds: 0`), plus
`(email, created_at desc)` for the resend cooldown and `(reset_token_hash)`
for token lookup.

The two secrets are hashed differently on purpose:

- **The OTP is bcrypt'd.** Six digits is a search space of 10⁶, so it needs a
  deliberately slow hash. `attempts` rises on every miss and the row is refused
  once the budget is gone, which is what stops an online attack from walking
  the whole space.
- **The reset token is an unsalted SHA-256.** It is 256 bits of
  `secrets.token_urlsafe`, so there is no dictionary to slow down — and the
  lookup is *by* hash, which salting would turn into a full collection scan.

`otp_hash` is cleared the moment the OTP verifies, which is what makes it
genuinely single-use. Without that, the same digits could be exchanged
repeatedly inside the validity window and mint a fresh reset token each time.

There is no `is_active` field. "Active" is computed by one shared predicate,
`otp_is_active()` in `models/password_reset.py`, so the request, verify and
reset paths cannot disagree about what counts as live — and a state the code
forgot to write cannot read as valid.

---

## 5. API endpoints

Mounted at the server root; the Vite dev proxy strips the client's `/api`
prefix, so the client calls `/api/auth/login` → server `/auth/login`.

**Every `🔒` endpoint requires `Authorization: Bearer <jwt>`.**
**Every `🛡` endpoint additionally requires the `patient` or `doctor` role shown.**

### Public
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | API + database + active AI provider |
| POST | `/auth/register` | Create patient or doctor |
| POST | `/auth/login` | → `{ access_token, user }` |
| 🔒 GET | `/auth/me` | Validate a stored token |
| 🔒 POST | `/auth/logout` | Logout acknowledgement (stateless JWT) |
| POST | `/auth/forgot-password` | Issue an OTP; always the same 200 |
| POST | `/auth/verify-reset-otp` | OTP → single-use `reset_token` |
| POST | `/auth/reset-password` | Spend the token, set the new password |

The three reset routes are deliberately **unauthenticated**: the person using
them has lost the password they would need a token for. They are constrained
instead by attempt limits, TTLs, single use, and the resend cooldown.

### Patient
Every path below starts with `/patients/me` — there is no patient id in any of
them, so there is no id in the request to change.

| Method | Path | Role | Status | Purpose |
|---|---|---|---|---|
| 🔒🛡 | GET | `/patients/me` | patient | ✅ Phase 2 | Own profile |
| 🔒🛡 | PATCH | `/patients/me` | patient | ✅ Phase 2 | Edit basic details (partial) |
| 🔒🛡 | GET | `/patients/me/documents` | patient | ✅ Phase 2 | Own records, newest first |
| 🔒🛡 | POST | `/patients/me/documents` | patient | ✅ Phase 2 | Upload PDF (`multipart`) |
| 🔒🛡 | GET | `/patients/me/documents/{documentId}` | patient | ✅ Phase 2 | Metadata + extracted data + text |
| 🔒🛡 | DELETE | `/patients/me/documents/{documentId}` | patient | ✅ Phase 2 | Delete record + file |
| 🔒🛡 | GET | `/patients/me/documents/{documentId}/file` | patient | ✅ Phase 2 | Stream the original PDF |
| 🔒🛡 | GET | `/patients/me/summary` | patient | ✅ Phase 4B | Own summary; generated on demand |
| 🔒🛡 | GET | `/patients/me/access` | patient | ✅ Phase 3 | Every grant issued, revoked included |
| 🔒🛡 | POST | `/patients/me/access` | patient | ✅ Phase 3 | Authorize one doctor (`doctor_id`, optional `note`) |
| 🔒🛡 | DELETE | `/patients/me/access/{accessId}` | patient | ✅ Phase 3 | Revoke |

### Doctor
All read-only. A doctor can read the records of patients who authorized them
and can do nothing else to them — there is deliberately no doctor-side upload,
edit or delete route.

| Method | Path | Role | Status | Purpose |
|---|---|---|---|---|
| 🔒🛡 | GET | `/doctor/patients` | doctor | ✅ Phase 3 | Authorized patients **only**, with a record count |
| 🔒🛡 | GET | `/doctor/patients/{patientId}` | doctor | ✅ Phase 3 | The patient's own profile, unchanged |
| 🔒🛡 | GET | `/doctor/patients/{patientId}/documents` | doctor | ✅ Phase 3 | Record list, newest first |
| 🔒🛡 | GET | `/doctor/patients/{patientId}/documents/{documentId}` | doctor | ✅ Phase 3 | One record, including extracted text |
| 🔒🛡 | GET | `/doctor/patients/{patientId}/documents/{documentId}/file` | doctor | ✅ Phase 3 | Stream the original PDF |
| 🔒🛡 | GET | `/doctor/patients/{patientId}/summary` | doctor | ✅ Phase 4B | Summary, generated if missing or stale ★ |
| 🔒🛡 | POST | `/doctor/patients/{patientId}/summary/regenerate` | doctor | ✅ Phase 4B | Discard the cached one and rebuild |

There is deliberately no `PUT`, `PATCH` or `DELETE` for a summary. A summary is
derived from records, not authored: it is generated, it can be thrown away, and
the next read rebuilds it from the records that exist. A client cannot hand the
server a summary — there is no write route through which invented clinical prose
could enter the database.

Both summary routes return the same `PatientSummaryResponse`. A regenerate is not
a different kind of object, so it does not get its own response model and the two
cannot drift apart. Authorization order is the same on both: token → role →
resolve and validate the id → `assert_patient_access` (or `assert_own_records`)
→ the service. The service receives an already-authorized `patient_id` and
loads its own documents; it never takes a caller-supplied document id, so there
is no path by which one patient's records could enter another patient's summary.

The doctor's document responses are the **Phase 2 response models, unchanged**
(`DocumentListResponse`, `MedicalDocumentDetailResponse`,
`PatientProfileResponse`). A record a doctor reads and a record the patient
reads are the same object, so there is no doctor-specific variant to audit and
no way for the two to drift apart. The schemas in `schemas/access.py` are
aliases, not redefinitions.

The file route is the same handler logic as the patient's, refactored to share
`utils/responses.pdf_response` so `Content-Disposition`, `X-Content-Type-Options`,
`Content-Security-Policy` and `Cache-Control` are emitted from one place.
There is one storage driver, one `DocumentService.read_file`, and one set of
response headers — the doctor path is an authorization check in front of the
existing read, not a second way to read a file.

### Error envelope
Every failure, from every layer:
```json
{ "detail": "Human readable sentence.", "code": "MACHINE_CODE" }
```

`detail` is safe to render: no stack traces, no filesystem paths, no
exception types, and nothing drawn from the document's contents.

| Situation | HTTP | `code` |
|---|---|---|
| No / bad bearer token | 401 | `MISSING_TOKEN` · `INVALID_TOKEN` |
| Wrong email or password | 401 | `INVALID_CREDENTIALS` |
| Email already registered | 409 | `EMAIL_TAKEN` |
| Not your own patient record | 403 | `NOT_RECORD_OWNER` |
| Doctor without a grant | 403 | `NO_PATIENT_ACCESS` |
| Wrong role for the route | 403 | `ROLE_NOT_ALLOWED` |
| Patient id in the path is malformed | 400 | `INVALID_PATIENT_ID` |
| Granting an account against itself | 400 | `SELF_ACCESS_NOT_ALLOWED` |
| Named doctor does not exist / is not a doctor | 404 | `DOCTOR_NOT_FOUND` |
| Grant not found, or not the caller's | 404 | `ACCESS_NOT_FOUND` |
| Doctor already authorized for this patient | 409 | `ACCESS_ALREADY_GRANTED` |
| Body or form field invalid | 422 | `VALIDATION_ERROR` |
| Upload is not a PDF by MIME | 415 | `UNSUPPORTED_FILE_TYPE` |
| Upload claims PDF but is not | 400 | `INVALID_FILE_TYPE` |
| No file part in the request | 400 | `FILE_MISSING` |
| Upload over `MAX_UPLOAD_MB` | 413 | `FILE_TOO_LARGE` |
| Document missing, or not yours | 404 | `DOCUMENT_NOT_FOUND` |
| Metadata exists, file does not | 404 | `DOCUMENT_FILE_MISSING` |
| Could not write the file | 500 | `STORAGE_FAILED` |
| Could not remove the file | 500 | `STORAGE_DELETE_FAILED` |
| Database unreachable | 503 | `DATABASE_UNAVAILABLE` |
| Anything unexpected | 500 | `INTERNAL_ERROR` |

**Extraction failure is not in this table, on purpose.** It is not an error
response: the upload succeeded, so the answer is `201` with
`extraction_status = "failed"` and a plain-language `extraction_error` on the
document. A patient whose PDF could not be parsed must not see the upload
itself reported as broken.

---

## 6. Authentication & authorization

### Authentication
1. `POST /auth/register` — Pydantic validates → `AuthService.register` bcrypts
   the password → unique index on `email` is the real duplicate guard → a
   `patient_profiles` row is upserted so a patient always has a profile.
2. `POST /auth/login` — email lowercased, compared with
   `bcrypt.checkpw`. A missing account still runs a dummy hash so timing does
   not reveal whether an email is registered. One message is returned for both
   "no such user" and "wrong password".
3. JWT: `{ sub, role, exp }`, HS256, 60 min.
4. `get_token_payload` validates the signature **without touching Mongo**.
5. `get_current_user` re-reads the user document, so a disabled account or a
   changed role takes effect immediately instead of at token expiry.

> **Why token validation is split from user loading:** FastAPI resolves all
> dependencies *before* calling a handler. A single combined dependency
> therefore raised `503 Database not available` before ever checking the
> token — masking auth failures and letting an unauthenticated caller probe
> whether Mongo was up. Splitting them means a bad token is always a `401`.

### Password recovery

`email → OTP → reset token → new password`. The OTP is a 6-digit code from
`secrets.randbelow` (never `random`) with a 10-minute life and 5 attempts; the
reset token is an opaque 256-bit `secrets.token_urlsafe(32)` with a 10-minute
life of its own.

It is a **plain opaque token, not a JWT**. A JWT cannot be revoked, so
single-use would be a claim rather than a fact — and an untested claim is
exactly the kind that fails open. Looking the hash up in MongoDB makes "already
spent" a real, enforced condition.

Every one of these responses is chosen so it cannot tell a stranger which
addresses are registered:

| Situation | Response | Why not something else |
|---|---|---|
| Unknown address | `200 OTP_REQUEST_ACCEPTED` | A `404` would be a user-enumeration oracle |
| Known address | `200 OTP_REQUEST_ACCEPTED` | Byte-identical; built only from constants |
| Resend inside cooldown | `200 OTP_REQUEST_ACCEPTED` | A `429` would leak that a code *exists* |
| No live code, or attempts spent | `400 OTP_ATTEMPTS_EXCEEDED` | One code for both, so six probes cannot separate a real account from a fake one |
| Mail relay failed | `200 OTP_REQUEST_ACCEPTED` | `send_password_reset_otp` returns a bool and never raises, so a broken relay cannot become a 5xx-vs-200 oracle |

`retry_after_seconds` and `expires_in` are returned so the client can count
down without leaking anything: they are configuration constants, identical for
every address.

The code never appears in a response. The only place it is ever printed is the
mock provider's `DEVELOPMENT ONLY` log line, and `config.py` refuses to start
with `EMAIL_PROVIDER=mock` when `ENVIRONMENT=production` — the same guard that
already exists for the JWT secret.

### Email delivery

`services/email_service.py` is a seam, not a vendor. It defines an
`EmailProvider` protocol and builds one from `EMAIL_PROVIDER`:

| Value | Behaviour |
|---|---|
| `mock` | Logs the OTP as `DEVELOPMENT ONLY` and keeps it in an in-memory outbox that tests read. Refused in production. |
| `smtp` | stdlib `smtplib`. Port 465 → `SMTP_SSL`, anything else → `STARTTLS`. |
| `gmail` | Recognized, but raises `EmailDeliveryError` until the API-oauth flow lands. Fails loudly rather than silently no-oping. |

Nodemailer is deliberately absent: this backend is Python, so the transport is
`smtplib`. Credentials come only from `SMTP_*` env vars — nothing is hardcoded,
and no `.env` file is committed.


### Authorization — the core rule

`assert_patient_access(db, user, patient_id)` is the **only** place that
decides whether a caller may see a patient's data. Both the patient routes and
the doctor routes call it, so there is one rule to audit.

```
assert_patient_access(db, caller, patient_id)
│
├─ caller.role == "patient"
│    └─ patient_id == caller.id ?  → "owner"
│       else                     → 403 NOT_RECORD_OWNER
│
├─ caller.role == "doctor"
│    └─ patient_access row exists where
│         doctor_id  == caller.id
│         patient_id == patient_id
│         status     == "active"   ?  → "granted"
│       else                       → 403 NO_PATIENT_ACCESS
│
└─ anything else → 403 ROLE_NOT_ALLOWED
```

Consequences that matter:

- **Role alone never grants access.** Being a doctor is not authorization.
- **Ownership is the only proof for a patient** — no sharing, no lookup of
  another patient's id.
- **Revocation is immediate**, because the grant row is re-read per request
  rather than baked into a token.
- **An unknown role fails closed** rather than falling through to a grant.
- Document-level reads additionally re-check `document.patient_id`, so a
  document id from another patient cannot be read by passing its own id.

Frontend `RequireAuth` is a UX convenience only. It is never the control.

### How access is established — Phase 3

The invariant is a single row:

```
doctor_id + patient_id  +  status == "active"
```

There is no other way in, and `assert_patient_access` is the only thing that
reads it. Three endpoints, all on the **patient's** side:

| Method | Path | What it does |
|---|---|---|
| `GET` | `/patients/me/access` | Every grant the caller has issued, revoked included |
| `POST` | `/patients/me/access` | Authorize one `doctor_id` |
| `DELETE` | `/patients/me/access/{accessId}` | Revoke |

**The patient grants; the doctor never requests.** This is not a UI
preference, it is the security model. A request flow means a doctor can *ask*
for a patient's records, and every such system needs an approval queue, an
expiry policy and an audit trail to stop the queue becoming a way to browse
patient records. Starting from consent means the only way a grant appears is
a patient naming a doctor.

The direction is enforced by the routes, not by convention: they are mounted
under `/patients/me` with `require_roles("patient")`, and the controller
derives the patient id from the session via `assert_own_records`. There is no
path segment, query parameter or body field through which a patient could name
a *different* patient, so the endpoint cannot be used to grant access to
somebody else's records even by mistake.

**`AccessService` is the only module that writes to `patient_access`.** The
doctor routes never create or modify a grant; they only ask whether one exists.
One writer, one reader, one question.

**Validation on the way in.** The named doctor must exist *and* have
`role == "doctor"` (`404 DOCTOR_NOT_FOUND` for both cases, since the difference
is not the caller's business). Without that check, a grant could be attached to
a patient account, which would let one patient read another's records. An
account cannot be authorized against itself
(`400 SELF_ACCESS_NOT_ALLOWED`), so the doctor path can never be used to read
its own records while bypassing the owner checks in the patient routes.

**Revocation is part of the mechanism, not a later feature.** Access to medical
records has to be withdrawable by the person whose records they are; a grant
with no way to end it is a one-way door. Revoke sets `status = "revoked"` and
stamps `revoked_at` rather than deleting the row, so "who had access in March"
stays answerable. Because the grant row is re-read on every request, a revoked
doctor is refused on their very next call — there is no cached grant to wait
out.

**Why there is no doctor directory.** The patient pastes the id of a doctor
they already have a relationship with. A searchable roster of clinicians would
be the obvious convenience and the wrong trade: it would let anyone with an
account enumerate every doctor on the platform, and it is not needed by the
workflow this phase supports. A patient who is seeing a doctor can get the id
from them.

**What is deliberately absent:** invitations, approval queues, request
workflows, organizations, hospital tenancy, role hierarchies, per-field
permissions, expiry, and any doctor-initiated write.

### Own-records routes (`/patients/me/*`) — Phase 2

Every Phase 2 route is mounted under `/patients/me` and gated by
`require_roles("patient")`. There is deliberately **no patient id in the path or
body**: a patient editing their own profile is not a resource lookup, so there
is no identifier in the request to substitute.

The controller still calls `assert_own_records(db, user)`, which resolves the
owner's id from the *session* and returns it. Two things follow:

1. Ownership is decided once, in the one function that also refuses a doctor.
   The id a handler queries by is the id that was authorized — it is never
   re-derived from request data at a call site.
2. Every MongoDB query is scoped by that returned id —
   `find({"patient_id": patient_id})`, `delete_one({"_id": …, "patient_id": …})`.
   The scope is **inside the query**, not a comparison applied afterwards.

```python
doc = self._docs.find_one({"_id": ObjectId(document_id), "patient_id": patient_id})
if doc is None:
    raise errors.not_found("Document not found", code="DOCUMENT_NOT_FOUND")
```

### Why cross-patient access is `404`, not `403`

A document id belonging to another patient and a document id that does not
exist are **the same response**: `404 DOCUMENT_NOT_FOUND`.

Answering `403` would confirm that someone else's record with that id is real —
a free enumeration oracle over the whole collection, from a single logged-in
account. With the id in the query filter, the "does it exist and is it mine?"
question is never asked, because the database cannot distinguish the two cases
either. The status code is the access-control decision, not a detail added on
top of one.

### Doctor routes — Phase 3

Every doctor handler runs the same three steps, in this order:

```python
requested = resolve_patient_id(patient_id)   # 400 if not an ObjectId
assert_patient_access(db, user, requested)   # 403 NO_PATIENT_ACCESS if no grant
return DoctorService(db).get_patient_profile(requested)
```

The id is taken from the path, but it is **not used** until the check has
passed, and the id used afterwards is the one that was checked. There is no
route that loads the patient first and authorizes afterwards.

**Why `403 NO_PATIENT_ACCESS` does not leak existence here.** The grant lookup
queries `patient_access` and never consults the patient collection. A patient id
that matches no account, and a patient id that matches a real patient this
doctor was never granted, therefore produce a byte-identical `403`. A doctor
learns only that they have no access — which is a fact about their own
authorization, not about another person's account. The test
`test_a_nonexistent_patient_id_answers_exactly_the_same` asserts the two
responses are equal, not merely the same status.

A malformed id is a `400 INVALID_PATIENT_ID` instead, and that difference is
deliberate: it says the string is not an id, which reveals nothing about
whether any id exists.

**The patient list is the same rule applied as a set.** `AccessService
.list_authorized_patient_ids` starts from `patient_access` and returns ids;
only those are then loaded. No query in the project starts from the patient
collection and filters by grant, because that shape is what becomes a
directory. There is no endpoint that returns "patients matching X", and a
doctor with zero grants gets `{"items": [], "total": 0}` — not a 403, because
an empty authorized set is a successful answer, not a refused one.

**Isolation between doctors** falls out of the same check: two doctors share
nothing but the `patient_access` collection, so doctor B is refused for any
patient whose grant names doctor A. `test_doctor_a_cannot_see_doctor_b_authorized_patients`
and `test_doctor_b_cannot_read_the_patient_granted_to_doctor_a` cover it.

**Documents are scoped twice.** Patient authorization runs first, so a doctor
without a grant never reaches a document query. Then the document lookup is
scoped by the authorized `patient_id`, so a valid document id belonging to a
*different* patient is `404 DOCUMENT_NOT_FOUND` — identical to a document that
does not exist.

**Ownership is unchanged.** No doctor route writes. A doctor aiming a `DELETE`
at a record gets `405`, and uploading to `/patients/me/documents` as a doctor
gets `403 ROLE_NOT_ALLOWED`. The patient keeps full control of their files.

---

## 7. Patient profile

Six editable fields, all of them typed by the patient: `full_name`,
`date_of_birth`, `gender`, `phone`, `address`, `notes`. There is no derived,
inferred or predicted field anywhere in the schema — a profile is what the
patient said about themselves, never what the system concluded.

The row is created at registration by `AuthService.ensure_patient_profile`
(upsert, so a patient always has one), and `ProfileService.get` will recreate
it lazily if it is ever missing. A patient who reaches the profile screen with
no row sees an empty form, not a 404: having an account *is* what the profile
is a fixture of.

### PATCH semantics

`PATCH /patients/me` writes only the fields present in the body
(`model_dump(exclude_unset=True)`). Sending `{"phone": "…"}` must not blank the
address; sending `{"address": null}` clears it. Omitting a field and clearing it
are different requests, and the schema is where that distinction is preserved.

Dates are validated as real calendar dates (`2026-02-30` is rejected) and
stored as bare `YYYY-MM-DD` strings. A date of birth is a fact about a
calendar, not an instant, so it is never converted to and from a timezone —
`new Date("1992-04-18")` in the client parses it as UTC midnight and can render
the previous day west of Greenwich. `client/src/utils/format.ts` parses it as a
bare date for the same reason.

`full_name` also updates `users.name`. They are one piece of information to the
patient, and storing it in two places only invites the topbar and the profile
to disagree. The write list is an explicit `EDITABLE_FIELDS` tuple rather than
the schema's own keys, so a new schema field cannot start persisting without
being added to that list on purpose.

---

## 8. PDF upload & extraction pipeline

Implemented in `services/document_service.py` (the pipeline),
`services/storage.py` (where bytes live) and
`services/extraction_service.py` (what the bytes say).

```
POST /patients/me/documents  (multipart/form-data)
│
  ├─ 1. cheap checks   filename present, MIME in ALLOWED_MIME_TYPES
│                    (415 UNSUPPORTED_FILE_TYPE)
  ├─ 2. read capped    stream in 256 KB chunks, abort at MAX_UPLOAD_MB
│                    (413 FILE_TOO_LARGE) — nothing is stored on failure
  ├─ 3. magic bytes    content must start with %PDF-  ← the extension lies
│                    (400 INVALID_FILE_TYPE)
  ├─ 4. store          driver.new_key() + driver.save() → opaque storage_key
│                    generated here, never taken from the upload
  ├─ 5. persist        medical_documents row, extraction_status="processing"
│                    rollback: if this insert fails, the file is deleted
  ├─ 6. extract        asyncio.to_thread(extraction_service.extract_text)
  ├─ 7. record outcome write extracted_text / page_count / extraction_status
  └─ 8. respond 201    the finished document, extraction already settled
```

Steps 1–3 run **before any write**, so a rejected upload leaves neither a file
nor a row behind. Step 5 happens **before** extraction, because extraction is
the only part of the pipeline that parses an untrusted file and the part most
likely to fail — and a failure there must not cost the patient their upload.

### Why extraction is inline

`ExtractionService` runs in the request, off the event loop
(`asyncio.to_thread`, so one crafted PDF cannot stall every other request).
There is no task queue in this phase. The trade-off is deliberate: the client
receives the **real** status instead of a `pending` placeholder it would have
to poll for, and a document is never observed in a state that is not real.

The cost is response latency on large files, which the client bounds with a
120 s timeout on the upload request specifically.

### The three honest outcomes

| `extraction_status` | When | `extracted_text` |
|---|---|---|
| `completed` | pypdf returned characters | the text |
| `needs_ocr` | the PDF read fine but has under `NEEDS_OCR_MIN_CHARS` characters | **`null`** |
| `failed` | pypdf raised, the file is encrypted, or it exceeds `MAX_PAGES` | **`null`** |

`pending` and `processing` exist in the enum and are written mid-pipeline, but
no request ever returns one, because extraction completes before the response.

Two rules make these trustworthy:

- **Nothing is invented.** A scanned PDF has no embedded text, so
  `extracted_text` is stored as `null` — not `""`. An empty string would let a
  later screen present "no text found" as if it were the record's content.
- **A failure never fails the upload.** The response is still `201` with
  `extraction_status = "failed"`, the file is still stored, and the original
  is still downloadable. The patient keeps the document they uploaded.

`extraction_error` carries a plain sentence for the patient. It is written
from a fixed set of phrases and never contains an exception type, a path, or
any part of the document.

### Bounds

| Constant | Value | Why |
|---|---|---|
| `NEEDS_OCR_MIN_CHARS` | 10 | A real page of results is orders of magnitude longer; an image-only page yields a stray page number at most |
| `MAX_EXTRACTED_CHARS` | 500 000 | Mongo caps a document at 16 MB; past this the text is not read in the UI anyway |
| `MAX_PAGES` | 1 000 | The byte cap does not bound CPU — thousands of tiny pages fit in 2 MB. Over the cap the document is **refused for extraction**, not silently truncated |

Truncating half a medical record and calling it `completed` would be worse than
saying it was not extracted, so the page cap refuses rather than cuts.

### Storage abstraction
```python
class StorageDriver(Protocol):
    def new_key(self, suffix: str = ".pdf") -> str: ...   # opaque, no user input
    def save(self, content: bytes, key: str) -> str: ...  # raises StorageError
    def open(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
```
`LocalStorageDriver` writes under `server/storage/documents/`, flat, one file
per document. An `S3StorageDriver` can be added later; only `STORAGE_DRIVER` in
`.env` changes, because no caller ever touches a filesystem path.

Three properties this layer is responsible for:

- **The key is generated, never taken from the upload.** A filename is
  attacker-controlled input and must never decide where bytes land on disk.
- **Every key is resolved and checked against the driver root.** A key with a
  path separator, or one that resolves outside the root, raises `StorageError` —
  so `../` cannot walk out of the storage directory even if one reaches here.
- **Writes are staged and renamed** (`.part` → final), so an interrupted write
  cannot leave a half-written PDF that later looks like a valid record.

Uploaded files are **never** served as static files. `GET …/file` re-runs
`assert_own_records` and re-reads the document through the same owner-scoped
query first. A predictable URL over `server/storage` would be a total
authorization bypass.

### Delete order

The file is removed **first**, then the row. An orphaned row is a visible,
retryable inconvenience; an orphaned copy of a medical document sitting on
disk is neither.

### Structured extraction — Phase 4A ✅

Implemented in `server/app/services/structured_extraction.py` as a single pure
function:

```python
extract_structured(text: str) -> ExtractedData
```

Deterministic, regex/pattern based — **not** an LLM, so it is testable and
reproducible. The same text always produces the same structure. The function
has no database access, no HTTP, no external API, and never raises.

It runs at upload, inside the same `asyncio.to_thread` as the text extraction,
and only when `extraction_status == "completed"` with non-empty text:

```
PDF → extraction_service.extract_text() → if completed:
        structured_extraction.extract_structured() → extracted_data
```

No new collection and no migration: the result is written into the existing
`medical_documents.extracted_data` field in the same single `$set` that already
stored `extracted_text`.

**Why this is a separate phase from the summary.** A summarizer handed 500,000
characters of raw clinical prose has to decide what it is looking at. One
handled structured, source-attributed facts does not. Everything that can be
established deterministically is established here first, so that nothing which
can be *checked* is left to be *guessed*.

#### Categories

| Field | Extracted when |
|---|---|
| `report_title` | An explicit label — `Report:`, `Test Name:`, `Investigation:` |
| `document_date` | An explicit date label — `Report Date:`, `Reported on:`, `Collected:` |
| `referring_facility` | An explicit label — `Hospital:`, `Clinic:`, `Laboratory:` |
| `referring_doctor` | An explicit label — `Referring Doctor:`, `Reported by:`, `Dr:` |
| `lab_values` | A `name value [unit] [(range)] [marker]` row |
| `medications` | A drug name plus a dosage form or an administration frequency |
| `abnormal_findings` | An explicit marker, or a labelled findings section |
| `stated_conditions` | An explicit statement phrase — `History of`, `Diagnosis:`, `Known` |

Each of the four metadata fields requires a printed label. There is no heading
heuristic and no positional guess: "the first line" is where a letterhead lives
on one document and where a patient's name lives on another, and telling those
apart is inference. A field with no label is **absent from the result**.

Anything not found is simply omitted from the result, which is how "not found
in the uploaded records" propagates to the summary. Absent keys are the
representation — not present-and-null — so a reader never has to distinguish
"empty" from "unknown".

#### The lab `flag` rule — transcribed, never computed

> **`flag` is populated only when an explicit flag or marker is present in the
> source document.** `H`, `L`, `*`, `(High)`, `Elevated`, `Critical`. It is
> **never** derived by comparing a value to its reference range, even when that
> range is printed in the text.

This is deliberately narrower than an earlier draft of this document, which
proposed deriving the flag from the range. Comparing a number to a range is an
*interpretation*, and an interpretation is exactly what this layer exists to
avoid. It would also be fragile: `<5`, `>180` and `70-99` are not the same
shape of claim as `12-16`, and a mistaken "high" would enter a future summary
as a clinical fact.

`Glucose: 126 mg/dL` therefore yields **no** `flag` at all. So does
`Haemoglobin 14.2 g/dL (12.0-15.0)` — silence is the honest answer, because a
`normal` flag on every in-range value would be a claim the document never made.
`Haemoglobin 8.2 g/dL (12.0-15.0) L` yields `flag: "low"` solely because of the
printed `L`.

#### Abnormal findings — two mechanisms only

1. **Explicit markers.** Verbatim sentences containing `abnormal`, `elevated`,
   `raised`, `high`, `increased`, `decreased`, `reduced`, `low`, `positive`,
   `critical`, `out of range`, `below range`, `above range`. `high` and `low`
   additionally require a measurement-like context (`BP is high`, `140 high`,
   `low count`) so that `low back pain` is not read as an abnormal result.

   `negative` is deliberately **excluded**. In a lab or radiology report it is
   overwhelmingly a statement of normality — `all negative` — and treating it as
   abnormal would invert the document's meaning. It is still recorded where it
   belongs: as the *value* of a qualitative result (`CRP: Negative`).

2. **Findings sections.** Sentences under a heading that labels them as
   findings — `Findings:`, `Impression:`, `Abnormal Findings:`, `Findings /
   Impression:`, `Comments:`, `Conclusion:`, `Observations:` — in either the
   two-line or the inline (`Impression: …`) form. The document has already made
   the judgement; the text is quoted, never reinterpreted.

   Sentences the document itself marks as normal (`no acute abnormality`,
   `unremarkable`, `within normal limits`, `negative for`) are suppressed even
   under such a heading, because recording them would be a false claim in the
   other direction.

There is deliberately no third mechanism. `Chest X-ray shows consolidation.`
in arbitrary prose is **not** captured, because deciding that consolidation is
abnormal is a clinical judgement this layer is not allowed to make. Printed
under `Findings:`, it is captured as a quote. This is a known recall limit, and
the marker vocabulary is never widened with medical terms to compensate.

#### The no-inference rule

There is no path from a lab value, a medication, or a finding to a condition
name. `Glucose: 126 mg/dL` cannot produce `diabetes` no matter what else is on
the page, because every condition pattern requires an explicit statement
phrase. Lines that deny having the thing they go on to mention (`no known
chronic conditions`) are rejected outright.

Nothing in this module assesses danger, recommends treatment or medication,
judges whether a medication is appropriate, or determines whether a record is
diagnostic.

#### Document date

Only unambiguous forms are accepted: ISO `YYYY-MM-DD` / `YYYY/MM/DD`, plus
`DD/MM/YYYY` **only** when the leading component exceeds 12, which proves it is
a day. `03/04/2025` is refused rather than resolved to one of two readings, and
every candidate is then checked against the real calendar so `2026-02-30` is
rejected rather than rolled over. Lines with a birth context are skipped.

A `document_date` the patient typed at upload is the document's date of record
and lives on the document row. `extracted_data.document_date` is a *separate*
reading of what the file says and never overwrites it. Both are recorded.

#### `needs_ocr` and `failed`

Neither status reaches the structured pass. A document with no extractable text
has nothing to structure, and there is no branch that could build
`extracted_data` out of a status or a filename. Both keep `extracted_data = {}`
exactly as in Phase 2 — which is what lets a later summary tell "no facts
found" apart from "this record was never readable".

#### Failure behaviour

Every category pass is individually guarded, so a parser bug costs one category
its results rather than all of them. A total failure degrades to `{}`. Nothing
here raises, because an exception would turn a successfully extracted document
into a failed upload — precisely the coupling the pipeline avoids. Only the
exception *type* is logged; a parse failure message routinely embeds the line
that failed, which is document content.

#### Bounds

Bounded by construction, so a hostile or merely enormous document cannot produce
an unbounded structure:

| Constant | Value | Bounds |
|---|---|---|
| `MAX_INPUT_CHARS` | 500,000 | Input text (mirrors `MAX_EXTRACTED_CHARS`) |
| `MAX_LINES` | 20,000 | Lines read |
| `MAX_LAB_VALUES` / `MAX_MEDICATIONS` / `MAX_ABNORMAL_FINDINGS` / `MAX_STATED_CONDITIONS` | 200 each | Output per category |
| `MAX_SOURCE_TEXT_CHARS` | 300 | A line longer than this is **skipped**, not truncated |
| `MAX_NAME_CHARS` / `MAX_VALUE_CHARS` / `MAX_CONDITION_CHARS` | 60 / 40 / 120 | Individual fields |

`source_text` must be verbatim, so an over-long line is skipped rather than
clipped — a quote that stops mid-sentence is worse than no quote. No Phase 2
limit is widened: a document refused for having too many pages is refused for
exactly the same reason and never reaches this pass.

---

## 9. Summary generation

Phase 4A produces structured facts. Phase 4B turns them into a summary a
doctor can read in one screen, with **every statement traceable to a document
that really belongs to that patient**. No real AI/LLM provider is involved: the
seam exists, and the only thing plugged into it is a deterministic provider
that can only restate what Phase 4A extracted.

### The flow
```
GET  /doctor/patients/{id}/summary   (or POST …/regenerate, or /patients/me/summary)
│
└─ SummaryService.get_summary(patient_id, force)      ← already authorized
     │
     ├─ ONE scoped query: documents for this patient, projection-limited
     │    ├─ extraction_status == "completed"  → summarized
     │    └─ needs_ocr / failed                → counted, never summarized
     ├─ + profile: full_name, date_of_birth, gender  (and nothing else)
     ├─ persisted = patient_summaries.find_one({patient_id})
     ├─ if persisted and not force and not _is_stale(...)  → return it as-is
     │
     ├─ payload = SummaryPayload(profile, documents oldest-first, unreadable count)
     ├─ draft   = provider.generate(payload)      ← the only switch point
     ├─ validate: unknown section keys dropped, fixed order re-imposed,
     │            every item's source_document_id checked against this
     │            patient's own readable document ids — mismatches are
     │            DROPPED, never re-attached to something plausible
     ├─ disclaimer = AI_SUMMARY_DISCLAIMER        ← server-owned, see below
     └─ upsert patient_summaries (unique uniq_patient_summary, 1 per patient)
```

`SummaryService` receives **only an already-authorized `patient_id`**. It loads
its own documents and never accepts a caller-supplied document id, so there is
no route by which one patient's record can be summarized inside another
patient's summary. Controllers stay thin: they authorize, call
`asyncio.to_thread(SummaryService.get_summary, ...)` — the same off-loop
pattern `DocumentService.upload` already uses — and return the result.

### Provider seam
```python
class SummaryProvider(Protocol):
    name: SummaryProviderName     # "mock" | "openai" | "anthropic" | "custom"
    is_mock: bool
    model: Optional[str]

    def generate(self, payload: SummaryPayload) -> SummaryDraft: ...
```

This mirrors the email provider seam (`email_service.py`) deliberately, so
Phase 4C is a config change and a new class rather than a redesign:
`get_summary_provider()` resolves from `AI_PROVIDER`, `set_summary_provider()`
injects a provider (tests use it), `reset_summary_provider()` clears the
override. `SummaryService` holds an optional injected provider and otherwise
resolves per call. **No controller imports a provider and no provider
specificity leaks past `summary_service.py`.**

Today `AI_PROVIDER` may only be `mock`. `AI_PROVIDER=openai` (or `anthropic`)
raises `SummaryProviderUnavailable` — a loud 503, not a silent downgrade,
exactly as `EMAIL_PROVIDER=gmail` behaves before Phase 1b shipped SMTP.
`AI_API_KEY` is still read by nothing at runtime.

`provider`, `is_mock` and `model` are **stored on the summary document** and
never inferred from the output text. A provider that is not a mock says so
itself; the UI renders `MOCK_SUMMARY_LABEL` whenever `is_mock` is true.

### Provider input: deliberately small
`SummaryPayload` carries the three approved profile fields and the readable
records. `phone`, `address` and `notes` are **absent by construction** — the
`SummaryProfile` dataclass has no such attributes, so a future edit cannot leak
one into a provider call by forgetting a filter. Per document the provider
receives `id`, `title`, `category`, `document_date`, `page_count`,
`character_count` and `extracted_data`. It does **not** receive
`storage_key`, `original_filename` / `stored_filename`, `extraction_error` or
`extracted_text`: the raw text is large, and the structured fields were derived
from it, so sending both would invite a provider to quote around the extraction
instead of using it. `extracted_data` is consumed exactly as Phase 4A wrote it.

### The mock provider
Not random prose, and not a template with holes — it assembles the real
`extracted_data` the pipeline produced:

| Section | Source |
|---|---|
| `patient_overview` | detected date, referring doctor, facility, report title |
| `medical_history` | `stated_conditions` (the document's own "Diagnosis:" line) |
| `key_findings` | `abnormal_findings` |
| `lab_values` | every `lab_values` entry, verbatim value + printed reference range |
| `recent_records` | the 10 newest records, newest first |
| `medications` | `medications` |
| `abnormal_values` | only `lab_values` entries carrying a `flag` |
| `chronological_overview` | every record, oldest first |

Profile facts (name, date of birth, gender) live in the top-level `overview`
string rather than as section items, so that **every item in the document has a
document id attached to it**. It demonstrates the exact output shape and
traceability a real provider must match, so swapping in an API key changes the
prose and nothing else.

The class contains no vocabulary of medical meaning — no condition words, no
severity, no advice. A value becomes the string `"Glucose: 126 mg/dL"` and
stops there. Whether that means anything is not a question this class is
allowed to have an answer to.

### Fixed output sections
`Patient Overview` · `Available Medical History` · `Key Findings From Records` ·
`Important Lab Values` · `Recent Records` · `Medications Mentioned In Records` ·
`Abnormal Values / Findings Mentioned In Records` ·
`Chronological Record Overview`

All eight are always present, in that order. An empty section is **persisted**
with `empty_note` of exactly **"Not found in the uploaded records."** Silence
would read as "nothing wrong"; the section says what it does not know.

### Bounds
`MAX_DOCUMENTS = 200`, `MAX_ITEMS_PER_SECTION = 200`, `MAX_ITEM_CHARS = 600`,
`MAX_OVERVIEW_CHARS = 600`, `MAX_SOURCE_TEXT_CHARS = 300`,
`MAX_RECENT_DOCUMENTS = 10`. The document cap keeps the oldest records, not
whichever rows MongoDB happened to return last. **Records dropped by the cap
are counted into `unreadable_document_count`**, so the number the UI shows can
never imply the summary read more than it actually did.

### Staleness — three comparisons, no cache
`GET` regenerates when the persisted summary no longer describes the records:
1. the set of readable document ids differs (something uploaded or deleted);
2. `unreadable_document_count` differs (a record became readable, or stopped
   being one);
3. the newest readable document's `uploaded_at` is later than `generated_at`.

No new stored field and no cache layer are involved — the summary document is
already the record of what it was built from. Documents are immutable after
upload, so a later `uploaded_at` means a different set, never a re-save.

Being wrong in one direction costs one cheap deterministic pass. Being wrong in
the other costs a doctor reading a summary that has silently fallen behind the
record list beside it. `POST …/regenerate` is `force=True` and skips all three.

### Medical-safety rules, enforced in code
- **The disclaimer is server-owned.** `SummaryDraft` has no `disclaimer` field,
  so there is nothing for a provider to fill in and nothing it can overwrite.
  `AI_SUMMARY_DISCLAIMER` is written in `_to_document` and is the only source;
  the client's copy in `client/src/utils/disclaimers.ts` is display-only.
- **Attribution is mandatory by construction.** `SummaryItem.source_document_id`
  has no default. Items whose id is not one of this patient's own readable
  document ids are dropped before anything is written, and the drop is counted
  in a log line with no content in it.
- **Restate only.** There is no code path that can emit a diagnosis,
  treatment, drug recommendation, interaction check, risk prediction or
  preventive advice. `Glucose 126 mg/dL` may be stated; "diabetes" is not
  derivable, because nothing in the path maps a number to a condition.
- **A provider failure degrades honestly.** `_generate` catches everything,
  logs the provider name and nothing else, and falls back to the deterministic
  provider with `is_mock` set. No raw exception reaches the client, and the
  fallback cannot fabricate a clinical fact because it only reads what Phase
  4A extracted.
- **The original is always one click away.** Every item links to
  `/doctor/patients/{patientId}/records/{documentId}`.
- **`is_mock` forces a visible label**, so mock output can never be mistaken
  for clinical AI.

---

## 10. Environment variables

### `server/.env`
| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` enforces a real JWT secret and a real email provider |
| `DEBUG` | `true` | Verbose logging |
| `MONGODB_URI` | `mongodb://localhost:27017` | Connection string |
| `MONGODB_DB_NAME` | `careverse` | Database name |
| `JWT_SECRET_KEY` | placeholder | **Must** be changed; boot fails in production |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_EXPIRE_MINUTES` | `60` | Token lifetime |
| `CORS_ORIGINS` | `http://localhost:5173,…` | Comma-separated allowlist |
| `STORAGE_DRIVER` | `local` | `local` now, `s3` later |
| `STORAGE_LOCAL_PATH` | `storage` | Local upload directory |
| `MAX_UPLOAD_MB` | `15` | Per-file upload cap |
| `ALLOWED_MIME_TYPES` | `application/pdf` | Upload allowlist |
| `AI_PROVIDER` | `mock` | Only `mock` in Phase 4B; anything else raises 503 `SummaryProviderUnavailable` |
| `AI_API_KEY` | *(empty)* | **Read by nothing** — reserved for Phase 4C |
| `AI_MODEL` | `gpt-4o-mini` | Phase 4C |
| `AI_BASE_URL` | `https://api.openai.com/v1` | Phase 4C |
| `AI_TIMEOUT_SECONDS` | `30` | Phase 4C |
| `OTP_LENGTH` | `6` | Digits in the reset code (4–10) |
| `OTP_TTL_MINUTES` | `10` | Code lifetime |
| `OTP_MAX_ATTEMPTS` | `5` | Wrong guesses allowed per code |
| `OTP_RESEND_COOLDOWN_SECONDS` | `60` | Minimum gap between codes |
| `RESET_TOKEN_TTL_MINUTES` | `10` | Reset-token lifetime |
| `EMAIL_PROVIDER` | `mock` | `mock` \| `smtp` \| `gmail`; `mock` refused in production |
| `EMAIL_FROM` | `no-reply@careverse.local` | Envelope sender |
| `SMTP_HOST` | *(empty)* | Required when `EMAIL_PROVIDER=smtp` |
| `SMTP_PORT` | `587` | `465` selects implicit TLS |
| `SMTP_USERNAME` | *(empty)* | Omit for unauthenticated relays |
| `SMTP_PASSWORD` | *(empty)* | **Never committed** |
| `SMTP_USE_TLS` | `true` | STARTTLS on non-465 ports |
| `EMAIL_TIMEOUT_SECONDS` | `15` | Mail relay timeout |

### `client/.env`
| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `/api` | Only `VITE_`-prefixed vars reach the browser |

**Secrets:** only server-side variables hold credentials. `AI_API_KEY` never
reaches the client, and no key is committed — `.env` is gitignored in both
projects and `.env.example` carries placeholders only.

---

## 11. Phased implementation plan

### Phase 1 — Foundation ✅
Project structure, both config layers, Mongo connection lifecycle, error
envelope, auth (register/login/me/logout), authorization primitives, design
tokens, reusable UI kit, full route table with honest placeholders, both
`.env.example` files, this document.

### Phase 1b — Password recovery ✅
OTP forgot/reset password, delivered after Phase 1 and ahead of the document
pipeline. Sixth collection (`password_reset_otps`) with a TTL index · bcrypt
for the code, SHA-256 for the reset token · attempt limits, resend cooldown
and single use enforced in the database rather than asserted · email-provider
seam (`mock` / `smtp` / `gmail`) · `/forgot-password` page · 35 backend tests.
**Exit criteria:** a locked-out user resets their password in the browser and
signs in with the new one, which the suite now asserts end to end.

### Phase 2 — Patient profile & document pipeline ✅
`GET`/`PATCH /patients/me` with partial-update and null-clearing semantics ·
`StorageDriver` seam + `LocalStorageDriver` (generated keys, root-confined
paths, staged writes) · PDF upload with MIME **and** magic-byte validation and
a chunked size cap · inline pypdf extraction with `completed` / `needs_ocr` /
`failed` outcomes and explicit bounds · list / detail / delete / file-stream,
every query scoped by `patient_id` and cross-patient access answered `404` ·
patient Dashboard, Profile, Medical Records, Upload and Record Details screens ·
47 new backend tests (82 total).
**Exit criteria:** a patient uploads 3 PDFs, sees them listed, opens one, and
sees the extracted text — **met and asserted end to end**, including the
scanned-document and unreadable-PDF cases.

Structured extraction (`extracted_data`) shipped separately as **Phase 4A**,
ahead of the summary that consumes it. Storing raw text alone was sufficient
until then, and left nothing unread.

### Phase 3 — Doctor access & authorized records ✅
Delivered as **access only**. The AI summary was split out into Phase 4 rather
than bundled here, because authorizing and reading a patient's records is a
different problem from interpreting them, and the access layer has to be
correct on its own before anything is generated from it.

*Backend* — `AccessService` as the sole writer of `patient_access` ·
partial unique index `uniq_active_doctor_patient` over
`(doctor_id, patient_id) where status == "active"` so a pair cannot be
authorized twice, while revoked rows survive as an audit trail · patient-side
`GET`/`POST`/`DELETE /patients/me/access` · `DoctorService` composing the
existing `ProfileService` and `DocumentService` rather than re-querying ·
`DoctorController` running `resolve_patient_id` → `assert_patient_access` →
read, in that order, on all five doctor routes · `utils/responses.pdf_response`
extracted from the Phase 2 document controller so the doctor's file route emits
identical `Content-Disposition`, `nosniff`, CSP and `no-store` headers from one
implementation · five read-only doctor routes.

*Frontend* — `ExtractionPanel`, `DocumentFileActions` and `DetailRow` extracted
from the Phase 2 record screen and reused by the doctor screens, so a report
cannot read one way to the patient who uploaded it and another to the clinician
they authorized · doctor Dashboard, Authorized Patients, Patient Details and
record view · patient-side authorize/revoke panel wired to the dashboard count
that previously read "Available in Phase 3" · the dead route
`/doctor/patients/:patientId/records` (no document id, so it named nothing)
repurposed as the record view `/doctor/patients/:patientId/records/:documentId` ·
the two dead `DOCTOR_NAV` links (`/doctor/patients/records`,
`/doctor/patients/summary`), which had no patient id and so could never resolve,
removed from the sidebar.

*Two things the client had to get right about refusals.* A React Query
observation is **pending but idle** on its first render, so a guard written as
`isLoading` (which is `isPending && isFetching`) falls straight through to the
success path and briefly renders a fully "not recorded" patient to a doctor who
simply has not loaded yet — the doctor pages branch on `isError`, then
`isPending`. And a `403 NO_PATIENT_ACCESS` is **never** retried
(`client/src/utils/query.ts`): it is a decision the server reached deliberately
and will reach identically on the next attempt, so retrying only doubles the
requests made against the authorization endpoint and delays the refusal message
behind a spinner. Only a missing response or a 5xx is retried, once.

*Tests* — 35 new API-level tests (117 total), covering unauthenticated 401,
wrong-role 403, ungranted 403, byte-identical responses for "ungranted" and
"nonexistent" patient ids, doctor A vs doctor B isolation, authorized profile /
list / detail / extracted text / PDF stream, and the four IDOR cases
(unauthorized list, retrieve, extracted text, and file).

**Exit criteria:** a patient authorizes a doctor, the doctor sees exactly that
patient, opens a record, reads the extracted text and downloads the original
PDF — **met and asserted end to end at the API boundary**, including that the
doctor still cannot upload, edit or delete.

### Phase 4A — Deterministic structured extraction ✅
`structured_extraction.extract_structured(text) -> ExtractedData` as a pure,
bounded, exception-safe function — no LLM, no network, no database · eight
categories: four labelled metadata fields plus `lab_values`, `medications`,
`abnormal_findings`, `stated_conditions` · the `flag` rule transcribed rather
than computed (§8) · findings-section capture for lines the document itself
labelled as findings · source attribution on every fact · absent keys rather
than nulls · per-category output caps · wired into `document_service.upload()`
inside the existing `asyncio.to_thread`, and only for
`extraction_status == "completed"`, so `needs_ocr` and `failed` keep
`extracted_data = {}` exactly as in Phase 2 · the Phase 2 assertion
`extracted_data == {}` in `test_documents.py` replaced with a stronger one that
pins the real lab values · 101 new tests.

**Exit criteria:** an uploaded PDF with extractable text receives populated
`extracted_data`; `Glucose: 126 mg/dL` never becomes a condition, a flag, or a
diagnosis — **met and asserted**, along with the `needs_ocr` and `failed` paths
and the Phase 4A determinism and bounds properties.

**Why this is not the summary.** Nothing in this phase generates prose. There is
no `SummaryService`, no AI provider, and no LLM call, and
`/doctor/patients/:patientId/summary` renders a `PhasePlaceholder` that says
so.

### Phase 4B — Summary generation (mock provider) ✅
`SummaryService` + a provider seam + `MockSummaryProvider`, wired to the
`extracted_data` Phase 4A already produced · one summary per patient in
`patient_summaries` under the existing `uniq_patient_summary` index ·
`GET /doctor/patients/{id}/summary` (generates when missing or stale),
`POST /doctor/patients/{id}/summary/regenerate`, and `GET /patients/me/summary`
— no `PUT`/`DELETE`, because a summary is derived, not authored · authorization
unchanged: `assert_patient_access` for the doctor, `assert_own_records` for the
patient, and the service receives only an authorized `patient_id` · items
without a valid same-patient `source_document_id` are dropped before persisting
· all eight §9 sections always present, empty ones saying exactly
"Not found in the uploaded records." · disclaimer written by the server from a
field the provider does not have · `is_mock` stored and labelled in the UI ·
staleness from three comparisons, no cache · the doctor summary screen replaces
its placeholder, rendering disclaimer → mock label → overview → sections →
source links → generation metadata, with one new `SummarySectionCard` · 78 new
tests.

**Exit criteria:** a summary cannot state anything that is not in an uploaded
record of that same patient, cannot be re-attributed after the fact, and is
never presented as real clinical AI — **met and asserted**, including the
no-inference cases carried forward from Phase 4A.

**No real provider exists.** `AI_PROVIDER` accepts only `mock`; `openai` and
`anthropic` raise `SummaryProviderUnavailable`. `AI_API_KEY` is read by nothing
and no HTTP client is called on this path. Phase 4C adds the provider class; the
seam, the controller, the persistence, the validation and the UI already exist
and are exercised by the mock, so that phase changes the prose and nothing else.
The patient-facing summary **endpoint** shipped and is tested, but no
patient-facing summary **screen** was added — the doctor screen was the only
screen in scope for this phase.

### Phase 5 — Demo hardening
Seed script with synthetic demo patients, records and grants (clearly
labelled, in `scripts/` only) · empty/loading/error state pass · responsive +
accessibility pass on the doctor patient-detail screen · README demo script.
**Exit criteria:** a clean-machine demo that cannot be broken by a missing
key or an empty database.

### Explicitly out of scope
OCR, image/document formats other than PDF, S3/Cloudinary, refresh-token
rotation, rate limiting, audit logging, and every feature in §17 of the
product spec.

A scanned PDF is a real case, not an edge case, and this phase answers it
honestly: `needs_ocr`, no invented text, the original still downloadable. An
OCR provider is a later branch behind the same `extract_text()` seam — it is
excluded because a wrong OCR read would enter the summary as a clinical fact,
which is worse than an honest "needs_ocr".

The same reasoning is why Phase 3 shipped no AI summary. Nothing in this phase
interprets a record: the doctor list carries a name, a date of birth and a count
of uploaded files, and that is all. A count of PDFs is a fact about the file
store, not a statement about a patient.

It is also why Phase 4A is deterministic rather than a first AI pass. A pattern
that mis-parses is a wrong fact that a test can catch and a review can trace. A
model that mis-parses is a wrong fact that arrives with a confident tone and no
traceable source, which in a health-records system is the worst possible
failure mode. Everything that can be established by reading what the document
actually says should be established that way first.
