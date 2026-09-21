"use client";

import { dueState, formatDateTime, formatDuration } from "@/lib/datetime";
import { TASK_PRIORITY_LABEL, type Task } from "@/types/task";

type Props = {
  task: Task;
  isSubtask?: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
};

const PRIORITY_CLASS: Record<Task["priority"], string> = {
  high: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  low: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
};

const DUE_CLASS: Record<string, string> = {
  overdue: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  today: "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300",
  tomorrow: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  upcoming: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
};

const DUE_PREFIX: Record<string, string> = {
  overdue: "期限切れ ",
  today: "今日 ",
  tomorrow: "明日 ",
  upcoming: "",
};

export function TaskItem({ task, isSubtask = false, onToggle, onEdit, onDelete }: Props) {
  const done = task.status === "done";
  const due = dueState(task.due_date);
  const duration = formatDuration(task.estimated_minutes);

  return (
    <li
      className={`group flex items-start gap-3 rounded-lg border border-border bg-surface p-3 ${
        isSubtask ? "ml-6 border-l-2 border-l-accent/40" : ""
      }`}
    >
      <input
        type="checkbox"
        checked={done}
        onChange={onToggle}
        aria-label={done ? `${task.title}を未完了に戻す` : `${task.title}を完了にする`}
        className="mt-1 size-4 shrink-0 accent-[var(--accent)]"
      />

      <div className="min-w-0 flex-1">
        <p className={done ? "text-sm text-muted line-through" : "text-sm font-medium"}>
          {task.title}
        </p>
        {task.description && (
          <p className="mt-0.5 line-clamp-2 text-xs text-muted">{task.description}</p>
        )}

        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px]">
          <span className={`rounded px-1.5 py-0.5 ${PRIORITY_CLASS[task.priority]}`}>
            {TASK_PRIORITY_LABEL[task.priority]}
          </span>
          {task.due_date && due !== "none" && (
            <span className={`rounded px-1.5 py-0.5 ${DUE_CLASS[due]}`}>
              {DUE_PREFIX[due]}
              {formatDateTime(task.due_date)}
            </span>
          )}
          {duration && <span className="text-muted">{duration}</span>}
          {task.status === "in_progress" && (
            <span className="text-muted">進行中</span>
          )}
        </div>
      </div>

      <div className="flex shrink-0 gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
        <button
          type="button"
          onClick={onEdit}
          className="rounded px-2 py-1 text-xs text-muted hover:bg-background"
        >
          編集
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="rounded px-2 py-1 text-xs text-red-600 hover:bg-background"
        >
          削除
        </button>
      </div>
    </li>
  );
}
