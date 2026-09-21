import { apiFetch } from "@/lib/api";
import type { Task, TaskFilters, TaskInput } from "@/types/task";

function buildQuery(filters: TaskFilters): string {
  const params = new URLSearchParams();
  filters.statuses.forEach((status) => params.append("status", status));
  filters.priorities.forEach((priority) => params.append("priority", priority));
  if (filters.keyword.trim()) params.set("keyword", filters.keyword.trim());
  params.set("sort_by", filters.sortBy);
  params.set("order", filters.order);
  return params.toString();
}

export function fetchTasks(filters: TaskFilters): Promise<Task[]> {
  return apiFetch<Task[]>(`/tasks?${buildQuery(filters)}`);
}

export function createTask(input: TaskInput): Promise<Task> {
  return apiFetch<Task>("/tasks", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateTask(id: number, input: TaskInput): Promise<Task> {
  return apiFetch<Task>(`/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteTask(id: number): Promise<void> {
  return apiFetch<void>(`/tasks/${id}`, { method: "DELETE" });
}

export function completeTask(id: number): Promise<Task> {
  return apiFetch<Task>(`/tasks/${id}/complete`, { method: "POST" });
}

export function reopenTask(id: number): Promise<Task> {
  return apiFetch<Task>(`/tasks/${id}/reopen`, { method: "POST" });
}


export type TaskRow = {
  task: Task;
  /** 分解で作られた小タスクとして、親の下にぶら下げて表示する */
  isSubtask: boolean;
};

/**
 * 親タスクの直後にその小タスクを並べる。
 * 親が一覧に無い小タスク（フィルタで外れた場合など）は独立した行として扱う。
 */
export function withSubtaskOrder(tasks: Task[]): TaskRow[] {
  const visibleIds = new Set(tasks.map((task) => task.id));
  const children = new Map<number, Task[]>();
  const roots: Task[] = [];

  for (const task of tasks) {
    const parentId = task.parent_task_id;
    if (parentId !== null && visibleIds.has(parentId)) {
      children.set(parentId, [...(children.get(parentId) ?? []), task]);
    } else {
      roots.push(task);
    }
  }

  return roots.flatMap((root) => [
    { task: root, isSubtask: false },
    ...(children.get(root.id) ?? []).map((child) => ({
      task: child,
      isSubtask: true,
    })),
  ]);
}
