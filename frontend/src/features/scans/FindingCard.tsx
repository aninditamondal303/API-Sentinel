import { ChevronDown, Eye } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import type { Finding } from "@/api/types";
import { Badge, MethodBadge, SeverityBadge, severityColor } from "@/components/ui/Badge";
import { categoryLabel, isBreaking } from "@/lib/findings";
import { formatValue } from "@/lib/format";
import { cn } from "@/lib/cn";

function ValueBox({ label, value, tone }: { label: string; value: unknown; tone: "old" | "new" }) {
  return (
    <div className="min-w-0">
      <p className="mb-1 text-[11px] font-medium text-ink-400">{label}</p>
      <pre className={cn("max-h-48 overflow-auto rounded-md border px-2.5 py-2 text-[12px]",
        tone === "old" ? "border-rose-500/20 bg-rose-500/[0.05] text-rose-200" : "border-emerald-500/20 bg-emerald-500/[0.05] text-emerald-200")}>
        {value === null || value === undefined ? <span className="text-ink-400">(absent)</span> : formatValue(value)}
      </pre>
    </div>
  );
}

export function FindingCard({ finding, defaultOpen = false }: { finding: Finding; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const breaking = isBreaking(finding);
  const hasValues = finding.oldValue !== null && finding.oldValue !== undefined || finding.newValue !== null && finding.newValue !== undefined;
  return (
    <article className="card overflow-hidden transition-colors hover:border-ink-600" style={{ boxShadow: `inset 3px 0 0 0 ${severityColor[finding.severity]}` }}>
      <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-3 px-4 py-3.5 text-left">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={finding.severity} />
            {breaking ? <Badge tone="danger">Breaking</Badge> : null}
            {finding.requiresManualReview ? <Badge tone="warning"><Eye className="size-3" />Manual review</Badge> : null}
            <Badge>{categoryLabel(finding.category)}</Badge>
            <code className="text-[11px] text-ink-400">{finding.ruleId}</code>
          </div>
          <h3 className="mt-2 text-sm font-medium text-ink-100">{finding.title}</h3>
          {finding.path ? (
            <p className="mt-1 flex items-center gap-2 truncate"><MethodBadge method={finding.method} /><code className="truncate text-xs text-ink-200">{finding.path}</code></p>
          ) : finding.location ? <p className="mt-1 truncate font-mono text-xs text-ink-300">{finding.location}</p> : null}
        </div>
        <ChevronDown className={cn("mt-1 size-4 shrink-0 text-ink-400 transition-transform", open && "rotate-180")} />
      </button>
      {open ? (
        <div className="space-y-4 border-t border-ink-700/60 bg-ink-950/40 px-4 py-4 text-sm">
          <p className="text-ink-200">{finding.message}</p>
          {finding.impact ? (
            <div><p className="text-[11px] font-semibold uppercase tracking-wide text-ink-400">Impact</p><p className="mt-1 text-ink-200">{finding.impact}</p></div>
          ) : null}
          {finding.remediation ? (
            <div className="rounded-lg border border-accent-500/20 bg-accent-500/[0.06] px-3 py-2.5">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-accent-300">Remediation</p>
              <p className="mt-1 text-ink-100">{finding.remediation}</p>
            </div>
          ) : null}
          <p className="text-xs text-ink-400">
            Rule{" "}
            <Link to={`/app/rules#${encodeURIComponent(finding.ruleId)}`} className="font-mono text-accent-300 hover:text-accent-200">
              {finding.ruleId}
            </Link>
            : see what it checks in the rules reference.
          </p>
          {hasValues ? (
            <div className="grid gap-3 md:grid-cols-2">
              <ValueBox label="Before (baseline)" value={finding.oldValue} tone="old" />
              <ValueBox label="After (candidate)" value={finding.newValue} tone="new" />
            </div>
          ) : null}
          <dl className="grid gap-2 text-xs sm:grid-cols-2">
            {finding.location ? <div><dt className="text-ink-400">Location</dt><dd className="break-all font-mono text-ink-200">{finding.location}</dd></div> : null}
            {finding.field ? <div><dt className="text-ink-400">Field</dt><dd className="break-all font-mono text-ink-200">{finding.field}</dd></div> : null}
            <div><dt className="text-ink-400">Fingerprint</dt><dd className="font-mono text-ink-300">{finding.fingerprint}</dd></div>
          </dl>
        </div>
      ) : null}
    </article>
  );
}
