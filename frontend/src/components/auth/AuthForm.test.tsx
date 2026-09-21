// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthForm } from "@/components/auth/AuthForm";
import { ApiError } from "@/lib/api";

const login = vi.fn();
const register = vi.fn();
const setUser = vi.fn();

vi.mock("@/lib/auth", () => ({
  login: (...args: unknown[]) => login(...args),
  register: (...args: unknown[]) => register(...args),
}));

vi.mock("@/store/SessionProvider", () => ({
  useSession: () => ({ setUser, user: null, loading: false, signOut: vi.fn() }),
}));

const user = { id: 1, name: "かんた", email: "a@example.com", timezone: "Asia/Tokyo" };

beforeEach(() => {
  vi.clearAllMocks();
});

async function submitLogin() {
  await userEvent.type(screen.getByLabelText("メールアドレス"), "a@example.com");
  await userEvent.type(screen.getByLabelText("パスワード"), "password123");
  await userEvent.click(screen.getByRole("button", { name: "ログイン" }));
}

describe("AuthForm", () => {
  it("最初はログイン画面を出す", () => {
    render(<AuthForm />);

    expect(screen.getByRole("button", { name: "ログイン" })).toBeInTheDocument();
    expect(screen.queryByLabelText("名前")).not.toBeInTheDocument();
  });

  it("登録画面に切り替えると名前の入力が出る", async () => {
    render(<AuthForm />);

    await userEvent.click(screen.getByText("アカウントをお持ちでない方はこちら"));

    expect(screen.getByLabelText("名前")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "登録する" })).toBeInTheDocument();
  });

  it("ログインに成功するとセッションに反映する", async () => {
    login.mockResolvedValue(user);
    render(<AuthForm />);

    await submitLogin();

    await waitFor(() => expect(setUser).toHaveBeenCalledWith(user));
    expect(login).toHaveBeenCalledWith({
      email: "a@example.com",
      password: "password123",
    });
  });

  it("認証に失敗したら理由を表示する", async () => {
    login.mockRejectedValue(new ApiError("API 401: {}", 401));
    render(<AuthForm />);

    await submitLogin();

    expect(
      await screen.findByText("メールアドレスまたはパスワードが違います。"),
    ).toBeInTheDocument();
    expect(setUser).not.toHaveBeenCalled();
  });

  it("メールアドレスが重複していたらその旨を伝える", async () => {
    register.mockRejectedValue(new ApiError("API 409: {}", 409));
    render(<AuthForm />);

    await userEvent.click(screen.getByText("アカウントをお持ちでない方はこちら"));
    await userEvent.type(screen.getByLabelText("名前"), "かんた");
    await userEvent.type(screen.getByLabelText("メールアドレス"), "a@example.com");
    await userEvent.type(screen.getByLabelText("パスワード"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "登録する" }));

    expect(
      await screen.findByText("このメールアドレスは既に登録されています。"),
    ).toBeInTheDocument();
  });

  it("通信できないときは接続を疑う案内を出す", async () => {
    login.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<AuthForm />);

    await submitLogin();

    expect(await screen.findByText(/Backend が起動しているか/)).toBeInTheDocument();
  });

  it("登録時はパスワードの長さを画面でも示す", async () => {
    render(<AuthForm />);

    await userEvent.click(screen.getByText("アカウントをお持ちでない方はこちら"));

    expect(screen.getByText("8文字以上")).toBeInTheDocument();
    expect(screen.getByLabelText("パスワード")).toHaveAttribute("minLength", "8");
  });
});
