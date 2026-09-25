# CAREVERSE

Centralized patient health records with traceable, AI-assisted summaries.

A patient's medical history is usually scattered across lab reports,
prescriptions and discharge summaries. CAREVERSE gives each patient one
profile, extracts what it can from the PDFs they upload, and gives an
authorized doctor a concise summary — with every claim linked back to the
original document.

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
| AI | Provider-independent, with a deterministic mock fallback |

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

**Phase 1 — foundation only.** Working end to end:

- API boots, connects to MongoDB, creates indexes on startup
- `GET /health`, `POST /auth/register`, `POST /auth/login`,
  `GET /auth/me`, `POST /auth/logout`
- Registration auto-creates the patient's profile
- JWT auth with bcrypt hashing, and the authorization primitives
  (`assert_patient_access`) that every record route will use
- Consistent `{ detail, code }` error envelope across all layers
- Client: landing, login and register screens; role-guarded patient and
  doctor route trees; shared UI kit; design tokens; safety notices

## What comes next

- **Phase 2** — patient profile editing, PDF upload → validation → storage →
  text extraction → structured data, record list/detail/delete, original-file
  streaming
- **Phase 3** — patient-authorized doctor access, doctor screens, and the
  AI summary with a provider abstraction plus a deterministic mock
- **Phase 4** — seed data, state/accessibility pass, demo script

See [§10 of the architecture doc](docs/ARCHITECTURE.md#10-phased-implementation-plan).

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture, MongoDB
  schemas, API reference, authorization rules, upload/extraction and summary
  pipelines, environment variables, phased plan
- [`server/README.md`](server/README.md) — server-specific commands
