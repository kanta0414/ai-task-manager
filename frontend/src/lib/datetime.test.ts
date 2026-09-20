import { afterEach, describe, expect, it, vi } from "vitest";

import {
  addDays,
  dueState,
  formatDuration,
  formatTime,
  startOfWeek,
  toDatetimeLocalValue,
  toJstSlot,
  toNaiveDateTime,
  todayKey,
} from "@/lib/datetime";

describe("toJstSlot", () => {
  it("UTC表記の日時を JST の日付と分に変換する", () => {
    // 2026-09-21T05:00Z = JST 14:00
    expect(toJstSlot("2026-09-21T05:00:00Z")).toEqual({
      dateKey: "2026-09-21",
      minutes: 14 * 60,
    });
  });

  it("JST の日付が UTC と異なる時刻でも正しく判定する", () => {
    // 2026-09-21T16:00Z = JST 翌日の 01:00
    expect(toJstSlot("2026-09-21T16:00:00Z")).toEqual({
      dateKey: "2026-09-22",
      minutes: 60,
    });
  });

  it("オフセット付きの表記をそのまま解釈する", () => {
    expect(toJstSlot("2026-09-21T14:30:00+09:00")).toEqual({
      dateKey: "2026-09-21",
      minutes: 14 * 60 + 30,
    });
  });
});

describe("toDatetimeLocalValue", () => {
  it("ISO日時を datetime-local 用の JST 表記にする", () => {
    expect(toDatetimeLocalValue("2026-09-21T14:00:00+09:00")).toBe(
      "2026-09-21T14:00",
    );
  });

  it("UTC表記でも JST に直して返す", () => {
    expect(toDatetimeLocalValue("2026-09-21T05:00:00Z")).toBe("2026-09-21T14:00");
  });

  it("null は空文字にする", () => {
    expect(toDatetimeLocalValue(null)).toBe("");
  });
});

describe("toNaiveDateTime", () => {
  it("ゼロ埋めした日時文字列を作る", () => {
    expect(toNaiveDateTime("2026-09-21", 9 * 60 + 5)).toBe("2026-09-21T09:05");
  });

  it("0時は 00:00 になる", () => {
    expect(toNaiveDateTime("2026-09-21", 0)).toBe("2026-09-21T00:00");
  });
});

describe("startOfWeek", () => {
  it("月曜はその日自身を返す", () => {
    expect(startOfWeek("2026-09-21")).toBe("2026-09-21");
  });

  it("日曜はその週の月曜（6日前）を返す", () => {
    expect(startOfWeek("2026-09-27")).toBe("2026-09-21");
  });

  it("月をまたぐ週でも正しく求める", () => {
    expect(startOfWeek("2026-10-01")).toBe("2026-09-28");
  });
});

describe("addDays", () => {
  it("月をまたいで加算できる", () => {
    expect(addDays("2026-09-30", 1)).toBe("2026-10-01");
  });

  it("負の日数で戻れる", () => {
    expect(addDays("2026-10-01", -1)).toBe("2026-09-30");
  });

  it("うるう年の2月末を扱える", () => {
    expect(addDays("2028-02-28", 1)).toBe("2028-02-29");
  });
});

describe("formatTime", () => {
  it("分数を HH:MM にする", () => {
    expect(formatTime(0)).toBe("00:00");
    expect(formatTime(9 * 60 + 5)).toBe("09:05");
    expect(formatTime(23 * 60 + 59)).toBe("23:59");
  });

  it("24:00 は 00:00 として扱う（日の終わりの表示）", () => {
    expect(formatTime(24 * 60)).toBe("00:00");
  });
});

describe("dueState", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  const freezeAt = (iso: string) => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(iso));
  };

  it("期限なしは none", () => {
    expect(dueState(null)).toBe("none");
  });

  it("過去の期限は overdue", () => {
    freezeAt("2026-09-21T09:00:00+09:00");
    expect(dueState("2026-09-19T10:00:00+09:00")).toBe("overdue");
  });

  it("同じ日の未来は today", () => {
    freezeAt("2026-09-21T09:00:00+09:00");
    expect(dueState("2026-09-21T18:00:00+09:00")).toBe("today");
  });

  it("翌日は tomorrow", () => {
    freezeAt("2026-09-21T09:00:00+09:00");
    expect(dueState("2026-09-22T10:00:00+09:00")).toBe("tomorrow");
  });

  it("それ以降は upcoming", () => {
    freezeAt("2026-09-21T09:00:00+09:00");
    expect(dueState("2026-09-30T10:00:00+09:00")).toBe("upcoming");
  });

  it("JSTの日付で判定する（UTCでは前日になる深夜も today）", () => {
    // JST 2026-09-21 23:00 = UTC 14:00。期限 JST 23:30 は「今日」
    freezeAt("2026-09-21T23:00:00+09:00");
    expect(dueState("2026-09-21T23:30:00+09:00")).toBe("today");
  });
});

describe("todayKey", () => {
  it("JST の日付を返す（UTCの日付とずれる時刻でも）", () => {
    vi.useFakeTimers();
    // UTC では 2026-09-20、JST では 2026-09-21
    vi.setSystemTime(new Date("2026-09-20T16:00:00Z"));
    expect(todayKey()).toBe("2026-09-21");
    vi.useRealTimers();
  });
});

describe("formatDuration", () => {
  it("分だけ・時間だけ・時間と分を出し分ける", () => {
    expect(formatDuration(45)).toBe("45分");
    expect(formatDuration(120)).toBe("2時間");
    expect(formatDuration(90)).toBe("1時間30分");
  });

  it("未設定は null", () => {
    expect(formatDuration(null)).toBeNull();
  });
});
