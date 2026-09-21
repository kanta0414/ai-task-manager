// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CalendarIntegration } from "@/components/integrations/CalendarIntegration";

const fetchIntegrations = vi.fn();
const fetchGoogleAuthorizeUrl = vi.fn();
const disconnectGoogle = vi.fn();

vi.mock("@/lib/integrations", () => ({
  fetchIntegrations: () => fetchIntegrations(),
  fetchGoogleAuthorizeUrl: () => fetchGoogleAuthorizeUrl(),
  disconnectGoogle: () => disconnectGoogle(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState({}, "", "/");
});

const base = {
  google_available: true,
  google_connected: false,
  google_account_email: null,
  google_needs_reauth: false,
};

describe("CalendarIntegration", () => {
  it("認証情報が未設定なら何も表示しない", async () => {
    fetchIntegrations.mockResolvedValue({ ...base, google_available: false });

    const { container } = render(<CalendarIntegration />);

    await waitFor(() => expect(fetchIntegrations).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("未連携なら連携ボタンを出す", async () => {
    fetchIntegrations.mockResolvedValue(base);

    render(<CalendarIntegration />);

    expect(await screen.findByText("連携する")).toBeInTheDocument();
  });

  it("連携中はアカウントと解除ボタンを出す", async () => {
    fetchIntegrations.mockResolvedValue({
      ...base,
      google_connected: true,
      google_account_email: "me@gmail.com",
    });

    render(<CalendarIntegration />);

    expect(await screen.findByText(/me@gmail.com/)).toBeInTheDocument();
    expect(screen.getByText("解除")).toBeInTheDocument();
  });

  it("連携が切れていたら、つなぎ直しを促す", async () => {
    fetchIntegrations.mockResolvedValue({
      ...base,
      google_connected: true,
      google_account_email: "me@gmail.com",
      google_needs_reauth: true,
    });

    render(<CalendarIntegration />);

    expect(await screen.findByText(/連携が切れました/)).toBeInTheDocument();
    expect(screen.getByText("つなぎ直す")).toBeInTheDocument();
  });

  it("解除すると状況を取り直す", async () => {
    fetchIntegrations.mockResolvedValue({
      ...base,
      google_connected: true,
      google_account_email: "me@gmail.com",
    });
    disconnectGoogle.mockResolvedValue(undefined);

    render(<CalendarIntegration />);
    await userEvent.click(await screen.findByText("解除"));

    await waitFor(() => expect(disconnectGoogle).toHaveBeenCalledOnce());
    expect(await screen.findByText("連携を解除しました。")).toBeInTheDocument();
  });

  it("連携から戻ってきた直後は結果を伝え、URL の目印を消す", async () => {
    fetchIntegrations.mockResolvedValue({
      ...base,
      google_connected: true,
      google_account_email: "me@gmail.com",
    });
    window.history.replaceState({}, "", "/?google=connected");

    render(<CalendarIntegration />);

    expect(
      await screen.findByText("Google カレンダーと連携しました。"),
    ).toBeInTheDocument();
    expect(window.location.search).toBe("");
  });

  it("失敗して戻ってきた場合も伝える", async () => {
    fetchIntegrations.mockResolvedValue(base);
    window.history.replaceState({}, "", "/?google=failed");

    render(<CalendarIntegration />);

    expect(await screen.findByText(/連携に失敗しました/)).toBeInTheDocument();
  });
});
