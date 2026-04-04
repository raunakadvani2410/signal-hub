# Security Rules

## Secrets and Credentials

- All secrets (OAuth client IDs, client secrets, access tokens, refresh tokens, API keys) live in `.env` only.
- `.env` is in `.gitignore`. Never commit it.
- Do not hardcode any token, key, or credential in source code, even as a placeholder.
- Do not log secrets. Do not include them in error messages or stack traces.

## OAuth Tokens (Single-User)

- In v1, OAuth tokens are stored in `.env` or a local file excluded from git (e.g., `.tokens.json`).
- Refresh tokens must be handled: always attempt a token refresh on 401 from an external API before failing.
- When multi-user auth is added later: tokens move to the DB, encrypted at rest. The service layer should accept a `user_id` argument now so that migration is a smaller change.

## API Security (v1 — local only)

- The FastAPI backend has no auth middleware in v1. It is assumed to be local-only (not exposed to the internet).
- If the API is ever exposed (e.g., via a tunnel for mobile access), add API key authentication before doing so. Do not expose an unauthenticated endpoint to the internet.
- Never disable CORS entirely. In development, restrict to `localhost` origins.

## External API Usage

- Use official OAuth flows. Do not use credentials stuffing or unofficial session-based auth for services that have an official API.
- For unofficial integrations (iMessage, WhatsApp, LinkedIn): do not store other users' data, do not run automation that impersonates user actions at scale.

## Input Handling

- Validate all inputs at the API boundary using Pydantic. Do not pass raw request data to the DB layer.
- Parameterize all DB queries via SQLAlchemy. No raw string interpolation in queries.
