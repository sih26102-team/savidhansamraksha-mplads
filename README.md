<div align="center">

# 🏛️ SavidhanSamraksha — MPLADS Monitoring Platform

### *CivicShield AI-Powered Infrastructure Governance System*

[![CI Status](https://github.com/sih26102-team/savidhansamraksha-mplads/actions/workflows/ci.yml/badge.svg)](https://github.com/sih26102-team/savidhansamraksha-mplads/actions)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-blue.svg)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-19.1-61dafb.svg)](https://react.dev/)
[![Python](https://img.shields.io/badge/Python-3.11-yellow.svg)](https://www.python.org/)
[![pnpm](https://img.shields.io/badge/pnpm-workspace-f69220.svg)](https://pnpm.io/)

*Smart India Hackathon 2026 — AI-Powered Audit System for MPLADS Funds*

</div>

---

## 🎯 Problem Statement

India's Members of Parliament Local Area Development Scheme (MPLADS) disburses **₹5 crore per MP per year** for local infrastructure works across 543 Lok Sabha + 250 Rajya Sabha constituencies. Despite the scale, there is **no unified real-time system** to track physical vs. financial progress, detect expenditure anomalies, or escalate governance failures through official channels.

---

## 🚀 Our Solution — SavidhanSamraksha

A **production-grade, full-stack AI monitoring platform** that:

| Feature | Description |
|:---|:---|
| 🧠 **ML Risk Engine** | Hybrid Isolation Forest + Domain Heuristic model producing real dynamic risk scores (6–99) per project |
| 📊 **Live Analytics Dashboard** | Real-time KPIs, project mix charts, fiscal year spending, and escalation queues |
| 🏛️ **Hierarchical Governance** | Role-based access for District Collectors, State Nodal Officers, CAG Auditors, and MPs |
| ⚖️ **Escalation State Machine** | Formal workflow to freeze sanctions, order inquiries, and escalate to national oversight |
| 🔐 **Cryptographic Audit Trail** | Tamper-evident SHA-256 hash-chained action log for every administrative decision |
| 📸 **Photo Evidence Integrity** | EXIF metadata validation, GPS clustering, and duplicate detection for field photos |

---

## 👥 Team & Module Ownership

| Domain Module | Owner | Responsibility |
|:---|:---|:---|
| [`ml-engine/`](./ml-engine/) | **Kousic** | ML Inference Engine, Isolation Forest, Feature Engineering, Python CLI |
| [`data-pipeline/`](./data-pipeline/) | **Phaneendra** | ETL Pipelines, Synthetic Database Seeders, Data Validation & Integrity |
| [`backend-case/`](./backend-case/) | **Poornesh** | Case Management, Escalation Router, State Machine, Audit Logger |
| [`backend-data/`](./backend-data/) | **Mokshagna** | Express REST API, PostgreSQL Drizzle ORM, Session Auth, Analytics |
| [`frontend-dashboard/`](./frontend-dashboard/) | **Chandana** | React 19 SPA, Tailwind UI, Charts, Governance Scope Selector, Escalation Queue |
| [`cloud-devops/`](./cloud-devops/) | **Mohith** | Docker Compose, GitHub Actions CI, Render/Vercel Deployment, Infra-as-Code |

---

## 🗂️ Repository Structure

```
SavidhanSamraksha-Monitoring-Platform/
│
├── 🧠 ml-engine/                      # Kousic — ML Risk & Anomaly Scoring
│   ├── src/
│   │   ├── index.ts                   # TypeScript package exports
│   │   └── ml-risk-engine.ts          # In-memory hybrid ML inference engine
│   ├── model_artifacts/weights.json   # Trained model weights & thresholds
│   ├── risk_engine.py                 # Python standalone CLI inference engine
│   ├── feature_engineering.py         # Feature extraction & normalization pipeline
│   ├── evaluate_models.py             # Accuracy benchmark suite (3/3 PASSED)
│   └── requirements.txt               # Python ML dependencies
│
├── 📦 data-pipeline/                  # Phaneendra — Data Ingestion & Seeding
│   ├── raw_data/sample_projects.json  # Curated realistic project fixture records
│   ├── scripts/                       # All seed, rescore, verify, and ETL scripts
│   └── etl_pipeline.py               # Python ETL ingestion & validation pipeline
│
├── ⚖️ backend-case/                   # Poornesh — Case Management Engine
│   └── src/
│       ├── workflow-state-machine.ts  # NORMAL → FLAGGED → ESCALATED → RESOLVED
│       ├── escalation-router.ts       # Multi-tier routing & SLA deadline assignment
│       ├── audit-logger.ts            # SHA-256 tamper-evident audit chain
│       └── notification-dispatcher.ts # SLA breach & freeze order alerts
│
├── 🗄️ backend-data/                   # Mokshagna — Core Express API Server
│   ├── src/
│   │   ├── routes/                    # auth, dashboard, projects, audit, health
│   │   └── lib/                       # ml-risk-engine, project-data, seed, session
│   ├── db/                            # Drizzle schema (projects, users, agencies, audit)
│   └── build.mjs                      # Esbuild production bundler
│
├── 🖥️ frontend-dashboard/             # Chandana — React 19 Web Application
│   └── src/
│       ├── App.tsx                    # 4000+ lines — full governance dashboard SPA
│       ├── components/ui/             # 50+ Radix/Shadcn UI primitives
│       └── index.css                  # Tailwind v4 governance theme tokens
│
├── ☁️ cloud-devops/                   # Mohith — Docker, CI/CD, Deployment
│   ├── docker/
│   │   ├── Dockerfile.api             # Multi-stage Express API container
│   │   └── Dockerfile.frontend        # React + Nginx production container
│   ├── docker-compose.yml             # Full-stack local orchestration
│   ├── render.yaml                    # Render.com deployment blueprint
│   ├── vercel.json                    # Vercel SPA + API proxy config
│   └── .github/workflows/ci.yml       # GitHub Actions validation pipeline
│
├── 📚 lib/                            # Shared TypeScript workspace libraries
│   ├── db/                            # @workspace/db — Drizzle ORM & PostgreSQL schema
│   ├── api-zod/                       # @workspace/api-zod — Validated Zod API types
│   └── api-client-react/              # @workspace/api-client-react — React Query hooks
│
├── 🛠️ scripts/                        # Root development orchestration scripts
│   ├── dev.mjs                        # Concurrent API + Frontend dev runner
│   ├── start-db.mjs                   # PostgreSQL daemon management
│   └── seed-demo-users.mjs            # Demo governance account provisioning
│
├── .github/workflows/ci.yml           # Root CI/CD pipeline (Git-tracked)
├── docker-compose.yml                 # Root docker-compose for easy access
├── .env.example                       # Master environment variable template
├── package.json                       # Root pnpm workspace scripts
├── pnpm-workspace.yaml                # Monorepo package declarations
└── tsconfig.json                      # TypeScript project references root
```

---

## ⚙️ Local Setup Guide

### Prerequisites

| Tool | Version | Purpose |
|:---|:---|:---|
| Node.js | 22+ | Runtime |
| pnpm | 9+ | Monorepo package manager |
| PostgreSQL | 16+ | Database |
| Python | 3.11+ | ML engine |

### Step 1 — Clone & Install

```bash
git clone https://github.com/sih26102-team/savidhansamraksha-mplads.git
cd savidhansamraksha-mplads
pnpm install
```

### Step 2 — Configure Environment

```bash
cp .env.example .env
# Edit DATABASE_URL, SESSION_SECRET as needed
```

### Step 3 — Setup PostgreSQL

> Already have PostgreSQL 18 installed? Just set `DATABASE_URL` in your `.env`.

```bash
# Start your local PostgreSQL instance (port 5433)
pnpm run db:start
```

### Step 4 — Initialize Database Schema & Seed Data

```bash
# Push schema to the database
pnpm --filter @workspace/db run push

# Seed realistic synthetic project data
node scripts/seed-projects.mjs

# Provision demo governance accounts
node scripts/seed-demo-users.mjs
```

### Step 5 — Install Python ML Dependencies

```bash
pip install -r ml-engine/requirements.txt
```

### Step 6 — Run ML Engine Tests

```bash
cd ml-engine
python risk_engine.py --test
python evaluate_models.py
```

### Step 7 — Start Full Dev Stack

```bash
pnpm run dev
```

- **Frontend**: http://localhost:5173
- **API Server**: http://localhost:5000

---

## 🔑 Demo Login Accounts

| Role | Email | Password | Scope |
|:---|:---|:---|:---|
| District Collector | `collector@district.gov.in` | `demo123` | Visakhapatnam District |
| State Nodal Officer | `nodal@ap.gov.in` | `demo123` | Andhra Pradesh State |
| Ministry (Central) | `ministry@mplads.gov.in` | `demo123` | National (All Projects) |
| Lok Sabha MP | `mp.loksabha@parliament.in` | `demo123` | Visakhapatnam Constituency |

---

## 🤖 ML Risk Engine Architecture

The risk scoring model is a **hybrid ensemble** combining:

$$\text{RiskScore} = 0.40 \times \text{IsolationForest}(\vec{x}) \times 100 + 0.60 \times \text{DomainPenalty}(\vec{x})$$

| Feature | Formula | Risk Type Detected |
|:---|:---|:---|
| `progressExpenditureDivergence` | $\text{expRate} - \text{progressRate}$ | Ghost works / payment fraud |
| `costRatio` | $\frac{\text{Sanctioned}}{\text{Estimated}}$ | Budget inflation |
| `timeElapsedRatio` | $\frac{\text{Elapsed}}{\text{Planned Duration}}$ | Schedule slippage |
| `governanceComplianceScore` | Deductions for missing tenders/UCs | Regulatory non-compliance |
| `evidenceIntegrityScore` | EXIF/duplicate photo deductions | Photo fraud |

Scores below 40 → **LOW** | 40–70 → **MODERATE** | 70+ → **HIGH** | Missing data → **DATA_INCOMPLETE**

---

## 🐳 Docker Deployment

```bash
# Start complete stack with one command
docker-compose up -d --build

# Services launched:
# - Frontend Dashboard  → http://localhost:80
# - Backend API         → http://localhost:5000
# - PostgreSQL          → localhost:5433
```

---

## 🏆 Hackathon Submission

- **Event**: Smart India Hackathon 2026
- **Problem Statement**: AI-Powered Audit System for MPLADS Funds
- **Team**: CivicShield AI (6 Members)
- **Category**: Government / GovTech / Open Innovation
- **Institution**: [Your Institution Name]

---

<div align="center">
<sub>Built with ❤️ by Team CivicShield AI for SIH 2026 · Protecting India's Public Infrastructure Funds</sub>
</div>
