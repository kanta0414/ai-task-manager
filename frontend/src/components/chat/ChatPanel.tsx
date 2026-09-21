"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import { ApiError } from "@/lib/api";
import {
  confirmAction,
  deleteConversation,
  fetchChatStatus,
  fetchConversation,
  sendChat,
} from "@/lib/chat";
import { useEvents } from "@/store/EventsProvider";
import { useTasks } from "@/store/TasksProvider";
import type { ChatMessage, ChatResponse, ChatStatus, PendingAction } from "@/types/chat";

const SUGGESTIONS = [
  "今日のタスクを教えて",
  "明日の14時から2時間、企業研究を入れて",
];

/** 直近の会話IDの置き場所。会話の中身はサーバーにあり、ここは目印だけ。 */
const CONVERSATION_KEY = "ai-task-manager.conversation-id";

function readStoredConversationId(): number | null {
  try {
    const raw = window.localStorage.getItem(CONVERSATION_KEY);
    const parsed = raw ? Number(raw) : NaN;
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  } catch {
    return null;
  }
}

function storeConversationId(id: number | null): void {
  try {
    if (id === null) window.localStorage.removeItem(CONVERSATION_KEY);
    else window.localStorage.setItem(CONVERSATION_KEY, String(id));
  } catch {
    // プライベートウィンドウなどで使えなくても動作に影響させない
  }
}

export function ChatPanel() {
  const { refresh: refreshTasks } = useTasks();
  const { refresh: refreshEvents } = useEvents();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<ChatStatus | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);

  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchChatStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  // リロードしても直前の会話から続けられるよう、保存済みの会話を読み直す
  useEffect(() => {
    const storedId = readStoredConversationId();
    if (storedId === null) return;

    fetchConversation(storedId)
      .then((conversation) => {
        setConversationId(conversation.id);
        setMessages(
          conversation.messages.map((message) => ({
            role: message.role,
            content: message.content,
          })),
        );
      })
      .catch(() => storeConversationId(null));
  }, []);

  // 新しい発言が増えたら最下部へ
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages, sending, pending]);

  /** AI がデータを変更したら、通常UIの表示も合わせる。 */
  const applyResponse = useCallback(
    (response: ChatResponse) => {
      setMessages((current) => [
        ...current,
        { role: "assistant", content: response.reply },
      ]);
      setConversationId(response.conversation_id);
      storeConversationId(response.conversation_id);
      setPending(response.pending_action);
      if (response.mutated) {
        void refreshTasks();
        refreshEvents();
      }
    },
    [refreshTasks, refreshEvents],
  );

  const handleFailure = (caught: unknown) => {
    const detail =
      caught instanceof ApiError
        ? caught.message.replace(/^API \d+: /, "")
        : "AI に接続できませんでした。";
    setError(extractDetail(detail));
  };

  const submit = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    setMessages((current) => [...current, { role: "user", content: trimmed }]);
    setInput("");
    setSending(true);
    setError(null);
    setPending(null);

    try {
      applyResponse(await sendChat(trimmed, conversationId));
    } catch (caught) {
      handleFailure(caught);
    } finally {
      setSending(false);
    }
  };

  const startNewConversation = async (deleteCurrent: boolean) => {
    const current = conversationId;
    setMessages([]);
    setPending(null);
    setError(null);
    setConversationId(null);
    storeConversationId(null);

    if (deleteCurrent && current !== null) {
      try {
        await deleteConversation(current);
      } catch {
        setError("前の会話を削除できませんでした。");
      }
    }
  };

  const runPending = async () => {
    if (!pending || sending || conversationId === null) return;
    setSending(true);
    setError(null);
    const action = pending;
    setPending(null);

    try {
      applyResponse(await confirmAction(conversationId, action));
    } catch (caught) {
      handleFailure(caught);
    } finally {
      setSending(false);
    }
  };

  const cancelPending = () => {
    setPending(null);
    setMessages((current) => [
      ...current,
      { role: "assistant", content: "キャンセルしました。" },
    ]);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit(input);
  };

  // Enter で送信、Shift+Enter で改行
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    // 日本語入力の変換確定にも Enter を使うため、変換中は送信しない
    if (event.nativeEvent.isComposing) return;

    event.preventDefault();
    void submit(input);
  };

  return (
    <section className="mt-8 flex flex-col rounded-lg border border-border bg-surface">
      <header className="flex items-center justify-between border-b border-border px-4 py-2">
        <h2 className="text-sm font-semibold">AI Assistant</h2>
        <div className="flex items-center gap-3">
          {status && (
            <span className="text-[11px] text-muted">
              {status.provider} / {status.model}
              {!status.available && "（未接続）"}
            </span>
          )}
          {messages.length > 0 && (
            <>
              <button
                type="button"
                onClick={() => void startNewConversation(false)}
                className="rounded-md border border-border px-2 py-1 text-[11px] hover:bg-background"
              >
                新しい会話
              </button>
              <button
                type="button"
                onClick={() => void startNewConversation(true)}
                className="rounded-md px-2 py-1 text-[11px] text-red-600 hover:bg-background"
              >
                この会話を削除
              </button>
            </>
          )}
        </div>
      </header>

      {status && !status.available && status.hint && (
        <p className="border-b border-border bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-200">
          {status.hint}
        </p>
      )}

      <div ref={logRef} className="max-h-80 min-h-32 overflow-y-auto px-4 py-3">
        {messages.length === 0 && !pending ? (
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
            {pending && (
              <li>
                <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950">
                  <p className="whitespace-pre-wrap text-sm text-amber-900 dark:text-amber-100">
                    {pending.description}
                  </p>
                  <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
                    この操作は取り消せません。実行してよいですか？
                  </p>
                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      onClick={() => void runPending()}
                      className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700"
                    >
                      実行
                    </button>
                    <button
                      type="button"
                      onClick={cancelPending}
                      className="rounded-md border border-border bg-surface px-3 py-1.5 text-xs hover:bg-background"
                    >
                      キャンセル
                    </button>
                  </div>
                </div>
              </li>
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
function extractDetail(raw: string): string {
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
