import { apiFetch } from "@/lib/api";
import type {
  ChatMessage,
  ChatResponse,
  ChatStatus,
  PendingAction,
} from "@/types/chat";

/**
 * AI へ発言を送る。会話履歴は Phase 9 でサーバー保存に移行するため、
 * 現時点ではクライアントが保持している履歴を一緒に送る。
 */
export function sendChat(
  message: string,
  history: ChatMessage[],
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
}

/** 承認された操作を実行する。引数は Backend 側で再検証される。 */
export function confirmAction(action: PendingAction): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/chat/confirm", {
    method: "POST",
    body: JSON.stringify(action),
  });
}

export function fetchChatStatus(): Promise<ChatStatus> {
  return apiFetch<ChatStatus>("/chat/status");
}
