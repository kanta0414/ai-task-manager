import { apiFetch } from "@/lib/api";
import type { DateKey } from "@/lib/datetime";
import { addDays, toNaiveDateTime } from "@/lib/datetime";
import type {
  CalendarEvent,
  EventCreateInput,
  EventUpdateInput,
} from "@/types/event";

/** 指定週（開始日から7日間）に重なる予定を取得する。 */
export function fetchWeekEvents(weekStart: DateKey): Promise<CalendarEvent[]> {
  const params = new URLSearchParams({
    from: toNaiveDateTime(weekStart, 0),
    to: toNaiveDateTime(addDays(weekStart, 7), 0),
  });
  return apiFetch<CalendarEvent[]>(`/events?${params.toString()}`);
}

export function createEvent(input: EventCreateInput): Promise<CalendarEvent> {
  return apiFetch<CalendarEvent>("/events", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateEvent(id: number, input: EventUpdateInput): Promise<CalendarEvent> {
  return apiFetch<CalendarEvent>(`/events/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteEvent(id: number): Promise<void> {
  return apiFetch<void>(`/events/${id}`, { method: "DELETE" });
}
