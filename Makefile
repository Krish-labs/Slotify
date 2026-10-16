COMPOSE ?= docker compose
LOAD_FILE ?= data/raw/Load Distribution.xlsx

.PHONY: help install dev backend frontend worker build build-backend build-frontend \
	prod-build prod-up prod-down prod-logs \
	test test-backend test-backend-unit test-backend-integration test-scheduler test-frontend \
	test-backend-pg verify-pg \
	lint lint-backend lint-frontend typecheck format \
	db-up db-down db-logs db-migrate db-migrate-create db-seed db-reset \
	import-load clean clean-outputs

help:
	@echo "SchedulAI - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install all dependencies"
	@echo "  make db-up            Start database services"
	@echo "  make db-down          Stop database services"
	@echo ""
	@echo "Development:"
	@echo "  make dev              Start all services (backend + frontend + workers)"
	@echo "  make backend          Start backend only"
	@echo "  make frontend         Start frontend only"
	@echo "  make worker           Start background worker"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate       Run database migrations"
	@echo "  make db-seed          Seed database with initial data"
	@echo "  make db-reset         Reset database (drop + migrate + seed)"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test             Run all tests"
	@echo "  make test-backend     Run backend tests"
	@echo "  make test-frontend    Run frontend tests"
	@echo "  make test-scheduler   Run scheduler tests"
	@echo "  make test-backend-pg  Run backend tests against PostgreSQL (needs DATABASE_URL)"
	@echo "  make verify-pg        Rebuild a disposable PG schema + API smoke (needs DATABASE_URL)"
	@echo "  make lint             Run all linters"
	@echo "  make typecheck        Run type checking"
	@echo ""
	@echo "Build:"
	@echo "  make build            Build all Docker images"
	@echo "  make build-backend    Build backend image"
	@echo "  make build-frontend   Build frontend image"
	@echo ""
	@echo "Data Processing:"
	@echo "  make import-load      Import load distribution from Excel"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Clean build artifacts and caches"
	@echo "  make clean-outputs    Remove generated timetable/report files"

# ============================================================================
# Setup
# ============================================================================
install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

# ============================================================================
# Database Services
# ============================================================================
db-up:
	$(COMPOSE) up -d postgres redis

db-down:
	$(COMPOSE) down

db-logs:
	$(COMPOSE) logs -f postgres redis

# ============================================================================
# Development
# ============================================================================
dev:
	$(COMPOSE) up --build

backend:
	$(COMPOSE) up backend

frontend:
	$(COMPOSE) up frontend

worker:
	$(COMPOSE) up worker

# Production overlay (requires .env.prod; see .env.prod.example).
# Never boots with development credentials: missing/insecure secrets fail
# compose interpolation or backend startup before serving traffic.
prod-build:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml build

prod-up:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-down:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml down

prod-logs:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml logs -f

# ============================================================================
# Database Operations
# ============================================================================
db-migrate:
	$(COMPOSE) exec backend alembic upgrade head

db-migrate-create:
	@read -p "Migration message: " msg; \
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$$msg"

# Roles + permissions. Set SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD to also create an admin:
#   make db-seed SEED_ADMIN_EMAIL=you@example.com SEED_ADMIN_PASSWORD=...
db-seed:
	$(COMPOSE) exec -e SEED_ADMIN_EMAIL -e SEED_ADMIN_PASSWORD backend python -m app.database.seed

db-reset:
	@echo "WARNING: db-reset drops the entire schema (downgrade base) and reseeds."
	@echo "Never point DATABASE_URL at production. Require CONFIRM=yes to proceed."
	@test "$${CONFIRM:-}" = "yes" || (echo "Aborted: re-run with CONFIRM=yes" && exit 1)
	$(COMPOSE) exec backend alembic downgrade base
	$(COMPOSE) exec backend alembic upgrade head
	$(COMPOSE) exec backend python -m app.database.seed

# ============================================================================
# Testing
# ============================================================================
test: test-backend test-frontend test-scheduler

test-backend:
	cd backend && pytest tests/ -v --cov=app --cov-report=term-missing

