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
