/** アプリの基準タイムゾーン。Backend の TIMEZONE と揃える。 */
export const APP_TIMEZONE = "Asia/Tokyo";

function jstDateKey(date: Date): string {
  // "YYYY-MM-DD" 形式。sv-SE ロケールは ISO 準拠の並びになる
  return date.toLocaleDateString("sv-SE", { timeZone: APP_TIMEZONE });
}

/** 一覧表示用: 「10/1(水) 18:00」 */
export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("ja-JP", {
    timeZone: APP_TIMEZONE,
    month: "numeric",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

/**
 * <input type="datetime-local"> 用の値に変換する。
 * 返すのはオフセット無しの JST 表記で、そのまま Backend に送ると
 * Backend 側で Asia/Tokyo として解釈される。
 */
export function toDatetimeLocalValue(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso)
    .toLocaleString("sv-SE", { timeZone: APP_TIMEZONE })
    .replace(" ", "T")
    .slice(0, 16);
}

export type DueState = "overdue" | "today" | "tomorrow" | "upcoming" | "none";

/** 期限の切迫度。一覧のバッジ色に使う。 */
export function dueState(iso: string | null): DueState {
  if (!iso) return "none";

  const due = new Date(iso);
  const now = new Date();
  if (due.getTime() < now.getTime()) return "overdue";

  const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
  const dueKey = jstDateKey(due);
  if (dueKey === jstDateKey(now)) return "today";
  if (dueKey === jstDateKey(tomorrow)) return "tomorrow";
  return "upcoming";
}

/** 所要時間（分）を「2時間30分」の形式にする。 */
export function formatDuration(minutes: number | null): string | null {
  if (!minutes) return null;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest}分`;
  if (rest === 0) return `${hours}時間`;
  return `${hours}時間${rest}分`;
}

/** 週の開始曜日（1 = 月曜）。 */
export const WEEK_STARTS_ON = 1;

/** "YYYY-MM-DD" 形式の日付キー。タイムゾーンの影響を受けない比較・加算に使う。 */
export type DateKey = string;

function keyToUtcDate(key: DateKey): Date {
  return new Date(`${key}T00:00:00Z`);
}

function utcDateToKey(date: Date): DateKey {
  return date.toISOString().slice(0, 10);
}

/** 今日（JST）の日付キー。 */
export function todayKey(): DateKey {
  return new Date().toLocaleDateString("sv-SE", { timeZone: APP_TIMEZONE });
}

export function addDays(key: DateKey, days: number): DateKey {
  const date = keyToUtcDate(key);
  date.setUTCDate(date.getUTCDate() + days);
  return utcDateToKey(date);
}

/** その日を含む週の初日（月曜）を返す。 */
export function startOfWeek(key: DateKey): DateKey {
  const weekday = keyToUtcDate(key).getUTCDay();
  const diff = (weekday - WEEK_STARTS_ON + 7) % 7;
  return addDays(key, -diff);
}

/** ISO日時を JST の「日付キー」と「0時からの分数」に分解する。 */
export function toJstSlot(iso: string): { dateKey: DateKey; minutes: number } {
  const [date, time] = new Date(iso)
    .toLocaleString("sv-SE", { timeZone: APP_TIMEZONE })
    .split(" ");
  const [hour, minute] = time.split(":").map(Number);
  return { dateKey: date, minutes: hour * 60 + minute };
}

/**
 * 日付キーと分数から、オフセット無しの日時文字列を作る。
 * Backend が Asia/Tokyo として解釈するため、フロントで変換しない。
 */
export function toNaiveDateTime(key: DateKey, minutes: number): string {
  const hour = Math.floor(minutes / 60);
  const minute = minutes % 60;
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${key}T${pad(hour)}:${pad(minute)}`;
}

/** 「14:00」形式。 */
export function formatTime(minutes: number): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(Math.floor(minutes / 60) % 24)}:${pad(minutes % 60)}`;
}

/** カレンダー見出し用の「9/21(月)」。 */
export function formatDayLabel(key: DateKey): string {
  return new Intl.DateTimeFormat("ja-JP", {
    timeZone: "UTC",
    month: "numeric",
    day: "numeric",
    weekday: "short",
  }).format(keyToUtcDate(key));
}

/** 週の範囲表示「2026年9月21日 - 27日」。 */
export function formatWeekRange(startKey: DateKey): string {
  const endKey = addDays(startKey, 6);
  const start = keyToUtcDate(startKey);
  const end = keyToUtcDate(endKey);
  const format = (date: Date, withYear: boolean) =>
    new Intl.DateTimeFormat("ja-JP", {
      timeZone: "UTC",
      year: withYear ? "numeric" : undefined,
      month: "numeric",
      day: "numeric",
    }).format(date);
  return `${format(start, true)} - ${format(end, start.getUTCMonth() !== end.getUTCMonth())}`;
}
