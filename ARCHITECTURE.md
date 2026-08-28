# CodeGuardian AI — MVP Architecture

> **Hackathon Category:** Intelligent Code Review and Quality Coach  
> **Target Build Time:** 2 days (solo developer)  
> **Stack:** Next.js · FastAPI · PostgreSQL · watsonx.ai

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [User Flow](#2-user-flow)
3. [Database Schema](#3-database-schema)
4. [API Endpoints](#4-api-endpoints)
5. [MVP Features](#5-mvp-features)
6. [Stretch Features](#6-stretch-features)
7. [Directory Structure](#7-directory-structure)
8. [Technology Decisions](#8-technology-decisions)
9. [Day-by-Day Build Plan](#9-day-by-day-build-plan)

---

## 1. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        BROWSER / CLIENT                               │
│                                                                        │
│   ┌─────────────────────────────────────────────────────────────┐    │
│   │                  Next.js 14 (App Router)                     │    │
│   │                                                               │    │
│   │  Dashboard   Scan Page   Report Page   History   Settings   │    │
│   │       └──────────┴────────────┴───────────┴─────────┘        │    │
│   │                        API Routes (/api/*)                    │    │
│   └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬───────────────────────────────────────┘
                                │  HTTPS / REST
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (Python 3.11)                     │
│                                                                        │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────────┐  │
│  │ /scan        │  │ /reports      │  │ /auth                    │  │
│  │  ├ upload    │  │  ├ list       │  │  ├ register              │  │
│  │  ├ github    │  │  ├ get        │  │  ├ login                 │  │
│  │  └ status   │  │  └ download   │  │  └ me                    │  │
│  └──────┬───────┘  └───────┬───────┘  └──────────────────────────┘  │
│         │                  │                                           │
│  ┌──────▼──────────────────▼──────────────────────────────────────┐  │
│  │                    Core Analysis Pipeline                        │  │
│  │                                                                   │  │
│  │  ┌─────────────────┐   ┌──────────────────┐   ┌─────────────┐  │  │
│  │  │ Security Scanner│   │ Dependency Auditor│   │ AI Summarizer│  │  │
│  │  │  (Bandit/Semgrep)│   │  (pip-audit/npm  │   │ (watsonx.ai)│  │  │
│  │  │                 │   │   audit/OSSC)     │   │             │  │  │
│  │  └────────┬────────┘   └────────┬─────────┘   └──────┬──────┘  │  │
│  │           └───────────────────── │ ──────────────────┘           │  │
│  │                                  ▼                                │  │
│  │                    ┌─────────────────────────┐                   │  │
│  │                    │  Report Aggregator       │                   │  │
│  │                    │  (severity scoring,      │                   │  │
│  │                    │   release-readiness calc)│                   │  │
│  │                    └─────────────────────────┘                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                    │                                    │
│  ┌─────────────────┐   ┌──────────▼──────────┐   ┌─────────────────┐  │
│  │  Background Jobs│   │    PostgreSQL DB     │   │  File Storage   │  │
│  │  (asyncio/tasks)│   │  (SQLAlchemy ORM)    │   │  (local /tmp or │  │
│  └─────────────────┘   └─────────────────────┘   │   S3-compatible)│  │
│                                                    └─────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                         ┌──────────▼──────────┐
                         │   IBM watsonx.ai     │
                         │  (llama-3-70b-instruct│
                         │   or granite-13b)    │
                         └─────────────────────┘
```

### Component Responsibilities

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| **Frontend** | Next.js 14, Tailwind CSS, shadcn/ui | Dashboard, scan submission, report rendering |
| **Backend** | FastAPI, Python 3.11 | REST API, orchestration, async scan pipeline |
| **Security Scanner** | Bandit (Python), Semgrep (multi-lang) | Static analysis for security vulnerabilities |
| **Dependency Auditor** | pip-audit, npm audit, Safety DB | CVE detection in third-party packages |
| **AI Summarizer** | IBM watsonx.ai (ibm-watsonx-ai SDK) | Plain-language summaries, fix suggestions |
| **Database** | PostgreSQL 15, SQLAlchemy + Alembic | Persisting scans, findings, reports, users |
| **Auth** | JWT (python-jose), bcrypt | Session management, API key protection |

---

## 2. User Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. ONBOARD                                                   │
│     User registers / logs in → lands on Dashboard            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  2. SUBMIT CODE                                               │
│     Option A: Paste code snippet directly in browser         │
│     Option B: Upload ZIP / tar.gz archive                    │
│     Option C: Enter public GitHub repo URL (MVP stretch)     │
│                                                               │
│     User selects language hint (auto-detected if possible)   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  3. SCAN PIPELINE (async, ~10–60 s)                          │
│     a. Extract / save code to temp directory                 │
│     b. Run Bandit/Semgrep → raw security findings            │
│     c. Parse dependency file (requirements.txt / package.json│
│        / Pipfile) → run pip-audit / npm-audit                │
│     d. Aggregate findings, calculate severity scores         │
│     e. POST structured findings to watsonx.ai                │
│        → receive: plain-language summary, fix suggestions    │
│     f. Compute Release Readiness Score (0–100)               │
│     g. Store everything in PostgreSQL                        │
│     h. Mark scan as COMPLETE                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  4. VIEW REPORT                                               │
│     Dashboard polls /scan/{id}/status until COMPLETE         │
│     Redirects to /report/{id}                                │
│                                                               │
│     Report sections:                                          │
│     ├── Release Readiness Gauge (big number / colour)        │
│     ├── Security Vulnerabilities (severity table)            │
│     ├── Dependency Risks (CVE list)                          │
│     ├── AI Summary (plain English, per-finding fixes)        │
│     └── Raw Details (expandable JSON)                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  5. HISTORY & COMPARISON                                      │
│     All past scans visible on dashboard                      │
│     Score trend line chart over time                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Database Schema

```sql
-- Users
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    name        VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    api_key     VARCHAR(64) UNIQUE,           -- for programmatic access
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Scan Jobs
CREATE TABLE scans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(255),              -- user-provided label
    status          VARCHAR(20) NOT NULL       -- PENDING | RUNNING | COMPLETE | FAILED
                    DEFAULT 'PENDING',
    source_type     VARCHAR(20) NOT NULL,      -- SNIPPET | UPLOAD | GITHUB
    source_meta     JSONB,                     -- {filename, repo_url, language, ...}
    language        VARCHAR(50),               -- detected or user-provided
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    error_message   TEXT
);

-- Security Findings  (one row per vulnerability)
CREATE TABLE security_findings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id         UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    tool            VARCHAR(50) NOT NULL,      -- bandit | semgrep
    rule_id         VARCHAR(100),
    severity        VARCHAR(20) NOT NULL,      -- CRITICAL | HIGH | MEDIUM | LOW | INFO
    confidence      VARCHAR(20),               -- HIGH | MEDIUM | LOW
    file_path       VARCHAR(500),
    line_number     INT,
    code_snippet    TEXT,
    message         TEXT NOT NULL,
    cwe_id          VARCHAR(20),               -- e.g. CWE-89
    owasp_category  VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Dependency Findings  (one row per vulnerable package)
CREATE TABLE dependency_findings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id         UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    package_name    VARCHAR(255) NOT NULL,
    installed_version VARCHAR(50),
    fixed_version   VARCHAR(50),
    severity        VARCHAR(20) NOT NULL,
    cve_ids         TEXT[],                    -- array of CVE identifiers
    description     TEXT,
    ecosystem       VARCHAR(20) NOT NULL,      -- pip | npm | cargo | gem
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Reports  (aggregated output, one per scan)
CREATE TABLE reports (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id                 UUID UNIQUE NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    release_readiness_score INT NOT NULL,      -- 0–100
    risk_level              VARCHAR(20) NOT NULL, -- CRITICAL | HIGH | MEDIUM | LOW | SAFE
    total_security_issues   INT DEFAULT 0,
    critical_count          INT DEFAULT 0,
    high_count              INT DEFAULT 0,
    medium_count            INT DEFAULT 0,
    low_count               INT DEFAULT 0,
    total_dep_issues        INT DEFAULT 0,
    ai_summary              TEXT,              -- watsonx plain-language summary
    ai_fix_suggestions      JSONB,             -- [{finding_id, suggestion}, ...]
    ai_review_narrative     TEXT,              -- overall code review paragraph
    model_used              VARCHAR(100),      -- watsonx model identifier
    generated_at            TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_scans_user_id     ON scans(user_id);
CREATE INDEX idx_scans_status      ON scans(status);
CREATE INDEX idx_sec_findings_scan ON security_findings(scan_id);
CREATE INDEX idx_dep_findings_scan ON dependency_findings(scan_id);
CREATE INDEX idx_reports_scan      ON reports(scan_id);
```

### Entity Relationship

```
users (1) ──< scans (1) ──< security_findings
                     │
                     ├──< dependency_findings
                     │
                     └──(1:1)── reports
```

---

## 4. API Endpoints

Base URL: `http://localhost:8000/api/v1`

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/register` | Create new account |
| `POST` | `/auth/login` | Returns JWT access token |
| `GET`  | `/auth/me` | Current user info |

### Scans

| Method | Path | Description | Body / Params |
|--------|------|-------------|---------------|
| `POST` | `/scans/snippet` | Scan pasted code | `{code, language, name}` |
| `POST` | `/scans/upload` | Scan uploaded archive | `multipart/form-data` |
| `POST` | `/scans/github` | Scan GitHub repo *(stretch)* | `{repo_url, branch}` |
| `GET`  | `/scans` | List user's scans (paginated) | `?page&limit&status` |
| `GET`  | `/scans/{id}` | Scan details + status | — |
| `GET`  | `/scans/{id}/status` | Lightweight polling endpoint | — |
| `DELETE` | `/scans/{id}` | Delete scan and all findings | — |

### Reports

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/reports/{scan_id}` | Full report for a scan |
| `GET`  | `/reports/{scan_id}/findings` | Paginated findings list |
| `GET`  | `/reports/{scan_id}/export` | Download PDF / JSON export |

### Dashboard

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/dashboard/stats` | Aggregate stats for current user |
| `GET`  | `/dashboard/trend` | Score trend data (for chart) |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness check |
| `GET`  | `/health/db` | DB connectivity check |

---

### Request / Response Samples

**POST `/scans/snippet`**
```json
// Request
{
  "name": "Login handler review",
  "language": "python",
  "code": "import pickle\ndef load_user(data):\n    return pickle.loads(data)\n"
}

// Response 202 Accepted
{
  "scan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "PENDING",
  "poll_url": "/api/v1/scans/3fa85f64-5717-4562-b3fc-2c963f66afa6/status"
}
```

**GET `/reports/{scan_id}`**
```json
{
  "scan_id": "3fa85f64-...",
  "release_readiness_score": 34,
  "risk_level": "HIGH",
  "ai_summary": "This code deserialises untrusted input with pickle, which can lead to arbitrary code execution (CWE-502). Recommend replacing with json.loads() and validating input schema.",
  "ai_review_narrative": "The submitted snippet contains one critical vulnerability and no dependency issues. Overall code quality is low for production use.",
  "findings": {
    "security": [
      {
        "id": "...",
        "tool": "bandit",
        "rule_id": "B301",
        "severity": "HIGH",
        "message": "Pickle and modules that wrap it can be unsafe when used to deserialize untrusted data",
        "file_path": "snippet.py",
        "line_number": 3,
        "cwe_id": "CWE-502",
        "ai_fix": "Replace pickle.loads(data) with json.loads(data) after validating the schema."
      }
    ],
    "dependencies": []
  },
  "counts": { "critical": 0, "high": 1, "medium": 0, "low": 0 }
}
```

---

## 5. MVP Features

These must ship for hackathon judging:

### Core (Day 1)
- [x] **User auth** — register, login, JWT-protected API
- [x] **Code snippet scanning** — paste code in UI, run Bandit analysis
- [x] **Dependency scanning** — parse `requirements.txt` / `package.json`, run pip-audit / npm audit
- [x] **Security findings table** — severity badge, file/line, CWE ID
- [x] **PostgreSQL persistence** — all scans, findings, reports stored

### AI Layer (Day 1–2)
- [x] **watsonx.ai integration** — POST findings to `ibm/granite-13b-instruct-v2` or `meta-llama/llama-3-70b-instruct`
- [x] **Plain-language AI summary** — one paragraph per scan explaining what was found
- [x] **Per-finding fix suggestions** — actionable remediation for each issue
- [x] **AI code review narrative** — overall quality assessment paragraph

### Reporting (Day 2)
- [x] **Release Readiness Score (0–100)** — algorithmically computed from finding counts and severity weights
- [x] **Risk level badge** — CRITICAL / HIGH / MEDIUM / LOW / SAFE
- [x] **Full report page** — score gauge, findings breakdown, AI narrative
- [x] **Scan history list** — dashboard showing all past scans with scores

### UI
- [x] **Dashboard** — summary stats, recent scans, trend chart
- [x] **New Scan page** — code paste + file upload tabs
- [x] **Report page** — structured report with severity colour-coding
- [x] **Responsive layout** — works on laptop/desktop

---

### Release Readiness Score Formula

```
score = 100

# Deductions
- CRITICAL finding:  -25 each  (floor: 0)
- HIGH finding:      -10 each
- MEDIUM finding:    -5 each
- LOW finding:       -1 each
- Critical CVE dep:  -20 each
- High CVE dep:      -8 each

score = max(0, score)

# Risk Level mapping
score >= 90  →  SAFE
score >= 70  →  LOW
score >= 50  →  MEDIUM
score >= 30  →  HIGH
score < 30   →  CRITICAL
```

---

## 6. Stretch Features

If time permits, add these in priority order:

| Priority | Feature | Effort |
|----------|---------|--------|
| 1 | **GitHub URL scanning** — clone public repo, scan all source files | ~2 h |
| 2 | **PDF export** — download report as PDF (WeasyPrint or pdfkit) | ~1 h |
| 3 | **Shareable report link** — public token-based read-only report URL | ~1 h |
| 4 | **Multi-file ZIP upload** — scan entire project archive, not just a snippet | ~2 h |
| 5 | **Diff view** — highlight vulnerable lines with red gutter in code viewer | ~2 h |
| 6 | **Email report** — send HTML report via SendGrid / SMTP | ~1 h |
| 7 | **Semgrep ruleset** — extend beyond Bandit to Semgrep multi-language rules | ~1.5 h |
| 8 | **SBOM generation** — generate CycloneDX Software Bill of Materials | ~2 h |
| 9 | **Webhook / CI badge** — POST results to callback URL, serve SVG badge | ~2 h |
| 10 | **Side-by-side comparison** — compare two scan reports of same project | ~3 h |

---

## 7. Directory Structure

```
codeguardian-ai/
├── frontend/                        # Next.js 14 app
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                 # redirect to /dashboard
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── dashboard/page.tsx       # scan history, stats
│   │   ├── scan/
│   │   │   ├── new/page.tsx         # new scan form
│   │   │   └── [id]/page.tsx        # polling / status
│   │   └── report/[id]/page.tsx     # full report view
│   ├── components/
│   │   ├── ui/                      # shadcn/ui primitives
│   │   ├── ScoreGauge.tsx
│   │   ├── FindingsTable.tsx
│   │   ├── DependencyTable.tsx
│   │   ├── AISummaryCard.tsx
│   │   ├── ScanForm.tsx
│   │   └── TrendChart.tsx
│   ├── lib/
│   │   ├── api.ts                   # typed API client
│   │   └── auth.ts                  # JWT helpers
│   ├── tailwind.config.ts
│   └── package.json
│
├── backend/                         # FastAPI app
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory
│   │   ├── config.py                # pydantic Settings
│   │   ├── database.py              # SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── scan.py
│   │   │   ├── finding.py
│   │   │   └── report.py
│   │   ├── schemas/                 # Pydantic request/response models
│   │   │   ├── auth.py
│   │   │   ├── scan.py
│   │   │   └── report.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── scans.py
│   │   │   ├── reports.py
│   │   │   └── dashboard.py
│   │   ├── services/
│   │   │   ├── scanner/
│   │   │   │   ├── bandit_runner.py
│   │   │   │   ├── semgrep_runner.py  (stretch)
│   │   │   │   └── dep_auditor.py
│   │   │   ├── ai/
│   │   │   │   ├── watsonx_client.py
│   │   │   │   └── prompts.py
│   │   │   └── report_builder.py
│   │   └── tasks/
│   │       └── scan_pipeline.py     # async orchestration
│   ├── alembic/                     # DB migrations
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
│
├── docker-compose.yml               # postgres + backend + frontend
├── ARCHITECTURE.md                  # this file
└── PROJECT_BRIEF.md
```

---

## 8. Technology Decisions

### Why Bandit (not Semgrep first)?
Bandit is a zero-config Python AST scanner — `pip install bandit`, run, get JSON output. For a 2-day MVP scanning Python code it is the fastest path. Semgrep supports 30+ languages but requires downloading rules; add as stretch.

### Why asyncio tasks (not Celery)?
A scan pipeline takes 5–60 seconds. For a hackathon demo, `asyncio.create_task()` in FastAPI is sufficient — no Redis, no worker process. Celery/RQ can replace it post-MVP.

### Why PostgreSQL (not SQLite)?
The brief specifies PostgreSQL. It runs in Docker, Alembic migrations are clean, JSONB columns store flexible AI output, and it signals production-readiness to judges.

### Why shadcn/ui (not custom CSS)?
shadcn/ui gives accessible, pre-built components (tables, badges, cards, charts) in one day. Tailwind handles all custom styling. Zero design effort for polished results.

### watsonx.ai Prompt Strategy
Each scan generates a single structured prompt containing all findings. Response is parsed into:
1. `ai_summary` — one paragraph
2. `ai_fix_suggestions` — array of `{finding_id, suggestion}` objects
3. `ai_review_narrative` — overall code health paragraph

Model preference: `ibm/granite-13b-instruct-v2` (IBM native, lower latency) with fallback to `meta-llama/llama-3-3-70b-instruct`.

---

## 9. Day-by-Day Build Plan

### Day 1 — Backend + Data Layer (8–10 h)

| Time | Task |
|------|------|
| 0–1 h | `docker-compose.yml`, PostgreSQL, FastAPI scaffold, `.env` |
| 1–2 h | SQLAlchemy models, Alembic migrations, DB session |
| 2–3 h | Auth: register/login, JWT middleware |
| 3–5 h | Bandit runner + dep auditor service, scan pipeline task |
| 5–6.5 h | watsonx.ai client + prompt builder |
| 6.5–8 h | Report builder (score formula, aggregation), all `/scans` + `/reports` routes |
| 8–9 h | Test with curl / Postman; fix critical bugs |
| 9–10 h | Buffer / debugging |

### Day 2 — Frontend + Polish (8–10 h)

| Time | Task |
|------|------|
| 0–1 h | Next.js scaffold, Tailwind, shadcn/ui, API client lib |
| 1–2 h | Auth pages (login/register), JWT storage |
| 2–4 h | Dashboard page: scan list, stats cards, trend chart |
| 4–6 h | New Scan page (snippet/upload tabs) + polling status page |
| 6–8 h | Report page: score gauge, findings tables, AI summary card |
| 8–9 h | End-to-end smoke test, CORS, Docker wiring |
| 9–10 h | Stretch features or demo polish |

---

## Environment Variables

```bash
# backend/.env
DATABASE_URL=postgresql+asyncpg://codeguardian:secret@localhost:5432/codeguardian
SECRET_KEY=change-me-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

WATSONX_API_KEY=your-ibm-cloud-api-key
WATSONX_PROJECT_ID=your-watsonx-project-id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-13b-instruct-v2

# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

---

*Architecture designed for IBM Bob Hackathon 2025 — CodeGuardian AI*
