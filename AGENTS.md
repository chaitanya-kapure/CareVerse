# AGENTS.md — CareVerse

Instructions for AI agents working in this repository.

## Git workflow (mandatory)

GitHub sync is **automatic**. After completing any requested code change, do all
of the following without asking for confirmation:

1. `git status` and `git diff` — review what actually changed.
2. Test/verify the change. Do not push code you have not exercised.
3. Stage the relevant files.
4. Commit with a meaningful message explaining *why*, not just *what*.
5. `git push origin main`.
6. Report the commit hash briefly to the user.

**Never force push.** If a push fails, stop and report the error — do not retry
with `--force` or rewrite history to work around it.

### Secrets

Never commit `.env` files, API keys, passwords, tokens, credentials, or any
other secret. Before every push, confirm the staged set contains none of them:

```powershell
git diff --cached --name-only | Select-String -Pattern '\.env$|\.pem$|\.key$|credential'
git grep -nIE '(secret|password|api[_-]?key|token)\s*[:=]\s*["'']?[A-Za-z0-9_\-]{12,}' -- . ':!*.md' ':!*.env.example'
```

Both commands must return nothing before you commit.

## This repository is PUBLIC

Treat every push as a publication. Specifically:

- **Never commit real patient data** — not a sample PDF, not a screenshot, not
  a seed record, not extracted medical text. This is a health-records system;
  real data here is a privacy incident, and public code is permanently indexed
  and mirrored, so deleting a file later does not undo it.
- The only files that belong under `server/storage/` are the two `.gitkeep`
  placeholders. `server/storage/documents/` must never contain a tracked file.
- The AI summary pipeline must never produce a diagnosis, treatment or drug
  recommendation, interaction check, risk prediction, or preventive advice. It
  summarizes what the uploaded records say and states "not found in the uploaded
  records" when they do not say it. It does not fill gaps.

## Project shape

- `client/` — React 18 + TypeScript + Vite 5 + Tailwind + React Router 6 +
  TanStack Query + Axios.
- `server/` — FastAPI + MongoDB (pymongo), layered
  `routes → controllers → services → models`.
- `docs/ARCHITECTURE.md` — the design of record. Read it before changing
  schemas, authorization, or the document/summary pipeline.

### Backend deviates from the original MERN spec

The spec called for Node/Express; this is FastAPI. The deviation is documented
in `README.md` and `docs/ARCHITECTURE.md` §2, including a porting table. The
layering is deliberately portable so an Express port stays mechanical. Do not
"fix" this by rewriting the backend in Node without being asked.

## Conventions that matter

- **The backend is the only authorization boundary.** Never trust a role check
  done in the client. Patient access goes through `assert_patient_access` in
  `app/middlewares/auth_middleware.py` — it is the single OWNER/GRANTED decision
  point.
- **No business logic in components or route handlers.** Controllers stay thin;
  rules live in services; AI calls live in `summaryService`.
- **All medical-safety copy lives in `client/src/utils/disclaimers.ts`** and
  `AI_SUMMARY_DISCLAIMER` in `server/app/config.py`. Do not inline safety
  strings into JSX.
- **Unfinished screens render `PhasePlaceholder`**, which states which phase
  delivers them. Never fake a success state to make a demo look finished.
- Errors use one envelope everywhere: `{"detail": ..., "code": ...}`.

## Environment

- Dev server: Vite binds IPv6 `::1` only — use `http://localhost:5173`, not
  `127.0.0.1:5173`.
- The Vite proxy strips `/api`, so the browser calls `/api/auth/login` and the
  server receives `/auth/login`.
- `npm run dev` from the root starts both services via `concurrently`.
- Server reads `server/.env` (gitignored). `server/.env.example` documents every
  variable.

## Known gaps

- MongoDB is not running in the dev environment; the auth round trip has been
  verified only up to the database boundary (correct `503 DATABASE_UNAVAILABLE`).
  The unauthenticated and validation error paths are verified.
- `npm audit` reports 2 advisories (esbuild moderate, vite high), both
  dev-server-only. The fix is a breaking Vite 5→8 upgrade; do not attempt it
  casually.
