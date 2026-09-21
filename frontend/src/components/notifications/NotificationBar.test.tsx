// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NotificationBar } from "@/components/notifications/NotificationBar";
import type { AppNotification } from "@/types/notification";

const fetchNotifications = vi.fn();
const markNotificationRead = vi.fn();

vi.mock("@/lib/notifications", () => ({
  fetchNotifications: () => fetchNotifications(),
  markNotificationRead: (id: number) => markNotificationRead(id),
}));

function makeNotification(overrides: Partial<AppNotification> = {}): AppNotification {
  return {
    id: 1,
    kind: "reminder",
    title: "まもなく開始: 面接",
    body: "14:00 から始まります。",
    read_at: null,
    created_at: "2026-09-21T13:40:00+09:00",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("NotificationBar", () => {
  it("通知が無ければ何も表示しない", async () => {
    fetchNotifications.mockResolvedValue([]);

    const { container } = render(<NotificationBar />);

    await waitFor(() => expect(fetchNotifications).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("通知の種類と内容を表示する", async () => {
    fetchNotifications.mockResolvedValue([makeNotification()]);

    render(<NotificationBar />);

    expect(await screen.findByText("まもなく開始: 面接")).toBeInTheDocument();
    expect(screen.getByText("リマインダー")).toBeInTheDocument();
    expect(screen.getByText("14:00 から始まります。")).toBeInTheDocument();
  });

  it("種類ごとに見出しを出し分ける", async () => {
    fetchNotifications.mockResolvedValue([
      makeNotification({ id: 1, kind: "daily_digest", title: "9/22 の予定" }),
      makeNotification({ id: 2, kind: "unfinished", title: "終わらなかった作業" }),
    ]);

    render(<NotificationBar />);

    expect(await screen.findByText("今日のまとめ")).toBeInTheDocument();
    expect(screen.getByText("やり残し")).toBeInTheDocument();
  });

  it("閉じると既読にして画面から消す", async () => {
    fetchNotifications.mockResolvedValue([makeNotification()]);
    markNotificationRead.mockResolvedValue(makeNotification({ read_at: "now" }));

    render(<NotificationBar />);
    await userEvent.click(await screen.findByLabelText("通知を閉じる"));

    await waitFor(() => expect(markNotificationRead).toHaveBeenCalledWith(1));
    expect(screen.queryByText("まもなく開始: 面接")).not.toBeInTheDocument();
  });

  it("取得に失敗しても画面を壊さない", async () => {
    fetchNotifications.mockRejectedValue(new Error("network"));

    const { container } = render(<NotificationBar />);

    await waitFor(() => expect(fetchNotifications).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
