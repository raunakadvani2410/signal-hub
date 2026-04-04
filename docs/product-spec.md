# Product Spec — Personal Command Center

## Goal

A personal dashboard for one user that pulls messages, emails, calendar events, and tasks from external services and presents them in a unified, scannable interface.

This is a personal productivity tool, not a SaaS product. The first version is entirely single-user.

---

## Core User Needs

1. See all incoming messages and emails in one place without switching apps.
2. See today's calendar events alongside tasks and notifications.
3. Mark items as read, done, or snoozed from the dashboard.
4. Search across all sources.

---

## Integrations

### Official

| Service | What we pull | API | Auth |
|---|---|---|---|
| Gmail | Inbox messages, labels, read/unread state | Google Gmail REST API v1 | OAuth 2.0 |
| Google Calendar | Events, attendees, times, links | Google Calendar API v3 | OAuth 2.0 (same app as Gmail) |
| Notion | Pages, tasks, database entries | Notion REST API | OAuth or internal integration token |

### Official but constrained — WhatsApp

**Status:** Feasible via the WhatsApp Business Platform / Cloud API. Not suitable for mirroring a personal consumer account.

| Dimension | Detail |
|---|---|
| **What works** | WhatsApp Business Platform (Meta Cloud API) supports sending and receiving messages programmatically with a verified business number. |
| **Key limitation** | Requires a Meta Business account and a dedicated WhatsApp Business phone number. A personal +1 consumer number cannot be connected. |
| **Reliability** | High — official, well-documented, actively maintained by Meta. |
| **Policy risk** | Low if used via the official Cloud API. High if using any unofficial library (e.g., `whatsapp-web.js`), which violates WhatsApp ToS and risks account bans. |
| **Auth complexity** | Moderate — requires Meta app setup, webhook configuration, and a persistent phone number. |
| **Long-term maintainability** | Good via the official API. Unofficial approaches are fragile and should not be used. |
| **Build decision** | Primary path is the Meta WhatsApp Business Platform / Cloud API. This requires a business account and a dedicated WhatsApp Business number — it cannot mirror a personal consumer account. If this constraint makes the official path unfit for the use case, a vendor connector may be evaluated as a secondary option, applying the same rigor used for LinkedIn connectors (explicit tradeoff review, no unofficial libraries). |

### Third-party / experimental — LinkedIn

**Status:** Strategically important but no broadly available personal messaging API exists. Requires a connector vendor or an experimental session-based bridge.

| Dimension | Detail |
|---|---|
| **What works** | LinkedIn's official APIs (Marketing, Compliance, Talent) do not include personal inbox access. The Messaging API is gated behind the LinkedIn Partner Program and not available to individuals. |
| **Connector vendor path** | Services like Unipile or Nango offer LinkedIn messaging connectors. These use session-based auth and are not officially sanctioned by LinkedIn, but are the most practical current path for personal inbox access. |
| **Browser/session bridge** | A local bridge that authenticates with a browser session (similar to how WhatsApp Web works) is technically possible but fragile, and LinkedIn actively rate-limits and blocks such patterns. |
| **Reliability** | Low to medium — any non-partner approach may break without notice when LinkedIn updates its platform. |
| **Policy risk** | Medium to high — personal session automation exists in a gray area under LinkedIn's User Agreement. Connector vendors accept this risk on behalf of users; building a custom implementation may not. |
| **Auth complexity** | High — no standard OAuth for personal messaging; connector vendors handle auth but introduce a third-party dependency. |
| **Long-term maintainability** | Poor if built from scratch. Acceptable if delegated to a maintained connector vendor. |
| **Build decision** | Do not build a custom LinkedIn scraper. If LinkedIn messaging is prioritized, evaluate a connector vendor (e.g., Unipile) and document the dependency clearly. |

### Local-only experimental — iMessage

**Status:** Feasible only on macOS, with no public API. Read-only access to local message history via SQLite.

| Dimension | Detail |
|---|---|
| **What works** | macOS stores iMessage history in a local SQLite database at `~/Library/Messages/chat.db`. Read-only queries are possible without any API. |
| **Key limitation** | macOS-only. Requires Full Disk Access permission grant. Schema is undocumented and has changed between OS versions. No way to receive new messages in real time without polling. |
| **Reliability** | Low — schema may break on any macOS update. |
| **Policy risk** | None for reading your own local data. |
| **Auth complexity** | None — local file read only. Requires macOS permission prompt. |
| **Long-term maintainability** | Low — tied to undocumented internals. |
| **Build decision** | Implement as an opt-in, clearly labeled experimental connector. Must be behind a feature flag. Polling interval should be conservative to avoid excessive disk I/O. |

---

## Non-Goals (v1)

- Multi-user support
- Mobile app
- Sending / replying from the dashboard (read-only first)
- AI summarization or prioritization
- Push notifications
- Real-time sync (polling is fine for v1)

---

## Success Criteria (v1)

- Gmail inbox loads and shows unread count and message previews.
- Google Calendar shows today's and tomorrow's events.
- Notion tasks appear in a list view.
- All items share a normalized shape (see `packages/shared/`).
- The dashboard loads in under 2 seconds on a local machine.
