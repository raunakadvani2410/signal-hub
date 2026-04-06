import type { FeedItem, IntegrationConfig, Message } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export interface GmailStatus {
  connected: boolean;
  last_synced_at: string | null;
  history_id: string | null;
}

export const api = {
  integrations: {
    list: () => apiFetch<IntegrationConfig[]>("/api/integrations/"),
  },
  messages: {
    list: (limit?: number) =>
      apiFetch<Message[]>(`/api/messages/${limit ? `?limit=${limit}` : ""}`),
  },
  feed: {
    list: (limit?: number) =>
      apiFetch<FeedItem[]>(`/api/feed/${limit ? `?limit=${limit}` : ""}`),
  },
  gmail: {
    status: () => apiFetch<GmailStatus>("/api/gmail/status"),
  },
};
