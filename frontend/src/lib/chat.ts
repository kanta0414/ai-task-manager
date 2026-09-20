import { apiFetch } from "@/lib/api";
import type { ChatMessage, ChatResponse, ChatStatus } from "@/types/chat";

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

export function fetchChatStatus(): Promise<ChatStatus> {
  return apiFetch<ChatStatus>("/chat/status");
}
