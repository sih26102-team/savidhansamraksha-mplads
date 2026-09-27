# ☁️ Cloud Infrastructure & DevOps (`cloud-devops/`)

**Module Owner:** Mohith (DevOps & Infrastructure Lead)

The `cloud-devops` module manages containerization, Docker orchestration, automated CI/CD GitHub Action workflows, environment configurations, and cloud deployment manifests (Render, Vercel) for the **SavidhanSamraksha** platform.

---

## 🚢 Deployment Architecture

```
                  GitHub Repository (main branch)
                                │
          ┌─────────────────────┴─────────────────────┐
          ▼                                           ▼
 [GitHub Actions CI]                         [Automated Deploy]
  - Node 22 & Python 3.11                     - Render (Backend API + Postgres)
  - Typecheck & Linting                       - Vercel (Frontend Dashboard SPA)
  - ML Benchmark Evaluation
  - Multi-stage Docker Builds
```

---

## 📂 File Directory

```
cloud-devops/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # GitHub Actions CI validation workflow
│       └── deploy.yml             # Cloud continuous deployment workflow
├── docker/
│   ├── Dockerfile.api             # Multi-stage production container for Express API
│   └── Dockerfile.frontend        # React 19 production build + Nginx reverse proxy
├── .env.example                   # Master template for production & development env vars
├── deploy-local.ps1               # Automated local deployment script for Windows
├── deploy-local.sh                # Automated local deployment script for Linux / macOS
├── docker-compose.yml             # Full-stack local orchestration (Postgres, API, UI)
├── package.json                   # NPM package declaration (@workspace/cloud-devops)
├── render.yaml                    # Render.com infrastructure as code blueprint
├── vercel.json                    # Vercel configuration for SPA routing & API proxy
└── README.md                      # Module documentation
```

---

## 🚀 Execution Commands

### Launch Entire Stack with Docker Compose
```bash
docker-compose up -d --build
```

### Stop All Services
```bash
docker-compose down
```

### Stream Container Logs
```bash
docker-compose logs -f
```
