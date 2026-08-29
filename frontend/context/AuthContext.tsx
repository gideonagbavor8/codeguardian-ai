"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { saveToken, getToken, removeToken, isTokenExpired } from "@/lib/auth";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Restore session on mount
  useEffect(() => {
    const stored = getToken();
    if (stored && !isTokenExpired(stored)) {
      setToken(stored);
      authApi
        .me(stored)
        .then(setUser)
        .catch(() => {
          removeToken();
          setToken(null);
        })
        .finally(() => setLoading(false));
    } else {
      removeToken();
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await authApi.login(email, password);
    saveToken(tokens.access_token);
    setToken(tokens.access_token);
    const me = await authApi.me(tokens.access_token);
    setUser(me);
    router.push("/dashboard");
  }, [router]);

  const logout = useCallback(() => {
    removeToken();
    setToken(null);
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
