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
