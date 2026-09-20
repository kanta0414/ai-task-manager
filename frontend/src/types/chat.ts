export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

/** ユーザーの承認を待っている操作（削除など）。 */
export type PendingAction = {
  tool: string;
  arguments: Record<string, unknown>;
  description: string;
};

export type ChatResponse = {
  reply: string;
  provider: string;
  model: string;
  executed_tools: string[];
  /** データが変わったか。true ならタスク・予定を再取得する */
  mutated: boolean;
  pending_action: PendingAction | null;
};

/** AI が使える状態か。使えない場合は hint に対処方法が入る。 */
export type ChatStatus = {
  provider: string;
  model: string;
  available: boolean;
  hint: string | null;
};
