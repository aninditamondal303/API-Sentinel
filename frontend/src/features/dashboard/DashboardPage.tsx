import { useQuery } from "@tanstack/react-query";
import { Activity, AlertOctagon, FileCode2, FolderKanban, Plus } from "lucide-react";
import type { ReactNode } from "react";
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dashboardApi, projectApi } from "@/api/endpoints";
import { SEVERITIES, type Dashboard } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { severityColor } from "@/components/ui/Badge";
import { ButtonLink } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import { ScanTable } from "@/features/scans/ScanTable";

function Stat({ label, value, icon, tone = "default", sub }: {
  label: string;
  value: number;
  icon: ReactNode;
  tone?: "default" | "danger";
  sub?: ReactNode;
}) {
  return (
    <Card className="relative overflow-hidden p-5 transition-colors hover:border-ink-600">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-ink-300">{label}</p>
        <span className={tone === "danger" ? "text-rose-400" : "text-accent-400"}>{icon}</span>
      </div>
      <p className={`mt-3 text-3xl font-semibold tabular-nums tracking-tight ${tone === "danger" && value > 0 ? "text-rose-300" : "text-ink-100"}`}>
        {value.toLocaleString()}
      </p>
      {sub ? <p className="mt-1 text-xs text-ink-400">{sub}</p> : null}
    </Card>
  );
}

const tooltipStyle = {
  contentStyle: { background: "#0d1423", border: "1px solid #22304c", borderRadius: 8, fontSize: 12, color: "#e2e8f2" },
  itemStyle: { color: "#e2e8f2" },
  cursor: { fill: "rgba(59,130,246,0.06)" },
};

