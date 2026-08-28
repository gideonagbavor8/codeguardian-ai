# CodeGuardian AI — Project Structure

> Complete file and folder map for the MVP.  
> Based on [`ARCHITECTURE.md`](ARCHITECTURE.md) · Stack: Next.js 14 · FastAPI · PostgreSQL · watsonx.ai

---

## Table of Contents

1. [Full Folder Tree](#1-full-folder-tree)
2. [Frontend — File-by-File](#2-frontend--file-by-file)
3. [Backend — File-by-File](#3-backend--file-by-file)
4. [Database — Migrations & Seeds](#4-database--migrations--seeds)
5. [Environment Variables](#5-environment-variables)
6. [Dependencies](#6-dependencies)
7. [Development Order](#7-development-order)

---

## 1. Full Folder Tree

```
codeguardian-ai/                         ← repo root
│
├── frontend/                            ← Next.js 14 (App Router)
│   ├── app/
│   │   ├── layout.tsx                   ← root layout (fonts, providers)
│   │   ├── page.tsx                     ← root redirect → /dashboard
│   │   ├── globals.css                  ← Tailwind base imports
│   │   ├── (auth)/                      ← auth route group (no sidebar)
│   │   │   ├── layout.tsx               ← centred card layout
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   └── register/
│   │   │       └── page.tsx
│   │   ├── dashboard/
│   │   │   └── page.tsx                 ← stats cards + scan history table
│   │   ├── scan/
│   │   │   ├── new/
│   │   │   │   └── page.tsx             ← snippet/upload tab form
│   │   │   └── [id]/
│   │   │       └── page.tsx             ← polling / processing status
│   │   └── report/
│   │       └── [id]/
│   │           └── page.tsx             ← full report view
│   │
│   ├── components/
│   │   ├── ui/                          ← shadcn/ui generated primitives
│   │   │   ├── badge.tsx
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── input.tsx
│   │   │   ├── label.tsx
│   │   │   ├── progress.tsx
│   │   │   ├── separator.tsx
│   │   │   ├── skeleton.tsx
│   │   │   ├── table.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── textarea.tsx
│   │   │   └── toast.tsx
│   │   ├── layout/
│   │   │   ├── Navbar.tsx               ← top nav with user menu
│   │   │   └── Sidebar.tsx              ← nav links (dashboard, new scan)
│   │   ├── dashboard/
│   │   │   ├── StatsCards.tsx           ← total scans / avg score / critical count
│   │   │   ├── RecentScansTable.tsx     ← paginated scan history
│   │   │   └── TrendChart.tsx           ← recharts line chart of score over time
│   │   ├── scan/
│   │   │   ├── ScanForm.tsx             ← tabbed snippet/upload form
│   │   │   ├── SnippetEditor.tsx        ← code textarea + language picker
│   │   │   ├── FileUpload.tsx           ← drag-and-drop zone
│   │   │   └── ScanStatus.tsx           ← animated polling progress
│   │   └── report/
│   │       ├── ScoreGauge.tsx           ← big circular score + risk badge
│   │       ├── FindingsTable.tsx        ← security findings with severity badges
│   │       ├── DependencyTable.tsx      ← CVE dependency rows
│   │       ├── AISummaryCard.tsx        ← watsonx plain-language output
│   │       └── FixSuggestion.tsx        ← per-finding AI fix accordion
│   │
│   ├── lib/
│   │   ├── api.ts                       ← typed fetch wrapper (all endpoints)
│   │   ├── auth.ts                      ← JWT storage + decode helpers
│   │   ├── utils.ts                     ← cn(), severity colours, score → label
│   │   └── types.ts                     ← shared TypeScript interfaces
│   │
│   ├── hooks/
│   │   ├── useAuth.ts                   ← auth context hook
│   │   ├── useScanStatus.ts             ← polling hook with SWR
│   │   └── useReport.ts                 ← report data fetcher
│   │
│   ├── context/
│   │   └── AuthContext.tsx              ← JWT context provider
│   │
│   ├── public/
│   │   └── logo.svg
│   │
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── postcss.config.js
│   ├── components.json                  ← shadcn/ui config
│   ├── .env.local                       ← NEXT_PUBLIC_API_URL (gitignored)
│   ├── .env.example
│   └── package.json
│
├── backend/                             ← FastAPI (Python 3.11)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                      ← FastAPI app factory, CORS, routers
│   │   ├── config.py                    ← pydantic BaseSettings
│   │   ├── database.py                  ← async SQLAlchemy engine + session dep
│   │   │
│   │   ├── models/                      ← SQLAlchemy ORM table definitions
│   │   │   ├── __init__.py              ← imports all models (for Alembic)
│   │   │   ├── base.py                  ← declarative Base + TimestampMixin
│   │   │   ├── user.py                  ← User model
│   │   │   ├── scan.py                  ← Scan model + ScanStatus enum
│   │   │   ├── finding.py               ← SecurityFinding + DependencyFinding
│   │   │   └── report.py                ← Report model
│   │   │
│   │   ├── schemas/                     ← Pydantic v2 request/response shapes
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                  ← RegisterRequest, LoginRequest, TokenResponse
│   │   │   ├── scan.py                  ← SnippetScanRequest, ScanResponse, ScanStatus
│   │   │   ├── finding.py               ← SecurityFindingOut, DependencyFindingOut
│   │   │   └── report.py                ← ReportResponse, DashboardStats, TrendPoint
│   │   │
│   │   ├── routers/                     ← FastAPI APIRouter instances
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                  ← POST /auth/register|login, GET /auth/me
│   │   │   ├── scans.py                 ← POST /scans/snippet|upload, GET /scans/*
│   │   │   ├── reports.py               ← GET /reports/{scan_id}[/findings|export]
│   │   │   └── dashboard.py             ← GET /dashboard/stats|trend
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py          ← password hash, JWT create/verify
│   │   │   │
│   │   │   ├── scanner/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py              ← ScannerResult dataclass
│   │   │   │   ├── bandit_runner.py     ← runs bandit subprocess → ScannerResult
│   │   │   │   ├── dep_auditor.py       ← pip-audit / npm audit → findings
│   │   │   │   └── semgrep_runner.py    ← STRETCH: semgrep subprocess wrapper
│   │   │   │
│   │   │   ├── ai/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── watsonx_client.py    ← ibm-watsonx-ai SDK wrapper
│   │   │   │   └── prompts.py           ← prompt templates + response parser
│   │   │   │
│   │   │   └── report_builder.py        ← score formula, aggregation, saves Report row
│   │   │
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   └── scan_pipeline.py         ← async task: extract→scan→ai→report→persist
│   │   │
│   │   └── dependencies.py              ← FastAPI Depends() helpers (get_db, current_user)
│   │
│   ├── alembic/
│   │   ├── env.py                       ← async Alembic env (uses DATABASE_URL)
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial_schema.py   ← creates all 5 tables
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                  ← pytest fixtures (test DB, auth tokens)
│   │   ├── test_auth.py
│   │   ├── test_scans.py
│   │   └── test_report_builder.py       ← unit tests for score formula
│   │
│   ├── scripts/
│   │   └── seed_demo.py                 ← inserts demo user + sample scan for demo
│   │
│   ├── alembic.ini
│   ├── requirements.txt                 ← pinned production deps
│   ├── requirements-dev.txt             ← pytest, httpx, black, ruff
│   ├── Dockerfile
│   ├── .env                             ← gitignored runtime secrets
│   └── .env.example                     ← committed template
│
├── database/
│   └── init.sql                         ← optional: CREATE DATABASE + GRANT for Docker
│
├── docker-compose.yml                   ← postgres + backend + frontend services
├── docker-compose.override.yml          ← local dev: volume mounts, hot reload
├── Makefile                             ← dev shortcuts (make dev, migrate, test)
├── ARCHITECTURE.md
├── PROJECT_BRIEF.md
└── PROJECT_STRUCTURE.md                 ← this file
```

---

## 2. Frontend — File-by-File

### `app/` — Pages

| File | Purpose |
|------|---------|
| `layout.tsx` | Root HTML shell, `<AuthContext>` provider, Toaster, global font |
| `page.tsx` | 307 redirect to `/dashboard` if logged in, else `/login` |
| `globals.css` | `@tailwind base/components/utilities` |
| `(auth)/layout.tsx` | Full-screen centred layout (no sidebar) |
| `(auth)/login/page.tsx` | Email + password form → calls `POST /auth/login` → stores JWT |
| `(auth)/register/page.tsx` | Name + email + password → calls `POST /auth/register` |
| `dashboard/page.tsx` | SSR: fetches `/dashboard/stats` + `/dashboard/trend` + `/scans` |
| `scan/new/page.tsx` | Client component: `<ScanForm>` with snippet/upload tabs |
| `scan/[id]/page.tsx` | Client component: polls `/scans/{id}/status` every 2 s; on COMPLETE → redirect to report |
| `report/[id]/page.tsx` | Fetches `/reports/{id}`, renders all report sub-components |

### `components/` — Key Components

| Component | Props | Notes |
|-----------|-------|-------|
| `ScoreGauge` | `score: number, riskLevel: string` | SVG arc gauge, colour-coded by risk |
| `FindingsTable` | `findings: SecurityFinding[]` | Sortable by severity, expandable rows |
| `DependencyTable` | `findings: DepFinding[]` | CVE links to NVD |
| `AISummaryCard` | `summary: string, narrative: string` | Markdown-rendered watsonx output |
| `FixSuggestion` | `findingId, suggestion: string` | Collapsible accordion per finding |
| `TrendChart` | `data: TrendPoint[]` | Recharts `<LineChart>` of score over time |
| `ScanForm` | — | Controlled tabs: snippet paste vs. file drag-drop |
| `ScanStatus` | `scanId: string` | Animated steps with useInterval polling |

### `lib/` — Utilities

| File | Exports |
|------|---------|
| `api.ts` | `apiFetch<T>()`, typed functions: `createSnippetScan()`, `getScanStatus()`, `getReport()`, `getDashboardStats()`, `login()`, `register()` |
| `auth.ts` | `saveToken()`, `getToken()`, `removeToken()`, `decodeToken()` |
| `utils.ts` | `cn()` (clsx+twMerge), `severityColour()`, `scoreToLabel()`, `scoreToColour()` |
| `types.ts` | `Scan`, `SecurityFinding`, `DependencyFinding`, `Report`, `DashboardStats`, `TrendPoint`, `User` |

---

## 3. Backend — File-by-File

### `app/main.py`
```
FastAPI()
  ├── CORSMiddleware (allow frontend origin)
  ├── /api/v1/auth      ← auth.router
  ├── /api/v1/scans     ← scans.router
  ├── /api/v1/reports   ← reports.router
  ├── /api/v1/dashboard ← dashboard.router
  └── /health           ← inline liveness probe
```

### `app/config.py`
`pydantic_settings.BaseSettings` — reads `.env`.  
Fields: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `WATSONX_MODEL_ID`

### `app/database.py`
```python
engine      = create_async_engine(settings.DATABASE_URL)
AsyncSession = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession() as session:
        yield session
```

### `app/models/`

| File | Class | Key Columns |
|------|-------|-------------|
| `base.py` | `Base`, `TimestampMixin` | `created_at`, `updated_at` |
| `user.py` | `User` | `id UUID PK`, `email`, `password_hash`, `api_key` |
| `scan.py` | `Scan`, `ScanStatus(enum)` | `id`, `user_id FK`, `status`, `source_type`, `source_meta JSONB`, `language` |
| `finding.py` | `SecurityFinding` | `id`, `scan_id FK`, `tool`, `rule_id`, `severity`, `file_path`, `line_number`, `code_snippet`, `message`, `cwe_id` |
| `finding.py` | `DependencyFinding` | `id`, `scan_id FK`, `package_name`, `installed_version`, `fixed_version`, `severity`, `cve_ids TEXT[]`, `ecosystem` |
| `report.py` | `Report` | `id`, `scan_id FK UNIQUE`, `release_readiness_score`, `risk_level`, `*_count`, `ai_summary`, `ai_fix_suggestions JSONB`, `ai_review_narrative`, `model_used` |

### `app/services/scanner/bandit_runner.py`
```
run_bandit(code: str, language: str) -> list[SecurityFinding]
  1. Write code to NamedTemporaryFile
  2. subprocess.run(["bandit", "-f", "json", "-q", tmpfile])
  3. Parse JSON output → SecurityFinding dataclasses
  4. Return findings list
```

### `app/services/scanner/dep_auditor.py`
```
audit_dependencies(dep_file_content: str, ecosystem: str) -> list[DependencyFinding]
  1. Write dep file to tmp dir
  2. pip ecosystem → subprocess.run(["pip-audit", "--format", "json", "-r", ...])
     npm ecosystem → subprocess.run(["npm", "audit", "--json"])
  3. Parse JSON → DependencyFinding dataclasses
```

### `app/services/ai/watsonx_client.py`
```
generate_analysis(findings: list, dep_findings: list) -> AIAnalysis
  1. Build prompt from prompts.py template
  2. ibm_watsonx_ai.ModelInference.generate(prompt, params)
  3. Parse response → AIAnalysis(summary, fix_suggestions, narrative)
  4. Returns AIAnalysis dataclass
```

### `app/services/ai/prompts.py`
Contains `build_analysis_prompt(findings, dep_findings) -> str`.  
Returns a structured prompt instructing the model to output valid JSON with keys `summary`, `fix_suggestions`, `narrative`.

### `app/services/report_builder.py`
```
build_report(scan_id, sec_findings, dep_findings, ai_analysis) -> Report
  1. Count findings by severity
  2. Apply score formula (see ARCHITECTURE.md §5)
  3. Compute risk_level string
  4. Construct Report ORM object
  5. Returns Report (caller persists to DB)
```

### `app/tasks/scan_pipeline.py`
```
async run_scan_pipeline(scan_id: UUID, db: AsyncSession)
  1. Set scan.status = RUNNING
  2. Load scan from DB, read code from source
  3. await bandit_runner.run_bandit(...)  → sec_findings
  4. await dep_auditor.audit(...)         → dep_findings
  5. Persist SecurityFinding rows
  6. Persist DependencyFinding rows
  7. await watsonx_client.generate_analysis(...)
  8. report = report_builder.build_report(...)
  9. Persist Report row
  10. Set scan.status = COMPLETE
  11. On any exception → scan.status = FAILED, save error_message
```

### `app/routers/scans.py`

| Route | Handler behaviour |
|-------|------------------|
| `POST /scans/snippet` | Save code to temp file, create Scan row (PENDING), fire `asyncio.create_task(run_scan_pipeline(...))`, return 202 |
| `POST /scans/upload` | Accept `UploadFile`, save to `/tmp/cg-{uuid}/`, same as above |
| `GET /scans` | Query `scans` for `current_user.id`, paginate, return list |
| `GET /scans/{id}` | Return full Scan row |
| `GET /scans/{id}/status` | Return `{scan_id, status, completed_at}` only (lightweight) |
| `DELETE /scans/{id}` | CASCADE deletes findings + report |

---

## 4. Database — Migrations & Seeds

### Alembic Setup
```
backend/
├── alembic.ini                          ← sqlalchemy.url = (read from env)
└── alembic/
    ├── env.py                           ← async Alembic + imports all models
    ├── script.py.mako
    └── versions/
        └── 0001_initial_schema.py       ← all 5 tables, indexes, enums
```

### Migration Commands
```bash
# Generate new migration (auto-detect from models)
cd backend && alembic revision --autogenerate -m "description"

# Apply all pending migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

### Demo Seed Script (`scripts/seed_demo.py`)
Creates a demo user `demo@codeguardian.ai / demo1234` with one pre-computed scan showing a HIGH risk score — useful for the hackathon demo without needing to run a live scan.

```bash
cd backend && python scripts/seed_demo.py
```

---

## 5. Environment Variables

### `backend/.env` (gitignored)

```bash
# ── Database ────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://codeguardian:secret@localhost:5432/codeguardian

# ── JWT Auth ─────────────────────────────────────────────────
SECRET_KEY=replace-with-32-char-random-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ── IBM watsonx.ai ───────────────────────────────────────────
WATSONX_API_KEY=your-ibm-cloud-api-key
WATSONX_PROJECT_ID=your-watsonx-project-id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-13b-instruct-v2

# ── App ──────────────────────────────────────────────────────
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:3000
MAX_UPLOAD_SIZE_MB=10
```

### `backend/.env.example` (committed)
Same keys with placeholder values — checked into source control.

### `frontend/.env.local` (gitignored)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### `frontend/.env.example` (committed)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### Docker Compose Environment Injection
`docker-compose.yml` passes backend env vars via `env_file: ./backend/.env`.  
Frontend gets `NEXT_PUBLIC_API_URL` pointing to the backend container name.

---

## 6. Dependencies

### Backend — `requirements.txt`

```text
# Web framework
fastapi==0.115.5
uvicorn[standard]==0.32.1

# Database
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0

# Auth
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.17

# Configuration
pydantic-settings==2.6.1

# Security scanning
bandit==1.8.0
pip-audit==2.7.3

# IBM watsonx.ai
ibm-watsonx-ai==1.1.22

# Utilities
aiofiles==24.1.0
python-dotenv==1.0.1
```

### Backend — `requirements-dev.txt`

```text
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2          # async test client for FastAPI
black==24.10.0
ruff==0.8.0
```

### Frontend — `package.json` dependencies

```json
{
  "dependencies": {
    "next": "14.2.18",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "typescript": "^5.6.3",

    "tailwindcss": "^3.4.15",
    "@tailwindcss/typography": "^0.5.15",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.4",
    "class-variance-authority": "^0.7.1",

    "@radix-ui/react-dialog": "^1.1.2",
    "@radix-ui/react-progress": "^1.1.0",
    "@radix-ui/react-tabs": "^1.1.1",
    "@radix-ui/react-toast": "^1.2.2",
    "lucide-react": "^0.460.0",

    "recharts": "^2.13.3",
    "swr": "^2.2.5",
    "js-cookie": "^3.0.5",
    "jwt-decode": "^4.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.9.0",
    "@types/react": "^18.3.12",
    "@types/js-cookie": "^3.0.6",
    "postcss": "^8.4.49",
    "autoprefixer": "^10.4.20",
    "eslint": "^8.57.1",
    "eslint-config-next": "14.2.18"
  }
}
```

### System / Tool Dependencies (must be installed)

| Tool | Version | Used by | Install |
|------|---------|---------|---------|
| Node.js | ≥ 20 | Frontend build | `nvm install 20` |
| Python | 3.11 | Backend | `pyenv install 3.11` |
| Docker + Compose | latest | PostgreSQL, full stack | docker.com |
| `bandit` | 1.8.x | Security scanner | installed via requirements.txt |
| `pip-audit` | 2.7.x | Dependency auditor | installed via requirements.txt |
| `npm` | ≥ 10 | npm audit (Node projects) | bundled with Node |

---

## 7. Development Order

Build in this exact sequence to always have a runnable state.

### Phase 1 — Infrastructure (30 min)
```
1. docker-compose.yml           → postgres service running
2. backend/.env                 → all vars set
3. backend/app/config.py        → BaseSettings reads .env
4. backend/app/database.py      → async engine + session dep
5. alembic init + env.py        → async Alembic configured
```

### Phase 2 — Data Layer (45 min)
```
6.  models/base.py              → Base, TimestampMixin
7.  models/user.py
8.  models/scan.py              → ScanStatus enum
9.  models/finding.py           → SecurityFinding + DependencyFinding
10. models/report.py
11. models/__init__.py          → import all (Alembic sees them)
12. alembic revision --autogenerate -m "initial_schema"
13. alembic upgrade head         → tables created ✓
```

### Phase 3 — Auth (45 min)
```
14. schemas/auth.py             → RegisterRequest, LoginRequest, TokenResponse
15. services/auth_service.py    → hash_password, verify_password, create_jwt, decode_jwt
16. dependencies.py             → get_db(), get_current_user()
17. routers/auth.py             → POST /register, POST /login, GET /me
18. main.py                     → app factory, include auth router
    → TEST: curl POST /auth/register + /auth/login returns JWT ✓
```

### Phase 4 — Scanner Services (90 min)
```
19. services/scanner/base.py        → ScannerResult dataclass
20. services/scanner/bandit_runner.py
21. services/scanner/dep_auditor.py
    → TEST: run both manually against a fixture file ✓
```

### Phase 5 — AI Layer (60 min)
```
22. services/ai/prompts.py          → build_analysis_prompt()
23. services/ai/watsonx_client.py   → generate_analysis()
    → TEST: run with sample findings, inspect JSON response ✓
```

### Phase 6 — Report Builder (30 min)
```
24. services/report_builder.py      → score formula, risk_level calc, Report constructor
    → TEST: unit test score = 100 - deductions ✓
```

### Phase 7 — Scan Pipeline + API Routes (90 min)
```
25. tasks/scan_pipeline.py          → full async orchestration
26. schemas/scan.py, schemas/finding.py, schemas/report.py
27. routers/scans.py                → snippet + upload endpoints, status polling
28. routers/reports.py              → report fetch + findings list
29. routers/dashboard.py            → stats + trend
30. main.py                         → include all routers, CORS middleware
    → TEST: full scan via curl, poll until COMPLETE, GET report ✓
```

### Phase 8 — Frontend Scaffold (45 min)
```
31. npx create-next-app@latest frontend --typescript --tailwind --app
32. npx shadcn-ui@latest init
33. Add all shadcn components: button card badge table tabs textarea progress toast
34. lib/types.ts                → all shared interfaces
35. lib/utils.ts                → cn(), severity helpers
36. lib/api.ts                  → apiFetch + all typed API functions
37. lib/auth.ts                 → JWT token helpers
38. context/AuthContext.tsx     → provider + useAuth hook
```

### Phase 9 — Frontend Auth (30 min)
```
39. app/(auth)/layout.tsx
40. app/(auth)/login/page.tsx
41. app/(auth)/register/page.tsx
42. components/layout/Navbar.tsx
    → TEST: login → JWT stored → redirect to /dashboard ✓
```

### Phase 10 — Dashboard (60 min)
```
43. hooks/useAuth.ts
44. components/dashboard/StatsCards.tsx
45. components/dashboard/RecentScansTable.tsx
46. components/dashboard/TrendChart.tsx
47. app/dashboard/page.tsx
    → TEST: shows scan history + stats ✓
```

### Phase 11 — New Scan + Status Pages (60 min)
```
48. components/scan/SnippetEditor.tsx
49. components/scan/FileUpload.tsx
50. components/scan/ScanForm.tsx
51. components/scan/ScanStatus.tsx
52. hooks/useScanStatus.ts              → SWR polling with 2 s interval
53. app/scan/new/page.tsx
54. app/scan/[id]/page.tsx
    → TEST: paste code → submit → polling → auto-redirect ✓
```

### Phase 12 — Report Page (60 min)
```
55. components/report/ScoreGauge.tsx
56. components/report/FindingsTable.tsx
57. components/report/DependencyTable.tsx
58. components/report/AISummaryCard.tsx
59. components/report/FixSuggestion.tsx
60. hooks/useReport.ts
61. app/report/[id]/page.tsx
    → TEST: full report renders with score, findings, AI text ✓
```

### Phase 13 — Polish & Demo Prep (30 min)
```
62. scripts/seed_demo.py        → pre-load demo scan for judging
63. docker-compose.yml          → wire all three services
64. README.md                   → one-command startup instructions
65. End-to-end smoke test across full stack ✓
```

### Phase 14 — Stretch (if time remains)
```
66. GitHub URL scanning         (POST /scans/github)
67. PDF report export           (WeasyPrint)
68. Shareable public report URL (token-based, no auth required)
69. Semgrep multi-language      (semgrep_runner.py)
```

---

### Dependency Graph (build nothing out of order)

```
Infrastructure
    └── Data Layer (models + migrations)
            └── Auth (services + routes)
                    └── Scanner Services
                            └── AI Layer
                                    └── Report Builder
                                            └── Scan Pipeline + All API Routes
                                                        └── Frontend (phases 8–12)
```

---

*Project structure aligned with [`ARCHITECTURE.md`](ARCHITECTURE.md) · IBM Bob Hackathon 2025*
