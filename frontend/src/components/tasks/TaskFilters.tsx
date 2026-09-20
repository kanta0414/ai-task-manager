"use client";

import { useTasks } from "@/store/TasksProvider";
import {
  TASK_PRIORITY_LABEL,
  TASK_SORT_LABEL,
  type TaskPriority,
  type TaskSortField,
  type TaskStatus,
} from "@/types/task";

const STATUS_PRESETS: { label: string; statuses: TaskStatus[] }[] = [
  { label: "未完了", statuses: ["todo", "in_progress"] },
  { label: "完了", statuses: ["done"] },
  { label: "すべて", statuses: [] },
];

function chipClass(active: boolean): string {
  return [
    "rounded-full border px-3 py-1 text-xs transition-colors",
    active
      ? "border-accent bg-accent text-white"
      : "border-border text-muted hover:bg-background",
  ].join(" ");
}

export function TaskFilters() {
  const { filters, setFilters } = useTasks();

  const togglePriority = (priority: TaskPriority) => {
    setFilters((current) => ({
      ...current,
      priorities: current.priorities.includes(priority)
        ? current.priorities.filter((value) => value !== priority)
        : [...current.priorities, priority],
    }));
  };

  return (
    <div className="space-y-3">
      <input
        type="search"
        value={filters.keyword}
        onChange={(event) =>
          setFilters((current) => ({ ...current, keyword: event.target.value }))
        }
        placeholder="タスクを検索"
        aria-label="タスクを検索"
        className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
      />

      <div className="flex flex-wrap items-center gap-2">
        {STATUS_PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            onClick={() =>
              setFilters((current) => ({ ...current, statuses: preset.statuses }))
            }
            className={chipClass(
              filters.statuses.join() === preset.statuses.join(),
            )}
          >
            {preset.label}
          </button>
        ))}

        <span className="mx-1 h-4 w-px bg-border" aria-hidden />

        {(Object.keys(TASK_PRIORITY_LABEL) as TaskPriority[]).map((priority) => (
          <button
            key={priority}
            type="button"
            onClick={() => togglePriority(priority)}
            className={chipClass(filters.priorities.includes(priority))}
          >
            優先度{TASK_PRIORITY_LABEL[priority]}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2 text-xs text-muted">
        <label htmlFor="sort">並び替え</label>
        <select
          id="sort"
          value={filters.sortBy}
          onChange={(event) =>
            setFilters((current) => ({
              ...current,
              sortBy: event.target.value as TaskSortField,
              // 優先度は「高い順」が自然なので既定の並びを反転させる
              order: event.target.value === "priority" ? "desc" : "asc",
            }))
          }
          className="rounded-md border border-border bg-surface px-2 py-1 outline-none focus:border-accent"
        >
          {Object.entries(TASK_SORT_LABEL).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() =>
            setFilters((current) => ({
              ...current,
              order: current.order === "asc" ? "desc" : "asc",
            }))
          }
          className="rounded-md border border-border px-2 py-1 hover:bg-background"
        >
          {filters.order === "asc" ? "昇順 ↑" : "降順 ↓"}
        </button>
      </div>
    </div>
  );
}