function SeverityChart({ data }: { data: Dashboard["severityDistribution"] }) {
  const rows = SEVERITIES.map((severity) => ({ severity, label: severity.charAt(0) + severity.slice(1).toLowerCase(), count: data[severity] ?? 0 }));
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  if (total === 0) return <EmptyState title="No findings yet" description="Severity distribution appears after your first completed scan." />;
  return (
    <div className="h-64 px-2 pb-3 pt-4" role="img" aria-label={`Findings by severity: ${rows.map((r) => `${r.label} ${r.count}`).join(", ")}`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 4, right: 16, bottom: 0, left: -12 }}>
          <XAxis dataKey="label" interval={0} tick={{ fill: "#8b99b3", fontSize: 12 }} axisLine={{ stroke: "#22304c" }} tickLine={false} />
          <YAxis allowDecimals={false} tick={{ fill: "#5b6b88", fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip {...tooltipStyle} formatter={(value) => [value, "Findings"]} />
          <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={56} isAnimationActive>
            {rows.map((row) => <Cell key={row.severity} fill={severityColor[row.severity]} fillOpacity={0.85} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function OutcomeChart({ scans }: { scans: Dashboard["scans"] }) {
  const rows = [
    { name: "Passed", value: scans.passed, color: "#34d399" },
    { name: "Failed threshold", value: scans.failedThreshold, color: "#f43f5e" },
    { name: "Errored", value: scans.failed, color: "#64748b" },
  ].filter((row) => row.value > 0);
  if (scans.total === 0) return <EmptyState title="No scans yet" description="Run a compatibility or security scan to see outcomes here." />;
  // Container query: side by side (the original layout) only when the card can hold padding (48px) +
  // donut (160px) + gap (24px) + the legend at its narrowest (~140px) = 372px (23.25rem). Narrower cards
  // (the two-column dashboard at ~1024px, phones) stack the legend under the donut so it never overflows.
  return (
    <div className="@container">
      <div className="flex flex-col items-center gap-4 px-6 py-6 @min-[23.25rem]:h-64 @min-[23.25rem]:flex-row @min-[23.25rem]:gap-6 @min-[23.25rem]:py-0">
        <div className="relative size-40 shrink-0" role="img" aria-label={`Scan outcomes: ${scans.passed} passed, ${scans.failedThreshold} failed threshold, ${scans.failed} errored`}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={rows} dataKey="value" innerRadius={52} outerRadius={72} paddingAngle={2} stroke="none">
                {rows.map((row) => <Cell key={row.name} fill={row.color} />)}
              </Pie>
              <Tooltip {...tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
            <div><p className="text-2xl font-semibold tabular-nums">{scans.total}</p><p className="text-[11px] text-ink-400">scans</p></div>
          </div>
        </div>
        <ul className="space-y-2.5 text-sm">
          {[
            { name: "Passed", value: scans.passed, color: "#34d399" },
            { name: "Failed threshold", value: scans.failedThreshold, color: "#f43f5e" },
            { name: "Errored", value: scans.failed, color: "#64748b" },
            { name: "Compatibility", value: scans.compatibility, color: "#3b82f6" },
            { name: "Security", value: scans.security, color: "#a78bfa" },
          ].map((row) => (
            <li key={row.name} className="flex items-center gap-2.5">
              <span className="size-2 rounded-full" style={{ background: row.color }} aria-hidden="true" />
              <span className="text-ink-300">{row.name}</span>
              <span className="ml-auto pl-4 font-medium tabular-nums text-ink-100">{row.value}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => projectApi.list() });
  const names = new Map((projects.data?.items ?? []).map((p) => [p.id, p.name]));

  return (
    <>
      <PageHeader eyebrow="Overview" title={`Welcome${user ? `, ${user.displayName.split(" ")[0]}` : ""}`}
        description="Live figures from your projects, specifications and scans."
        actions={<ButtonLink to="/app/projects?new=1" icon={<Plus className="size-4" />}>New project</ButtonLink>} />

      {dashboard.isError ? (
        <Card><ErrorState error={dashboard.error} onRetry={() => void dashboard.refetch()} /></Card>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {dashboard.data ? (
              <>
                <Stat label="Projects" value={dashboard.data.projects} icon={<FolderKanban className="size-4" />} />
                <Stat label="Specifications" value={dashboard.data.specifications} icon={<FileCode2 className="size-4" />} />
                <Stat label="Scans" value={dashboard.data.scans.total} icon={<Activity className="size-4" />}
                  sub={`${dashboard.data.scans.compatibility} compatibility · ${dashboard.data.scans.security} security`} />
                <Stat label="Breaking changes" value={dashboard.data.breakingChanges} icon={<AlertOctagon className="size-4" />} tone="danger"
                  sub="Across completed compatibility scans" />
              </>
            ) : Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-[118px] rounded-xl" />)}
          </div>

          <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
            <Card>
              <CardHeader title="Findings by severity" description="All findings from completed scans" />
              {dashboard.data ? <SeverityChart data={dashboard.data.severityDistribution} /> : <Skeleton className="m-5 h-56" />}
            </Card>
            <Card>
              <CardHeader title="Scan outcomes" description="Decisions against each project's threshold" />
              {dashboard.data ? <OutcomeChart scans={dashboard.data.scans} /> : <Skeleton className="m-5 h-56" />}
            </Card>
          </div>

          <Card>
            <CardHeader title="Recent activity" description="Your 10 most recent scans" />
            {!dashboard.data ? (
              <div className="space-y-2 p-5">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-9" />)}</div>
            ) : dashboard.data.recentScans.length === 0 ? (
              <EmptyState icon={<Activity className="size-5" />} title="No scans yet"
                description={dashboard.data.projects === 0 ? "Create a project and upload two versions of an OpenAPI spec to run your first comparison."
                  : "Open a project and run a compatibility or security scan."}
                action={<ButtonLink to={dashboard.data.projects === 0 ? "/app/projects?new=1" : "/app/projects"} size="sm" variant="secondary">
                  {dashboard.data.projects === 0 ? "Create a project" : "Go to projects"}</ButtonLink>} />
            ) : (
              <ScanTable scans={dashboard.data.recentScans} projectNames={names} />
            )}
          </Card>
        </div>
      )}
    </>
  );
}
