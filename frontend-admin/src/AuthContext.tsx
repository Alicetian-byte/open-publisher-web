import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";

export interface AdminUser {
  id: string;
  username: string;
  displayName: string;
  role: string;
}

interface LoginPayload {
  token: string;
  user: AdminUser;
}

interface AuthContextValue {
  user: AdminUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<AdminUser>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("opw_access_token");
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get<AdminUser>("/auth/me")
      .then((res) => setUser(res.data.role === "admin" ? res.data : null))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.post<LoginPayload>("/auth/admin/login", { username, password });
    localStorage.setItem("opw_access_token", res.data.token);
    setUser(res.data.user);
    return res.data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      localStorage.removeItem("opw_access_token");
      setUser(null);
    }
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAdminAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAdminAuth 必须在 AdminAuthProvider 中使用");
  return context;
}
