import { WeekCalendar } from "@/components/calendar/WeekCalendar";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { TaskBoard } from "@/components/tasks/TaskBoard";
import { EventsProvider } from "@/store/EventsProvider";
import { TasksProvider } from "@/store/TasksProvider";

export default function Home() {
  return (
    <div className="mx-auto w-full max-w-[1400px] p-4 sm:p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">AI Task Manager</h1>
        <p className="mt-1 text-sm text-muted">
          通常UIとAIアシスタントの両方から操作できるタスク・スケジュール管理
        </p>
      </header>

      {/* AI が操作した結果をタスク一覧とカレンダーへ反映できるよう、
          チャットも同じ Provider の内側に置く（Phase 6 で refresh を呼ぶ） */}
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
