import React, { createContext, useContext, useState } from "react";
import type { UserRole } from "@/api/client";

interface AuthUser {
  user_id: number;
  email: string;
  full_name: string;
  role: UserRole;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  login: (token: string, user: AuthUser) => void;
  logout: () => void;
  isAdmin: boolean;
  isAlgoTester: boolean;
  isDatasetProvider: boolean;
  isMetricProvider: boolean;
  // legacy helpers
  isManager: boolean;
  isResearcher: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));
  const [user, setUser] = useState<AuthUser | null>(() => {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  });

  const login = (t: string, u: AuthUser) => {
    localStorage.setItem("token", t);
    localStorage.setItem("user", JSON.stringify(u));
    setToken(t);
    setUser(u);
  };

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken(null);
    setUser(null);
  };

  const isAdmin = user?.role === "admin";
  const isAlgoTester = user?.role === "algo_tester" || isAdmin;
  const isDatasetProvider = user?.role === "dataset_provider" || isAdmin;
  const isMetricProvider = user?.role === "metric_provider" || isAdmin;

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        logout,
        isAdmin,
        isAlgoTester,
        isDatasetProvider,
        isMetricProvider,
        // legacy aliases
        isManager: isAdmin,
        isResearcher: isAlgoTester,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
