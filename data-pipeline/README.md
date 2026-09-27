# 🗄️ Data Pipeline & Ingestion (`data-pipeline/`)

**Module Owner:** Phaneendra (Data Pipeline & Engineering Lead)

The `data-pipeline` module manages synthetic governance dataset generation, ETL (Extract, Transform, Load) pipelines, database seeders, and continuous data integrity validation for the **SavidhanSamraksha** platform.

---

## 🏗️ Data Architecture

The pipeline models the multi-tier Indian administrative hierarchy for MPLADS monitoring:

```
                            [India National Level]
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
     [Lok Sabha Constituencies]                     [Rajya Sabha Allocations]
              │                                               │
              └───────────────────────┬───────────────────────┘
                                      ▼
                                [State Nodal]
                                      │
                                [Districts]
                                      │
                        ┌─────────────┴─────────────┐
                        ▼                           ▼
              [Implementing Agencies]       [Active Projects]
                        │                           │
                        └─────────────┬─────────────┘
                                      ▼
                            [Work Milestone Records]
                          ├── Financial Disbursements
                          ├── Physical Measurement Books (MB)
                          ├── Geotagged Field Photos
                          └── Cryptographic Audit Trail
```

---

## 📂 File Directory

```
data-pipeline/
├── raw_data/
│   └── sample_projects.json            # Curated raw project fixture data
├── scripts/
│   ├── audit-ml-engine.mjs             # Diagnostic inspection of feature distributions
│   ├── check-db.mjs                    # PostgreSQL connectivity and table checks
│   ├── query-demo.mjs                  # Demo account query verification
│   ├── reseed-categories-and-fiscal.mjs # Work category and fiscal year normalization
│   ├── rescore-all-projects-ml.mjs     # Batch ML recalculation over active database
│   ├── seed-demo-users.mjs             # Official governance test accounts provisioning
│   ├── seed-projects.mjs               # Complete project generation & database seeding
│   ├── seed.ts                         # Core TypeScript seed engine
│   └── verify-scores.mjs               # Score audit ensuring zero static fallback mocks
├── etl_pipeline.py                     # Python ETL ingestion & schema validation pipeline
├── package.json                        # NPM package declaration (@workspace/data-pipeline)
└── README.md                           # Module documentation
```

---

## 🚀 Execution Commands

### Run Python ETL Validation
```bash
python etl_pipeline.py
```

### Seed Full Realistic Database
```bash
node scripts/seed-projects.mjs
```

### Provision Official Test Accounts
```bash
node scripts/seed-demo-users.mjs
```

### Batch Recalculate All Project Risk Scores with ML Engine
```bash
node scripts/rescore-all-projects-ml.mjs
```

### Verify Score Distribution (Zero Static Mocks)
```bash
node scripts/verify-scores.mjs
```
