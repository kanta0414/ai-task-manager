export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

export type ChatResponse = {
  reply: string;
  provider: string;
  model: string;
};

/** AI が使える状態か。使えない場合は hint に対処方法が入る。 */
export type ChatStatus = {
  provider: string;
  model: string;
  available: boolean;
  hint: string | null;
};
