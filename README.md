# Personal Command Center

A personal dashboard that aggregates messages, notifications, email, calendar events, and tasks from external services into a single interface.

Single-user, personal use. Designed to be extended to multi-user auth later without a full rewrite.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind |
| Backend | FastAPI + Pydantic |
| Database | PostgreSQL |
| Shared schemas | `packages/shared/typescript` (Zod + TS types), `packages/shared/python` (Pydantic models) |
| Package manager | pnpm workspaces (TS side); pip editable install (Python side) |

---

## Integrations

| Service | Type | Integration Status | Notes |
|---|---|---|---|
| Gmail | Email | **Official** | Google Gmail REST API, OAuth 2.0 |
| Google Calendar | Calendar | **Official** | Google Calendar API v3, OAuth 2.0 |
| Notion | Tasks / Notes | **Official** | Notion REST API, OAuth or internal token |
| WhatsApp | Messaging | **Official but constrained** | Business Platform / Cloud API only; personal consumer accounts not supported |
| LinkedIn | Messaging | **Third-party / experimental** | No personal messaging API; requires connector vendor or session bridge |
| iMessage | Messaging | **Local-only experimental** | macOS only; no public API; local SQLite read |

See `docs/product-spec.md` and `.claude/rules/integrations.md` for full tradeoff analysis per integration.

---

## Repo Structure

```
signal-hub/
├── apps/
│   ├── api/          # FastAPI backend
│   └── web/          # Next.js frontend
├── packages/
│   └── shared/
│       ├── python/   # Pydantic base models
│       └── typescript/ # Zod schemas + inferred TS types
├── docs/
│   ├── product-spec.md
│   └── architecture.md
├── .claude/
│   └── rules/        # Repo rules for Claude Code
├── .gitignore
├── CLAUDE.md
└── README.md
```

---

## Development Phases

| Phase | Scope |
|---|---|
| **0 — Scaffolding** | Docs, rules, CLAUDE.md, .gitignore |
| **1 — Foundation** | FastAPI skeleton, Next.js skeleton, shared package stubs, DB + Alembic setup |
| **2 — Core models** | Normalized `Message`, `Event`, `Task`, `Notification` schemas in shared/ |
| **3 — First integrations** | Gmail + Google Calendar (OAuth, fetch, normalize, persist) |
| **4 — Dashboard UI** | Unified feed view, item detail panel, filters |
| **5 — Notion** | Task and page ingestion |
| **6 — Messaging integrations** | WhatsApp (Business API), LinkedIn (connector/bridge), iMessage (local experimental) |
