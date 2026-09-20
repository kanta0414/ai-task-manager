import { describe, expect, it } from "vitest";

import { layoutDay } from "@/lib/calendarLayout";
import type { CalendarEvent } from "@/types/event";

let nextId = 1;

function event(title: string, startAt: string, endAt: string): CalendarEvent {
  return {
    id: nextId++,
    title,
    description: null,
    start_at: startAt,
    end_at: endAt,
    location: null,
    task_id: null,
    created_at: startAt,
    updated_at: startAt,
  };
}

describe("layoutDay", () => {
  it("同じ日の予定を0時からの分数に変換する", () => {
    const events = [
      event("面接", "2026-09-21T09:00:00+09:00", "2026-09-21T10:00:00+09:00"),
    ];

    const [positioned] = layoutDay(events, "2026-09-21");
    expect(positioned.startMinutes).toBe(9 * 60);
    expect(positioned.endMinutes).toBe(10 * 60);
    expect(positioned.columns).toBe(1);
    expect(positioned.column).toBe(0);
  });

  it("別の日の予定は含めない", () => {
    const events = [
      event("面接", "2026-09-21T09:00:00+09:00", "2026-09-21T10:00:00+09:00"),
    ];
    expect(layoutDay(events, "2026-09-22")).toHaveLength(0);
  });

  it("日をまたぐ予定を初日は日の終わりまでで切る", () => {
    const events = [
      event("夜間作業", "2026-09-25T23:00:00+09:00", "2026-09-26T01:00:00+09:00"),
    ];

    const [first] = layoutDay(events, "2026-09-25");
    expect(first.startMinutes).toBe(23 * 60);
    expect(first.endMinutes).toBe(24 * 60);
  });

  it("日をまたぐ予定を翌日は0時からで表示する", () => {
    const events = [
      event("夜間作業", "2026-09-25T23:00:00+09:00", "2026-09-26T01:00:00+09:00"),
    ];

    const [second] = layoutDay(events, "2026-09-26");
    expect(second.startMinutes).toBe(0);
    expect(second.endMinutes).toBe(60);
  });

  it("ちょうど24時に終わる予定は翌日に現れない", () => {
    const events = [
      event("深夜まで", "2026-09-25T22:00:00+09:00", "2026-09-26T00:00:00+09:00"),
    ];

    expect(layoutDay(events, "2026-09-25")).toHaveLength(1);
    expect(layoutDay(events, "2026-09-26")).toHaveLength(0);
  });

  it("重なり合う予定に別々の列を割り当てる", () => {
    const events = [
      event("企業研究", "2026-09-21T13:00:00+09:00", "2026-09-21T15:00:00+09:00"),
      event("OB訪問", "2026-09-21T14:00:00+09:00", "2026-09-21T16:00:00+09:00"),
    ];

    const positioned = layoutDay(events, "2026-09-21");
    expect(positioned.map((item) => item.column)).toEqual([0, 1]);
    expect(positioned.every((item) => item.columns === 2)).toBe(true);
  });

  it("重ならない予定は全幅で表示する", () => {
    const events = [
      event("朝", "2026-09-21T09:00:00+09:00", "2026-09-21T10:00:00+09:00"),
      event("昼", "2026-09-21T11:00:00+09:00", "2026-09-21T12:00:00+09:00"),
    ];

    const positioned = layoutDay(events, "2026-09-21");
    expect(positioned.every((item) => item.columns === 1)).toBe(true);
  });

  it("3件重なれば3列に分ける", () => {
    const events = [
      event("A", "2026-09-21T13:00:00+09:00", "2026-09-21T16:00:00+09:00"),
      event("B", "2026-09-21T14:00:00+09:00", "2026-09-21T15:00:00+09:00"),
      event("C", "2026-09-21T14:30:00+09:00", "2026-09-21T15:30:00+09:00"),
    ];

    const positioned = layoutDay(events, "2026-09-21");
    expect(positioned.map((item) => item.column)).toEqual([0, 1, 2]);
    expect(positioned.every((item) => item.columns === 3)).toBe(true);
  });

  it("終わった予定の列を再利用する", () => {
    // A(9:00-10:00) と C(10:30-12:00) は重ならないので同じ列を使える
    const events = [
      event("A", "2026-09-21T09:00:00+09:00", "2026-09-21T10:00:00+09:00"),
      event("B", "2026-09-21T09:30:00+09:00", "2026-09-21T11:00:00+09:00"),
      event("C", "2026-09-21T10:30:00+09:00", "2026-09-21T12:00:00+09:00"),
    ];

    const positioned = layoutDay(events, "2026-09-21");
    expect(positioned.map((item) => item.column)).toEqual([0, 1, 0]);
    expect(positioned.every((item) => item.columns === 2)).toBe(true);
  });

  it("短い予定にも読める高さを確保する", () => {
    const events = [
      event("5分だけ", "2026-09-21T09:00:00+09:00", "2026-09-21T09:05:00+09:00"),
    ];

    const [positioned] = layoutDay(events, "2026-09-21");
    expect(positioned.endMinutes - positioned.startMinutes).toBeGreaterThanOrEqual(20);
  });

  it("開始時刻の早い順に返す", () => {
    const events = [
      event("後", "2026-09-21T15:00:00+09:00", "2026-09-21T16:00:00+09:00"),
      event("先", "2026-09-21T09:00:00+09:00", "2026-09-21T10:00:00+09:00"),
    ];

    expect(layoutDay(events, "2026-09-21").map((item) => item.event.title)).toEqual([
      "先",
      "後",
    ]);
  });
});
