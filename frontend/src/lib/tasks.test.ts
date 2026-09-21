import { describe, expect, it } from "vitest";

import { withSubtaskOrder } from "@/lib/tasks";
import type { Task } from "@/types/task";

function task(id: number, title: string, parentId: number | null = null): Task {
  return {
    id,
    title,
    description: null,
    status: "todo",
    priority: "medium",
    due_date: null,
    estimated_minutes: null,
    completed_at: null,
    parent_task_id: parentId,
    created_at: "2026-09-21T00:00:00+09:00",
    updated_at: "2026-09-21T00:00:00+09:00",
  };
}

describe("withSubtaskOrder", () => {
  it("小タスクを親の直後に並べる", () => {
    const rows = withSubtaskOrder([
      task(1, "ES作成"),
      task(2, "SPI"),
      task(3, "企業研究", 1),
      task(4, "自己PR", 1),
    ]);

    expect(rows.map((r) => r.task.title)).toEqual([
      "ES作成",
      "企業研究",
      "自己PR",
      "SPI",
    ]);
    expect(rows.map((r) => r.isSubtask)).toEqual([false, true, true, false]);
  });

  it("親が一覧に無い小タスクは独立した行として扱う", () => {
    const rows = withSubtaskOrder([task(3, "企業研究", 999)]);

    expect(rows).toHaveLength(1);
    expect(rows[0].isSubtask).toBe(false);
  });

  it("並び順（サーバー側の指定）を壊さない", () => {
    const rows = withSubtaskOrder([task(5, "後"), task(1, "先")]);
    expect(rows.map((r) => r.task.title)).toEqual(["後", "先"]);
  });

  it("空の一覧を扱える", () => {
    expect(withSubtaskOrder([])).toEqual([]);
  });
});
