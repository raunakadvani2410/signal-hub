/**
 * Integration registry types.
 * Mirrors packages/shared/python/signal_hub_shared/integrations.py.
 */

import { z } from "zod";

export const IntegrationStatus = z.enum([
  "official",
  "official_constrained",
  "third_party_experimental",
  "local_only_experimental",
]);
export type IntegrationStatus = z.infer<typeof IntegrationStatus>;

export const ConnectorType = z.enum([
  "oauth2",
  "api_key",
  "vendor_connector",
  "local_file",
]);
export type ConnectorType = z.infer<typeof ConnectorType>;

export const RiskLevel = z.enum(["low", "medium", "high"]);
export type RiskLevel = z.infer<typeof RiskLevel>;

export const IntegrationConfigSchema = z.object({
  integration_key: z.string(),
  display_name: z.string(),
  status: IntegrationStatus,
  connector_type: ConnectorType,
  risk_level: RiskLevel,
  official_api_available: z.boolean(),
  notes: z.string(),
});
export type IntegrationConfig = z.infer<typeof IntegrationConfigSchema>;
