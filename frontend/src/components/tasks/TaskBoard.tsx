"use client";

import { useState } from "react";

import { TaskFilters } from "@/components/tasks/TaskFilters";
import { TaskForm } from "@/components/tasks/TaskForm";
import { TaskItem } from "@/components/tasks/TaskItem";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { ApiError } from "@/lib/api";
import { reserveTimeForTask, withSubtaskOrder } from "@/lib/tasks";
import { formatDateTime } from "@/lib/datetime";
import { useEvents } from "@/store/EventsProvider";
import { useTasks } from "@/store/TasksProvider";
import type { Task } from "@/types/task";

export function TaskBoard() {
  const { tasks, loading, error, addTask, editTask, removeTask, toggleTask } =
    useTasks();

  const { refresh: refreshEvents } = useEvents();
  const [reservingId, setReservingId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const reserve = async (task: Task) => {
    setReservingId(task.id);
    setNotice(null);
    try {
      const item = await reserveTimeForTask(task.id);
      setNotice(
        `「${task.title}」の作業時間を ${formatDateTime(item.start_at)} から${item.minutes}分の予定を作りました。`,
      );
      refreshEvents();
    } catch (caught) {
      setNotice(
        caught instanceof ApiError
          ? readDetail(caught.message)
          : "時間を確保できませんでした。",
      );
    } finally {
      setReservingId(null);
    }
  };

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [deleting, setDeleting] = useState<Task | null>(null);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          タスク
          {!loading && <span className="ml-2 text-sm text-muted">{tasks.length}件</span>}
        </h2>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
        >
          ＋ タスク追加
        </button>
      </div>

      <TaskFilters />

      {notice && (
        <p className="rounded-md border border-border bg-background px-3 py-2 text-xs text-muted">
          {notice}
        </p>
      )}

      {error && (
        <p className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {loading ? (
        <p className="py-8 text-center text-sm text-muted">読み込み中...</p>
      ) : tasks.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border py-10 text-center text-sm text-muted">
          該当するタスクはありません
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {withSubtaskOrder(tasks).map(({ task, isSubtask }) => (
            <TaskItem
              key={task.id}
              task={task}
              isSubtask={isSubtask}
              onToggle={() => void toggleTask(task)}
              onEdit={() => setEditing(task)}
              onDelete={() => setDeleting(task)}
              onReserve={() => void reserve(task)}
              reserving={reservingId === task.id}
            />
          ))}
        </ul>
      )}

      {creating && (
        <TaskForm onSubmit={addTask} onClose={() => setCreating(false)} />
      )}

      {editing && (
        <TaskForm
          task={editing}
          onSubmit={(input) => editTask(editing.id, input)}
          onClose={() => setEditing(null)}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title="タスクを削除"
          message={`「${deleting.title}」を削除します。この操作は取り消せません。`}
          onConfirm={() => {
            void removeTask(deleting.id);
            setDeleting(null);
          }}
          onCancel={() => setDeleting(null)}
        />
      )}
    </section>
  );
}

/** Backend が返した JSON から表示用の文言を取り出す。 */
function readDetail(raw: string): string {
  const body = raw.replace(/^API \d+: /, "");
  try {
    const parsed: unknown = JSON.parse(body);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "detail" in parsed &&
      typeof (parsed as { detail: unknown }).detail === "string"
    ) {
      return (parsed as { detail: string }).detail;
    }
  } catch {
    // JSON でなければそのまま
  }
  return body;
}
