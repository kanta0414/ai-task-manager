// 画面と同じホスト名にする。localhost と 127.0.0.1 は SameSite 判定で
// 別サイト扱いになり、セッション Cookie が送られなくなる。
const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

/**
 * FastAPI 呼び出しの共通ラッパー。
 * 通常UIからのデータ操作はすべてこの層を経由する（LLMはBackendのTool経由）。
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    // セッション Cookie を送受信する（JS からは読めない httpOnly Cookie）
    credentials: "include",
    cache: "no-store",
  });

  if (!res.ok) {
    throw new ApiError(`API ${res.status}: ${await res.text()}`, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
