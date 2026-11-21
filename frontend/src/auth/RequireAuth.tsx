import type { ReactNode } from "react";
import { Navigate, useLocation, useSearchParams } from "react-router";
import { FullPageSpinner } from "@/components/ui/Spinner";
import { useAuth } from "./AuthContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, expired, signedOut } = useAuth();
  const location = useLocation();
  if (status === "loading") return <FullPageSpinner label="Restoring your session" />;
  if (status === "anonymous") {
    // A deliberate sign-out starts fresh; only an interrupted session remembers where the user was.
    if (signedOut) return <Navigate to="/login" replace />;
    const next = location.pathname + location.search;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}${expired ? "&expired=1" : ""}`} replace />;
  }
  return <>{children}</>;
}

/** Only same-app paths are accepted as a post-login destination (prevents open redirects). */
export function safeNext(next: string | null): string {
  return next && next.startsWith("/app") && !next.startsWith("//") ? next : "/app";
}

export function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const [params] = useSearchParams();
  // Honour ?next= so a user whose session expired returns to the page they were on.
  if (status === "authenticated") return <Navigate to={safeNext(params.get("next"))} replace />;
  return <>{children}</>;
}
