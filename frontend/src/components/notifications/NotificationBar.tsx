"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchNotifications, markNotificationRead } from "@/lib/notifications";
import { NOTIFICATION_LABEL, type AppNotification } from "@/types/notification";

/** バックグラウンド処理が作った通知を取りに行く間隔。 */
const POLL_INTERVAL_MS = 60_000;

const KIND_CLASS: Record<AppNotification["kind"], string> = {
  reminder: "border-blue-300 bg-blue-50 dark:border-blue-900 dark:bg-blue-950",
  daily_digest:
    "border-emerald-300 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950",
  unfinished:
    "border-amber-300 bg-amber-50 dark:border-amber-900 dark:bg-amber-950",
};

export function NotificationBar() {
  const [notifications, setNotifications] = useState<AppNotification[]>([]);

  const load = useCallback(() => {
    fetchNotifications()
      .then(setNotifications)
      .catch(() => setNotifications([]));
  }, []);

  useEffect(() => {
    load();
    // 定期実行が作った通知に気づけるよう、一定間隔で取り直す
    const timer = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [load]);

  const dismiss = async (id: number) => {
    setNotifications((current) => current.filter((item) => item.id !== id));
    try {
      await markNotificationRead(id);
    } catch {
      load(); // 失敗したら表示を元に戻す
    }
  };

  if (notifications.length === 0) return null;

  return (
    <section className="mb-6 flex flex-col gap-2">
      {notifications.map((notification) => (
        <div
          key={notification.id}
          className={`flex items-start justify-between gap-4 rounded-lg border px-4 py-3 ${KIND_CLASS[notification.kind]}`}
        >
          <div className="min-w-0">
            <p className="text-sm font-medium">
              <span className="mr-2 text-[11px] text-muted">
                {NOTIFICATION_LABEL[notification.kind]}
              </span>
              {notification.title}
            </p>
            {notification.body && (
              <p className="mt-1 whitespace-pre-wrap text-xs text-muted">
                {notification.body}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={() => void dismiss(notification.id)}
            aria-label="通知を閉じる"
            className="shrink-0 rounded-md px-2 py-1 text-xs text-muted hover:bg-surface"
          >
            閉じる
          </button>
        </div>
      ))}
    </section>
  );
}
