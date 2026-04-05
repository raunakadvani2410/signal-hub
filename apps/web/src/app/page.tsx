import type { IntegrationConfig } from "@/lib/types";

// ── status badge display config ──────────────────────────────────────────────

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

async function fetchIntegrations(): Promise<IntegrationConfig[]> {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const res = await fetch(`${base}/api/integrations/`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API responded ${res.status}`);
  return res.json();
}

// ── page ──────────────────────────────────────────────────────────────────────

export default async function Home() {
  let integrations: IntegrationConfig[] = [];
  let error: string | null = null;

  try {
    integrations = await fetchIntegrations();
  } catch {
    error =
      "Could not reach the backend. Make sure the API is running on http://localhost:8000.";
  }

  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <h1 className="text-xl font-semibold text-white mb-1">
        Personal Command Center
      </h1>
      <p className="text-gray-500 text-sm mb-8">Integrations</p>

      {error ? (
        <div className="rounded border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {integrations.map((item) => {
            const status = STATUS_META[item.status] ?? {
              label: item.status,
              cls: "border-gray-700 bg-gray-800 text-gray-400",
            };
            return (
              <div
                key={item.integration_key}
                className="rounded-lg border border-gray-800 bg-gray-900 px-5 py-4"
              >
                {/* header row */}
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="font-medium text-white">
                    {item.display_name}
                  </span>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs font-medium ${status.cls}`}
                  >
                    {status.label}
                  </span>
                  <span className="ml-auto text-xs text-gray-600">
                    connector:{" "}
                    <span className="text-gray-400">{item.connector_type}</span>
                  </span>
                  <span
                    className={`text-xs font-medium ${RISK_CLS[item.risk_level] ?? "text-gray-400"}`}
                  >
                    risk: {item.risk_level}
                  </span>
                </div>
                {/* notes */}
                <p className="text-sm leading-relaxed text-gray-400">
                  {item.notes}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}
