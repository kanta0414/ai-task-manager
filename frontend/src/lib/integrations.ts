import { apiFetch } from "@/lib/api";
import type { IntegrationStatus } from "@/types/integration";

export function fetchIntegrations(): Promise<IntegrationStatus> {
  return apiFetch<IntegrationStatus>("/integrations");
}

export function fetchGoogleAuthorizeUrl(): Promise<{ url: string }> {
  return apiFetch<{ url: string }>("/integrations/google/authorize");
}

export function disconnectGoogle(): Promise<void> {
  return apiFetch<void>("/integrations/google", { method: "DELETE" });
}
