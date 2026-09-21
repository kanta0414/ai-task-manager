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

/** 外部カレンダーで埋まっている時間帯（画面に重ねて表示するため）。 */
export function fetchExternalBusy(
  fromNaive: string,
  toNaive: string,
): Promise<{ count: number; intervals: { start_at: string; end_at: string }[] }> {
  const params = new URLSearchParams({ from: fromNaive, to: toNaive });
  return apiFetch(`/integrations/busy?${params.toString()}`);
}
