# 🗄️ Backend Data & Core API (`backend-data/`)

**Module Owner:** Mokshagna (Backend Data & Database Lead)

The `backend-data` module is the core Express.js REST API server and PostgreSQL database persistence layer for **SavidhanSamraksha**. It serves analytics data, enforces role-based session authentication, manages project life cycles, and executes database queries via Drizzle ORM.

---

## 🏛️ System Architecture

```
                             HTTP Requests (Port 5000)
                                        │
                                        ▼
                                [Express Router]
                                        │
      ┌───────────────┬─────────────────┼─────────────────┬───────────────┐
      ▼               ▼                 ▼                 ▼               ▼
 [Auth Routes]  [Dashboard API]  [Project Routes]  [Audit History] [Admin Master]
  Cookie session  Totals, Mix,    Search, Filters,   Action trail    States, MPs,
    management     Risk scores     Evidence, Action   verification    Districts
      │               │                 │                 │               │
      └───────────────┼─────────────────┴─────────────────┴───────────────┘
                      ▼
               [Drizzle ORM]
                      ▼
      [PostgreSQL Database (Port 5433)]
       ├── users
       ├── projects
       ├── project_milestones
       ├── project_escalations
       ├── project_findings
       ├── project_payments
       ├── project_photos
       └── flag_actions
```

---

## 📂 File Directory

```
backend-data/
├── db/
│   ├── drizzle/               # Drizzle migration SQL files
│   ├── src/
│   │   ├── schema/
│   │   │   ├── administration.ts  # States, districts, constituencies
│   │   │   ├── agencies.ts        # Implementing agencies
│   │   │   ├── audit.ts           # Flag actions & escalation logs
│   │   │   ├── index.ts           # Schema master export
│   │   │   ├── projects.ts        # Projects, payments, photos, findings
│   │   │   └── users.ts           # User accounts & roles
│   │   └── index.ts           # Database connection client
│   └── drizzle.config.ts      # Drizzle migration configuration
├── src/
│   ├── lib/
│   │   ├── ml-risk-engine.ts  # ML risk inference engine
│   │   ├── project-data.ts    # Project data access layer & queries
│   │   ├── seed.ts            # Synthetic India hierarchy seeder
│   │   └── session.ts         # User session & cookie handling
│   ├── routes/
│   │   ├── administration.ts  # Geography & administrative boundaries
│   │   ├── audit.ts           # Audit log history
│   │   ├── auth.ts            # Login, demo accounts, logout, session info
│   │   ├── dashboard.ts       # Analytics aggregation & KPI totals
│   │   ├── health.ts          # Healthcheck endpoint
│   │   └── projects.ts        # Project detail, filtering & actions
│   └── index.ts               # Express application entrypoint
├── build.mjs                  # Esbuild bundler script
├── package.json               # NPM package declaration (@workspace/backend-data)
├── tsconfig.json              # TypeScript configuration
└── README.md                  # Module documentation
```

---

## 🚀 Execution Commands

### Build API Server Bundle
```bash
node build.mjs
# or
pnpm run build
```

### Start API Server
```bash
node --enable-source-maps ./dist/index.mjs
```

### Run Type Checking
```bash
pnpm run typecheck
```
