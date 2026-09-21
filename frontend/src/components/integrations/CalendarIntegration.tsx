"use client";

import { useCallback, useEffect, useState } from "react";

import {
  disconnectGoogle,
  fetchGoogleAuthorizeUrl,
  fetchIntegrations,
} from "@/lib/integrations";
import type { IntegrationStatus } from "@/types/integration";

/** 連携直後の戻り先に付く目印。 */
const RESULT_MESSAGE: Record<string, string> = {
  connected: "Google カレンダーと連携しました。",
  failed: "連携に失敗しました。もう一度お試しください。",
  invalid_state: "連携の手続きが無効でした。最初からやり直してください。",
};

export function CalendarIntegration() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  const load = useCallback(() => {
    fetchIntegrations()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  useEffect(() => {
    load();

    // 連携から戻ってきた直後は結果を伝え、URL からは目印を消す。
    // 初回マウント時に一度読むだけで、再レンダーの連鎖は起きない。
    const params = new URLSearchParams(window.location.search);
    const outcome = params.get("google");
    if (outcome && RESULT_MESSAGE[outcome]) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- URLの読み取りは初回1回だけ
      setResult(RESULT_MESSAGE[outcome]);
      params.delete("google");
      const query = params.toString();
      window.history.replaceState(
        {},
        "",
        window.location.pathname + (query ? `?${query}` : ""),
      );
    }
  }, [load]);

  // 認証情報が未設定のときは機能自体を出さない
  if (!status?.google_available) return null;

  const connect = async () => {
    setWorking(true);
    try {
      const { url } = await fetchGoogleAuthorizeUrl();
      window.location.href = url;
    } catch {
      setResult("連携を開始できませんでした。");
      setWorking(false);
    }
  };

  const disconnect = async () => {
    setWorking(true);
    try {
      await disconnectGoogle();
      setResult("連携を解除しました。");
      load();
    } catch {
      setResult("解除に失敗しました。");
    } finally {
      setWorking(false);
    }
  };

  return (
    <section className="mb-6 flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3 text-xs">
      <span className="font-medium">Google カレンダー</span>
      {status.google_connected ? (
        <>
          {status.google_needs_reauth ? (
            <span className="text-amber-700 dark:text-amber-300">
              連携が切れました（{status.google_account_email}）。
              つなぎ直すまで Google の予定は考慮されません
            </span>
          ) : (
            <span className="text-muted">
              連携中: {status.google_account_email}（空き時間の計算に反映されます）
            </span>
          )}
          {status.google_needs_reauth && (
            <button
              type="button"
              onClick={() => void connect()}
              disabled={working}
              className="rounded-md bg-accent px-3 py-1 font-medium text-white disabled:opacity-50"
            >
              つなぎ直す
            </button>
          )}
          <button
            type="button"
            onClick={() => void disconnect()}
            disabled={working}
            className="rounded-md border border-border px-3 py-1 hover:bg-background disabled:opacity-50"
          >
            解除
          </button>
        </>
      ) : (
        <>
          <span className="text-muted">
            連携すると、Google 側の予定も避けて空き時間を探します
          </span>
          <button
            type="button"
            onClick={() => void connect()}
            disabled={working}
            className="rounded-md bg-accent px-3 py-1 font-medium text-white disabled:opacity-50"
          >
            連携する
          </button>
        </>
      )}
      {result && <span className="text-muted">{result}</span>}
    </section>
  );
}
