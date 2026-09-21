// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TaskItem } from "@/components/tasks/TaskItem";
import type { Task } from "@/types/task";

function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 1,
    title: "ES作成",
    description: null,
    status: "todo",
    priority: "medium",
    due_date: null,
    estimated_minutes: null,
    completed_at: null,
    parent_task_id: null,
    created_at: "2026-09-21T00:00:00+09:00",
    updated_at: "2026-09-21T00:00:00+09:00",
    ...overrides,
  };
}

const noop = () => {};

function renderItem(task: Task, handlers: Partial<Record<string, () => void>> = {}) {
  return render(
    <TaskItem
      task={task}
      onToggle={handlers.onToggle ?? noop}
      onEdit={handlers.onEdit ?? noop}
      onDelete={handlers.onDelete ?? noop}
      onReserve={handlers.onReserve ?? noop}
    />,
  );
}

describe("TaskItem", () => {
  it("未完了のタスクはチェックが外れている", () => {
    renderItem(makeTask());

    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });

  it("完了したタスクはチェックが入り、打ち消し線がつく", () => {
    renderItem(makeTask({ status: "done" }));

    expect(screen.getByRole("checkbox")).toBeChecked();
    expect(screen.getByText("ES作成").className).toContain("line-through");
  });

  it("完了したタスクには時間確保のボタンを出さない", () => {
    renderItem(makeTask({ status: "done" }));

    expect(screen.queryByText("時間を確保")).not.toBeInTheDocument();
  });

  it("所要時間を読みやすい形式で表示する", () => {
    renderItem(makeTask({ estimated_minutes: 90 }));

    expect(screen.getByText("1時間30分")).toBeInTheDocument();
  });

  it("期限切れのタスクにはその旨を表示する", () => {
    renderItem(makeTask({ due_date: "2020-01-01T10:00:00+09:00" }));

    expect(screen.getByText(/期限切れ/)).toBeInTheDocument();
  });

  it("優先度を日本語で表示する", () => {
    renderItem(makeTask({ priority: "high" }));

    expect(screen.getByText("高")).toBeInTheDocument();
  });

  it("チェックで完了を切り替える", async () => {
    const onToggle = vi.fn();
    renderItem(makeTask(), { onToggle });

    await userEvent.click(screen.getByRole("checkbox"));

    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("各ボタンが対応する処理を呼ぶ", async () => {
    const onEdit = vi.fn();
    const onDelete = vi.fn();
    const onReserve = vi.fn();
    renderItem(makeTask(), { onEdit, onDelete, onReserve });

    await userEvent.click(screen.getByText("編集"));
    await userEvent.click(screen.getByText("削除"));
    await userEvent.click(screen.getByText("時間を確保"));

    expect(onEdit).toHaveBeenCalledOnce();
    expect(onDelete).toHaveBeenCalledOnce();
    expect(onReserve).toHaveBeenCalledOnce();
  });

  it("読み上げ用のラベルが操作内容を表す", () => {
    const { rerender } = renderItem(makeTask());
    expect(
      screen.getByLabelText("ES作成を完了にする"),
    ).toBeInTheDocument();

    rerender(
      <TaskItem
        task={makeTask({ status: "done" })}
        onToggle={noop}
        onEdit={noop}
        onDelete={noop}
        onReserve={noop}
      />,
    );
    expect(
      screen.getByLabelText("ES作成を未完了に戻す"),
    ).toBeInTheDocument();
  });
});
