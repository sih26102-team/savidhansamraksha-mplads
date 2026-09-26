# SavidhanSamraksha

AI-powered MPLADS monitoring and risk intelligence for scoped public infrastructure oversight.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `artifacts/savidhan-samraksha` — React/Vite web application with authority login, scoped dashboard, project explorer, evidence detail, workflow actions, and audit history.
- `artifacts/api-server/src/routes` — Express API routes for auth, administration, dashboard analytics, projects, and audit history.
- `artifacts/api-server/src/lib/seed.ts` — deterministic synthetic India hierarchy, users, agencies, projects, findings, payments, photos, and audit seed data.
- `lib/api-spec/openapi.yaml` — API source of truth; generated client hooks and Zod schemas are derived from it.
- `lib/db/src/schema` — Drizzle/PostgreSQL schema for users, administrative hierarchy, agencies, projects, evidence, payments, and flag actions.
- `artifacts/savidhan-samraksha/src/index.css` — application theme and governance-room visual tokens.

## Architecture decisions

- The app uses a signed, HTTP-only JWT-style session cookie for the synthetic demo identities because the prototype must support working role/scope flows without an external identity provider.
- Scope authorization is enforced in API queries, not only in the frontend: ministry is national, state is state-bound, district is district-bound, and MP is constituency-bound/read-only.
- Satellite findings are always labelled simulated or inconclusive; the system does not present unavailable imagery as a negative finding.
- Risk evidence is stored as modular flags and returned as separate Financial & Temporal, Visual & Spatial, and Satellite module results so future adapters can replace demo logic without changing the product surface.
- The seed dataset intentionally uses valid foreign-key relationships and a small set of deterministic anomaly patterns so the demo remains reproducible.

## Product

SavidhanSamraksha provides a governed monitoring room for Ministry, State Nodal, District Nodal, and MP authorities. Users can sign in with synthetic demo accounts, view scoped project analytics, inspect risk findings and evidence, take authorized workflow actions with required reasons, and review an auditable history. MP users are strictly read-only.

## User preferences

The user asked for a realistic, polished, demonstrable government/enterprise monitoring platform using synthetic data only.

## Gotchas

- The API server seeds the development database on first startup; changing seed rules requires a fresh database or an explicit data correction.
- Demo credentials all use `Demo@123`; the exact accounts are shown in the login screen and `/api/auth/demo`.
- Run API code changes through the managed `artifacts/api-server: API Server` workflow and web changes through `artifacts/savidhan-samraksha: web`.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
