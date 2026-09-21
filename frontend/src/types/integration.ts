export type IntegrationStatus = {
  /** サーバー側に認証情報が設定されているか */
  google_available: boolean;
  google_connected: boolean;
  google_account_email: string | null;
  /** 更新トークンが失効し、つなぎ直しが必要 */
  google_needs_reauth: boolean;
};
