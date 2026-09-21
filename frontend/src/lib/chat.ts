import { apiFetch } from "@/lib/api";
import type {
  ChatResponse,
  ChatStatus,
  Conversation,
  ConversationDetail,
  PendingAction,
} from "@/types/chat";

/**
 * AI へ発言を送る。会話履歴はサーバー側（conversations / messages）が持つため、
 * クライアントは会話IDだけを渡す。省略すると新しい会話が始まる。
 */
export function sendChat(
  message: string,
  conversationId: number | null,
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
}

/** 承認された操作を実行する。引数は Backend 側で再検証される。 */
export function confirmAction(
  conversationId: number,
  action: PendingAction,
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/chat/confirm", {
    method: "POST",
    body: JSON.stringify({ conversation_id: conversationId, ...action }),
  });
}

export function fetchChatStatus(): Promise<ChatStatus> {
  return apiFetch<ChatStatus>("/chat/status");
}

export function fetchConversations(): Promise<Conversation[]> {
  return apiFetch<Conversation[]>("/conversations");
}

export function fetchConversation(id: number): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/conversations/${id}`);
}

export function deleteConversation(id: number): Promise<void> {
  return apiFetch<void>(`/conversations/${id}`, { method: "DELETE" });
}