test-backend-unit:
	cd backend && pytest tests/unit/ -v

test-backend-integration:
	cd backend && pytest tests/integration/ -v

test-scheduler:
	cd backend && pytest tests/scheduler/ -v

test-frontend:
	cd frontend && npm run test

# Same suite as CI: DATABASE_URL must point at a (disposable) PostgreSQL, or
# conftest.py falls back to in-memory SQLite and the run proves nothing new.
# The suite drops every table in the target database after each test, so
# pointing it at the shared dev database wipes real data: refuse the
# well-known non-disposable names unless CONFIRM=yes.
test-backend-pg:
	@case "$$DATABASE_URL" in postgresql*) ;; *) \
		echo "DATABASE_URL must be a postgresql+asyncpg:// URL (got: $${DATABASE_URL:-unset})"; exit 2;; esac
	@dbname=$$(echo "$$DATABASE_URL" | sed -E 's#^[^/]*//[^/]*/##; s#[?].*$$##'); \
	if [ "$$dbname" = "schedulai" ] && [ "$${CONFIRM:-}" != "yes" ]; then \
		echo "Refusing: test-backend-pg drops all tables in '$$dbname'; use a disposable database or re-run with CONFIRM=yes"; exit 2; fi
	cd backend && pytest tests/ -q -p no:warnings

# PostgreSQL schema/API verification (see scripts/pg_*.py).
# verify-pg is DESTRUCTIVE: it drops and recreates the schema of the database
# DATABASE_URL points at. Never point it at a database you care about.
# The smoke runs first because it rebuilds the schema from alembic; the audit
# then validates that schema (a bare test run leaves the schema dropped).
verify-pg:
	@case "$$DATABASE_URL" in postgresql*) ;; *) \
		echo "DATABASE_URL must be a postgresql+asyncpg:// URL (got: $${DATABASE_URL:-unset})"; exit 2;; esac
	@dbname=$$(echo "$$DATABASE_URL" | sed -E 's#^[^/]*//[^/]*/##; s#[?].*$$##'); \
	if [ "$$dbname" = "schedulai" ] && [ "$${CONFIRM:-}" != "yes" ]; then \
		echo "Refusing: verify-pg drops and recreates the schema of '$$dbname'; use a disposable database or re-run with CONFIRM=yes"; exit 2; fi
	python scripts/pg_integration_smoke.py --allow-destructive
	PYTHONPATH=backend python scripts/pg_schema_audit.py

# ============================================================================
# Linting & Type Checking
# ============================================================================
lint: lint-backend lint-frontend

lint-backend:
	cd backend && ruff check app/ tests/
	cd backend && black --check app/ tests/

lint-frontend:
	cd frontend && npm run lint

typecheck:
	cd backend && mypy app/
	cd frontend && npm run typecheck

format:
	cd backend && black app/ tests/
	cd backend && ruff check --fix app/ tests/

# ============================================================================
# Build
# ============================================================================
build: build-backend build-frontend

build-backend:
	docker build -t schedulai/backend:latest ./backend

build-frontend:
	docker build -t schedulai/frontend:latest ./frontend

# ============================================================================
# Data Processing Scripts
# ============================================================================
import-load:
	$(COMPOSE) exec backend python scripts/import_data.py --file "$(LOAD_FILE)"

# ============================================================================
# Cleanup
# ============================================================================
clean:
	rm -rf backend/__pycache__ backend/.pytest_cache backend/.coverage backend/htmlcov
	rm -rf backend/app/__pycache__ backend/app/**/__pycache__
	rm -rf frontend/node_modules frontend/dist frontend/build frontend/.vite
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

clean-outputs:
	@echo "WARNING: clean-outputs deletes generated timetables/reports/validation/logs."
	@echo "Ensure artifacts are backed up or regenerable. Require CONFIRM=yes."
	@test "$${CONFIRM:-}" = "yes" || (echo "Aborted: re-run with CONFIRM=yes" && exit 1)
	rm -rf outputs/timetables/* outputs/reports/* outputs/validation/* outputs/logs/*
