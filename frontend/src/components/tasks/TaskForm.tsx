"use client";

import { useState, type FormEvent } from "react";

import { Modal } from "@/components/ui/Modal";
import { toDatetimeLocalValue } from "@/lib/datetime";
import {
  TASK_PRIORITY_LABEL,
  TASK_STATUS_LABEL,
  type Task,
  type TaskInput,
  type TaskPriority,
  type TaskStatus,
} from "@/types/task";

type Props = {
  task?: Task;
  onSubmit: (input: TaskInput) => Promise<void>;
  onClose: () => void;
};

const inputClass =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent";

export function TaskForm({ task, onSubmit, onClose }: Props) {
  const [title, setTitle] = useState(task?.title ?? "");
  const [description, setDescription] = useState(task?.description ?? "");
  const [dueDate, setDueDate] = useState(toDatetimeLocalValue(task?.due_date ?? null));
  const [priority, setPriority] = useState<TaskPriority>(task?.priority ?? "medium");
  const [status, setStatus] = useState<TaskStatus>(task?.status ?? "todo");
  const [estimatedMinutes, setEstimatedMinutes] = useState(
    task?.estimated_minutes?.toString() ?? "",
  );
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim() || saving) return;

    setSaving(true);
    await onSubmit({
      title: title.trim(),
      description: description.trim() || null,
      priority,
      status,
      // オフセット無しで送る。Backend が Asia/Tokyo として解釈する
      due_date: dueDate || null,
      estimated_minutes: estimatedMinutes ? Number(estimatedMinutes) : null,
    });
    setSaving(false);
    onClose();
  };

  return (
    <Modal title={task ? "タスクを編集" : "タスクを追加"} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="title" className="mb-1 block text-xs text-muted">
            タイトル
          </label>
          <input
            id="title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
            maxLength={200}
            autoFocus
            placeholder="例: ES作成"
            className={inputClass}
          />
        </div>

        <div>
          <label htmlFor="description" className="mb-1 block text-xs text-muted">
            説明
          </label>
          <textarea
            id="description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={2}
            className={inputClass}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="due" className="mb-1 block text-xs text-muted">
              期限
            </label>
            <input
              id="due"
              type="datetime-local"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="minutes" className="mb-1 block text-xs text-muted">
              所要時間（分）
            </label>
            <input
              id="minutes"
              type="number"
              min={1}
              max={1440}
              value={estimatedMinutes}
              onChange={(event) => setEstimatedMinutes(event.target.value)}
              placeholder="例: 120"
              className={inputClass}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="priority" className="mb-1 block text-xs text-muted">
              優先度
            </label>
            <select
              id="priority"
              value={priority}
              onChange={(event) => setPriority(event.target.value as TaskPriority)}
              className={inputClass}
            >
              {Object.entries(TASK_PRIORITY_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="status" className="mb-1 block text-xs text-muted">
              状態
            </label>
            <select
              id="status"
              value={status}
              onChange={(event) => setStatus(event.target.value as TaskStatus)}
              className={inputClass}
            >
              {Object.entries(TASK_STATUS_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border px-4 py-2 text-sm hover:bg-background"
          >
            キャンセル
          </button>
          <button
            type="submit"
            disabled={saving || !title.trim()}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
