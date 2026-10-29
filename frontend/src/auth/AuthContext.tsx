import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";

import { ApiError, ensureCsrf, get, post } from "@/api/client";
import type { Me } from "@/api/types";

interface AuthValue {
  me: Me | null;
  loading: boolean;
  can: (perm: string) => boolean;
  has: (module: string) => boolean;
  login: (username: string, password: string, schoolCode?: string, portal?: "school" | "platform") => Promise<Me>;
  logout: () => Promise<void>;
  switchSchool: (schoolId: number) => Promise<void>;
  refresh: () => Promise<unknown>;
}

const AuthContext = createContext<AuthValue | null>(null);

/** Set by the owner console while it sets up a school: the setup screens then show every
 *  edit control (the server still allows the platform team setup changes only). */
export const SetupSchoolContext = createContext<{ id: number; name: string } | null>(null);

export function useSetupSchool() {
  return useContext(SetupSchoolContext);
}

async function fetchMe(): Promise<Me | null> {
  await ensureCsrf();
  try {
    return await get<Me>("/auth/me/");
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return null;
    throw error;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const { data, isLoading, refetch } = useQuery({ queryKey: ["me"], queryFn: fetchMe, staleTime: 5 * 60_000 });
  const me = data ?? null;

  /** Switch the signed-in identity: drop every cached query that belonged to the previous
   *  user or school, but keep the "me" query itself so the components watching it update.
   *  (Clearing the whole cache detached them and left the app thinking nobody signed in.) */
  const setIdentity = useCallback(
    (result: Me | null) => {
      client.removeQueries({ predicate: (query) => query.queryKey[0] !== "me" });
      client.setQueryData(["me"], result);
    },
    [client],
  );

  const login = useCallback(
    async (username: string, password: string, schoolCode?: string, portal: "school" | "platform" = "school") => {
      await ensureCsrf();
      const result = await post<Me>("/auth/login/", { username, password, portal, school_code: schoolCode || undefined });
      setIdentity(result);
      return result;
    },
    [setIdentity],
  );

  const logout = useCallback(async () => {
    await post("/auth/logout/");
    setIdentity(null);
  }, [setIdentity]);

  const switchSchool = useCallback(
    async (schoolId: number) => {
      const result = await post<Me>("/auth/switch-school/", { school_id: schoolId });
      setIdentity(result);
    },
    [setIdentity],
  );

  const value = useMemo<AuthValue>(
    () => ({
      me,
      loading: isLoading,
      can: (perm) => !!me?.perms.includes(perm),
      has: (module) => !!me?.modules.includes(module),
      login,
      logout,
      switchSchool,
      refresh: refetch,
    }),
    [me, isLoading, login, logout, switchSchool, refetch],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  const setupSchool = useContext(SetupSchoolContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return setupSchool ? { ...value, can: () => true } : value;
}
