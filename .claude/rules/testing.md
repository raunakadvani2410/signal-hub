# Testing Rules

## Philosophy

Test behavior, not implementation. A test that breaks when you rename an internal variable is a bad test.

## Python (`apps/api`)

- Framework: `pytest`
- Unit tests live in `apps/api/tests/` mirroring the `app/` structure.
- Test services with real logic; mock only external HTTP calls (not the DB).
- Use `pytest-asyncio` for async service tests.
- Integration tests that hit the DB should use a separate test database, not the dev database.
- Do not mock SQLAlchemy sessions in unit tests — if a test needs the DB, use a real test DB.

## TypeScript (`apps/web`)

- Framework: Vitest (preferred over Jest for this stack) or Jest — decide in Phase 1.
- Test `lib/api.ts` and any non-trivial utility functions.
- Component tests: test user-visible behavior, not internal state. Use Testing Library.
- Do not snapshot-test components by default; snapshots are fragile and rarely catch real bugs.

## Shared Package

- Python models: test serialization and validation edge cases in `packages/shared/python/tests/`.
- TypeScript schemas: test Zod parse/safeParse for invalid inputs.

## What Not to Test

- Trivial getters/setters with no logic.
- Framework behavior (e.g., do not test that FastAPI returns 422 for missing fields — that is FastAPI's job).
- Generated migration files.
