# CodeGuardian AI

**AI-powered code review and security analysis that scans your source for vulnerabilities, then explains and prioritises them in plain English using IBM watsonx.ai.**

🔗 **Live app:** https://codeguardian-ai-beta.vercel.app/
📦 **Repository:** https://github.com/gideonagbavor8/codeguardian-ai

---

## The problem

Security review is the step teams skip when a deadline is close. Static analysers do exist, but they hand a developer a wall of raw rule IDs — `B602`, `B324`, `CWE-327` — with no sense of what matters, what to fix first, or whether the code is safe to ship. Findings get ignored, and vulnerable code reaches production.

## The solution

CodeGuardian AI runs industry-standard scanners across your code and dependencies, then puts an AI layer on top. Instead of a raw finding list you get a prioritised summary, a concrete fix suggestion for each issue, and a single **Release Readiness Score** that answers the actual question: *is this safe to ship?*

Point it at a file, a project ZIP, or a public GitHub repository, and get a report in seconds.

---

## Key features

| Feature | What it does |
| --- | --- |
| **Source file upload scanning** | Upload a single source file or a project `.zip`; the archive is unpacked and its source files are scanned |
| **GitHub repository scanning** | Paste a public GitHub URL and branch; the repository is downloaded and scanned in full, with findings reported per file |
| **Bandit scanning** | Python static analysis — shell injection, weak hashes, hardcoded secrets, insecure randomness |
| **Semgrep scanning** | Multi-language rule-based analysis, used automatically when the Semgrep binary is available |
| **Dependency vulnerability checking** | `requirements.txt` and `package.json` audited against known CVE advisories via pip-audit / npm audit |
| **AI security analysis** | IBM watsonx.ai (IBM Granite) turns raw findings into a readable summary and a specific fix suggestion per issue |
| **Security scoring** | A 0–100 Release Readiness Score, severity-weighted, mapped to a risk level from SAFE to CRITICAL |
| **Security reports** | Per-scan report with severity breakdown, per-file findings, CWE references and AI commentary |

Every finding is normalised into one shape regardless of which scanner produced it, so Bandit, Semgrep and dependency results are scored and displayed consistently.

---

## Architecture

```
Next.js frontend (Vercel)
        │  REST /api/v1
        ▼
FastAPI backend (Render)
        │
        ├── Scan pipeline ── Bandit ─┐
        │                   Semgrep ─┼─► normalised findings
        │                   pip-audit ┘
        │
        ├── IBM watsonx.ai (Granite) ─► summary + fix suggestions
        │
        └── PostgreSQL (Neon) ─► scans, findings, reports
```

A scan is accepted immediately (`202`) and runs as a background task through `PENDING → RUNNING → COMPLETE`, so the UI polls status while the pipeline extracts the source, runs the scanners, persists findings, calls watsonx.ai, and builds the report.

### Technology stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, Python 3.11+, SQLAlchemy 2 (async), Alembic |
| Database | PostgreSQL (Neon) |
| Security scanners | Bandit, Semgrep, pip-audit |
| AI | IBM watsonx.ai, IBM Granite |
| Development platform | IBM Bob 2.0 |
| Hosting | Vercel (frontend), Render (backend) |
| Auth | JWT (python-jose), bcrypt password hashing |

---

## IBM technology

### IBM watsonx.ai + IBM Granite

watsonx.ai is the intelligence layer of CodeGuardian AI. Once the scanners finish, the normalised findings are built into a structured prompt and sent to an **IBM Granite** foundation model through the `ibm-watsonx-ai` SDK. Granite returns JSON containing:

- a **summary** explaining the most important issues in plain English,
- a **fix suggestion** for each finding, referenced by index,
- a **narrative** assessing overall code health and release readiness.

The integration is built to fail safe. Credentials are read only from environment variables, the blocking SDK call runs in a thread-pool executor so the event loop is never blocked, and every failure mode — missing credentials, auth failure, timeout, malformed response — falls back to a deterministic placeholder analysis. **A watsonx.ai outage degrades the AI commentary; it never fails a scan or loses a finding.**

### IBM Bob 2.0

IBM Bob 2.0 was the core development platform for CodeGuardian AI, driving every stage of the build.

Of Bob 2.0's three modes — **Agent**, **Plan** and **Ask** — the project was built in **Agent mode**, so Bob worked autonomously across the codebase: reading the source-of-truth documents, creating and editing files directly, running commands to verify its work, and iterating on failures rather than only returning suggestions. Each stage below is a task Bob executed end to end in that mode:

| Stage | How IBM Bob was used |
| --- | --- |
| **Architecture** | Read `PROJECT_BRIEF.md` and produced the complete MVP architecture — system design, user flow, database schema, API surface and scope |
| **Scaffolding** | Generated the full repository structure from `ARCHITECTURE.md` |
| **Backend** | Implemented the FastAPI application, models, schemas and routers against `ARCHITECTURE.md` and `PROJECT_STRUCTURE.md` |
| **Scan pipeline** | Built the Bandit / Semgrep / dependency-audit pipeline and the finding normalisation layer |
| **Frontend** | Built the Next.js dashboard, scan and report pages |
| **Debugging** | Fixed the Alembic migration error, the scan-detail endpoint 500, the status-polling bug, the report page, and a scanner pipeline bug found during verification |
| **AI integration** | Diagnosed and hardened the watsonx.ai layer, including its fallback behaviour |

The exported task session records are in
[`docs/bob-session-summaries/`](docs/bob-session-summaries/) — a session covering
19 tasks and 141 assistant responses, alongside the Bobalytics usage dashboard
for the development period.

---

## Running locally

**Prerequisites:** Python 3.11+, Node.js 18+, PostgreSQL, and a watsonx.ai project (optional — the app runs without it and falls back to placeholder analysis).

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then fill in your own values
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs · Health: http://localhost:8000/health/db

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local         # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

App: http://localhost:3000

### Tests

```bash
cd backend && python -m pytest tests -q
```

---

## Security

**No secrets belong in this repository.** Every credential is supplied through environment variables and read via `app/config.py`; nothing is hardcoded in source.

- `backend/.env.example` and `frontend/.env.example` document the **names** of the required variables. They contain no real values — copy them and fill in your own.
- Real `.env` files are excluded by `.gitignore` and must never be committed.
- In production, configure variables in the hosting dashboard (Vercel / Render), not in the repository.

Variables required by the backend: `DATABASE_URL`, `SECRET_KEY`, `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `WATSONX_MODEL_ID`, `ALLOWED_ORIGINS`.

Repository scanning is restricted to **public** GitHub URLs. No credentials are ever sent to GitHub, repository URLs are validated against a strict allowlist before any request is made, downloaded archives are extracted with path-traversal and size protections, and cloned files are deleted after every scan including on failure.

---

*Built for the IBM TechXchange 2026 Pre-conference Dev Day Hackathon.*
