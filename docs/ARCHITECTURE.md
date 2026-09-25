# CAREVERSE — Architecture & Design

**Status:** Phase 1 complete (foundation scaffolded). Phases 2–4 not yet built.
**Last updated:** Phase 1

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
  → services/api.ts (axios attaches JWT)
  → GET /api/doctor/patients/{id}/documents
  → routes/documents.py           parse path + deps
  → controllers/document_controller.py
  → middlewares: get_current_user → assert_patient_access
  → services/document_service.py  business rules
  → models/medical_document.py    collection + serializer
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
│       │   ├── LandingPage · LoginPage · RegisterPage · NotFoundPage
│       │   ├── patient/  Dashboard · Profile · MedicalRecords ·
│       │   │             UploadRecord · RecordDetails
│       │   └── doctor/   Dashboard · AuthorizedPatients ·
│       │                 PatientDetails · PatientRecords · PatientSummary
│       ├── services/
│       │   ├── api.ts            # axios instance + error normalization
│       │   └── auth.service.ts
│       ├── types/index.ts
│       └── utils/
│           ├── disclaimers.ts    # all medical-safety copy, one place
│           └── navigation.ts     # role → nav items
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
    │   │   └── health_controller.py
    │   ├── middlewares/
    │   │   ├── auth_middleware.py    # ★ security boundary
    │   │   └── error_handler.py
    │   ├── models/
    │   │   ├── collections.py    # 5 collection names + accessors
    │   │   ├── indexes.py        # startup index creation
    │   │   ├── user.py
    │   │   ├── patient_profile.py
    │   │   ├── medical_document.py
    │   │   ├── access.py
    │   │   └── patient_summary.py
    │   ├── routes/
    │   │   ├── __init__.py       # router registry
    │   │   ├── health.py
    │   │   └── auth.py
    │   ├── schemas/              # Pydantic request/response
    │   │   ├── auth.py
    │   │   └── common.py
    │   ├── services/
    │   │   ├── auth_service.py   # ★ Phase 2: document, extraction,
    │   │   └── __init__.py       #   storage, summary services
    │   └── utils/
    │       ├── security.py       # bcrypt + JWT
    │       └── errors.py         # error envelope helpers
    ├── scripts/                  # seed/demo data (Phase 4)
    └── storage/
        └── documents/            # uploaded PDFs (gitignored)
