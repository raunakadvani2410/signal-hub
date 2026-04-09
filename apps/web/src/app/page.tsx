import { revalidatePath } from "next/cache";
import type { FeedItem, IntegrationConfig } from "@/lib/types";
import type { GmailStatus } from "@/lib/api";

// ── display config ────────────────────────────────────────────────────────────

const SOURCE_BADGE: Record<string, { label: string; cls: string }> = {
  gmail: {
    label: "Gmail",
    cls: "bg-red-950/70 text-red-400 border-red-900",
  },
  google_calendar: {
    label: "Calendar",
    cls: "bg-blue-950/70 text-blue-400 border-blue-900",
  },
  notion: {
    label: "Notion",
    cls: "bg-gray-800 text-gray-300 border-gray-700",
  },
};

const STATUS_META: Record<string, { label: string; cls: string }> = {
  official: {
    label: "Official",
    cls: "border-green-800 bg-green-900/40 text-green-300",
  },
  official_constrained: {
    label: "Official · constrained",
    cls: "border-yellow-800 bg-yellow-900/40 text-yellow-300",
  },
  third_party_experimental: {
    label: "3rd-party · experimental",
    cls: "border-orange-800 bg-orange-900/40 text-orange-300",
  },
  local_only_experimental: {
    label: "Local-only · experimental",
    cls: "border-gray-700 bg-gray-800/60 text-gray-400",
  },
};

const RISK_CLS: Record<string, string> = {
  low: "text-green-400",
  medium: "text-yellow-400",
  high: "text-red-400",
};

// ── data fetching ─────────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchIntegrations(): Promise<IntegrationConfig[]> {
  const res = await fetch(`${API_BASE}/api/integrations/`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API responded ${res.status}`);
  return res.json();
}

async function fetchFeed(source?: string, limit = 50): Promise<FeedItem[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (source) params.set("source", source);
  const res = await fetch(`${API_BASE}/api/feed/?${params}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API responded ${res.status}`);
  return res.json();
}

async function fetchGmailStatus(): Promise<GmailStatus> {
  const res = await fetch(`${API_BASE}/api/gmail/status`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API responded ${res.status}`);
  return res.json();
}

// ── helpers ───────────────────────────────────────────────────────────────────

