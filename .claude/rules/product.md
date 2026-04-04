# Product Rules

## What This Is

A personal, single-user productivity dashboard. The goal is to reduce context-switching by showing the user what needs their attention across Gmail, Google Calendar, Notion, and (eventually) messaging platforms in one place.

## What This Is Not

- Not a SaaS product. Do not design for multi-tenancy in v1.
- Not a communication tool. The dashboard is read-only in v1. Do not add reply/send features until the read layer is solid.
- Not an AI product. No summarization, prioritization, or LLM calls in v1.
- Not a mobile app.

## Scope Discipline

- Before adding a feature, check if it is in `docs/product-spec.md`. If it is not, flag it rather than building it.
- "Nice to have" features belong in a backlog comment in `docs/product-spec.md`, not in the code.
- Prefer shipping a working, narrow feature over a broad, half-finished one.

## UX Principles

- The unified feed is the primary view. Everything else is secondary.
- Fast load over rich features. The dashboard should feel instant on a local machine.
- If an integration is broken or slow, fail gracefully — show what works, surface an error for what does not.

## Non-Goals (v1)

- Push notifications
- Real-time sync (polling is acceptable)
- Replying or sending from the dashboard
- AI features
- Multi-user auth
- Mobile