```

**Not yet created** (arrive with their phase, rather than as empty stubs):
`hooks/usePatientProfile.ts`, `hooks/useDocuments.ts` and the
`services/{storage,document,extraction,summary}*.py` modules.

---

## 4. MongoDB schemas

Five collections. A field that is absent means "not found" — CAREVERSE never
writes a default that could be mistaken for a clinical fact.

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
  "full_name": "Asha Menon",       // seeded from the user at registration
  "date_of_birth": "1992-04-18",   // ISO string, nullable
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
  "storage_key": "b3f1...pdf",
  "mime_type": "application/pdf",
  "size_bytes": 182340,
  "title": "Complete Blood Count",
  "category": "lab_report",        // lab_report|prescription|
                                   // discharge_summary|imaging|other
  "document_date": "2025-11-02",   // date ON the document, not upload date
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

### `patient_summaries`
```jsonc
{
  "_id": ObjectId,
  "patient_id": "<users._id>",     // UNIQUE — one live summary
  "provider": "mock",              // mock|openai|anthropic|custom
  "is_mock": true,                 // surfaced in the UI as a demo label
  "model": null,
  "disclaimer": "AI-generated summary of available records. Verify important
                 information with the original medical documents.",
  "overview": "…",
  "sections": [
    { "key": "lab_values", "title": "Important Lab Values",
      "items": [ { "text": "…", "source_document_id": "…" } ],
      "empty_note": "Not found in the uploaded records." }
  ],
  "source_document_ids": ["…"],
  "source_document_count": 4,
  "unreadable_document_count": 1,
  "generated_at": ISODate
}
```

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

### Patient
| Method | Path | Role | Purpose |
|---|---|---|---|
| 🔒🛡 | GET | `/patients/me` | patient | Own profile |
| 🔒🛡 | PATCH | `/patients/me` | patient | Edit basic details |
| 🔒🛡 | GET | `/patients/me/documents` | patient | Own records, newest first |
| 🔒🛡 | POST | `/patients/me/documents` | patient | Upload PDF (`multipart`) |
| 🔒🛡 | GET | `/patients/me/documents/{documentId}` | patient | Metadata + extracted data + text |
| 🔒🛡 | DELETE | `/patients/me/documents/{documentId}` | patient | Delete record + file |
| 🔒🛡 | GET | `/patients/me/documents/{documentId}/file` | patient | Stream the original PDF |
| 🔒🛡 | GET | `/patients/me/summary` | patient | Own generated summary |
| 🔒🛡 | GET | `/patients/me/access` | patient | Doctors currently authorized |
| 🔒🛡 | POST | `/patients/me/access` | patient | Grant a doctor (`doctor_id`) |
| 🔒🛡 | DELETE | `/patients/me/access/{accessId}` | patient | Revoke |

### Doctor
| Method | Path | Role | Purpose |
|---|---|---|---|
| 🔒🛡 | GET | `/doctor/patients` | doctor | Authorized patients **only** |
| 🔒🛡 | GET | `/doctor/patients/{patientId}` | doctor | Patient basic info |
| 🔒🛡 | GET | `/doctor/patients/{patientId}/documents` | doctor | Record list / timeline |
| 🔒🛡 | GET | `/doctor/patients/{patientId}/documents/{documentId}` | doctor | One record's details |
| 🔒🛡 | GET | `/doctor/patients/{patientId}/documents/{documentId}/file` | doctor | Stream original PDF |
| 🔒🛡 | GET | `/doctor/patients/{patientId}/summary` | doctor | The AI summary ★ |
| 🔒🛡 | POST | `/doctor/patients/{patientId}/summary/regenerate` | doctor | Force regeneration |

### Error envelope
Every failure, from every layer:
```json
{ "detail": "Human readable sentence.", "code": "MACHINE_CODE" }
```
Codes: `MISSING_TOKEN`, `INVALID_TOKEN`, `INVALID_CREDENTIALS`, `FORBIDDEN`,
`NOT_RECORD_OWNER`, `NO_PATIENT_ACCESS`, `ROLE_NOT_ALLOWED`, `NOT_FOUND`,
`EMAIL_TAKEN`, `VALIDATION_ERROR`, `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`,
`EXTRACTION_FAILED`, `DATABASE_UNAVAILABLE`, `INTERNAL_ERROR`.

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

---

## 7. PDF upload & extraction pipeline

```
POST /patients/me/documents  (multipart)
  │
  ├─ 1. multer receives into a temp dir, size-capped at MAX_UPLOAD_MB
  ├─ 2. validate      MIME in ALLOWED_MIME_TYPES (application/pdf)
  │                   + magic bytes start with %PDF-  ← extension lies
  ├─ 3. store         StorageDriver.save() → generated name, never the
  │                   user's filename; returns a storage_key
  ├─ 4. persist       medical_documents row, extraction_status="pending"
  │                   → respond 201 immediately (upload is not blocked
  │                     on extraction)
  ├─ 5. extract       ExtractionService.extract()
  ├─ 6. structure     InformationExtractor.parse(text)
  ├─ 7. store         write extracted_text + extracted_data,
  │                   set extraction_status
  ├─ 8. summarize     SummaryService.regenerate(patient_id)
  └─ 9. cleanup       delete the temp file
```

### Storage abstraction
```python
class StorageDriver(Protocol):
    def save(self, source: Path, key: str) -> StoredFile: ...
    def open(self, key: str) -> BinaryIO: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
