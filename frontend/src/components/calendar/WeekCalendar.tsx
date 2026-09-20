"use client";

import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";

import { EventForm } from "@/components/calendar/EventForm";
import { DAY_MINUTES, layoutDay, type PositionedEvent } from "@/lib/calendarLayout";
import {
  addDays,
  formatDayLabel,
  formatTime,
  formatWeekRange,
  toJstSlot,
  toNaiveDateTime,
  todayKey,
} from "@/lib/datetime";
import { useEvents } from "@/store/EventsProvider";
import type { CalendarEvent } from "@/types/event";

const HOUR_HEIGHT = 44;
/** ドラッグ移動時に吸着させる単位（分）。 */
const SNAP_MINUTES = 15;
const HOURS = Array.from({ length: 24 }, (_, hour) => hour);

type DragState = {
  eventId: number;
  dayIndex: number;
  startMinutes: number;
  durationMinutes: number;
  pointerStartX: number;
  pointerStartY: number;
  deltaMinutes: number;
  deltaDays: number;
  moved: boolean;
  /** ドラッグ開始時に測った1日分の列幅。レンダー中に ref を読まないため保持する */
  columnWidth: number;
};

export function WeekCalendar() {
  const {
    events,
    weekStart,
    loading,
    error,
    shiftWeek,
    goToToday,
    addEvent,
    editEvent,
    removeEvent,
  } = useEvents();

  const days = useMemo(
    () => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)),
    [weekStart],
  );

  const [creating, setCreating] = useState<{ start: string; end: string } | null>(null);
  const [editing, setEditing] = useState<CalendarEvent | null>(null);
  const [now, setNow] = useState<{ dateKey: string; minutes: number } | null>(null);
  const [preview, setPreview] = useState<DragState | null>(null);

  const dragRef = useRef<DragState | null>(null);
  const columnsRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 最初の表示位置を朝7時にする（0時始まりだと空白ばかり見えるため）
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 7 * HOUR_HEIGHT;
  }, []);

  // 現在時刻の線
  useEffect(() => {
    const update = () => setNow(toJstSlot(new Date().toISOString()));
    update();
    const timer = setInterval(update, 60_000);
    return () => clearInterval(timer);
  }, []);

  const openCreate = (dayKey: string, minutes: number) => {
    setCreating({
      start: toNaiveDateTime(dayKey, minutes),
      end: toNaiveDateTime(dayKey, Math.min(minutes + 60, DAY_MINUTES)),
    });
  };

  const handlePointerDown = (
    pointerEvent: PointerEvent<HTMLDivElement>,
    positioned: PositionedEvent,
    dayIndex: number,
  ) => {
    const { event } = positioned;
    const start = toJstSlot(event.start_at);
    const end = toJstSlot(event.end_at);

    // 日をまたぐ予定はドラッグ対象外（クリックで編集フォームを開く）
    if (start.dateKey !== end.dateKey) {
      setEditing(event);
      return;
    }

    pointerEvent.preventDefault();
    const columnWidth = (columnsRef.current?.clientWidth ?? 0) / 7;
    const state: DragState = {
      eventId: event.id,
      dayIndex,
      startMinutes: start.minutes,
      durationMinutes: end.minutes - start.minutes,
      pointerStartX: pointerEvent.clientX,
      pointerStartY: pointerEvent.clientY,
      deltaMinutes: 0,
      deltaDays: 0,
      moved: false,
      columnWidth,
    };
    dragRef.current = state;
    setPreview(state);


    const onMove = (moveEvent: globalThis.PointerEvent) => {
      const current = dragRef.current;
      if (!current) return;

      const dx = moveEvent.clientX - current.pointerStartX;
      const dy = moveEvent.clientY - current.pointerStartY;
      const next: DragState = {
        ...current,
        deltaMinutes:
          Math.round((dy / HOUR_HEIGHT) * 60 / SNAP_MINUTES) * SNAP_MINUTES,
        deltaDays: columnWidth ? Math.round(dx / columnWidth) : 0,
        moved: current.moved || Math.abs(dx) > 3 || Math.abs(dy) > 3,
      };
      dragRef.current = next;
      setPreview(next);
    };

    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);

      const current = dragRef.current;
      dragRef.current = null;
      setPreview(null);
      if (!current) return;

      if (!current.moved) {
        setEditing(event);
        return;
      }

      const dayIndexAfter = Math.min(
        6,
        Math.max(0, current.dayIndex + current.deltaDays),
      );
      const startAfter = Math.min(
        DAY_MINUTES - current.durationMinutes,
        Math.max(0, current.startMinutes + current.deltaMinutes),
      );
      if (
        dayIndexAfter === current.dayIndex &&
        startAfter === current.startMinutes
      ) {
        return;
      }

      const dayKey = addDays(weekStart, dayIndexAfter);
      void editEvent(current.eventId, {
        start_at: toNaiveDateTime(dayKey, startAfter),
        end_at: toNaiveDateTime(dayKey, startAfter + current.durationMinutes),
      });
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const today = todayKey();

  return (
    <section className="flex min-w-0 flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          カレンダー
          <span className="ml-2 text-sm font-normal text-muted">
            {formatWeekRange(weekStart)}
          </span>
        </h2>
        <div className="flex items-center gap-1 text-sm">
          <button
            type="button"
            onClick={() => shiftWeek(-1)}
            aria-label="前の週"
            className="rounded-md border border-border px-2 py-1 hover:bg-background"
          >
            ←
          </button>
          <button
            type="button"
            onClick={goToToday}
            className="rounded-md border border-border px-3 py-1 hover:bg-background"
          >
            今週
          </button>
          <button
            type="button"
            onClick={() => shiftWeek(1)}
            aria-label="次の週"
            className="rounded-md border border-border px-2 py-1 hover:bg-background"
          >
            →
          </button>
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      <div
        ref={scrollRef}
        className="max-h-[70vh] overflow-y-auto rounded-lg border border-border bg-surface"
      >
        <div className="sticky top-0 z-20 flex border-b border-border bg-surface">
          <div className="w-12 shrink-0" />
          <div className="grid flex-1 grid-cols-7">
            {days.map((day) => (
              <div
                key={day}
                className={`border-l border-border py-2 text-center text-xs ${
                  day === today ? "font-semibold text-accent" : "text-muted"
                }`}
              >
                {formatDayLabel(day)}
              </div>
            ))}
          </div>
        </div>

        <div className="flex">
          <div className="w-12 shrink-0">
            {HOURS.map((hour) => (
              <div
                key={hour}
                style={{ height: HOUR_HEIGHT }}
                className="pr-1 text-right text-[10px] text-muted"
              >
                {hour}:00
              </div>
            ))}
          </div>

          <div ref={columnsRef} className="grid flex-1 grid-cols-7">
            {days.map((day, dayIndex) => (
              <div key={day} className="relative border-l border-border">
                {HOURS.map((hour) => (
                  <button
                    key={hour}
                    type="button"
                    onClick={() => openCreate(day, hour * 60)}
                    aria-label={`${formatDayLabel(day)} ${hour}:00 に予定を追加`}
                    style={{ height: HOUR_HEIGHT }}
                    className="block w-full border-b border-border/60 hover:bg-accent/10"
                  />
                ))}

                {layoutDay(events, day).map((positioned) => {
                  const dragging = preview?.eventId === positioned.event.id;
                  const width = 100 / positioned.columns;
                  return (
                    <div
                      key={positioned.event.id}
                      onPointerDown={(pointerEvent) =>
                        handlePointerDown(pointerEvent, positioned, dayIndex)
                      }
                      style={{
                        top: (positioned.startMinutes / 60) * HOUR_HEIGHT,
                        height:
                          ((positioned.endMinutes - positioned.startMinutes) / 60) *
                          HOUR_HEIGHT,
                        left: `${positioned.column * width}%`,
                        width: `calc(${width}% - 2px)`,
                        transform: dragging
                          ? `translate(${
                              (preview?.deltaDays ?? 0) * (preview?.columnWidth ?? 0)
                            }px, ${
                              ((preview?.deltaMinutes ?? 0) / 60) * HOUR_HEIGHT
                            }px)`
                          : undefined,
                      }}
                      className={`absolute z-10 cursor-grab overflow-hidden rounded border-l-2 px-1 py-0.5 text-[10px] leading-tight select-none ${
                        positioned.event.task_id
                          ? "border-emerald-500 bg-emerald-500/15"
                          : "border-accent bg-accent/15"
                      } ${dragging ? "z-30 opacity-80 shadow-lg" : ""}`}
                    >
                      <p className="truncate font-medium">{positioned.event.title}</p>
                      <p className="truncate text-muted">
                        {formatTime(positioned.startMinutes)}–
                        {formatTime(positioned.endMinutes)}
                      </p>
                    </div>
                  );
                })}

                {now?.dateKey === day && (
                  <div
                    aria-hidden
                    style={{ top: (now.minutes / 60) * HOUR_HEIGHT }}
                    className="pointer-events-none absolute left-0 right-0 z-20 border-t border-red-500"
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {loading && <p className="text-center text-xs text-muted">読み込み中...</p>}

      {creating && (
        <EventForm
          defaultStart={creating.start}
          defaultEnd={creating.end}
          onSubmit={addEvent}
          onClose={() => setCreating(null)}
        />
      )}

      {editing && (
        <EventForm
          event={editing}
          onSubmit={(input) => editEvent(editing.id, input)}
          onDelete={() => removeEvent(editing.id)}
          onClose={() => setEditing(null)}
        />
      )}
    </section>
  );
}
