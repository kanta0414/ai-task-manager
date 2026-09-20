"use client";

import { useEffect, useState, type FormEvent } from "react";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Modal } from "@/components/ui/Modal";
import { toDatetimeLocalValue } from "@/lib/datetime";
import { fetchTasks } from "@/lib/tasks";
import type { CalendarEvent, EventCreateInput } from "@/types/event";
import type { Task } from "@/types/task";

type Props = {
  event?: CalendarEvent;
  /** 新規作成時の初期値（"2026-09-21T14:00" 形式） */
  defaultStart?: string;
  defaultEnd?: string;
  onSubmit: (input: EventCreateInput) => Promise<void>;
  onDelete?: () => Promise<void>;
  onClose: () => void;
};

const inputClass =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent";

export function EventForm({
  event,
  defaultStart = "",
  defaultEnd = "",
  onSubmit,
  onDelete,
  onClose,
}: Props) {
  const [title, setTitle] = useState(event?.title ?? "");
  const [description, setDescription] = useState(event?.description ?? "");
  const [startAt, setStartAt] = useState(
    event ? toDatetimeLocalValue(event.start_at) : defaultStart,
  );
  const [endAt, setEndAt] = useState(
    event ? toDatetimeLocalValue(event.end_at) : defaultEnd,
  );
  const [location, setLocation] = useState(event?.location ?? "");
  const [taskId, setTaskId] = useState(event?.task_id?.toString() ?? "");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  // 予定を「どのタスクの作業時間か」に紐づけられるようにする
  useEffect(() => {
    fetchTasks({
      statuses: ["todo", "in_progress"],
      priorities: [],
      keyword: "",
      sortBy: "due_date",
      order: "asc",
    })
      .then(setTasks)
      .catch(() => setTasks([]));
  }, []);

  const handleSubmit = async (submitEvent: FormEvent) => {
    submitEvent.preventDefault();
    if (!title.trim() || saving) return;
    if (endAt <= startAt) {
      setFormError("終了時刻は開始時刻より後にしてください");
      return;
    }

    setSaving(true);
    await onSubmit({
      title: title.trim(),
      description: description.trim() || null,
      start_at: startAt,
      end_at: endAt,
      location: location.trim() || null,
      task_id: taskId ? Number(taskId) : null,
    });
    setSaving(false);
    onClose();
  };

  if (confirmingDelete && onDelete) {
    return (
      <ConfirmDialog
        title="予定を削除"
        message={`「${event?.title}」を削除します。この操作は取り消せません。`}
        onConfirm={() => {
          void onDelete();
          onClose();
        }}
        onCancel={() => setConfirmingDelete(false)}
      />
    );
  }

  return (
    <Modal title={event ? "予定を編集" : "予定を追加"} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="event-title" className="mb-1 block text-xs text-muted">
            タイトル
          </label>
          <input
            id="event-title"
            value={title}
            onChange={(changeEvent) => setTitle(changeEvent.target.value)}
            required
            maxLength={200}
            autoFocus
            placeholder="例: 企業研究"
            className={inputClass}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="event-start" className="mb-1 block text-xs text-muted">
              開始
            </label>
            <input
              id="event-start"
              type="datetime-local"
              value={startAt}
              onChange={(changeEvent) => setStartAt(changeEvent.target.value)}
              required
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="event-end" className="mb-1 block text-xs text-muted">
              終了
            </label>
            <input
              id="event-end"
              type="datetime-local"
              value={endAt}
              onChange={(changeEvent) => setEndAt(changeEvent.target.value)}
              required
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <label htmlFor="event-location" className="mb-1 block text-xs text-muted">
            場所
          </label>
          <input
            id="event-location"
            value={location}
            onChange={(changeEvent) => setLocation(changeEvent.target.value)}
            maxLength={255}
            className={inputClass}
          />
        </div>

        <div>
          <label htmlFor="event-task" className="mb-1 block text-xs text-muted">
            関連タスク（任意）
          </label>
          <select
            id="event-task"
            value={taskId}
            onChange={(changeEvent) => setTaskId(changeEvent.target.value)}
            className={inputClass}
          >
            <option value="">紐づけない</option>
            {tasks.map((task) => (
              <option key={task.id} value={task.id}>
                {task.title}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="event-description" className="mb-1 block text-xs text-muted">
            メモ
          </label>
          <textarea
            id="event-description"
            value={description}
            onChange={(changeEvent) => setDescription(changeEvent.target.value)}
            rows={2}
            className={inputClass}
          />
        </div>

        {formError && <p className="text-xs text-red-600">{formError}</p>}

        <div className="flex items-center justify-between pt-1">
          {onDelete ? (
            <button
              type="button"
              onClick={() => setConfirmingDelete(true)}
              className="rounded-md px-3 py-2 text-sm text-red-600 hover:bg-background"
            >
              削除
            </button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
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
        </div>
      </form>
    </Modal>
  );
}
