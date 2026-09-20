import { apiFetch } from "@/lib/api";

type Health = { status: string; database?: string };

async function fetchHealth(): Promise<Health | null> {
  try {
    return await apiFetch<Health>("/health/db");
  } catch {
    return null;
  }
}

export default async function Home() {
  const health = await fetchHealth();
  const connected = health?.status === "ok";

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-8 p-10">
      <header>
        <h1 className="text-3xl font-bold">AI Task Manager</h1>
        <p className="mt-2 text-sm text-gray-500">
          通常UIとAIアシスタントの両方から操作できるタスク・スケジュール管理
        </p>
      </header>

      <section className="rounded-lg border border-gray-200 p-6 dark:border-gray-800">
        <h2 className="mb-4 text-lg font-semibold">Phase 0: 環境構築の確認</h2>
        <ul className="space-y-2 text-sm">
          <li>✅ Next.js フロントエンドが表示されている</li>
          <li>
            {connected ? "✅" : "❌"} FastAPI に接続
            {connected ? "できている" : "できていない（バックエンドを起動してください）"}
          </li>
          <li>
            {health?.database === "connected" ? "✅" : "❌"} PostgreSQL に接続
            {health?.database === "connected" ? "できている" : "できていない"}
          </li>
        </ul>
      </section>

      <section className="text-sm text-gray-500">
        <p>次のフェーズ: データモデル（users / tasks / calendar_events）とCRUD API</p>
      </section>
    </main>
  );
}
