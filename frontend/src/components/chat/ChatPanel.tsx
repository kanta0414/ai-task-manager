"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { ApiError } from "@/lib/api";
import { fetchChatStatus, sendChat } from "@/lib/chat";
import type { ChatMessage, ChatStatus } from "@/types/chat";

const SUGGESTIONS = ["今日のタスクを教えて", "明日の予定を教えて"];

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<ChatStatus | null>(null);

  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchChatStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  // 新しい発言が増えたら最下部へ
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages, sending]);

  const submit = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    const history = messages;
    setMessages([...history, { role: "user", content: trimmed }]);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const response = await sendChat(trimmed, history);
      setMessages((current) => [
        ...current,
        { role: "assistant", content: response.reply },
      ]);
    } catch (caught) {
      const detail =
        caught instanceof ApiError
          ? caught.message.replace(/^API \d+: /, "")
          : "AI に接続できませんでした。";
      setError(safeDetail(detail));
    } finally {
      setSending(false);
    }
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit(input);
  };

  // Enter で送信、Shift+Enter で改行
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit(input);
    }
  };

  return (
    <section className="mt-8 flex flex-col rounded-lg border border-border bg-surface">
      <header className="flex items-center justify-between border-b border-border px-4 py-2">
        <h2 className="text-sm font-semibold">AI Assistant</h2>
        {status && (
          <span className="text-[11px] text-muted">
            {status.provider} / {status.model}
            {!status.available && "（未接続）"}
          </span>
        )}
      </header>

      {status && !status.available && status.hint && (
        <p className="border-b border-border bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-200">
          {status.hint}
        </p>
      )}

      <div ref={logRef} className="max-h-72 min-h-32 overflow-y-auto px-4 py-3">
        {messages.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted">
            <p>タスクや予定について話しかけてください。</p>
            <div className="mt-3 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => void submit(suggestion)}
                  className="rounded-full border border-border px-3 py-1 text-xs hover:bg-background"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {messages.map((message, index) => (
              <li
                key={index}
                className={message.role === "user" ? "text-right" : "text-left"}
              >
                <span
                  className={`inline-block max-w-[80%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
                    message.role === "user"
                      ? "bg-accent text-white"
                      : "bg-background text-foreground"
                  }`}
                >
                  {message.content}
                </span>
              </li>
            ))}
            {sending && (
              <li className="text-left text-sm text-muted">考えています...</li>
            )}
          </ul>
        )}
      </div>

      {error && (
        <p className="border-t border-border px-4 py-2 text-xs text-red-600">{error}</p>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2 border-t border-border p-3">
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="何をしますか？（Enterで送信 / Shift+Enterで改行）"
          className="min-h-10 flex-1 resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          送信
        </button>
      </form>
    </section>
  );
}

/** Backend が返した JSON のエラー本文から、表示用の文言を取り出す。 */
function safeDetail(raw: string): string {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "detail" in parsed &&
      typeof (parsed as { detail: unknown }).detail === "string"
    ) {
      return (parsed as { detail: string }).detail;
    }
  } catch {
    // JSON でなければそのまま表示する
  }
  return raw;
}
