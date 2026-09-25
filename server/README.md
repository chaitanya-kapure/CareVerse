# CAREVERSE API (FastAPI)

Layering, top to bottom:

```
routes/       path, method, dependencies, status code, response model
controllers/  orchestration
services/     business logic  ← AI logic lives ONLY here
models/       collections, document shapes, indexes
middlewares/  auth, authorization, error envelope
schemas/      Pydantic request/response validation
```

## Setup

```bash
python -m venv .venv

# Windows
.venv\Scripts\python -m pip install -r requirements.txt
# macOS / Linux
.venv/bin/python -m pip install -r requirements.txt

copy .env.example .env     # Windows
# cp .env.example .env     # macOS / Linux
```

## Run

```bash
python dev.py                 # recommended, resolves the venv for you
python dev.py --port 8001
python dev.py --no-reload
```

Or directly:

```bash
.venv/Scripts/python -m uvicorn app.main:app --reload
```

| URL | Purpose |
|---|---|
| `http://127.0.0.1:8000/health` | Health + database state |
| `http://127.0.0.1:8000/docs` | Swagger UI |
| `http://127.0.0.1:8000/redoc` | ReDoc |

## Configuration

Everything is read in `app/config.py` from `.env`; no other module touches
`os.environ`. See `.env.example` for the full list.

**Before deploying:** set a real `JWT_SECRET_KEY`. The app raises on startup
if `ENVIRONMENT=production` and the value is still the placeholder:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Indexes

Created idempotently on startup by `app/models/indexes.py`. The security-relevant
one is the unique index on `patient_profiles.patient_id`, which is what makes
"one profile per patient" a database guarantee rather than a convention.

## Uploaded documents

`storage/documents/` holds the original PDFs. It is gitignored: these are
patient health records and must not enter version control.

Uploaded files are **never** served as static files — a `GET …/file` route
re-runs `assert_patient_access` first. Serving `storage/` directly over HTTP
would be a complete authorization bypass.
