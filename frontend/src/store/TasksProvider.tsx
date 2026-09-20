"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";

import {
  completeTask,
  createTask,
  deleteTask,
  fetchTasks,
  reopenTask,
  updateTask,
} from "@/lib/tasks";
import type { Task, TaskFilters, TaskInput } from "@/types/task";

export const DEFAULT_FILTERS: TaskFilters = {
  statuses: ["todo", "in_progress"],
  priorities: [],
  keyword: "",
  sortBy: "due_date",
  order: "asc",
};

type TasksContextValue = {
  tasks: Task[];
  loading: boolean;
  error: string | null;
  filters: TaskFilters;
  setFilters: Dispatch<SetStateAction<TaskFilters>>;
  refresh: () => Promise<void>;
  addTask: (input: TaskInput) => Promise<void>;
  editTask: (id: number, input: TaskInput) => Promise<void>;
  removeTask: (id: number) => Promise<void>;
  toggleTask: (task: Task) => Promise<void>;
};

const TasksContext = createContext<TasksContextValue | null>(null);

/**
 * タスクの取得・更新を一元管理する。
 * Phase 5 以降、AI アシスタントが操作した結果も refresh() でこの状態へ反映する。
 */
export function TasksProvider({ children }: { children: ReactNode }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<TaskFilters>(DEFAULT_FILTERS);

  // 後から来た応答で古い結果を上書きしないための世代管理
  const requestId = useRef(0);

  const load = useCallback(async (current: TaskFilters) => {
    const id = ++requestId.current;
    setLoading(true);
    try {
      const result = await fetchTasks(current);
      if (id !== requestId.current) return;
      setTasks(result);
      setError(null);
    } catch {
      if (id !== requestId.current) return;
      setError("タスクを取得できませんでした。Backend が起動しているか確認してください。");
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, []);

  // 検索キーワードの入力ごとにリクエストしないよう少し待つ
  useEffect(() => {
    const timer = setTimeout(() => void load(filters), 250);
    return () => clearTimeout(timer);
  }, [filters, load]);

  const refresh = useCallback(() => load(filters), [filters, load]);

  const run = useCallback(
    async (action: () => Promise<unknown>, failureMessage: string) => {
      try {
        await action();
        await load(filters);
      } catch {
        setError(failureMessage);
      }
    },
    [filters, load],
  );

  const value = useMemo<TasksContextValue>(
    () => ({
      tasks,
      loading,
      error,
      filters,
      setFilters,
      refresh,
      addTask: (input) =>
        run(() => createTask(input), "タスクを作成できませんでした。"),
      editTask: (id, input) =>
        run(() => updateTask(id, input), "タスクを更新できませんでした。"),
      removeTask: (id) =>
        run(() => deleteTask(id), "タスクを削除できませんでした。"),
      toggleTask: (task) =>
        run(
          () => (task.status === "done" ? reopenTask(task.id) : completeTask(task.id)),
          "タスクの状態を変更できませんでした。",
        ),
    }),
    [tasks, loading, error, filters, refresh, run],
  );

  return <TasksContext.Provider value={value}>{children}</TasksContext.Provider>;
}

export function useTasks(): TasksContextValue {
  const context = useContext(TasksContext);
  if (!context) {
    throw new Error("useTasks は TasksProvider の内側で使用してください");
  }
  return context;
}
