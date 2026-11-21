/** JWT helpers. The signature is verified by the backend; the client only reads `exp` to drop stale tokens. */
const STORAGE_KEY = "apisentinel.session";

export interface StoredSession {
  token: string;
  expiresAt: number; // epoch millis
}

export function expiryOf(token: string): number | null {
  const payload = token.split(".")[1];
  if (!payload) return null;
  try {
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/"))) as { exp?: unknown };
    return typeof json.exp === "number" ? json.exp * 1000 : null;
  } catch {
    return null;
  }
}

/**
 * sessionStorage (not localStorage): the session ends with the tab, is not shared across tabs,
 * and the backend token itself expires after 60 minutes.
 */
export function loadSession(now = Date.now()): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as StoredSession;
    if (typeof session.token !== "string" || typeof session.expiresAt !== "number" || session.expiresAt <= now) {
      sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

export function saveSession(token: string, expiresInSeconds: number, now = Date.now()): StoredSession {
  const expiresAt = expiryOf(token) ?? now + expiresInSeconds * 1000;
  const session = { token, expiresAt };
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    /* storage unavailable: the session lives in memory only */
  }
  return session;
}

export function clearSession(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
