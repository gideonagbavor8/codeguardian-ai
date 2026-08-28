# ── CodeGuardian AI — Makefile ────────────────────────────────
# Shortcuts for common dev tasks. Run from repo root.

.PHONY: dev backend frontend migrate seed test lint fmt help

# Start full stack with Docker Compose
dev:
	docker compose up --build

# Run backend in dev mode (requires local postgres on 5432)
backend:
	cd backend && uvicorn app.main:app --reload --port 8000

# Apply Alembic migrations
migrate:
	cd backend && alembic upgrade head

# Seed demo data
seed:
	cd backend && python scripts/seed_demo.py

# Run tests
test:
	cd backend && pytest tests/ -v

# Lint
lint:
	cd backend && ruff check app/ tests/

# Format
fmt:
	cd backend && black app/ tests/ scripts/

help:
	@echo ""
	@echo "  make dev       — start full stack (docker compose)"
	@echo "  make backend   — run FastAPI locally with hot reload"
	@echo "  make migrate   — apply Alembic migrations"
	@echo "  make seed      — seed demo user + scan"
	@echo "  make test      — run pytest suite"
	@echo "  make lint      — ruff lint check"
	@echo "  make fmt       — black format"
	@echo ""
