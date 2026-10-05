# CAREVERSE

Centralized patient health records with traceable, AI-assisted summaries.

A patient's medical history is usually scattered across lab reports,
prescriptions and discharge summaries. CAREVERSE gives each patient one
profile, extracts what it can from the PDFs they upload, and gives an
authorized doctor a concise summary — with every claim linked back to the
original document.

The summary is produced behind a **provider seam**, selected by `AI_PROVIDER`.
Two implementations ship:

- `mock` (**the default**) assembles the sections deterministically from the
  extracted data. No language model, no network call, no account. It is
  reproducible, offline, free, and it cannot invent a finding. It is also the
  automatic fallback if a real provider fails mid-request.
- `openai` calls any OpenAI-compatible chat-completions endpoint once per
  summary, over plain `httpx`, with a JSON response format. Everything it
  returns is validated before it is stored, and every claim must name a
  document belonging to that same patient or it is dropped.

Either way the summary is labelled with what produced it. A deterministic
fallback is stored with `is_mock: true` and the UI shows a demo label; it is
never presented as a model's output.

> **CAREVERSE is not a diagnostic system.** It summarizes documents that
> already exist. It does not diagnose conditions, recommend treatment, or
> check for drug interactions. See
> [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 · Vite 5 · TypeScript · Tailwind CSS · React Router · TanStack Query · Axios |
| Backend | Python 3.13 · FastAPI · Pydantic v2 · PyMongo |
| Database | MongoDB |
| Auth | JWT (HS256) · bcrypt |
| Uploads | python-multipart · pypdf |
| AI | Provider-independent seam · `mock` (deterministic, default) or `openai` (any OpenAI-compatible endpoint, via `httpx`) |

> The original spec asked for MERN (Node + Express). At your direction the
> pre-existing **Python FastAPI** backend was kept instead, so the client is
> TypeScript exactly as specified but the backend is not Node. See
> [§2 of the architecture doc](docs/ARCHITECTURE.md#2-architecture) for what
> this changes and how a later port to Express would work.

---

## Prerequisites

- **Node.js 18+**
- **Python 3.11+**
- **MongoDB** running locally (`mongodb://localhost:27017`)

### Running MongoDB

No credentials are involved in local development. The API connects to a
plain, unauthenticated local instance via `MONGODB_URI` in `server/.env`
(default `mongodb://localhost:27017`).

**If it is already a Windows service**, start it and move on:

```powershell
Get-Service MongoDB | Start-Service
```

**If you have no service** — the MSI sometimes installs the binaries without
registering one — run `mongod` directly. This needs no administrator rights:

```powershell
$env:MONGODB_LOG = "$env:TEMP\mongod.log"
mongod --dbpath "$env:TEMP\mongo-data" --port 27017 --bind_ip 127.0.0.1
```

Leave that window open while developing. To install it first:

```powershell
winget install --id MongoDB.Server --exact
```

`mongod` must be on your `PATH`; it is not added automatically. If the
`winget` install prompts for elevation and you want to skip it, download the
archive from the MongoDB downloads page and copy `mongod.exe` somewhere on
your `PATH`.

Verify with `GET /health` — it reports `database: connected` on success and
`database: unavailable` when Mongo is not reachable, so you always get an
honest answer instead of a connection error at the first request.

## Setup

```bash
# 1. Client dependencies
npm install                 # runs the client install via postinstall

# 2. Server dependencies
cd server
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt     # macOS / Linux
cd ..

# 3. Environment files
copy server\.env.example server\.env      # Windows
# cp server/.env.example server/.env      # macOS / Linux
copy client\.env.example client\.env      # Windows
```

The defaults work as-is for local development. `server/.env` ships with a
placeholder `JWT_SECRET_KEY`, which is fine in development and **refuses to
boot** if `ENVIRONMENT=production`.

## Run

```bash
npm run dev
```

This starts both services side by side:

| Service | URL |
|---|---|
| Client (Vite) | http://localhost:5173 |
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

The Vite dev server proxies `/api/*` to the API, so there is no CORS setup
needed in development.

To run them separately:

```bash
npm run dev:server     # or: python server/dev.py
npm run dev:client
```

## Verify the install

```bash
curl http://localhost:8000/health
```

```json
{ "status": "ok", "database": "connected",
  "environment": "development", "ai_provider": "mock" }
```

`status` is `degraded` and `database` is `unavailable` when MongoDB is not
running — the API still boots so the cause is visible instead of a crash loop.

## Scripts

| Command | Does |
|---|---|
| `npm run dev` | API + client together |
| `npm run dev:server` / `dev:client` | One at a time |
| `npm run build` | Typecheck + production client build |
| `npm run lint` | ESLint |
| `npm run typecheck` | `tsc --noEmit` |

---

## What works today

Phases 1 through 4B. Working end to end:

- **Foundation** — API boots, connects to MongoDB, creates indexes on startup;
  `GET /health` reports database and AI provider; JWT auth with bcrypt
  hashing; consistent `{ detail, code }` error envelope across all layers
- **Accounts** — register, login, `GET /auth/me`, logout, and password
  recovery via a single-use OTP (`forgot-password` → `verify-reset-otp` →
  `reset-password`). Registration auto-creates the patient's profile
- **Patient profile** — view and edit, including the three fields a summary is
  allowed to use (`full_name`, `date_of_birth`, `gender`)
- **Document pipeline** — PDF upload → MIME and magic-byte validation → size
  cap → storage → text extraction; own-records list, detail, delete, and
  streaming of the original file. Upload succeeds even when extraction fails,
  and says so in plain language rather than reporting the upload as broken
- **Structured extraction (4A)** — deterministic, offline parsing of dates,
  lab values, medications and stated conditions into a typed `extracted_data`
  block. No model, no network, no API key
- **Doctor access (3)** — a patient authorizes a named doctor, and revokes
  them. Every doctor record route runs through `assert_patient_access`, so
  "no such patient" and "not authorized" are the same `403`
- **Summary (4B)** — a doctor's summary of one patient, and the patient's view
  of their own. Eight fixed sections, every claim carrying the id of the
  record it came from, and the provenance count stated on screen

### About the summary

**`AI_PROVIDER=mock` is the default and needs no third-party account.**
`MockSummaryProvider` assembles sections by pattern-matching the extracted data,
so it is reproducible, offline, and free — and it is labelled as a mock in the
response, in the UI, and in the API reference. It never infers, interprets or
predicts; it copies what a record says, or states that the uploaded records do
not say.

**`AI_PROVIDER=openai` adds one real provider** behind the same seam, with no
change to any route, schema, stored document or component. Set `AI_API_KEY` and
`AI_MODEL` in `server/.env`; the key is read only by the server and never
reaches the client bundle, a response, or a log line. A summary generated by
this provider is stored with `is_mock: false` and the demo label is hidden.

Two behaviours worth knowing before you turn it on:

- **A runtime failure degrades honestly.** A timeout, a refused connection, a
  `429` or a `5xx` falls back to the deterministic summary, stored with
  `is_mock: true`, so the UI still shows the demo label. Nothing claims a model
  wrote output it did not.
- **A configuration failure does not.** `AI_PROVIDER=openai` with no
  `AI_API_KEY`, or an endpoint that answers `401`, is permanent. It fails with
  `503 SUMMARY_PROVIDER_UNAVAILABLE` naming the variable to set, persists
  nothing, and is not retried. Naming a provider this build does not implement —
  `anthropic` — fails the same way.

The model summarizes and does not interpret. It is instructed not to diagnose,
predict, recommend, or infer a condition from a value, and every claim it
returns must carry the id of one of this patient's own records or be dropped. A
medical document's text is treated as untrusted data, never as instructions. See
[§9 of the architecture doc](docs/ARCHITECTURE.md#9-summary-generation) for the
prompt, the validation chain, and the limits.

## What comes next

- **Phase 5** — seed data, state/accessibility pass, demo script

See [§10 of the architecture doc](docs/ARCHITECTURE.md#10-phased-implementation-plan).

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture, MongoDB
  schemas, API reference, authorization rules, upload/extraction and summary
  pipelines, environment variables, phased plan
- [`server/README.md`](server/README.md) — server-specific commands
