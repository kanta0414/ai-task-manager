"use client";

import { WeekCalendar } from "@/components/calendar/WeekCalendar";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { NotificationBar } from "@/components/notifications/NotificationBar";
import { AuthForm } from "@/components/auth/AuthForm";
import { TaskBoard } from "@/components/tasks/TaskBoard";
import { EventsProvider } from "@/store/EventsProvider";
import { useSession } from "@/store/SessionProvider";
import { TasksProvider } from "@/store/TasksProvider";

export function AppShell() {
  const { user, loading, signOut } = useSession();

  // 確認中に画面を出すと、ログイン済みでも一瞬ログイン画面が見えてしまう
  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center text-sm text-muted">
        読み込み中...
      </main>
    );
  }

  if (!user) return <AuthForm />;

  return (
    <div className="mx-auto w-full max-w-[1400px] p-4 sm:p-8">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">AI Task Manager</h1>
          <p className="mt-1 text-sm text-muted">
            通常UIとAIアシスタントの両方から操作できるタスク・スケジュール管理
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="text-xs text-muted">{user.name}</span>
          <button
            type="button"
            onClick={() => void signOut()}
            className="rounded-md border border-border px-3 py-1.5 text-xs hover:bg-background"
          >
            ログアウト
          </button>
        </div>
      </header>

      <NotificationBar />

      {/* AI が操作した結果をタスク一覧とカレンダーへ反映できるよう、
          チャットも同じ Provider の内側に置く */}
      <TasksProvider>
        <EventsProvider>
          <div className="grid gap-8 lg:grid-cols-[minmax(320px,380px)_minmax(0,1fr)]">
            <TaskBoard />
            <WeekCalendar />
          </div>
          <ChatPanel />
        </EventsProvider>
      </TasksProvider>
    </div>
  );
}
