# CareVerse — Client

React + TypeScript + Vite frontend for CareVerse.

## Stack

- React 18 + TypeScript
- Vite 5 (dev server + proxy)
- Tailwind CSS
- React Router 6
- TanStack Query (server state)
- Axios (HTTP client)

## Commands

Run these from the repo root with `npm run dev`, or directly here:

| Command | What it does |
| --- | --- |
| `npm install` | Install dependencies |
| `npm run dev` | Start Vite on http://localhost:5173 |
| `npm run build` | Type-check and build to `dist/` |
| `npm run lint` | ESLint |
| `npm run preview` | Serve the production build |

## Dev server

Vite binds IPv6 `::1` only, so use `http://localhost:5173` — not
`http://127.0.0.1:5173`.

The dev proxy forwards `/api/*` to the backend on port 8000 and strips the
`/api` prefix, so the browser calls `/api/auth/login` and the server receives
`/auth/login`. See `vite.config.ts`.

## Environment

Copy `.env.example` to `.env`. All variables are prefixed `VITE_` and are
inlined into the client bundle at build time, so **never put a secret here**.

## Where things live

```
src/
  components/   reusable UI (ui/, auth/) and shared features
  context/      AuthProvider — session state
  hooks/        useAuth and data hooks
  layouts/      AppShell (signed in) and AuthLayout (signed out)
  pages/        one file per screen
  services/     api.ts (axios instance) and per-domain API calls
  types/        shared TypeScript types
  utils/        disclaimers.ts (all medical-safety copy) and navigation
```

Business rules never live in components. Components render; `services/` talks
to the API; the backend is the only thing that enforces authorization.

See `../docs/ARCHITECTURE.md` for the full system design and
`../README.md` for setup.
