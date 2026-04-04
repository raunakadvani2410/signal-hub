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

**API (`apps/api`) — run from `apps/api/`**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../../packages/shared/python
pip install -e ".[dev]"

uvicorn app.main:app --reload          # dev server on :8000
pytest                                 # run all tests
pytest tests/test_health.py            # run one file

alembic upgrade head                   # apply all migrations
alembic revision --autogenerate -m "description"  # generate a migration
```

**Web (`apps/web`) — run from repo root**
```bash
pnpm install                           # install all workspaces
pnpm --filter web dev                  # dev server on :3000
pnpm --filter web build
pnpm --filter web lint
pnpm --filter web type-check
```

**Postgres — local setup (one-time)**
```bash
createdb signal_hub                    # create the database
# Then in apps/api: alembic upgrade head
```

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
