# 🧠 ML Engine (`ml-engine/`)

**Module Owner:** Kousic (AI & Machine Learning Lead)

The `ml-engine` module houses the predictive risk inference models, multi-factor anomaly scoring algorithms, and automated audit explanation generation for the **SavidhanSamraksha** platform.

---

## 📐 Architecture & Model Methodology

The risk engine employs a **hybrid ensemble architecture** combining unsupervised anomaly detection with multi-factor domain loss minimization:

```
                                Raw Project Telemetry
                                         │
                         ┌───────────────┴───────────────┐
                         ▼                               ▼
                 Feature Extraction             Metadata Validation
             (Expenditure, Milestones,       (Tender Status, UC Filing,
                 Timelines, Costs)             EXIF / Photo Integrity)
                         │                               │
                         └───────────────┬───────────────┘
                                         ▼
                            Normalized Feature Vector (7D)
                                         │
                  ┌──────────────────────┴──────────────────────┐
                  ▼                                             ▼
        Isolation Forest Anomaly                      Domain Penalty Heuristics
       Statistical outlier score (0-1)              (Financial Divergence, Delay,
              (40% Weight)                         Governance, Evidence Tampering)
                  │                                             │
                  └──────────────────────┬──────────────────────┘
                                         ▼
                             Ensemble Risk Evaluator
                                         │
                  ┌──────────────────────┼──────────────────────┐
                  ▼                      ▼                      ▼
           Risk Score (6-99)        Risk Level          Dynamic Reasoning
             Bounded Float      (LOW, MODERATE, HIGH,    Audit findings &
                                  DATA_INCOMPLETE)      evidence breakdown
```

### Feature Vector Formulation

| Feature Index | Feature Identifier | Mathematical Definition | Risk Target |
|:---:|:---|:---|:---|
| 0 | `costRatio` | $\frac{\text{Sanctioned Amount}}{\text{Estimated DPR Cost}}$ | Budget inflation / cost overrun |
| 1 | `expenditureRate` | $\frac{\text{Expenditure Incurred}}{\text{Sanctioned Amount}}$ | Disbursement velocity |
| 2 | `progressRate` | $\frac{\text{Physical Progress \%}}{100}$ | Ground progress |
| 3 | `progressExpenditureDivergence` | $\text{expenditureRate} - \text{progressRate}$ | Payment ahead of milestones (Ghost works) |
| 4 | `timeElapsedRatio` | $\frac{\text{Current Date} - \text{Date of Sanction}}{\text{Target Date} - \text{Date of Sanction}}$ | Schedule slippage / deadlocks |
| 5 | `governanceComplianceScore` | Deductions for missing tenders, late UCs, unverified approvals | Regulatory adherence |
| 6 | `evidenceIntegrityScore` | Deductions for duplicate EXIF coordinates, missing photo tags | Visual evidence fraud |

---

## 📂 File Directory

```
ml-engine/
├── model_artifacts/
│   └── weights.json          # Pre-trained model weights, penalty multipliers, and thresholds
├── src/
│   ├── index.ts              # TypeScript workspace package export
│   └── ml-risk-engine.ts     # In-memory TypeScript production inference engine
├── evaluate_models.py        # Accuracy, ROC-AUC, and scenario benchmark suite
├── feature_engineering.py    # Feature extraction & telemetry transformation pipeline
├── package.json              # NPM package declaration (@workspace/ml-engine)
├── requirements.txt          # Python dependencies
├── risk_engine.py            # Standalone Python inference engine & CLI
├── tsconfig.json             # TypeScript project config
└── README.md                 # Module documentation
```

---

## 🚀 Usage & Commands

### Running Python Self-Test
```bash
python risk_engine.py --test
```

### Running Model Benchmarks
```bash
python evaluate_models.py
```

### CLI Inference on Project JSON
```bash
python risk_engine.py --predict sample.json
```

### Node / TypeScript Integration
```typescript
import { computeProjectRisk } from "@workspace/ml-engine";

const riskEvaluation = computeProjectRisk({
  workId: "WS-AP-2024-001",
  estimatedCost: 5000000,
  sanctionedAmount: 5000000,
  expenditureIncurred: 4500000,
  physicalProgressPct: 35.0,
  dateOfSanction: "2024-01-01",
  expectedCompletionDate: "2024-12-31",
  tenderInvited: true,
  ucFiled: false,
});

console.log(riskEvaluation.riskScore); // e.g. 68.45
console.log(riskEvaluation.riskLevel); // "MODERATE"
console.log(riskEvaluation.findings);  // Detailed explanation objects
```
