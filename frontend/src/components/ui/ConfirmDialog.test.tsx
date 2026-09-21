// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

function renderDialog(overrides: Partial<Parameters<typeof ConfirmDialog>[0]> = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(
    <ConfirmDialog
      title="タスクを削除"
      message="「ES作成」を削除します。この操作は取り消せません。"
      onConfirm={onConfirm}
      onCancel={onCancel}
      {...overrides}
    />,
  );
  return { onConfirm, onCancel };
}

describe("ConfirmDialog", () => {
  it("取り消せないことを明記する", () => {
    renderDialog();

    expect(screen.getByText(/取り消せません/)).toBeInTheDocument();
  });

  it("実行ボタンで確定する", async () => {
    const { onConfirm, onCancel } = renderDialog();

    await userEvent.click(screen.getByText("削除する"));

    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("キャンセルボタンで取りやめる", async () => {
    const { onConfirm, onCancel } = renderDialog();

    await userEvent.click(screen.getByText("キャンセル"));

    expect(onCancel).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("Escape キーで取りやめる", async () => {
    const { onConfirm, onCancel } = renderDialog();

    await userEvent.keyboard("{Escape}");

    expect(onCancel).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("背景をクリックすると取りやめる", async () => {
    const { onCancel } = renderDialog();

    await userEvent.click(screen.getByRole("presentation"));

    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("ダイアログ内のクリックでは閉じない", async () => {
    const { onCancel } = renderDialog();

    await userEvent.click(screen.getByRole("dialog"));

    expect(onCancel).not.toHaveBeenCalled();
  });

  it("確定ボタンの文言を変えられる", () => {
    renderDialog({ confirmLabel: "実行する" });

    expect(screen.getByText("実行する")).toBeInTheDocument();
  });
});
