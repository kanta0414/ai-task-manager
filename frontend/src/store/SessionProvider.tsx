"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { fetchMe, logout as requestLogout } from "@/lib/auth";
import type { SessionUser } from "@/types/auth";

type SessionContextValue = {
  user: SessionUser | null;
  /** 最初の確認が終わるまでは画面を出さない（ちらつき防止） */
  loading: boolean;
  setUser: (user: SessionUser) => void;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetchMe()
      .then((me) => {
        if (active) setUser(me);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const signOut = useCallback(async () => {
    try {
      await requestLogout();
    } finally {
      setUser(null);
      // 前のユーザーの会話を引き継がないよう目印も消す
      try {
        window.localStorage.removeItem("ai-task-manager.conversation-id");
      } catch {
        // 使えない環境でも動作に影響させない
      }
    }
  }, []);

  return (
    <SessionContext.Provider value={{ user, loading, setUser, signOut }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession は SessionProvider の内側で使用してください");
  }
  return context;
}
