import type { ReactNode } from "react";
import type { Decision, ScanStatus, Severity } from "@/api/types";
import { cn } from "@/lib/cn";

type Tone = "neutral" | "accent" | "success" | "danger" | "warning";
const tones: Record<Tone, string> = {
  neutral: "border-ink-600 bg-ink-800 text-ink-200",
  accent: "border-accent-500/40 bg-accent-500/10 text-accent-300",
  success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  danger: "border-rose-500/40 bg-rose-500/10 text-rose-300",
  warning: "border-amber-500/40 bg-amber-500/10 text-amber-200",
};

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-4", tones[tone], className)}>
      {children}
    </span>
  );
}

const severityStyles: Record<Severity, string> = {
  CRITICAL: "border-sev-critical/50 bg-sev-critical/15 text-rose-200",
  HIGH: "border-sev-high/50 bg-sev-high/15 text-orange-200",
  MEDIUM: "border-sev-medium/50 bg-sev-medium/15 text-yellow-100",
  LOW: "border-sev-low/50 bg-sev-low/15 text-sky-200",
  INFO: "border-sev-info/40 bg-sev-info/10 text-slate-200",
};

export const severityColor: Record<Severity, string> = {
  CRITICAL: "var(--color-sev-critical)",
  HIGH: "var(--color-sev-high)",
  MEDIUM: "var(--color-sev-medium)",
  LOW: "var(--color-sev-low)",
  INFO: "var(--color-sev-info)",
};

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-md border px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide", severityStyles[severity], className)}>
      <span className="size-1.5 rounded-full" style={{ background: severityColor[severity] }} aria-hidden="true" />
      {severity.toLowerCase()}
    </span>
  );
}

export function DecisionBadge({ decision, status }: { decision: Decision | null; status: ScanStatus }) {
  if (status === "FAILED") return <Badge tone="danger">Error</Badge>;
  if (status === "RUNNING") return <Badge tone="accent">Running</Badge>;
  if (decision === "PASS") return <Badge tone="success">Passed</Badge>;
  if (decision === "FAIL") return <Badge tone="danger">Failed</Badge>;
  return <Badge>—</Badge>;
}

export function MethodBadge({ method }: { method: string | null }) {
  if (!method) return null;
  const upper = method.toUpperCase();
  const color = upper === "GET" ? "text-sky-300" : upper === "POST" ? "text-emerald-300"
    : upper === "DELETE" ? "text-rose-300" : upper === "PUT" || upper === "PATCH" ? "text-amber-200" : "text-ink-200";
  return <span className={cn("font-mono text-[11px] font-semibold", color)}>{upper}</span>;
}
