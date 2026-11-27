import { Hourglass } from "lucide-react";
import { useEffect, useState } from "react";

/** How long a sign-in or registration request may run before the notice appears. */
export const SLOW_REQUEST_MS = 5000;

/**
 * The hosted demo's backend runs on a free instance that sleeps when idle, so the first request
 * after a pause can take up to a minute. While `active` (a request is pending) for longer than
 * `delayMs`, this explains the wait instead of leaving the visitor with a spinner only.
 */
export function SlowServerNotice({ active, delayMs = SLOW_REQUEST_MS }: { active: boolean; delayMs?: number }) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (!active) {
      setSlow(false);
      return;
    }
    const timer = window.setTimeout(() => setSlow(true), delayMs);
    return () => window.clearTimeout(timer);
  }, [active, delayMs]);

  if (!active || !slow) return null;
  return (
    <p role="status" className="flex items-start gap-2 rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-2.5 text-sm text-sky-100">
      <Hourglass className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span>Starting the server. The free hosting tier sleeps when idle, so this can take up to a minute.</span>
    </p>
  );
}
