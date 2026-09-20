import { toJstSlot, type DateKey } from "@/lib/datetime";
import type { CalendarEvent } from "@/types/event";

export const DAY_MINUTES = 24 * 60;
/** 短い予定でもタイトルが読めるようにする最小の表示高さ（分換算）。 */
const MIN_VISIBLE_MINUTES = 20;

export type PositionedEvent = {
  event: CalendarEvent;
  /** その日の0時からの分数（日をまたぐ予定は日の端で切り詰める） */
  startMinutes: number;
  endMinutes: number;
  /** 重なっている予定を横に並べるための位置 */
  column: number;
  columns: number;
};

/**
 * 1日分の予定を、重なりを考慮した配置情報に変換する。
 * 日をまたぐ予定は、その日に見えている部分だけを返す。
 */
export function layoutDay(
  events: CalendarEvent[],
  dayKey: DateKey,
): PositionedEvent[] {
  const visible: PositionedEvent[] = [];

  for (const event of events) {
    const start = toJstSlot(event.start_at);
    const end = toJstSlot(event.end_at);

    let startMinutes: number;
    if (start.dateKey === dayKey) startMinutes = start.minutes;
    else if (start.dateKey < dayKey) startMinutes = 0;
    else continue;

    let endMinutes: number;
    if (end.dateKey === dayKey) endMinutes = end.minutes;
    else if (end.dateKey > dayKey) endMinutes = DAY_MINUTES;
    else continue;

    if (endMinutes <= startMinutes) continue;

    visible.push({
      event,
      startMinutes,
      endMinutes: Math.min(
        DAY_MINUTES,
        Math.max(endMinutes, startMinutes + MIN_VISIBLE_MINUTES),
      ),
      column: 0,
      columns: 1,
    });
  }

  visible.sort(
    (a, b) => a.startMinutes - b.startMinutes || a.endMinutes - b.endMinutes,
  );

  // 重なり合う予定をまとまり（cluster）ごとに分け、その中で列を割り当てる
  let cluster: PositionedEvent[] = [];
  let clusterEnd = -1;

  const flush = () => {
    const columns = Math.max(...cluster.map((item) => item.column + 1), 1);
    cluster.forEach((item) => {
      item.columns = columns;
    });
    cluster = [];
    clusterEnd = -1;
  };

  for (const item of visible) {
    if (cluster.length > 0 && item.startMinutes >= clusterEnd) flush();

    const columnEnds: number[] = [];
    cluster.forEach((placed) => {
      columnEnds[placed.column] = Math.max(
        columnEnds[placed.column] ?? 0,
        placed.endMinutes,
      );
    });

    let column = 0;
    while ((columnEnds[column] ?? 0) > item.startMinutes) column += 1;
    item.column = column;

    cluster.push(item);
    clusterEnd = Math.max(clusterEnd, item.endMinutes);
  }
  if (cluster.length > 0) flush();

  return visible;
}
