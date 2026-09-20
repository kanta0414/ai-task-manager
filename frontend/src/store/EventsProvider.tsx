"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { startOfWeek, todayKey, type DateKey } from "@/lib/datetime";
import {
  createEvent,
  deleteEvent,
  fetchWeekEvents,
  updateEvent,
} from "@/lib/events";
import type {
  CalendarEvent,
  EventCreateInput,
  EventUpdateInput,
} from "@/types/event";

type EventsContextValue = {
  events: CalendarEvent[];
  weekStart: DateKey;
  loading: boolean;
  error: string | null;
  shiftWeek: (weeks: number) => void;
  goToToday: () => void;
  refresh: () => void;
  addEvent: (input: EventCreateInput) => Promise<void>;
  editEvent: (id: number, input: EventUpdateInput) => Promise<void>;
  removeEvent: (id: number) => Promise<void>;
};

const EventsContext = createContext<EventsContextValue | null>(null);

/**
 * 表示中の週と、その週の予定を管理する。
 * Phase 5 以降、AI が作成・変更した予定も refresh() でこの状態へ反映する。
 */
export function EventsProvider({ children }: { children: ReactNode }) {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [weekStart, setWeekStart] = useState<DateKey>(() => startOfWeek(todayKey()));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // 週の変更以外（作成・更新・削除・手動更新）で再取得するためのトークン
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let active = true;

    fetchWeekEvents(weekStart)
      .then((result) => {
        if (!active) return;
        setEvents(result);
        setError(null);
      })
      .catch(() => {
        if (!active) return;
        setError("予定を取得できませんでした。Backend が起動しているか確認してください。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    // 週を素早く切り替えたとき、古い応答で上書きしない
    return () => {
      active = false;
    };
  }, [weekStart, reloadToken]);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  const run = useCallback(
    async (action: () => Promise<unknown>, failureMessage: string) => {
      setLoading(true);
      try {
        await action();
      } catch {
        setError(failureMessage);
      } finally {
        // 失敗した操作の見た目が残らないよう、成否に関わらずサーバーの状態へ同期する
        reload();
      }
    },
    [reload],
  );

  const value = useMemo<EventsContextValue>(
    () => ({
      events,
      weekStart,
      loading,
      error,
      shiftWeek: (weeks) => {
        setLoading(true);
        setWeekStart((current) => {
          const date = new Date(`${current}T00:00:00Z`);
          date.setUTCDate(date.getUTCDate() + weeks * 7);
          return date.toISOString().slice(0, 10);
        });
      },
      goToToday: () => {
        setLoading(true);
        setWeekStart(startOfWeek(todayKey()));
      },
      refresh: reload,
      addEvent: (input) =>
        run(() => createEvent(input), "予定を作成できませんでした。"),
      editEvent: (id, input) =>
        run(() => updateEvent(id, input), "予定を変更できませんでした。"),
      removeEvent: (id) =>
        run(() => deleteEvent(id), "予定を削除できませんでした。"),
    }),
    [events, weekStart, loading, error, reload, run],
  );

  return <EventsContext.Provider value={value}>{children}</EventsContext.Provider>;
}

export function useEvents(): EventsContextValue {
  const context = useContext(EventsContext);
  if (!context) {
    throw new Error("useEvents は EventsProvider の内側で使用してください");
  }
  return context;
}
