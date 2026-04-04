# Architecture — Personal Command Center

## System Overview

```
┌─────────────────────────────────────────────────────┐
│                    Browser                          │
│              Next.js (App Router)                   │
│         apps/web  —  TypeScript + Tailwind          │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (REST)
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI                            │
│              apps/api  —  Python                    │
│    routers/ → services/ → db/ (SQLAlchemy)          │
└───────┬───────────────────────────┬─────────────────┘
        │                           │
┌───────▼───────┐         ┌─────────▼─────────────────┐
│  PostgreSQL   │         │   External APIs            │
│  (local)      │         │   Gmail, GCal, Notion, ... │
└───────────────┘         └───────────────────────────┘
```

---

## Layers

### `apps/api`

```
app/
├── main.py          # App entry point, middleware
├── config.py        # Settings (pydantic-settings, reads from .env)
├── db/
│   ├── models.py    # SQLAlchemy ORM models
│   └── migrations/  # Alembic migration files
├── routers/         # One file per domain (messages, events, tasks)
├── services/        # Business logic + external API clients
└── schemas/         # Pydantic request/response schemas (may re-export from shared)
```

- Routers are thin: validate input, call a service, return output.
- Services own integration logic. One service per external source.
- DB models are internal. They do not leak out of the API layer directly.

### `apps/web`

```
src/
├── app/             # Next.js App Router pages and layouts
├── components/      # UI components
└── lib/
    ├── api.ts       # Typed fetch wrapper for the FastAPI backend
    └── types.ts     # Re-exports from packages/shared/typescript
```

- All API calls go through `lib/api.ts`. No raw fetch calls in components.
- Shared types are imported from `packages/shared/typescript`, not duplicated.

### `packages/shared`

```
packages/shared/
├── python/
│   └── signal_hub_shared/
│       ├── __init__.py
│       └── models.py   # Pydantic base models: Message, Event, Task, Notification
└── typescript/
    └── src/
        ├── index.ts
        └── models.ts   # Zod schemas + inferred TS types (mirrors Python models)
```

- This is the single source of truth for normalized data shapes.
- Both sides must stay in sync. When a Python model changes, update the TS schema too.
- Python: installed as editable local package (`pip install -e packages/shared/python`).
- TypeScript: referenced as pnpm workspace package (`"signal-hub-shared": "workspace:*"`).

---

## Data Flow (example: Gmail)

1. Cron or manual trigger hits `POST /api/sync/gmail`.
2. `services/gmail.py` fetches messages via Gmail REST API using stored OAuth token.
3. Each raw Gmail message is normalized into a `Message` (from `signal_hub_shared`).
4. Normalized messages are upserted into Postgres.
5. `GET /api/messages` returns stored messages to the frontend.
6. Web renders them using TS types from `packages/shared/typescript`.

---

## Auth (Single-User)

- OAuth tokens (Gmail, GCal, Notion) are stored in `.env` or a local token file outside git.
- No session management, no user table in v1.
- The API has no authentication middleware in v1 — it assumes local-only access.
- **Design note:** When multi-user auth is added, introduce a `User` model and move token storage to the DB with per-user encryption. The service layer should already accept a `user_id` parameter to make this migration easier.

### Auth patterns by integration status

| Status | Auth approach |
|---|---|
| Official | Standard OAuth 2.0 with refresh tokens stored in `.env` |
| Official but constrained (WhatsApp) | Meta Business app credentials + webhook secret in `.env`; phone number is fixed |
| Third-party / experimental (LinkedIn) | Connector vendor handles auth (e.g., Unipile API key); vendor token stored in `.env` |
| Local-only experimental (iMessage) | No auth — local file read; macOS Full Disk Access permission required |

---

## Database

- PostgreSQL, managed with Alembic for migrations.
- ORM: SQLAlchemy (async via `asyncpg`).
- One table per normalized type: `messages`, `events`, `tasks`, `notifications`.
- Each row stores: `source` (e.g., `"gmail"`), `external_id`, normalized fields, `raw_json` (for debugging).

---

## Key Constraints

- No Docker in Phase 0–1. Run Postgres locally.
- No message queue or background workers in v1. Sync is triggered manually or by a simple cron endpoint.
- Polling over webhooks for v1. Webhooks can be added per-integration later.
