import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertOctagon, ArrowLeft, CheckCircle2, Download, Eye, ListFilter, Search, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { saveBlob } from "@/api/client";
import { projectApi, scanApi } from "@/api/endpoints";
import { SEVERITIES, type Finding, type Scan, type Severity } from "@/api/types";
import { SeverityBadge, severityColor } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Input, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorState, InlineError, Skeleton } from "@/components/ui/States";
import { Tabs } from "@/components/ui/Tabs";
import { groupFindings, type FindingGroup } from "@/lib/findings";
import { formatDateTime, formatDuration, pluralize } from "@/lib/format";
import { cn } from "@/lib/cn";
import { FindingCard } from "./FindingCard";
import { ScanTypeLabel, SpecsLabel } from "./ScanTable";
import { SecurityNotice } from "./SecurityNotice";

function DecisionBanner({ scan }: { scan: Scan }) {
  if (scan.status === "FAILED") {
    return (
      <Card className="border-rose-500/30 p-5">
        <div className="flex gap-3">
          <XCircle className="mt-0.5 size-5 shrink-0 text-rose-400" />
          <div>
            <p className="font-semibold text-ink-100">The scan could not be completed</p>
            <p className="mt-1 text-sm text-ink-300">{scan.errorMessage ?? "The analysis service returned an error."}</p>
            {scan.errorCode ? <code className="mt-2 inline-block text-xs text-ink-400">{scan.errorCode}</code> : null}
          </div>
        </div>
      </Card>
    );
  }
  const pass = scan.decision === "PASS";
  return (
    <Card className={cn("relative overflow-hidden p-5", pass ? "border-emerald-500/30" : "border-rose-500/30")}>
      <div className={cn("pointer-events-none absolute inset-0 opacity-60", pass ? "bg-[radial-gradient(ellipse_at_top_left,rgba(16,185,129,0.12),transparent_60%)]" : "bg-[radial-gradient(ellipse_at_top_left,rgba(244,63,94,0.12),transparent_60%)]")} />
      <div className="relative flex flex-wrap items-start gap-4">
        {pass ? <CheckCircle2 className="size-8 shrink-0 text-emerald-400" /> : <AlertOctagon className="size-8 shrink-0 text-rose-400" />}
        <div className="min-w-0 flex-1">
          <p className={cn("text-lg font-semibold", pass ? "text-emerald-200" : "text-rose-200")}>
            {pass ? "Passed: no findings reach this policy's threshold" : scan.type === "COMPATIBILITY" ? "Failed: this change does not meet the release policy" : "Failed: findings reach this policy's threshold"}
          </p>
          <p className="mt-0.5 text-sm text-ink-300">
            Threshold: fail on {scan.failOn ? scan.failOn.toLowerCase() : "nothing"}
            {scan.type === "COMPATIBILITY" ? `; manual review ${scan.failOnManualReview ? "blocks" : "does not block"}` : ""}.
          </p>
          {scan.reasons.length > 0 ? (
            <ul className="mt-3 space-y-1 text-sm text-ink-200">
              {scan.reasons.map((reason) => <li key={reason} className="flex gap-2"><span className="text-ink-500">•</span>{reason}</li>)}
            </ul>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

function Metric({ label, value, tone }: { label: string; value: number | string; tone?: "danger" | "warning" }) {
  return (
    <div className="card px-4 py-3.5">
      <p className="text-xs text-ink-400">{label}</p>
      <p className={cn("mt-1 text-2xl font-semibold tabular-nums", tone === "danger" ? "text-rose-300" : tone === "warning" ? "text-amber-200" : "text-ink-100")}>{value}</p>
    </div>
  );
}

function SeverityBar({ scan }: { scan: Scan }) {
  const counts: Record<Severity, number> = { CRITICAL: scan.bySeverity.critical, HIGH: scan.bySeverity.high, MEDIUM: scan.bySeverity.medium, LOW: scan.bySeverity.low, INFO: scan.bySeverity.info };
  const total = scan.totalFindings || 1;
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-ink-800" role="img" aria-label={SEVERITIES.map((s) => `${s.toLowerCase()} ${counts[s]}`).join(", ")}>
        {SEVERITIES.map((s) => counts[s] > 0 ? <div key={s} style={{ width: `${(counts[s] / total) * 100}%`, background: severityColor[s] }} /> : null)}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs">
        {SEVERITIES.map((s) => (
          <span key={s} className="inline-flex items-center gap-1.5 text-ink-300">
            <span className="size-2 rounded-full" style={{ background: severityColor[s] }} />{s.charAt(0) + s.slice(1).toLowerCase()}
            <span className="font-medium tabular-nums text-ink-100">{counts[s]}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

type View = FindingGroup | "all";

export function ScanDetailPage() {
  const { projectId = "", scanId = "" } = useParams();
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => projectApi.get(projectId) });
  const scan = useQuery({ queryKey: ["scan", projectId, scanId], queryFn: () => scanApi.get(projectId, scanId) });
  const findings = useQuery({
    queryKey: ["findings", projectId, scanId],
    queryFn: () => scanApi.allFindings(projectId, scanId),
    enabled: scan.data?.status === "COMPLETED",
  });
  const report = useMutation({ mutationFn: () => scanApi.report(projectId, scanId), onSuccess: saveBlob });
  const [view, setView] = useState<View | null>(null);
  const [severity, setSeverity] = useState<Severity | "">("");
  const [search, setSearch] = useState("");

  const groups = useMemo(() => groupFindings(findings.data ?? []), [findings.data]);
  const isCompat = scan.data?.type === "COMPATIBILITY";
  const activeView: View = view ?? (isCompat ? (groups.breaking.length > 0 ? "breaking" : "all") : "all");
  const visible = useMemo(() => {
    const source: Finding[] = activeView === "all" ? findings.data ?? [] : groups[activeView];
    const needle = search.trim().toLowerCase();
    return source.filter((f) => (!severity || f.severity === severity)
      && (!needle || [f.title, f.path, f.ruleId, f.message, f.location].some((v) => v?.toLowerCase().includes(needle))));
  }, [activeView, findings.data, groups, severity, search]);

  if (scan.isError) return <Card><ErrorState error={scan.error} onRetry={() => void scan.refetch()} /></Card>;
  if (!scan.data) return <div className="space-y-4"><Skeleton className="h-12 w-80" /><Skeleton className="h-32 rounded-xl" /><Skeleton className="h-64 rounded-xl" /></div>;
  const s = scan.data;

  return (
    <>
      <PageHeader
        eyebrow={<Link to={`/app/projects/${projectId}?tab=scans`} className="inline-flex items-center gap-1 hover:text-ink-100"><ArrowLeft className="size-3.5" />{project.data?.name ?? "Project"} · scans</Link>}
        title={isCompat ? "Compatibility analysis" : "Security analysis"}
        description={<span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1"><ScanTypeLabel scan={s} /><SpecsLabel scan={s} /><span>{formatDateTime(s.createdAt)}</span></span>}
        actions={s.status === "COMPLETED" ? <Button variant="secondary" icon={<Download className="size-4" />} loading={report.isPending} onClick={() => report.mutate()}>JSON report</Button> : null} />

      <div className="space-y-6">
        <InlineError error={report.error} />
        <DecisionBanner scan={s} />
        {!isCompat ? <SecurityNotice /> : null}

        {s.status === "COMPLETED" ? (
          <>
            <div className={cn("grid grid-cols-2 gap-4", isCompat ? "lg:grid-cols-5" : "sm:grid-cols-3")}>
              <Metric label="Findings" value={s.totalFindings} />
              {isCompat ? <Metric label="Breaking changes" value={s.breakingChanges} tone={s.breakingChanges > 0 ? "danger" : undefined} /> : null}
              {isCompat ? <Metric label="Manual review" value={s.manualReview} tone={s.manualReview > 0 ? "warning" : undefined} /> : null}
              <Metric label="Endpoints affected" value={s.endpointsAffected} />
              <Metric label="Analysis time" value={formatDuration(s.durationMs)} />
            </div>
            <Card className="p-5"><SeverityBar scan={s} /></Card>

            <Card>
              <CardHeader title="Findings" description={`Analyzer ${s.analyzerVersion ?? "?"} · ruleset ${s.rulesetVersion ?? "?"}`} />
              <div className="px-5 pt-3">
                <Tabs label="Finding groups" value={activeView} onChange={setView}
                  items={isCompat ? [
                    { key: "breaking", label: <><AlertOctagon className="size-3.5" />Breaking</>, count: groups.breaking.length },
                    { key: "manual", label: <><Eye className="size-3.5" />Manual review</>, count: groups.manual.length },
                    { key: "other", label: "Other changes", count: groups.other.length },
                    { key: "all", label: "All", count: findings.data?.length ?? s.totalFindings },
                  ] : [{ key: "all", label: "All findings", count: findings.data?.length ?? s.totalFindings }]} />
              </div>
              <div className="flex flex-wrap items-center gap-3 px-5 py-4">
                <div className="relative min-w-56 flex-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" />
                  <Input aria-label="Search findings" placeholder="Search by path, rule or text" value={search} onChange={(e) => setSearch(e.target.value)}
                    className="w-full rounded-lg border border-ink-600 bg-ink-900 pl-9 pr-3 text-sm focus:border-accent-500 focus:outline-none" />
                </div>
                <div className="flex items-center gap-2">
                  <ListFilter className="size-4 text-ink-400" />
                  <Select aria-label="Filter by severity" value={severity} onChange={(e) => setSeverity(e.target.value as Severity | "")}
                    className="w-40 rounded-lg border border-ink-600 bg-ink-900 px-3 text-sm">
                    <option value="">All severities</option>
                    {SEVERITIES.map((sv) => <option key={sv} value={sv}>{sv.charAt(0) + sv.slice(1).toLowerCase()}</option>)}
                  </Select>
                </div>
              </div>
              <div className="space-y-3 px-5 pb-5">
                {findings.isError ? <ErrorState error={findings.error} onRetry={() => void findings.refetch()} />
                  : !findings.data ? Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)
                  : visible.length === 0 ? (
                    <EmptyState title={s.totalFindings === 0 ? "No findings" : "Nothing in this view"}
                      description={s.totalFindings === 0 ? (isCompat ? "The candidate is compatible with the baseline." : "No security hygiene issues were detected in this specification.")
                        : activeView === "breaking" ? "No breaking changes. Check the other tabs for risky or informational changes." : "Try another tab or clear the filters."} />
                  ) : (
                    <>
                      <p className="text-xs text-ink-400">{pluralize(visible.length, "finding")}{severity ? <> · <SeverityBadge severity={severity} /></> : null}</p>
                      {visible.map((f, i) => <FindingCard key={f.id} finding={f} defaultOpen={i === 0 && activeView === "breaking"} />)}
                    </>
                  )}
              </div>
            </Card>
          </>
        ) : null}
      </div>
    </>
  );
}