function formatSender(sender: string): string {
  const match = sender.match(/^([^<]+)</);
  return match ? match[1].trim() : sender;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const isToday =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();

  if (isToday) {
    return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  }
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// ── shared feed item row ──────────────────────────────────────────────────────

function FeedItemRow({ item }: { item: FeedItem }) {
  const badge = SOURCE_BADGE[item.source] ?? {
    label: item.source,
    cls: "bg-gray-800 text-gray-400 border-gray-700",
  };
  const senderName = item.sender ? formatSender(item.sender) : null;

  return (
    <div
      className={`px-4 py-3 transition-colors ${
        item.is_read
          ? "bg-gray-950"
          : "bg-gray-900 border-l-2 border-blue-600"
      }`}
    >
      {/* top row: badge + sender/title-label + date */}
      <div className="flex items-center gap-2 mb-1 min-w-0">
        <span
          className={`inline-flex shrink-0 items-center rounded border px-1.5 py-px text-[10px] font-medium leading-none ${badge.cls}`}
        >
          {badge.label}
        </span>
        {senderName && (
          <span
            className={`text-xs truncate flex-1 min-w-0 ${
              item.is_read ? "text-gray-500" : "text-gray-300"
            }`}
          >
            {senderName}
          </span>
        )}
        <span className="ml-auto text-xs text-gray-600 shrink-0 tabular-nums">
          {formatDate(item.received_at)}
        </span>
      </div>

      {/* title */}
      <p
        className={`text-sm truncate leading-snug ${
          item.is_read ? "text-gray-400" : "font-medium text-white"
        }`}
      >
        {item.title}
      </p>

      {/* preview */}
      {item.preview && (
        <p className="text-xs text-gray-600 truncate mt-0.5 leading-relaxed">
          {item.preview}
        </p>
      )}
    </div>
  );
}

// ── feed section ──────────────────────────────────────────────────────────────

function FeedSection({
  title,
  items,
  emptyMessage,
  rightLabel,
}: {
  title: string;
  items: FeedItem[];
  emptyMessage: string;
  rightLabel?: string;
}) {
  return (
    <section>
      <div className="flex items-center gap-3 mb-2">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
          {title}
        </h2>
        <div className="flex-1 border-t border-gray-800" />
        {rightLabel && (
          <span className="text-xs text-gray-600">{rightLabel}</span>
        )}
      </div>

      {items.length === 0 ? (
        <div className="rounded-lg border border-gray-800 bg-gray-900/50 px-5 py-6 text-center">
          <p className="text-sm text-gray-500">{emptyMessage}</p>
        </div>
      ) : (
        <div className="rounded-lg border border-gray-800 overflow-hidden divide-y divide-gray-800/60">
          {items.map((item) => (
            <FeedItemRow key={item.id} item={item} />
          ))}
        </div>
      )}
    </section>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default async function Home() {
  async function syncAll() {
    "use server";
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    await Promise.allSettled([
      fetch(`${base}/api/gmail/sync`, { method: "POST" }),
      fetch(`${base}/api/gcal/sync`, { method: "POST" }),
      fetch(`${base}/api/notion/sync`, { method: "POST" }),
    ]);
    revalidatePath("/");
  }

  let integrations: IntegrationConfig[] = [];
  let allItems: FeedItem[] = [];
  let gmailItems: FeedItem[] = [];
  let calendarItems: FeedItem[] = [];
  let notionItems: FeedItem[] = [];
  let gmailStatus: GmailStatus | null = null;
  let apiError: string | null = null;

  try {
    [integrations, allItems, gmailStatus, gmailItems, calendarItems, notionItems] =
      await Promise.all([
        fetchIntegrations(),
        fetchFeed(),
        fetchGmailStatus(),
        fetchFeed("gmail"),
        fetchFeed("google_calendar", 20),
        fetchFeed("notion"),
      ]);
  } catch {
    apiError =
      "Could not reach the backend. Make sure the API is running on http://localhost:8000.";
  }

  const unreadCount = allItems.filter((i) => !i.is_read).length;

  const gmailSyncLabel = gmailStatus?.last_synced_at
    ? `synced ${formatRelativeTime(gmailStatus.last_synced_at)}`
    : gmailStatus?.connected
      ? "never synced"
      : "not connected";

  return (
    <main className="max-w-2xl mx-auto px-6 py-10 space-y-10">
      {/* ── header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-white tracking-tight">
            Signal Hub
          </h1>
          {gmailStatus?.last_synced_at && (
            <span className="text-xs text-gray-600">
              synced {formatRelativeTime(gmailStatus.last_synced_at)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <span className="rounded-full bg-blue-600 px-2 py-0.5 text-xs font-medium text-white">
              {unreadCount} unread
            </span>
          )}
          <form action={syncAll}>
            <button
              type="submit"
              className="rounded border border-gray-700 bg-gray-900 px-2.5 py-1 text-xs text-gray-400 hover:border-gray-600 hover:text-gray-300 transition-colors"
            >
              Sync now
            </button>
          </form>
        </div>
      </div>

      {apiError && (
        <div className="rounded border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-400">
          {apiError}
        </div>
      )}

      {!apiError && (
        <>
          {/* ── consolidated Signal Hub feed ── */}
          <FeedSection
            title="Signal Hub"
            items={allItems}
            emptyMessage="No items yet. Run a sync to populate the feed."
          />

          {/* ── Gmail ── */}
          <FeedSection
            title="Gmail"
            items={gmailItems}
            emptyMessage="No emails synced yet."
            rightLabel={gmailSyncLabel}
          />

          {/* ── Google Calendar ── */}
          <FeedSection
            title="Google Calendar"
            items={calendarItems}
            emptyMessage="No upcoming events in the next 7 days."
          />

          {/* ── Notion ── */}
          <FeedSection
            title="Notion"
            items={notionItems}
            emptyMessage="No open tasks. Run: curl -X POST http://localhost:8000/api/notion/sync"
          />

          {/* ── integrations (reference panel) ── */}
          <section>
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
                Integrations
              </h2>
              <div className="flex-1 border-t border-gray-800" />
            </div>
            <div className="flex flex-col gap-2">
              {integrations.map((item) => {
                const status = STATUS_META[item.status] ?? {
                  label: item.status,
                  cls: "border-gray-700 bg-gray-800 text-gray-400",
                };
                return (
                  <div
                    key={item.integration_key}
                    className="rounded-lg border border-gray-800 bg-gray-950 px-4 py-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-gray-200">
                        {item.display_name}
                      </span>
                      <span
                        className={`rounded-full border px-2 py-px text-[10px] font-medium ${status.cls}`}
                      >
                        {status.label}
                      </span>
                      <span className="ml-auto text-xs text-gray-700">
                        {item.connector_type}
                      </span>
                      <span
                        className={`text-xs ${RISK_CLS[item.risk_level] ?? "text-gray-500"}`}
                      >
                        {item.risk_level} risk
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </>
      )}
    </main>
  );
}
