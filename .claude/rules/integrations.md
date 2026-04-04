# Integration Rules

## Status Labels

Every integration must carry exactly one of these four labels:

| Label | Meaning |
|---|---|
| **Official** | Supported public API, standard OAuth or API key, actively maintained by the service. Build with confidence. |
| **Official but constrained** | Official API exists and is reliable, but has meaningful limitations (e.g., only works with a business account, not a personal one). Build against the official path only; document the constraint clearly in code and UI. |
| **Third-party / experimental** | No personal API from the service itself. Implementation requires a connector vendor or session-based bridge. Strategically important but not production-stable. Build only after confirming the specific approach and accepting the tradeoffs. |
| **Local-only experimental** | No API at all. Access is via local files or OS internals. macOS-only or similarly constrained. Must be opt-in, behind a feature flag, and clearly labeled in the UI. |

---

## Current Integrations

### Official

| Service | API | Auth | What we pull |
|---|---|---|---|
| Gmail | Google Gmail REST API v1 | OAuth 2.0 (offline, refresh token) | Inbox messages, labels, read/unread |
| Google Calendar | Google Calendar API v3 | OAuth 2.0 (same Google app as Gmail) | Events, attendees, times, links |
| Notion | Notion REST API | OAuth or internal integration token | Pages, tasks, database entries |

### Official but constrained — WhatsApp

- **API:** WhatsApp Business Platform / Meta Cloud API
- **Auth:** Meta Business app credentials + webhook secret
- **What works:** Full send/receive via a verified WhatsApp Business phone number.
- **Key constraint:** A personal consumer phone number cannot be connected. This is a business number integration, not a personal account mirror.
- **Do not use** unofficial libraries (`whatsapp-web.js`, etc.) — they reverse-engineer the web client, violate WhatsApp ToS, and risk permanent account bans.
- **If the Business API path does not fit** (e.g., the use case requires a personal account mirror): a vendor connector may be evaluated as a secondary option, applying the same tradeoff review process as LinkedIn connectors. This is not the default path.
- **Reliability:** High via the official API. Low via any unofficial path.
- **Policy risk:** Low (official API). Medium (vendor connector). High (unofficial library).

### Third-party / experimental — LinkedIn

- **API:** None available to individuals. LinkedIn Partner Program required for the Messaging API.
- **Viable path:** Connector vendor (e.g., Unipile, Nango) that handles LinkedIn session auth on your behalf. Vendor provides a normalized API you call; they manage the LinkedIn session.
- **Auth:** Connector vendor API key stored in `.env`; vendor handles the LinkedIn session.
- **Do not build** a custom LinkedIn scraper or browser automation. LinkedIn actively rate-limits and blocks such patterns, and it sits in a gray area under LinkedIn's User Agreement.
- **Reliability:** Medium — vendor-dependent. Any non-partner approach may break when LinkedIn updates its platform.
- **Policy risk:** Medium to high for custom session automation. Delegated risk when using a connector vendor.
- **Build decision:** Evaluate a connector vendor before writing any LinkedIn-specific code. Document the vendor dependency explicitly.

### Local-only experimental — iMessage

- **API:** None. Local SQLite read at `~/Library/Messages/chat.db`.
- **Auth:** No auth. Requires macOS Full Disk Access permission granted by the user.
- **What works:** Read-only access to local message history via SQL queries.
- **Key constraints:** macOS-only. Undocumented schema that has changed between OS versions. No real-time delivery — polling only. No way to write or send.
- **Must be:** opt-in, behind a feature flag, clearly labeled as experimental in the UI.
- **Reliability:** Low — schema may break on any macOS update.
- **Policy risk:** None for reading your own local data.

---

## How to Add a New Integration

1. Choose the correct status label from the table above. Document it in this file and in `docs/product-spec.md`.
2. For **Third-party / experimental** integrations: confirm the specific vendor or approach with the user before writing code. Do not start implementation speculatively.
3. Create a service file: `apps/api/app/services/<source>.py`.
4. The service must:
   - Accept a `user_id` parameter (even if unused in v1) for future multi-user compatibility.
   - Return normalized `Message`, `Event`, or `Task` objects from `signal_hub_shared`. Never return raw third-party API shapes to the router layer.
   - Surface the integration's status label as a constant (e.g., `INTEGRATION_STATUS = "official_constrained"`) so it can be displayed in the UI.
5. Add a sync endpoint: `POST /api/sync/<source>`.
6. Document the auth setup (credentials needed, where to get them) in `docs/architecture.md`.
7. For **Local-only experimental** integrations: gate the service behind a feature flag in `config.py`.

## What Not to Do

- Do not use unofficial libraries for services that have an official API.
- Do not scrape any service. Scraping violates ToS and is fragile.
- Do not build a custom session-bridge for LinkedIn — use a connector vendor or wait.
- Do not treat **Third-party / experimental** or **Local-only experimental** integrations as equivalent to **Official** ones. They require explicit tradeoff acceptance before build.
