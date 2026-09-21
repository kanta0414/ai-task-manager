import { apiFetch } from "@/lib/api";
import type { LoginInput, RegisterInput, SessionUser } from "@/types/auth";

/** ログイン中のユーザー。未ログインなら 401 が投げられる。 */
export function fetchMe(): Promise<SessionUser> {
  return apiFetch<SessionUser>("/auth/me");
}

export function register(input: RegisterInput): Promise<SessionUser> {
  return apiFetch<SessionUser>("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      ...input,
    }),
  });
}

export function login(input: LoginInput): Promise<SessionUser> {
  return apiFetch<SessionUser>("/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}
