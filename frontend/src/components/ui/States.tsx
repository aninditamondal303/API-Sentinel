import { AlertTriangle, RefreshCw, SearchX } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { ApiError } from "@/api/client";
import { cn } from "@/lib/cn";
import { Button } from "./Button";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-ink-700/60", className)} aria-hidden="true" />;
}

export function EmptyState({ icon, title, description, action, className }: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 px-6 py-12 text-center", className)}>
      {icon ? <div className="grid size-11 place-items-center rounded-xl border border-ink-600 bg-ink-800 text-accent-400">{icon}</div> : null}
      <div>
        <p className="text-sm font-medium text-ink-100">{title}</p>
        {description ? <p className="mx-auto mt-1 max-w-sm text-sm text-ink-300">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export function ErrorState({ error, onRetry, className }: { error: unknown; onRetry?: () => void; className?: string }) {
  const requestId = error instanceof ApiError ? error.requestId : null;
  // 404, or 400 for a malformed id in the URL: retrying cannot help.
  const missing = error instanceof ApiError && (error.status === 404 || (error.status === 400 && error.code === "VALIDATION_FAILED"));
  if (missing) {
    return (
      <div role="alert" className={cn("flex flex-col items-center gap-3 px-6 py-12 text-center", className)}>
        <div className="grid size-11 place-items-center rounded-xl border border-ink-600 bg-ink-800 text-ink-300"><SearchX className="size-5" /></div>
        <div>
          <p className="text-sm font-medium text-ink-100">Not found</p>
          <p className="mt-1 max-w-md text-sm text-ink-300">This item does not exist, or it belongs to another account.</p>
        </div>
        <Link to="/app/projects" className="text-sm font-medium text-accent-300 hover:text-accent-200">Back to projects</Link>
      </div>
    );
  }
  return (
    <div role="alert" className={cn("flex flex-col items-center gap-3 px-6 py-10 text-center", className)}>
      <div className="grid size-11 place-items-center rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-300">
        <AlertTriangle className="size-5" />
      </div>
      <div>
        <p className="text-sm font-medium text-ink-100">Could not load this data</p>
        <p className="mt-1 max-w-md text-sm text-ink-300">{errorMessage(error)}</p>
        {requestId ? <p className="mt-1 font-mono text-[11px] text-ink-400">Request ID {requestId}</p> : null}
      </div>
      {onRetry ? <Button variant="secondary" size="sm" icon={<RefreshCw className="size-3.5" />} onClick={onRetry}>Try again</Button> : null}
    </div>
  );
}

export function InlineError({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div role="alert" className="flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-200">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <span>{errorMessage(error)}</span>
    </div>
  );
}