```
`LocalStorageDriver` writes under `server/storage/documents/`. An
`S3StorageDriver` can be added later; only the driver name in `.env` changes,
because no caller ever touches a filesystem path.

Uploaded files are **never** served as static files. A `GET …/file` route
re-runs `assert_patient_access` first, then streams. A predictable URL over
`server/storage` would be a total authorization bypass.

### Extraction
- **pypdf** — pure Python, no native build, good enough for digitally
  generated PDFs. This is the direct answer to the spec's "choose a reliable
  PDF text-extraction library".
- Page count and per-page text come from the same read, so pages are
  traceable in the source reference.
- **Low-text PDFs** (below a character threshold) are marked
  `extraction_status = "needs_ocr"`. The UI shows *"This PDF contains no
  readable text. It looks like a scanned or image-only document."*
  **No text is ever fabricated to fill the gap.**
- The extractor sits behind a narrow interface, so an OCR provider can be
  added as a fallback branch later without touching the pipeline.

### Structured extraction
Deterministic, regex/heuristic based — **not** an LLM, so it is testable and
reproducible:

- document date: date-like patterns near "date", "reported on"
- lab values: `name  value unit (range)` with an abnormal flag when the value
  falls outside the stated range, or a neighbouring `H/L/*` marker
- medications: drug-name + dose + frequency patterns in prescription contexts
- abnormal findings: **verbatim sentences** containing abnormal markers
  (elevated, low, positive, abnormal, raised…) — quoted, never paraphrased
- stated conditions: sentences naming a condition **already diagnosed
  elsewhere** — CAREVERSE records them; it does not infer them

Anything not found is simply omitted from the result, which is how "not found
in the uploaded records" propagates to the summary.

---

## 8. Summary generation

```
SummaryService.regenerate(patient_id)
  │
  ├─ load documents for the patient
  ├─ select those with extraction_status == "completed"
  │     (needs_ocr / failed are counted, never summarized)
  ├─ build the provider input:
  │     { profile, documents: [{ id, title, document_date,
  │                              category, text, extracted_data }] }
  ├─ provider = get_provider()          ← single switch point
  ├─ result = provider.generate(input)
  ├─ validate the shape (sections present, disclaimer intact)
  └─ upsert patient_summaries (1 per patient)
```

### Provider abstraction
```python
class SummaryProvider(Protocol):
    name: str
    def generate(self, payload: SummaryInput) -> SummaryResult: ...
```
`summary_service.get_provider()` returns:
- `OpenAIProvider` / `AnthropicProvider` when `AI_API_KEY` is set
- `MockProvider` otherwise — **deterministic**, so the demo works offline

`is_mock` and `provider` are **stored on the summary document**, not inferred
at read time, and the UI labels mock output explicitly. A demo can never
mistake a fallback for a real model.

### The mock summarizer
Not random prose — it assembles the real `extracted_data` that the pipeline
actually produced, sorted chronologically. It demonstrates the exact output
shape and traceability that the real provider must match, so swapping in an
API key changes only the prose, not the UI contract.

### Fixed output sections
`PATIENT OVERVIEW` · `AVAILABLE MEDICAL HISTORY` · `KEY FINDINGS FROM RECORDS` ·
`IMPORTANT LAB VALUES` · `RECENT RECORDS` · `MEDICATIONS MENTIONED IN RECORDS` ·
`ABNORMAL VALUES / FINDINGS MENTIONED IN RECORDS` · `CHRONOLOGICAL RECORD OVERVIEW`

Every section carries an `empty_note` of
**"Not found in the uploaded records."** A missing section is always stated
explicitly, never left blank — silence would read as "nothing wrong".

### Prompt-level safety rules
- Restate only; never infer, diagnose, or recommend.
- Quote values; never round, correct, or reinterpret a lab number.
- Attribute every statement to a document id; omit anything untraceable.
- State "not found" rather than filling a gap with a plausible value.
- On failure or timeout, fall back to `MockProvider` and set `is_mock`.

### Medical-safety rules, enforced in code
- The prompt instructs summarization only; there is no code path that can
  emit a diagnosis, treatment, or drug recommendation.
- `AI_SUMMARY_DISCLAIMER` is a single constant on the server **and** in
  `client/src/utils/disclaimers.ts`, rendered on every summary view.
- Original PDFs are always reachable from the summary via source links.
- `patient_summaries.is_mock` forces a visible demo label.

---

## 9. Environment variables

### `server/.env`
| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` enforces a real JWT secret |
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
| `AI_PROVIDER` | `mock` | Provider id |
| `AI_API_KEY` | *(empty)* | Empty ⇒ mock summarizer |
| `AI_MODEL` | `gpt-4o-mini` | Model id |
| `AI_BASE_URL` | `https://api.openai.com/v1` | Provider base URL |
| `AI_TIMEOUT_SECONDS` | `30` | Provider request timeout |

### `client/.env`
| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `/api` | Only `VITE_`-prefixed vars reach the browser |

**Secrets:** only server-side variables hold credentials. `AI_API_KEY` never
reaches the client, and no key is committed — `.env` is gitignored in both
projects and `.env.example` carries placeholders only.

---

## 10. Phased implementation plan

### Phase 1 — Foundation ✅ (this commit)
Project structure, both config layers, Mongo connection lifecycle, error
envelope, auth (register/login/me/logout), authorization primitives, design
tokens, reusable UI kit, full route table with honest placeholders, both
`.env.example` files, this document.

### Phase 2 — Patient profile & document pipeline
Patient profile read/edit · storage driver + local implementation · PDF
upload with MIME + magic-byte validation · pypdf extraction with
`needs_ocr` handling · structured extraction · document list/detail/delete ·
file streaming with authorization · patient record screens.
**Exit criteria:** a patient uploads 3 PDFs, sees them listed, opens one, and
sees the extracted text.

### Phase 3 — Authorization & AI summary
Patient grants/revokes doctor access · `assert_patient_access` wired into
every doctor route · doctor authorized-patients list · patient detail/records/
summary screens · provider abstraction + mock summarizer + real provider ·
source-linked summary rendering with the disclaimer.
**Exit criteria:** the full §16 demo flow runs end to end.

### Phase 4 — Demo hardening
Seed script with synthetic demo patients, records and grants (clearly
labelled, in `scripts/` only) · empty/loading/error state pass · responsive +
accessibility pass on the doctor patient-detail screen · README demo script.
**Exit criteria:** a clean-machine demo that cannot be broken by a missing
key or an empty database.

### Explicitly out of scope
OCR, image/document formats other than PDF, S3/Cloudinary, refresh-token
rotation, rate limiting, audit logging, and every feature in §17 of the
product spec.
