"use client";

import { useState, type FormEvent } from "react";

import { ApiError } from "@/lib/api";
import { login, register } from "@/lib/auth";
import { useSession } from "@/store/SessionProvider";

const inputClass =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent";

export function AuthForm() {
  const { setUser } = useSession();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const isRegister = mode === "register";

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (sending) return;

    setSending(true);
    setError(null);
    try {
      const user = isRegister
        ? await register({ name, email, password })
        : await login({ email, password });
      setUser(user);
    } catch (caught) {
      setError(readError(caught, isRegister));
    } finally {
      setSending(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center gap-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">AI Task Manager</h1>
        <p className="mt-1 text-sm text-muted">
          {isRegister ? "アカウントを作成します。" : "ログインしてください。"}
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5"
      >
        {isRegister && (
          <div>
            <label htmlFor="name" className="mb-1 block text-xs text-muted">
              名前
            </label>
            <input
              id="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              maxLength={100}
              autoComplete="name"
              className={inputClass}
            />
          </div>
        )}

        <div>
          <label htmlFor="email" className="mb-1 block text-xs text-muted">
            メールアドレス
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            autoComplete="email"
            className={inputClass}
          />
        </div>

        <div>
          <label htmlFor="password" className="mb-1 block text-xs text-muted">
            パスワード
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={isRegister ? 8 : 1}
            autoComplete={isRegister ? "new-password" : "current-password"}
            className={inputClass}
          />
          {isRegister && (
            <p className="mt-1 text-[11px] text-muted">8文字以上</p>
          )}
        </div>

        {error && <p className="text-xs text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={sending}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {sending ? "処理中..." : isRegister ? "登録する" : "ログイン"}
        </button>
      </form>

      <button
        type="button"
        onClick={() => {
          setMode(isRegister ? "login" : "register");
          setError(null);
        }}
        className="text-xs text-muted underline underline-offset-4"
      >
        {isRegister
          ? "すでにアカウントをお持ちの方はこちら"
          : "アカウントをお持ちでない方はこちら"}
      </button>
    </main>
  );
}

function readError(caught: unknown, isRegister: boolean): string {
  if (caught instanceof ApiError) {
    if (caught.status === 401) return "メールアドレスまたはパスワードが違います。";
    if (caught.status === 409) return "このメールアドレスは既に登録されています。";
    if (caught.status === 422) {
      return isRegister
        ? "入力内容を確認してください（パスワードは8文字以上）。"
        : "入力内容を確認してください。";
    }
  }
  return "通信に失敗しました。Backend が起動しているか確認してください。";
}
