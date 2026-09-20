import { TaskBoard } from "@/components/tasks/TaskBoard";
import { TasksProvider } from "@/store/TasksProvider";

export default function Home() {
  return (
    <div className="mx-auto w-full max-w-3xl p-6 sm:p-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">AI Task Manager</h1>
        <p className="mt-1 text-sm text-muted">
          通常UIとAIアシスタントの両方から操作できるタスク・スケジュール管理
        </p>
      </header>

      <TasksProvider>
        <TaskBoard />
      </TasksProvider>
    </div>
  );
}
