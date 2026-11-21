import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { configureAuth } from "@/api/client";
import { authApi } from "@/api/endpoints";
import type { TokenResponse, User } from "@/api/types";
import { clearSession, loadSession, saveSession, type StoredSession } from "./token";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthState {
  status: Status;
  user: User | null;
  /** Set when the session ended because the server rejected the token. */
  expired: boolean;
  /** Set when the user signed out on purpose (no "return to" page is kept). */
  signedOut: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const sessionRef = useRef<StoredSession | null>(loadSession());
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<Status>(sessionRef.current ? "loading" : "anonymous");
  const [expired, setExpired] = useState(false);
  const [signedOut, setSignedOut] = useState(false);

  const endSession = useCallback((wasExpired: boolean, explicit = false) => {
    sessionRef.current = null;
    clearSession();
    queryClient.clear();
    setUser(null);
    setExpired(wasExpired);
    setSignedOut(explicit);
    setStatus("anonymous");
  }, [queryClient]);

  // Configure before any child effect fires a request (useState initializer runs during render).
  useState(() => configureAuth(() => {
    const session = sessionRef.current;
    return session && session.expiresAt > Date.now() ? session.token : null;
  }, () => endSession(true)));

  useEffect(() => {
    configureAuth(() => {
      const session = sessionRef.current;
      return session && session.expiresAt > Date.now() ? session.token : null;
    }, () => endSession(true));
  }, [endSession]);

  // Restore a stored session: confirm the token with the backend before trusting it.
  useEffect(() => {
    if (!sessionRef.current) return;
    let cancelled = false;
    authApi.me().then((me) => {
      if (!cancelled) {
        setUser(me);
        setStatus("authenticated");
      }
    }).catch(() => {
      if (!cancelled) endSession(false);
    });
    return () => {
      cancelled = true;
    };
  }, [endSession]);

  // Sign out automatically when the token's own expiry passes.
  useEffect(() => {
    const session = sessionRef.current;
    if (status !== "authenticated" || !session) return;
    const timer = window.setTimeout(() => endSession(true), Math.max(0, session.expiresAt - Date.now()));
    return () => window.clearTimeout(timer);
  }, [status, endSession]);

  const accept = useCallback((response: TokenResponse) => {
    sessionRef.current = saveSession(response.accessToken, response.expiresIn);
    queryClient.clear();
    setUser(response.user);
    setExpired(false);
    setSignedOut(false);
    setStatus("authenticated");
  }, [queryClient]);

  const value = useMemo<AuthState>(() => ({
    status,
    user,
    expired,
    signedOut,
    login: async (email, password) => accept(await authApi.login({ email, password })),
    register: async (email, password, displayName) =>
      accept(await authApi.register({ email, password, displayName })),
    logout: () => endSession(false, true),
  }), [status, user, expired, signedOut, accept, endSession]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
