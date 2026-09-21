import { apiFetch } from "@/lib/api";
import type { AppNotification } from "@/types/notification";

export function fetchNotifications(unreadOnly = true): Promise<AppNotification[]> {
  return apiFetch<AppNotification[]>(
    `/notifications?unread_only=${unreadOnly}`,
  );
}

export function markNotificationRead(id: number): Promise<AppNotification> {
  return apiFetch<AppNotification>(`/notifications/${id}/read`, {
    method: "POST",
  });
}
