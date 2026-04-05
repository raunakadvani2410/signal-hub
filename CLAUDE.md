# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Personal Command Center — a single-user personal dashboard aggregating email, calendar, messages, and tasks from external services.

## Stack

- **Frontend:** `apps/web` — Next.js (App Router) + TypeScript + Tailwind
- **Backend:** `apps/api` — FastAPI + Pydantic + SQLAlchemy + Alembic
- **Database:** PostgreSQL (local: started manually or via `postgres` CLI)
- **Shared:** `packages/shared/typescript` (Zod + TS types), `packages/shared/python` (Pydantic base models)
- **Package manager:** pnpm workspaces for TS; pip editable install for Python

## Commands

> On macOS, use `python3` — the `python` command is not aliased by default.
> All `uvicorn`, `pytest`, and `alembic` commands must be run with the venv active,
> or prefixed with `.venv/bin/` (e.g. `.venv/bin/uvicorn ...`).

**API — one-time setup (run from `apps/api/`)**
```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ../../packages/shared/python
pip install -e ".[dev]"
cp .env.example .env
# Edit .env — set DATABASE_URL with your macOS username (run `whoami` to find it)
```

**API — daily use (run from `apps/api/`, venv active)**
```bash
source .venv/bin/activate              # activate if not already active
uvicorn app.main:app --reload          # dev server on http://localhost:8000
pytest                                 # run all tests
pytest tests/test_health.py           # run one test file
alembic upgrade head                   # apply pending migrations
alembic revision --autogenerate -m "description"  # generate a new migration
```

**Web — one-time setup (run from repo root)**
```bash
pnpm install                           # installs apps/web + packages/shared/typescript
cp apps/web/.env.example apps/web/.env.local
```

**Web — daily use (run from repo root)**
```bash
pnpm --filter web dev                  # dev server on http://localhost:3000
pnpm --filter web build
pnpm --filter web lint
pnpm --filter web type-check
```

**Postgres — one-time local setup**
```bash
createdb signal_hub                    # create the empty database
# Then run: alembic upgrade head (from apps/api with venv active)
```

## Docs

- `docs/architecture.md` — system design and layer boundaries
- `docs/product-spec.md` — integration status, scope, success criteria
- `docs/google-oauth-setup.md` — step-by-step Google Cloud credential setup for Gmail/GCal

## Rules

Detailed rules live in `.claude/rules/`:

- `architecture.md` — where code goes, import conventions, layer boundaries
- `testing.md` — testing strategy per layer
- `security.md` — secrets handling, OAuth, what never to do
- `product.md` — product scope and principles
- `integrations.md` — official vs unofficial integrations, how to add new ones

## Key Conventions

- All cross-app data shapes are defined once in `packages/shared/` and imported by both `api` and `web`. Do not duplicate schemas.
- Auth is single-user for now. OAuth tokens are stored in `.env` or a local secrets file, never in the database or committed to git.
- Integrations have four status levels: **Official**, **Official but constrained**, **Third-party / experimental**, and **Local-only experimental**. Each status carries different build and reliability expectations. See `.claude/rules/integrations.md` before building any integration.
- Prefer flat, explicit code over abstractions. Add a layer only when there are at least three concrete use cases for it.
