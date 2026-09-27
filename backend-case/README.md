# ⚖️ Case Management & Escalation Engine (`backend-case/`)

**Module Owner:** Poornesh (Backend Case Management Lead)

The `backend-case` module provides the formal governance escalation state machine, multi-tier authority routing, cryptographic tamper-evident action audit logging, and SLA deadline alerting for the **SavidhanSamraksha** platform.

---

## 🏛️ Hierarchical Escalation Workflow

The state machine implements India's administrative oversight structure for MPLADS project governance:

```
                            [NORMAL]
                               │
               (District Collector flags anomaly)
                               ▼
                           [FLAGGED]
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
   [UNDER_INQUIRY]                      [ESCALATED_STATE]
(Field team dispatched)              (State Nodal Officer Review)
            │                                     │
            ▼                                     ▼
   [SANCTION_FROZEN]                    [ESCALATED_NATIONAL]
(Treasury release locked)              (MoSPI Central Oversight)
            │                                     │
            └──────────────────┬──────────────────┘
                               ▼
                           [RESOLVED] / [DISMISSED]
```

### State Definitions & SLA Deadlines

| State | Authority Tier | Description | SLA Window |
|:---|:---|:---|:---:|
| `NORMAL` | Project Authority | Baseline execution within approved milestones | N/A |
| `FLAGGED` | District Collector | Flagged for physical verification due to ML anomaly | 7 Days |
| `ESCALATED_STATE` | State Nodal Officer | Unresolved district anomaly requiring state review | 14 Days |
| `ESCALATED_NATIONAL`| MoSPI Central | Inter-state anomaly or critical fiscal variance | 5 Days |
| `UNDER_INQUIRY` | CAG / ACB Vigilance | Formal audit and engineering inspection inquiry | 30 Days |
| `SANCTION_FROZEN` | District Treasury | Treasury disbursements locked; no bills paid | 3 Days |
| `RESOLVED` | Competent Authority | Work rectified, verified, and sanctioned | Finalized |

---

## 🔐 Cryptographic Action Audit Trail

Every administrative decision, status transition, and sanction lock is recorded as a **tamper-evident SHA-256 hash chain**:

$$\text{Hash}_n = \text{SHA256}(\text{Hash}_{n-1} \parallel \text{WorkID} \parallel \text{Action} \parallel \text{Timestamp} \parallel \text{UserID} \parallel \text{Notes})$$

Any modification to historical audit logs causes a hash-chain break that is immediately flagged during system verification.

---

## 📂 File Directory

```
backend-case/
├── src/
│   ├── audit-logger.ts             # Cryptographic SHA-256 audit chaining & verification
│   ├── escalation-router.ts        # Multi-tier routing & case SLA assignment
│   ├── index.ts                    # Main package exports
│   ├── notification-dispatcher.ts  # Alert dispatching for SLA breaches & freeze orders
│   └── workflow-state-machine.ts   # State transition rules & role permission matrix
├── package.json                    # NPM package declaration (@workspace/backend-case)
├── tsconfig.json                   # TypeScript configuration
└── README.md                       # Module documentation
```
