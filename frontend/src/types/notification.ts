export type NotificationKind = "reminder" | "daily_digest" | "unfinished";

export type AppNotification = {
  id: number;
  kind: NotificationKind;
  title: string;
  body: string | null;
  read_at: string | null;
  created_at: string;
};

export const NOTIFICATION_LABEL: Record<NotificationKind, string> = {
  reminder: "リマインダー",
  daily_digest: "今日のまとめ",
  unfinished: "やり残し",
};
