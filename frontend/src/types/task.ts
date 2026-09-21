export type TaskStatus = "todo" | "in_progress" | "done";
export type TaskPriority = "low" | "medium" | "high";
export type TaskSortField = "due_date" | "priority" | "created_at" | "title";
export type SortOrder = "asc" | "desc";

/** FastAPI の TaskRead に対応する。 */
export type Task = {
  id: number;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  /** ISO8601（オフセット付き） */
  due_date: string | null;
  estimated_minutes: number | null;
  completed_at: string | null;
  /** 分解元のタスク。分解で作られた小タスクのみ値が入る */
  parent_task_id: number | null;
  created_at: string;
  updated_at: string;
};

export type TaskInput = {
  title: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  /** "2026-09-30T23:59" のようなオフセット無しの値を送ると Backend が Asia/Tokyo として解釈する */
  due_date?: string | null;
  estimated_minutes?: number | null;
};

export type TaskFilters = {
  statuses: TaskStatus[];
  priorities: TaskPriority[];
  keyword: string;
  sortBy: TaskSortField;
  order: SortOrder;
};

export const TASK_STATUS_LABEL: Record<TaskStatus, string> = {
  todo: "未着手",
  in_progress: "進行中",
  done: "完了",
};

export const TASK_PRIORITY_LABEL: Record<TaskPriority, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export const TASK_SORT_LABEL: Record<TaskSortField, string> = {
  due_date: "期限",
  priority: "優先度",
  created_at: "作成日",
  title: "タイトル",
};
