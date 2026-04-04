# Architecture Rules

## Monorepo Layout

- `apps/api` — FastAPI backend. Self-contained Python project.
- `apps/web` — Next.js frontend. Part of the pnpm workspace.
- `packages/shared/python` — Pydantic base models. Editable pip install.
- `packages/shared/typescript` — Zod schemas + TS types. pnpm workspace package.
- `docs/` — Product and architecture documentation only. No code.
- `.claude/rules/` — Repo rules for Claude Code. No code.

## Layer Boundaries

- **Routers** (`apps/api/app/routers/`) are thin. They validate, call a service, return a response. No business logic, no direct DB access.
- **Services** (`apps/api/app/services/`) own all integration logic and business rules. One file per external source (e.g., `gmail.py`, `gcal.py`, `notion.py`).
- **DB models** (`apps/api/app/db/models.py`) are internal to the API. They do not leak into router responses directly — use Pydantic schemas for output.
- **Components** (`apps/web/src/components/`) must not call external APIs directly. All data fetching goes through `apps/web/src/lib/api.ts`.

## Shared Package Rule

- Normalized data shapes (`Message`, `Event`, `Task`, `Notification`) are defined **once** in `packages/shared/` and imported by both `api` and `web`.
- Do not define the same shape in both `apps/api` and `apps/web`. If you find yourself doing that, move it to `packages/shared/`.
- When updating a shared model, update both the Python and TypeScript versions in the same change.

## Naming Conventions

- Python: `snake_case` for files, functions, variables. `PascalCase` for classes.
- TypeScript: `camelCase` for variables/functions. `PascalCase` for types/components. Files: `kebab-case.ts`.
- Router files named after their domain noun, plural: `messages.py`, `events.py`.
- Service files named after their source: `gmail.py`, `notion.py`.

## Abstraction Threshold

Add a shared utility or abstraction only when there are **at least three concrete, existing uses** for it. Do not create helpers speculatively.
