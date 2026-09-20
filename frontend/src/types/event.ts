/** FastAPI の EventRead に対応する。 */
export type CalendarEvent = {
  id: number;
  title: string;
  description: string | null;
  /** ISO8601（オフセット付き） */
  start_at: string;
  end_at: string;
  location: string | null;
  task_id: number | null;
  created_at: string;
  updated_at: string;
};

/** 作成時の入力。Backend の EventCreate に対応する。 */
export type EventCreateInput = {
  title: string;
  description?: string | null;
  /** "2026-09-21T14:00" のようなオフセット無しの値を送ると Backend が Asia/Tokyo として解釈する */
  start_at: string;
  end_at: string;
  location?: string | null;
  task_id?: number | null;
};

/** 部分更新の入力。Backend の EventUpdate に対応する（ドラッグ移動は時間だけを送る）。 */
export type EventUpdateInput = Partial<EventCreateInput>;
