# 🖥️ Frontend Dashboard (`frontend-dashboard/`)

**Module Owner:** Chandana (Frontend & UI/UX Engineering Lead)

The `frontend-dashboard` module contains the official web application for the **SavidhanSamraksha** platform built with **React 19**, **Vite**, **Tailwind CSS v4**, and **Recharts**. It delivers a high-density, real-time command center for district collectors, state nodal officers, and citizens.

---

## 🎨 UI Architecture & Features

```
                                [React 19 SPA Root]
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
            [Role Provider]                            [Query Client]
       (Session auth, user tier,               (TanStack React Query caching)
        authority state machine)                              │
                    │                                         │
                    └────────────────────┬────────────────────┘
                                         ▼
                                 [App Layout Shell]
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                          ▼
     [Hierarchical Sidebar]      [Top Navigation Bar]      [Main Content Canvas]
      - Active Scope Pill         - Institution Crest       - Metric Summary Cards
      - MP/Constituency Tiers     - National Emblems        - Analytics Charts
      - Escalations Badge (10)    - Profile Drawer Dropdown - Project Explorer Table
      - Audit Log Link            - Real Sign Out Action    - Evidence Detail Drawer
```

### Key UI Features
1. **Hierarchical Governance Scope Selector**: Seamlessly inspect National, State, District, Lok Sabha, Rajya Sabha, or Nominated MP jurisdictions.
2. **Dynamic Project Mix & Fiscal Charts**: Responsive Recharts components visualizing multi-category distribution and expenditure vs physical completion.
3. **Multi-Factor Risk Badging**: Color-coded badges with numeric scores (6.00 to 98.60) reflecting real ML inference output.
4. **Dedicated Escalations Workflow Queue**: High-priority case drawer for district, state, and central authorities to review flagged anomalies, freeze sanctions, and dispatch inspection orders.
5. **Interactive Photo Evidence Drawer**: Visual inspection pane with ground photos, EXIF metadata, timestamp validation, and tamper indicators.

---

## 📂 File Directory

```
frontend-dashboard/
├── public/                    # Static assets & favicon
├── src/
│   ├── components/
│   │   ├── ui/                # 50+ Radix/Shadcn headless UI primitives
│   │   └── error-boundary.tsx # Crash recovery wrapper
│   ├── hooks/
│   │   ├── use-mobile.tsx     # Mobile viewport responsiveness
│   │   └── use-toast.ts       # Alert notifications
│   ├── lib/
│   │   └── utils.ts           # Tailwind merge & styling utilities
│   ├── pages/
│   │   └── not-found.tsx      # 404 Route fallback
│   ├── App.tsx                # Main single-page application & routing
│   ├── index.css              # Tailwind v4 theme & governance visual tokens
│   └── main.tsx               # React DOM bootstrap
├── index.html                 # Single page application HTML shell
├── package.json               # NPM package declaration (@workspace/frontend-dashboard)
├── tsconfig.json              # TypeScript configuration
├── vite.config.ts             # Vite build & development proxy configuration
└── README.md                  # Module documentation
```

---

## 🚀 Execution Commands

### Run Frontend in Development Mode (Port 5173)
```bash
pnpm run dev
```

### Production Build
```bash
pnpm run build
```

### Preview Production Build
```bash
pnpm run serve
```
